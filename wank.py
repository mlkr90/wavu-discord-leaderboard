import aiohttp
import asyncio
from bs4 import BeautifulSoup
from player import Player

ids = ["4mYnqRYyfB6h","345rd8bebDME", "2ha3FT2n2JBa", "3FiREENG8aB8", "4ygajnLMb8rJ", "663enJ4Fm4Md", "4TD829R9M9JE", "3y5EBJDJRR42", "66FT9eMem5hn", "34AeDTmj8g9B", "4ENRH586BEd4"]

async def get_leaderboard() -> None:
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.ensure_future(get_player(id, session)) for id in ids]
        leaderboard = await asyncio.gather(*tasks)
        print(leaderboard.__str__())
    

async def get_player(id, session) -> Player | None:
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

loop = asyncio.new_event_loop()
loop.run_until_complete(get_leaderboard())