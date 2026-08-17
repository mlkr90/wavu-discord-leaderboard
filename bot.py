"""
bot.py
------
Entry point. Run with:  python bot.py
"""

import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database as db

load_dotenv()

TOKEN    = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ.get("GUILD_ID", 0))   # 0 = global commands (up to 1h to propagate)


class LeaderboardBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False   # not needed for slash commands

        super().__init__(
            command_prefix="!",           # fallback prefix (unused)
            intents=intents,
            owner_id=int(os.environ["OWNER_ID"]),
        )

    async def setup_hook(self):
        # Load cogs
        await self.load_extension("cogs.leaderboard")

        # Sync slash commands
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"[bot] Slash commands synced to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            print("[bot] Slash commands synced globally (may take up to 1 hour)")

    async def on_ready(self):
        print(f"[bot] Logged in as {self.user} (id={self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the leaderboard 📊",
            )
        )


async def main():
    db.load()   # load persisted data before starting

    async with LeaderboardBot() as bot:
        await bot.start(TOKEN)


asyncio.run(main())
