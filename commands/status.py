import asyncio

import discord
from discord import app_commands

from services import match_service, sheets_service
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
        local_match = await asyncio.to_thread(match_service.get_match, guild_id, uid)
        if local_match is None:
            local_match = await asyncio.to_thread(match_service.find_match_by_draft, guild_id, uid)

        sheet_id = sheets_service.get_active_sheet_id(guild_id)
        if not sheet_id and not local_match:
            await interaction.followup.send("No data found and no active season sheet is configured.")
            return

        data = {"games": [], "match_status": "", "stats_rows_found": 0, "winner": "TBD", "series_score": "TBD"}
        if sheet_id:
            data = await asyncio.to_thread(sheets_service.get_match_status, sheet_id, uid, guild_id)

        if not data["games"] and not local_match:
            await interaction.followup.send(f"No data found for `{uid}`.")
            return

        display_id = local_match["match_id"] if local_match else uid
        lines = [f"**{display_id}**"]
        if local_match:
            lines.append(f"Local status: {local_match['status']} | Bo{local_match['best_of']}")
            lines.append(
                f"Teams: {local_match['teams']['blue'] or 'Blue'} vs {local_match['teams']['red'] or 'Red'}"
            )
            lines.append(f"Linked drafts: {len(local_match.get('drafts', []))}")
        for g in data["games"]:
            lines.append(f"  Game {g['game_number']}: {g['game_status']}")
        if sheet_id:
            lines.append(f"Sheet status: {data['match_status']}")
            lines.append(f"Stats rows: {data['stats_rows_found']}")
            lines.append(f"Winner: {data['winner']}  |  Score: {data['series_score']}")
        elif local_match:
            lines.append(
                f"Winner: {local_match['result']['winner'] or 'TBD'}  |  Score: {local_match['result']['score'] or 'TBD'}"
            )

        await interaction.followup.send("\n".join(lines))
