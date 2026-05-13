import asyncio

import discord
from discord import app_commands

from services import sheets_service
from commands._checks import require_guild, staff_only


def setup(tree: app_commands.CommandTree) -> None:
    @tree.command(name="result", description="Set the series result for a draft ID")
    @app_commands.describe(
        uid="The draft ID (e.g. GF-08R8)",
        winner="Winning team or player name",
        score="Series score (e.g. 2-1)",
    )
    @staff_only()
    async def result(interaction: discord.Interaction, uid: str, winner: str, score: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return

        uid = uid.upper().strip()
        sheet_id = sheets_service.get_active_sheet_id(guild_id)
        if not sheet_id:
            await interaction.followup.send("No active season sheet. Run `/newseason` first.")
            return

        updated = await asyncio.to_thread(
            sheets_service.update_match_result, sheet_id, uid, winner, score, guild_id, "official"
        )

        if updated:
            await interaction.followup.send(
                f"`{uid}` is official - winner: **{winner}**, score: **{score}**"
            )
        else:
            await interaction.followup.send(
                f"No Match Log rows found for `{uid}`. Check the draft ID and try again."
            )
