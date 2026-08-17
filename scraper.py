"""
scraper.py
----------
Replace the body of `fetch_player` and `fetch_all_tracked_players` with your
actual scraping logic.  The rest of the bot only depends on the signatures
defined here, so you can swap in any implementation without touching anything
else.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from models import Player


# ---------------------------------------------------------------------------
# Public API used by the bot
# ---------------------------------------------------------------------------

async def fetch_player(player_id: str, session) -> Player | None:
    """
    Fetch a single player by their site ID.

    Returns a populated Player object, or None if the player was not found.
    Replace this stub with your real scraping / API call.
    """
    async with session.get("https://wank.wavu.wiki/player/" + id) as response:
            soup = BeautifulSoup(await response.text(), "html.parser")
            player = Player(id)
            character = None
            rating = 0
    
            for div in soup.find_all('div', class_='rating'):
                new_rating = int(div.find('div', class_='mu').text[2:])
                if new_rating > rating:
                    rating = new_rating
                    character = div
                # add check for cases when rating is the same, then pick whichever has lower deviation
            
            player.main_character = character.find('div', class_='char').text
            player.name = soup.find('div', class_='name').text.strip()
            player.last_played = character.find('div', class_='last-seen').text
            player.rating = rating
            player.games = int(character.find('div', class_='games').text.replace(" games", ""))
            player.deviation = int(character.find('div', class_='sigma').text.replace("σ² ", ""))
    
            return player

    # Stub: return a fake player so you can test the bot before writing the scraper.
    await asyncio.sleep(0)          # keep it a proper coroutine
    return Player(
        id=player_id,
        name=f"Player_{player_id}",
        main_character="Unknown",
        rating=1500,
        games=0,
        deviation=350,
        last_played="N/A",
    )


async def fetch_all_tracked_players(player_ids: list[str]) -> list[Player]:
    """
    Refresh data for every tracked player ID in one go.

    Returns a list of Player objects (skips any IDs that returned None).
    Feel free to replace the gather approach with a single bulk request if
    the site offers one.
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
