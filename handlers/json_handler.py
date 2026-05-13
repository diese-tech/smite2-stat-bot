import asyncio
import json
from datetime import timezone

import discord

import config
from services import evidence_service, guild_config_service, match_service, sheets_service
from utils.uid_parser import extract_uid


async def handle_json_message(
    message: discord.Message,
    configured_json_channel_id: int | None = None,
) -> None:
    """Observe public GodForge handoff messages while keeping ForgeLens standalone."""
    if message.guild is None:
        return

    await _observe_godforge_embeds(message)

    json_attachments = [a for a in message.attachments if a.filename.lower().endswith(".json")]
    if not json_attachments:
        return

    guild_cfg = guild_config_service.get_guild_config(message.guild.id)
    json_channel_id = configured_json_channel_id
    if json_channel_id is None:
        json_channel_id = guild_cfg.get("json_channel_id") or config.JSON_CHANNEL_ID

    for attachment in json_attachments:
        await _process_attachment(message, attachment, json_channel_id)


async def _process_attachment(
    message: discord.Message,
    attachment: discord.Attachment,
    json_channel_id: int | None,
) -> None:
    raw_bytes = await attachment.read()

    try:
        data = json.loads(raw_bytes)
    except json.JSONDecodeError:
        await _admin(message, f"Could not parse `{attachment.filename}` because the JSON is invalid.")
        return

    if data.get("producer") != "GodForge":
        if json_channel_id is not None and message.channel.id == json_channel_id:
            await _admin(message, f"Ignored `{attachment.filename}` because producer is not `GodForge`.")
        return

    draft_id = data.get("draft_id") or extract_uid(filenames=[attachment.filename])
    if not draft_id:
        await _admin(message, f"Could not determine a draft_id from `{attachment.filename}`.")
        return

    data["draft_id"] = draft_id
    guild_id = message.guild.id
    fingerprint = evidence_service.fingerprint_json(data)
    link_result = await asyncio.to_thread(
        match_service.import_godforge_draft,
        guild_id,
        message.channel.id,
        message.id,
        data,
    )

    sheet_id = sheets_service.get_active_sheet_id(guild_id)
    submitted_at = message.created_at.replace(tzinfo=timezone.utc).isoformat()
    games = data.get("games") or [data]
    if sheet_id and not sheets_service.evidence_exists(sheet_id, guild_id, draft_id, fingerprint):
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
            "notes": "GodForge draft enrichment only; settlement still requires official ForgeLens result",
        })
        for i, game in enumerate(games, start=1):
            await asyncio.to_thread(sheets_service.append_match_log, sheet_id, {
                "draft_id": draft_id,
                "guild_id": str(guild_id),
                "game_number": game.get("game_number", i),
                "submitted_at": submitted_at,
                "blue_captain": data.get("blue_captain", ""),
                "red_captain": data.get("red_captain", ""),
                "blue_picks": _join(game.get("blue_picks", [])),
                "red_picks": _join(game.get("red_picks", [])),
                "blue_bans": _join(game.get("blue_bans", [])),
                "red_bans": _join(game.get("red_bans", [])),
                "fearless_pool": _join(game.get("fearless_pool", [])),
                "game_status": game.get("status", game.get("game_status", "Unknown")),
                "match_status": "evidence_uploaded",
                "evidence_fingerprints": fingerprint,
                "review_notes": "GodForge draft enrichment; stats and results remain ForgeLens-owned",
                "winner": "TBD",
                "series_score": "TBD",
            })

    game_word = "game" if len(games) == 1 else "games"
    linked_match = link_result["linked_match_id"] or "unlinked"
    await _admin(
        message,
        f"Imported GodForge draft `{draft_id}` with {len(games)} {game_word}; ForgeLens linked it to `{linked_match}`.",
    )


async def _observe_godforge_embeds(message: discord.Message) -> None:
    for embed in message.embeds:
        parsed = _parse_forgelens_status(embed)
        if not parsed:
            continue
        try:
            result = await asyncio.to_thread(
                match_service.observe_godforge_status,
                message.guild.id,
                message.channel.id,
                message.id,
                parsed,
            )
        except ValueError:
            continue
        if result:
            linked = result["linked_match_id"] or "unlinked"
            await _admin(
                message,
                f"Observed GodForge handoff `{parsed['draft_id']}` from an embed and linked it to `{linked}`.",
            )


def _parse_forgelens_status(embed: discord.Embed) -> dict | None:
    for field in embed.fields:
        if field.name.strip().lower() != "forgelens status":
            continue
        parsed = {}
        for raw_line in field.value.splitlines():
            if "=" not in raw_line:
                continue
            key, value = raw_line.split("=", 1)
            parsed[key.strip()] = value.strip()
        if parsed.get("draft_status") and parsed.get("draft_id"):
            return parsed
    return None


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
