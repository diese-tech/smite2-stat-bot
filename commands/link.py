import asyncio
import json
from datetime import timezone

import discord
from discord import app_commands

from services import sheets_service
from commands._checks import require_guild, staff_only


def setup(tree: app_commands.CommandTree) -> None:
    @tree.command(name="link", description="Link an unlinked screenshot submission to a draft ID")
    @app_commands.describe(uid="The draft ID to link to (e.g. GF-08R8)")
    @staff_only()
    async def link(interaction: discord.Interaction, uid: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return

        if not interaction.message or not interaction.message.reference:
            await interaction.followup.send(
                "Please **reply to the screenshot message** before running `/link`."
            )
            return

        ref = interaction.message.reference
        message_id = str(ref.message_id)
        uid = uid.upper().strip()

        sheet_id = sheets_service.get_active_sheet_id(guild_id)
        if not sheet_id:
            await interaction.followup.send("No active season sheet. Run `/newseason` first.")
            return

        unlinked = await asyncio.to_thread(
            sheets_service.remove_unlinked_by_message_id, sheet_id, message_id, guild_id
        )

        if unlinked is None:
            await interaction.followup.send(
                f"No unlinked submission found for message `{message_id}`. "
                "It may already be linked or was never saved."
            )
            return

        # Recover stats rows from the stored JSON payload
        raw_json = unlinked.get("Raw Stats JSON", "{}")
        try:
            extraction = json.loads(raw_json)
        except json.JSONDecodeError:
            await interaction.followup.send("Could not parse stored stats JSON. Try `/reparse` instead.")
            return

        date = unlinked.get("Timestamp", "")
        from handlers.match_correlator import merge_extractions
        rows = merge_extractions(
            scoreboard=extraction if extraction.get("screenshot_type") == "scoreboard" else None,
            details=extraction    if extraction.get("screenshot_type") == "details"    else extraction,
            draft_id=uid,
            game_number="",
            date=date,
        )
        for row in rows:
            row["draft_id"] = uid
            row["guild_id"] = str(guild_id)
            row["match_status"] = "parsed"
            row["evidence_fingerprint"] = unlinked.get("Evidence Fingerprint", "")

        if not await asyncio.to_thread(sheets_service.match_exists, sheet_id, uid, guild_id):
            submitted_at = interaction.created_at.replace(tzinfo=timezone.utc).isoformat()
            await asyncio.to_thread(sheets_service.append_match_log, sheet_id, {
                "draft_id": uid,
                "guild_id": str(guild_id),
                "game_number": "",
                "submitted_at": submitted_at,
                "game_status": "Evidence Uploaded",
                "match_status": "evidence_uploaded",
                "evidence_fingerprints": unlinked.get("Evidence Fingerprint", ""),
                "review_notes": "Created when an unlinked screenshot was attached",
            })

        await asyncio.to_thread(sheets_service.append_player_stats, sheet_id, rows)
        await asyncio.to_thread(
            sheets_service.update_match_status, sheet_id, uid, guild_id, "parsed"
        )
        await interaction.followup.send(
            f"✅ Linked message `{message_id}` to `{uid}`. {len(rows)} player rows moved to Player Stats."
        )
