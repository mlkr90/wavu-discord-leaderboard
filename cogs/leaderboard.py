"""
cogs/leaderboard.py
-------------------
Slash-command cog that handles:
  /leaderboard add    – register your site player ID
  /leaderboard remove – unregister yourself (or any player if owner)
  /leaderboard show   – post/refresh the leaderboard in the current channel
  /leaderboard refresh – manually trigger a data refresh (owner only)
  /leaderboard list        – show all registered Discord <-> player ID mappings (owner only)
  /leaderboard addplayer   – add a player ID with no Discord account attached (owner only)
  /leaderboard removeplayer – remove an unlinked player ID (owner only)

A background task automatically refreshes data and updates the pinned
leaderboard message every REFRESH_INTERVAL seconds.
"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks

import database as db
import scraper
from models import Player

# How often (seconds) the background refresh runs
REFRESH_INTERVAL = 300   # 5 minutes


def build_leaderboard_embed(players: list[Player]) -> discord.Embed:
    embed = discord.Embed(
        title="🏆 Leaderboard",
        color=discord.Color.gold(),
    )

    if not players:
        embed.description = "*No players registered yet. Use `/leaderboard add` to join!*"
        return embed

    lines = []
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for rank, player in enumerate(players, start=1):
        prefix = medals.get(rank, f"`#{rank:>2}`")
        name_field = player.name or player.id
        char_field = f" • {player.main_character}" if player.main_character else ""
        lines.append(
            f"{prefix} **{name_field}**{char_field}\n"
            f"    Rating: **{player.rating}** (±{player.deviation}) | Games: {player.games} | Last: {player.last_played}"
        )

    embed.description = "\n\n".join(lines)
    embed.set_footer(text="Updates every 5 minutes • /leaderboard add to join")
    return embed


class LeaderboardCog(commands.Cog):
    """Manages the leaderboard channel message and player registration."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_refresh.start()

    def cog_unload(self):
        self.auto_refresh.cancel()

    # ------------------------------------------------------------------
    # Background auto-refresh task
    # ------------------------------------------------------------------

    @tasks.loop(seconds=REFRESH_INTERVAL)
    async def auto_refresh(self):
        await self._refresh_data()
        for channel_id, message_id in list(db.get_leaderboard_messages().items()):
            await self._update_leaderboard_message(channel_id, message_id)

    @auto_refresh.before_loop
    async def before_auto_refresh(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _refresh_data(self):
        """Pull fresh data from the site and cache it."""
        player_ids = db.all_player_ids()
        if not player_ids:
            return
        players = await scraper.fetch_all_tracked_players(player_ids)
        await db.update_leaderboard(players)

    async def _update_leaderboard_message(self, channel_id: int, message_id: int):
        """Edit the existing leaderboard message in place."""
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return
        try:
            message = await channel.fetch_message(message_id)
            embed = build_leaderboard_embed(db.get_leaderboard())
            await message.edit(embed=embed)
        except discord.NotFound:
            # Message was deleted; stop tracking it
            db.clear_leaderboard_message(channel_id)
        except discord.Forbidden:
            pass  # bot lost permissions

    async def _post_or_update_leaderboard(self, channel: discord.TextChannel) -> discord.Message:
        """Post a new leaderboard or update the existing one; returns the message."""
        embed = build_leaderboard_embed(db.get_leaderboard())
        existing_id = db.get_leaderboard_messages().get(channel.id)

        if existing_id:
            try:
                msg = await channel.fetch_message(existing_id)
                await msg.edit(embed=embed)
                return msg
            except discord.NotFound:
                pass  # fall through to post new

        msg = await channel.send(embed=embed)
        db.set_leaderboard_message(channel.id, msg.id)
        try:
            await msg.pin()
        except discord.Forbidden:
            pass  # no manage_messages permission – that's fine
        return msg

    def _is_owner(self, user: discord.User | discord.Member) -> bool:
        return user.id == self.bot.owner_id

    # ------------------------------------------------------------------
    # Slash command group
    # ------------------------------------------------------------------

    lb = app_commands.Group(name="leaderboard", description="Leaderboard commands")

    @lb.command(name="add", description="Register your site player ID on the leaderboard.")
    @app_commands.describe(player_id="Your player ID on the site")
    async def lb_add(self, interaction: discord.Interaction, player_id: str):
        await interaction.response.defer(ephemeral=True)

        owner_id = self.bot.owner_id
        success, msg = await db.register(interaction.user.id, player_id, owner_id=owner_id)
        if not success:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            return

        # Verify the player actually exists on the site
        player = await scraper.fetch_player(player_id)
        if player is None:
            await db.unregister(interaction.user.id)
            await interaction.followup.send(
                f"❌ Player ID `{player_id}` was not found on the site. Registration cancelled.",
                ephemeral=True,
            )
            return

        # Refresh leaderboard data
        await self._refresh_data()
        await interaction.followup.send(f"✅ {msg} Welcome, **{player.name or player_id}**!", ephemeral=True)

    @lb.command(name="remove", description="Remove your site player ID from the leaderboard.")
    @app_commands.describe(player_id="(Owner only) Remove a specific player ID instead of your own")
    async def lb_remove(self, interaction: discord.Interaction, player_id: str | None = None):
        await interaction.response.defer(ephemeral=True)

        if player_id and not self._is_owner(interaction.user):
            await interaction.followup.send("❌ Only the bot owner can remove other players.", ephemeral=True)
            return

        if player_id:
            removed = await db.remove_registration_for_player(player_id)
            if removed:
                await interaction.followup.send(f"✅ Removed registration for `{player_id}`.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ No registration found for `{player_id}`.", ephemeral=True)
        else:
            success, msg = await db.unregister(interaction.user.id)
            if success:
                await self._refresh_data()
            await interaction.followup.send(("✅ " if success else "❌ ") + msg, ephemeral=True)

    @lb.command(name="show", description="Post (or refresh) the leaderboard in this channel.")
    async def lb_show(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._refresh_data()
        await self._post_or_update_leaderboard(interaction.channel)
        await interaction.followup.send("✅ Leaderboard posted!", ephemeral=True)

    @lb.command(name="refresh", description="(Owner only) Manually refresh leaderboard data.")
    async def lb_refresh(self, interaction: discord.Interaction):
        if not self._is_owner(interaction.user):
            await interaction.response.send_message("❌ Only the bot owner can force a refresh.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await self._refresh_data()
        for channel_id, message_id in list(self._leaderboard_messages.items()):
            await self._update_leaderboard_message(channel_id, message_id)
        await interaction.followup.send("✅ Leaderboard refreshed.", ephemeral=True)

    @lb.command(name="list", description="(Owner only) List all Discord <-> player ID mappings.")
    async def lb_list(self, interaction: discord.Interaction):
        if not self._is_owner(interaction.user):
            await interaction.response.send_message("❌ Only the bot owner can view all registrations.", ephemeral=True)
            return

        regs = db.all_registrations()
        unlinked = db.all_unlinked()

        if not regs and not unlinked:
            await interaction.response.send_message("No registrations yet.", ephemeral=True)
            return

        lines = [f"<@{did}> → `{pid}`" for did, pid in regs.items()]
        if unlinked:
            lines.append("")
            lines.append("**Unlinked (no Discord account):**")
            lines.extend(f"• `{pid}`" for pid in unlinked)

        embed = discord.Embed(title="📋 All Registrations", description="\n".join(lines), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @lb.command(name="addplayer", description="(Owner only) Add a player ID to the leaderboard without a Discord account.")
    @app_commands.describe(player_id="The site player ID to add")
    async def lb_addplayer(self, interaction: discord.Interaction, player_id: str):
        if not self._is_owner(interaction.user):
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Verify the player exists on the site before adding
        player = await scraper.fetch_player(player_id)
        if player is None:
            await interaction.followup.send(
                f"❌ Player ID `{player_id}` was not found on the site.",
                ephemeral=True,
            )
            return

        success, msg = await db.add_unlinked(player_id)
        if not success:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            return

        await self._refresh_data()
        await interaction.followup.send(f"✅ {msg} ({player.name})", ephemeral=True)

    @lb.command(name="removeplayer", description="(Owner only) Remove an unlinked player ID from the leaderboard.")
    @app_commands.describe(player_id="The unlinked site player ID to remove")
    async def lb_removeplayer(self, interaction: discord.Interaction, player_id: str):
        if not self._is_owner(interaction.user):
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        success, msg = await db.remove_unlinked(player_id)
        if success:
            await self._refresh_data()
        await interaction.followup.send(("✅ " if success else "❌ ") + msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
