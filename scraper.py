"""
scraper.py
----------
Scrapes player data from wank.wavu.wiki.

Rate-limit strategy:
  - Requests are sent one at a time (no concurrency) with a small delay
    between each to avoid triggering 429s in the first place.
  - On a 429 the request retries up to MAX_RETRIES times with exponential
    backoff, honouring the Retry-After header when the server sends one.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from models import Player

BASE_URL            = "https://wank.wavu.wiki/player/"
DEVIATION_THRESHOLD = 75
REQUEST_DELAY       = 1.0   # seconds between requests during a bulk fetch
MAX_RETRIES         = 4     # attempts before giving up on a single player
BACKOFF_BASE        = 2.0   # seconds; doubles each retry: 2, 4, 8, 16 …


def _parse_player(player_id: str, html: str) -> Player | None:
    """Parse the HTML for a player page and return a Player, or None."""
    soup = BeautifulSoup(html, "html.parser")

    best_char      = None
    best_rating    = -1
    best_deviation = float("inf")

    for div in soup.find_all("div", class_="rating"):
        mu_div    = div.find("div", class_="mu")
        sigma_div = div.find("div", class_="sigma")
        if mu_div is None or sigma_div is None:
            continue

        rating    = int(mu_div.text[2:])                    # strips "μ=" prefix
        deviation = int(sigma_div.text.replace("σ² ", ""))

        if deviation >= DEVIATION_THRESHOLD:
            continue

        if rating > best_rating or (rating == best_rating and deviation < best_deviation):
            best_rating    = rating
            best_deviation = deviation
            best_char      = div

    if best_char is None:
        return None

    name_div = soup.find("div", class_="name")
    return Player(
        id=player_id,
        name=name_div.text.strip() if name_div else "",
        main_character=best_char.find("div", class_="char").text,
        rating=best_rating,
        games=int(best_char.find("div", class_="games").text.replace(" games", "")),
        deviation=best_deviation,
        last_played=best_char.find("div", class_="last-seen").text,
    )


async def fetch_player(player_id: str, session: aiohttp.ClientSession | None = None) -> Player | None:
    """
    Fetch a single player by their site ID.
    Returns a populated Player object, or None if not found / unqualified.
    Accepts an optional shared session for bulk fetches.
    Retries on 429 with exponential backoff.
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    try:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(BASE_URL + player_id) as response:
                    if response.status == 404:
                        return None

                    if response.status == 429:
                        retry_after = float(
                            response.headers.get("Retry-After", BACKOFF_BASE * (2 ** attempt))
                        )
                        print(
                            f"[scraper] 429 for {player_id}, "
                            f"waiting {retry_after:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                        )
                        await asyncio.sleep(retry_after)
                        continue    # retry

                    if response.status != 200:
                        print(f"[scraper] Unexpected status {response.status} for {player_id}")
                        return None

                    return _parse_player(player_id, await response.text())

            except aiohttp.ClientError as e:
                wait = BACKOFF_BASE * (2 ** attempt)
                print(f"[scraper] Network error for {player_id}: {e} — retrying in {wait:.1f}s")
                await asyncio.sleep(wait)

        print(f"[scraper] Gave up on {player_id} after {MAX_RETRIES} attempts")
        return None

    except Exception as e:
        print(f"[scraper] Unexpected error fetching {player_id}: {e}")
        return None
    finally:
        if own_session:
            await session.close()


async def fetch_all_tracked_players(player_ids: list[str]) -> list[Player]:
    """
    Refresh data for every tracked player ID using a shared session.
    Requests are sent sequentially with a REQUEST_DELAY gap between each
    to stay well under the site's rate limit.
    Returns a list of Player objects (skips any that returned None).
    """
    players: list[Player] = []

    async with aiohttp.ClientSession() as session:
        for i, pid in enumerate(player_ids):
            if i > 0:
                await asyncio.sleep(REQUEST_DELAY)
            try:
                result = await fetch_player(pid, session)
                if result is not None:
                    players.append(result)
            except Exception as e:
                print(f"[scraper] Error fetching {pid}: {e}")

    return players