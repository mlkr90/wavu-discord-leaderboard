"""
scraper.py
----------
Scrapes player data from wank.wavu.wiki.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from models import Player

BASE_URL = "https://wank.wavu.wiki/player/"


async def fetch_player(player_id: str, session: aiohttp.ClientSession | None = None) -> Player | None:
    """
    Fetch a single player by their site ID.
    Returns a populated Player object, or None if the player was not found.
    Accepts an optional shared session for bulk fetches.
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    try:
        async with session.get(BASE_URL + player_id) as response:
            if response.status == 404:
                return None
            if response.status != 200:
                print(f"[scraper] Unexpected status {response.status} for player {player_id}")
                return None

            soup = BeautifulSoup(await response.text(), "html.parser")

            # Find the character div with the highest rating.
            # Tiebreak: lower deviation wins.
            best_char = None
            best_rating = -1
            best_deviation = float("inf")

            for div in soup.find_all("div", class_="rating"):
                mu_div = div.find("div", class_="mu")
                sigma_div = div.find("div", class_="sigma")
                if mu_div is None or sigma_div is None:
                    continue

                rating = int(mu_div.text[2:])  # strips the "μ=" prefix
                deviation = int(sigma_div.text.replace("σ² ", ""))

                if rating > best_rating or (rating == best_rating and deviation < best_deviation):
                    best_rating = rating
                    best_deviation = deviation
                    best_char = div

            if best_char is None:
                return None

            name_div = soup.find("div", class_="name")
            player = Player(
                id=player_id,
                name=name_div.text.strip() if name_div else "",
                main_character=best_char.find("div", class_="char").text,
                rating=best_rating,
                games=int(best_char.find("div", class_="games").text.replace(" games", "")),
                deviation=best_deviation,
                last_played=best_char.find("div", class_="last-seen").text,
            )
            return player

    except Exception as e:
        print(f"[scraper] Error fetching player {player_id}: {e}")
        return None
    finally:
        if own_session:
            await session.close()


async def fetch_all_tracked_players(player_ids: list[str]) -> list[Player]:
    """
    Refresh data for every tracked player ID in one go using a shared session.
    Returns a list of Player objects (skips any IDs that returned None).
    """
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_player(pid, session) for pid in player_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    players: list[Player] = []
    for pid, result in zip(player_ids, results):
        if isinstance(result, Exception):
            print(f"[scraper] Error fetching {pid}: {result}")
        elif result is not None:
            players.append(result)

    return players
