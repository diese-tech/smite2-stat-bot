import asyncio

import discord
from discord import app_commands

import config
from services import guild_config_service, match_service, sheets_service
from commands._checks import require_guild, staff_only


def setup(tree: app_commands.CommandTree) -> None:
    @tree.command(name="newmatch", description="Generate a match UID and log it to the Match Log")
    @app_commands.describe(
        blue_captain="Blue (Order) team captain name",
        red_captain="Red (Chaos) team captain name",
    )
    @staff_only()
    async def newmatch(interaction: discord.Interaction, blue_captain: str, red_captain: str):
        await interaction.response.defer(ephemeral=False)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return

        guild_cfg = guild_config_service.get_guild_config(guild_id)
        league_prefix = str(guild_cfg.get("league_prefix") or config.LEAGUE_PREFIX).upper()
        started = await asyncio.to_thread(
            match_service.create_or_open_match,
            guild_id,
            interaction.channel_id,
            interaction.user.id,
            1,
            blue_captain,
            red_captain,
        )
        uid = started["match"]["match_id"]

        from datetime import timezone
        submitted_at = interaction.created_at.replace(tzinfo=timezone.utc).isoformat()

        sheet_id = sheets_service.get_active_sheet_id(guild_id)
        if sheet_id and not await asyncio.to_thread(sheets_service.match_exists, sheet_id, uid, guild_id):
            await asyncio.to_thread(sheets_service.append_match_log, sheet_id, {
                "draft_id": uid,
                "guild_id": str(guild_id),
                "game_number": "",
                "submitted_at": submitted_at,
                "blue_captain": blue_captain.strip(),
                "red_captain": red_captain.strip(),
                "blue_picks": "",
                "red_picks": "",
                "blue_bans": "",
                "red_bans": "",
                "fearless_pool": "",
                "game_status": "Pending",
                "match_status": "created",
                "winner": "TBD",
                "series_score": "TBD",
            })

        await interaction.followup.send(
            f"**Match ID: `{uid}`**\n"
            f"{blue_captain} (Order) vs {red_captain} (Chaos)\n"
            f"Series: Bo1 | Prefix: `{league_prefix}`\n"
            "Active match context opened for this channel."
        )
