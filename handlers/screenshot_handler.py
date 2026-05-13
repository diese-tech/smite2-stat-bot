import asyncio
from datetime import timezone

import discord

import config
from handlers.match_correlator import merge_extractions
from services import evidence_service, gemini_vision, guild_config_service, sheets_service
from utils.uid_parser import extract_uid

REACT_OK      = "✅"
REACT_WARN    = "⚠️"
REACT_UNKNOWN = "❓"
REACT_FAIL    = "❌"

# Mime types accepted for vision analysis
_IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}


async def handle_screenshot_message(message: discord.Message) -> None:
    if message.guild is None:
        return

    guild_id = message.guild.id
    images = [a for a in message.attachments if _is_image(a)]
    if not images:
        return

    sheet_id = sheets_service.get_active_sheet_id(guild_id)
    if not sheet_id:
        await message.add_reaction(REACT_WARN)
        await _admin(message, "⚠️ No active season sheet. Run `/newseason` first.")
        return

    draft_id = extract_uid(
        text=message.content,
        filenames=[a.filename for a in images],
    )

    scoreboard: dict | None = None
    details:    dict | None = None
    failed_count = 0
    unknown_count = 0
    duplicate_count = 0
    fingerprints: list[str] = []
    filenames: list[str] = []

    for attachment in images:
        raw = await attachment.read()
        mime = attachment.content_type or "image/png"
        fingerprint = evidence_service.fingerprint_bytes(raw)
        fingerprints.append(fingerprint)
        filenames.append(attachment.filename)

        if draft_id and sheets_service.evidence_exists(sheet_id, guild_id, draft_id, fingerprint):
            duplicate_count += 1
            await _admin(
                message,
                f"⚠️ Duplicate evidence ignored for `{draft_id}` in guild `{guild_id}` "
                f"(`{attachment.filename}`).",
            )
            continue

        try:
            result = await gemini_vision.analyze_image(raw, mime)
        except Exception as e:
            failed_count += 1
            await _admin(message, f"❌ Gemini error on `{attachment.filename}`: {e}")
            continue

        if not result.get("valid"):
            unknown_count += 1
            continue

        stype = result.get("screenshot_type", "")
        if stype == "scoreboard":
            scoreboard = result
        elif stype == "details":
            details = result

        player_names = _player_names(result)
        await asyncio.to_thread(sheets_service.append_evidence, sheet_id, {
            "guild_id": str(guild_id),
            "match_id": draft_id or "",
            "evidence_fingerprint": fingerprint,
            "evidence_type": f"screenshot:{stype}",
            "message_id": str(message.id),
            "filename": attachment.filename,
            "uploaded_at": message.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "parsed_player_names": ", ".join(player_names),
            "status": "parsed",
            "notes": "",
        })

    # Nothing usable extracted
    if scoreboard is None and details is None:
        if duplicate_count and duplicate_count == len(images):
            await message.add_reaction(REACT_WARN)
        elif failed_count > 0:
            await message.add_reaction(REACT_FAIL)
        else:
            await message.add_reaction(REACT_UNKNOWN)
        return

    # Build merged rows
    date = message.created_at.replace(tzinfo=timezone.utc).isoformat()
    game_number = ""  # assigned by submission order; correlator doesn't know game number yet
    rows = merge_extractions(scoreboard, details, draft_id or "", game_number, date)

    partial = _is_partial(details, scoreboard)
    match_status = "review_required" if partial else "parsed"
    evidence_fingerprint = ",".join(fingerprints)

    if draft_id:
        if not await asyncio.to_thread(sheets_service.match_exists, sheet_id, draft_id, guild_id):
            await asyncio.to_thread(sheets_service.append_match_log, sheet_id, {
                "draft_id": draft_id,
                "guild_id": str(guild_id),
                "game_number": "",
                "submitted_at": date,
                "game_status": "Evidence Uploaded",
                "match_status": "evidence_uploaded",
                "evidence_fingerprints": evidence_fingerprint,
                "review_notes": "Created from screenshot evidence",
            })
        for row in rows:
            row["guild_id"] = str(guild_id)
            row["match_status"] = match_status
            row["evidence_fingerprint"] = evidence_fingerprint
            row["confidence"] = ""
            row["review_notes"] = "Partial extraction requires stat admin review" if partial else ""

        await asyncio.to_thread(sheets_service.append_player_stats, sheet_id, rows)
        await asyncio.to_thread(
            sheets_service.update_match_status,
            sheet_id,
            draft_id,
            guild_id,
            match_status,
            "Partial extraction requires stat admin review" if partial else "",
        )
        if partial:
            await message.add_reaction(REACT_WARN)
            await _admin(message, f"⚠️ `{draft_id}` — partial extraction. Some stats may be missing.")
        else:
            await message.add_reaction(REACT_OK)
    else:
        # No UID found — route to Unlinked
        player_names = _player_names(details or scoreboard)
        unlinked_rows = await asyncio.to_thread(sheets_service.get_unlinked_rows, sheet_id, guild_id)
        fuzzy_candidate = await asyncio.to_thread(
            evidence_service.best_fuzzy_match,
            player_names,
            unlinked_rows,
        )
        await asyncio.to_thread(sheets_service.append_unlinked, sheet_id, {
            "timestamp":           date,
            "message_id":          str(message.id),
            "parsed_player_names": ", ".join(player_names),
            "raw_stats_json":      _raw_json(details or scoreboard),
            "notes":               "No UID found in message or filenames",
            "guild_id":            str(guild_id),
            "evidence_fingerprint": evidence_fingerprint,
            "fuzzy_match_candidate": fuzzy_candidate,
        })
        await message.add_reaction(REACT_WARN)
        fuzzy_note = f" Possible duplicate of message `{fuzzy_candidate}`." if fuzzy_candidate else ""
        await _admin(
            message,
            f"⚠️ Screenshot posted without a draft ID (message {message.id}). "
            "Stats saved to Unlinked tab. Use `/link uid:GF-XXXX` replying to that message to resolve."
            f"{fuzzy_note}",
        )


