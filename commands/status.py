import asyncio

import discord
from discord import app_commands

from services import sheets_service
from commands._checks import require_guild, staff_only


def setup(tree: app_commands.CommandTree) -> None:
    @tree.command(name="status", description="Show game count and sheet status for a draft ID")
    @app_commands.describe(uid="The draft ID (e.g. GF-08R8)")
    @staff_only()
    async def status(interaction: discord.Interaction, uid: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return

        uid = uid.upper().strip()
        sheet_id = sheets_service.get_active_sheet_id(guild_id)
        if not sheet_id:
            await interaction.followup.send("No active season sheet. Run `/newseason` first.")
            return

        data = await asyncio.to_thread(sheets_service.get_match_status, sheet_id, uid, guild_id)

        if not data["games"]:
            await interaction.followup.send(f"No data found for `{uid}`.")
            return

        lines = [f"**{uid}**"]
        for g in data["games"]:
            lines.append(f"  Game {g['game_number']}: {g['game_status']}")
        lines.append(f"Match status: {data['match_status']}")
        lines.append(f"Stats rows: {data['stats_rows_found']}")
        lines.append(f"Winner: {data['winner']}  |  Score: {data['series_score']}")

        await interaction.followup.send("\n".join(lines))
