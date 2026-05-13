import asyncio
import random
import string

import discord
from discord import app_commands

import config
from services import guild_config_service
from services import sheets_service
from commands._checks import require_guild, staff_only


def _generate_uid(prefix: str) -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=4))
    return f"{prefix}-{suffix}"


async def _uid_is_unique(sheet_id: str, uid: str, guild_id: int) -> bool:
    """Return True if this UID doesn't already exist in the Match Log."""
    status = await asyncio.to_thread(sheets_service.get_match_status, sheet_id, uid, guild_id)
    return len(status["games"]) == 0


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

        sheet_id = sheets_service.get_active_sheet_id(guild_id)
        if not sheet_id:
            await interaction.followup.send("No active season sheet. Run `/newseason` first.")
            return

        guild_cfg = guild_config_service.get_guild_config(guild_id)
        league_prefix = str(guild_cfg.get("league_prefix") or config.LEAGUE_PREFIX).upper()

        # Generate a collision-free UID (retries handle the rare duplicate)
        uid = _generate_uid(league_prefix)
        for _ in range(5):
            if await _uid_is_unique(sheet_id, uid, guild_id):
                break
            uid = _generate_uid(league_prefix)

        from datetime import timezone
        submitted_at = interaction.created_at.replace(tzinfo=timezone.utc).isoformat()

        await asyncio.to_thread(sheets_service.append_match_log, sheet_id, {
            "draft_id":      uid,
            "guild_id":      str(guild_id),
            "game_number":   "",
            "submitted_at":  submitted_at,
            "blue_captain":  blue_captain.strip(),
            "red_captain":   red_captain.strip(),
            "blue_picks":    "",
            "red_picks":     "",
            "blue_bans":     "",
            "red_bans":      "",
            "fearless_pool": "",
            "game_status":   "Pending",
            "match_status":  "created",
            "winner":        "TBD",
            "series_score":  "TBD",
        })

        await interaction.followup.send(
            f"**Match ID: `{uid}`**\n"
            f"{blue_captain} (Order) vs {red_captain} (Chaos)\n"
            f"Players: include `{uid}` in your screenshot message."
        )