async def reparse_message(message: discord.Message) -> bool:
    """Re-send all images in message to Gemini and overwrite existing sheet data. Returns True on success."""
    images = [a for a in message.attachments if _is_image(a)]
    if not images:
        return False

    if message.guild is None:
        return False

    sheet_id = sheets_service.get_active_sheet_id(message.guild.id)
    if not sheet_id:
        return False

    # Remove from Unlinked if present, then re-run the full flow
    await asyncio.to_thread(
        sheets_service.remove_unlinked_by_message_id, sheet_id, str(message.id), message.guild.id
    )

    # Clear any existing reactions by the bot
    try:
        me = message.guild.me
        for reaction in message.reactions:
            await reaction.remove(me)
    except discord.HTTPException:
        pass

    await handle_screenshot_message(message)
    return True


# ── Helpers ────────────────────────────────────────────────────────────────

def _is_image(attachment: discord.Attachment) -> bool:
    ct = attachment.content_type or ""
    return any(ct.startswith(m) for m in _IMAGE_MIMES) or attachment.filename.lower().endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".webp")
    )


def _is_partial(details: dict | None, scoreboard: dict | None) -> bool:
    """Return True if either extraction is missing players or has empty stat fields."""
    if details is None or scoreboard is None:
        return True
    all_players = details.get("order_players", []) + details.get("chaos_players", [])
    if len(all_players) < 10:  # 5v5
        return True
    key_stats = ["player_damage", "gpm", "k"]
    return any(p.get(s, "") == "" for p in all_players for s in key_stats)


def _player_names(extraction: dict) -> list[str]:
    players = extraction.get("order_players", []) + extraction.get("chaos_players", [])
    return [p.get("player_name", "") for p in players if p.get("player_name")]


def _raw_json(extraction: dict) -> str:
    import json
    return json.dumps(extraction)


async def _admin(message: discord.Message, text: str) -> None:
    guild_cfg = guild_config_service.get_guild_config(message.guild.id)
    channel_id = guild_cfg.get("admin_report_channel_id") or config.ADMIN_REPORT_CHANNEL_ID
    if channel_id is None:
        return
    channel = message.guild.get_channel(channel_id)
    if channel:
        await channel.send(text)
