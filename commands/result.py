import asyncio

import discord
from discord import app_commands

from services import match_service, sheets_service
from commands._checks import require_guild, staff_only


def setup(tree: app_commands.CommandTree) -> None:
    @tree.command(name="result", description="Mark a ForgeLens match result official")
    @app_commands.describe(
        winner="Winning team or player name",
        score="Series score (e.g. 2-1)",
        uid="Optional ForgeLens match ID or linked draft ID. Defaults to the active channel match.",
    )
    @staff_only()
    async def result(interaction: discord.Interaction, winner: str, score: str, uid: str = ""):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return

        resolved_uid = uid.upper().strip()
        match = None
        if resolved_uid:
            match = await asyncio.to_thread(match_service.get_match, guild_id, resolved_uid)
            if match is None:
                match = await asyncio.to_thread(match_service.find_match_by_draft, guild_id, resolved_uid)
        else:
            match = await asyncio.to_thread(match_service.resolve_match_for_channel, guild_id, interaction.channel_id)

        if match is None:
            await interaction.followup.send(
                "No ForgeLens match found. Pass `uid:` or open a match first with `/match start`."
            )
            return

        match_id = match["match_id"]
        await asyncio.to_thread(match_service.official_result, guild_id, match_id, winner, score, interaction.user.id)

        sheet_id = sheets_service.get_active_sheet_id(guild_id)
        updated_drafts = 0
        if sheet_id:
            linked_drafts = {draft.get("draft_id") for draft in match.get("drafts", []) if draft.get("draft_id")}
            if not linked_drafts and resolved_uid:
                linked_drafts.add(resolved_uid)
            for draft_id in linked_drafts:
                changed = await asyncio.to_thread(
                    sheets_service.update_match_result,
                    sheet_id,
                    draft_id,
                    winner,
                    score,
                    guild_id,
                    "official",
                )
                updated_drafts += int(bool(changed))

        await interaction.followup.send(
            f"`{match_id}` is official - winner: **{winner}**, score: **{score}**. "
            f"Linked draft rows updated: **{updated_drafts}**."
        )
