import asyncio
import json
from datetime import timezone

import discord

import config
from services import evidence_service, guild_config_service, sheets_service
from utils.uid_parser import extract_uid


async def handle_json_message(message: discord.Message) -> None:
    """Process a new message in the JSON drop channel."""
    if message.guild is None:
        return

    json_attachments = [a for a in message.attachments if a.filename.endswith(".json")]
    if not json_attachments:
        return

    sheet_id = sheets_service.get_active_sheet_id(message.guild.id)
    if not sheet_id:
        await _admin(message, "⚠️ No active season sheet. Run `/newseason` first.")
        return

    for attachment in json_attachments:
        await _process_attachment(message, attachment, sheet_id)


async def _process_attachment(
    message: discord.Message,
    attachment: discord.Attachment,
    sheet_id: str,
) -> None:
    raw_bytes = await attachment.read()

    try:
        data = json.loads(raw_bytes)
    except json.JSONDecodeError:
        await _admin(message, f"❌ Could not parse `{attachment.filename}` — invalid JSON.")
        return

    if "draft_id" not in data:
        await _admin(
            message,
            f"❌ `{attachment.filename}` is missing a `draft_id` field. Is this a GodForge file?",
        )
        return

    # Prefer the draft_id from JSON content; fall back to filename
    draft_id = data.get("draft_id") or extract_uid(filenames=[attachment.filename])
    if not draft_id:
        await _admin(message, f"❌ Could not determine draft_id from `{attachment.filename}`.")
        return

    guild_id = message.guild.id
    fingerprint = evidence_service.fingerprint_json(data)
    if sheets_service.evidence_exists(sheet_id, guild_id, draft_id, fingerprint):
        await _admin(message, f"⚠️ Duplicate Draft JSON ignored for `{draft_id}` in guild `{guild_id}`.")
        return

    submitted_at = message.created_at.replace(tzinfo=timezone.utc).isoformat()
    games = data.get("games") or [data]  # support flat (single-game) or games-array format

    await asyncio.to_thread(sheets_service.append_evidence, sheet_id, {
        "guild_id": str(guild_id),
        "match_id": draft_id,
        "evidence_fingerprint": fingerprint,
        "evidence_type": "draft_json",
        "message_id": str(message.id),
        "filename": attachment.filename,
        "uploaded_at": submitted_at,
        "parsed_player_names": "",
        "status": "evidence_uploaded",
        "notes": "Draft JSON enriches match context only",
    })

    for i, game in enumerate(games, start=1):
        row = {
            "draft_id":      draft_id,
            "guild_id":      str(guild_id),
            "game_number":   game.get("game_number", i),
            "submitted_at":  submitted_at,
            "blue_captain":  data.get("blue_captain", ""),
            "red_captain":   data.get("red_captain", ""),
            "blue_picks":    _join(game.get("blue_picks", [])),
            "red_picks":     _join(game.get("red_picks", [])),
            "blue_bans":     _join(game.get("blue_bans", [])),
            "red_bans":      _join(game.get("red_bans", [])),
            "fearless_pool": _join(game.get("fearless_pool", [])),
            "game_status":   game.get("status", game.get("game_status", "Unknown")),
            "match_status":  "evidence_uploaded",
            "evidence_fingerprints": fingerprint,
            "review_notes":  "Draft JSON enrichment; stats require screenshot evidence and confirmation",
            "winner":        "TBD",
            "series_score":  "TBD",
        }
        await asyncio.to_thread(sheets_service.append_match_log, sheet_id, row)

    game_word = "game" if len(games) == 1 else "games"
    await _admin(
        message,
        f"✅ `{draft_id}` — {len(games)} {game_word} logged to Match Log.",
    )


def _join(values: list) -> str:
    return ", ".join(str(v) for v in values) if values else ""


async def _admin(message: discord.Message, text: str) -> None:
    guild_cfg = guild_config_service.get_guild_config(message.guild.id)
    channel_id = guild_cfg.get("admin_report_channel_id") or config.ADMIN_REPORT_CHANNEL_ID
    if channel_id is None:
        return
    channel = message.guild.get_channel(channel_id)
    if channel:
        await channel.send(text)
