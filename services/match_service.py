import json
import os
import random
import string
import tempfile
import time
from pathlib import Path

import config
from services import guild_config_service


MATCHES_FILE = "forgelens_matches.json"
MATCH_STATUSES = {"created", "open", "closed", "official", "archived"}


def _now() -> int:
    return int(time.time())


def matches_path() -> Path:
    return Path(config.FORGELENS_MATCHES_PATH or MATCHES_FILE)


def _empty_store() -> dict:
    return {"guilds": {}}


def _empty_guild(guild_id: int | str) -> dict:
    return {
        "guild_id": str(guild_id),
        "matches": {},
        "drafts": {},
        "active_match_contexts": {},
        "counters": {"match": 0},
    }


def _load_store() -> dict:
    path = matches_path()
    if not path.exists():
        return _empty_store()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("guilds", {})
    return data


def _save_store(data: dict) -> None:
    path = matches_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent if str(path.parent) != "." else None,
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
        ) as tmp:
            json.dump(data, tmp, indent=2, sort_keys=True)
            tmp.flush()
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def _guild(data: dict, guild_id: int | str) -> dict:
    key = str(guild_id)
    if key not in data["guilds"]:
        data["guilds"][key] = _empty_guild(key)
    guild = data["guilds"][key]
    guild.setdefault("matches", {})
    guild.setdefault("drafts", {})
    guild.setdefault("active_match_contexts", {})
    guild.setdefault("counters", {"match": 0})
    return guild


def _league_prefix(guild_id: int | str) -> str:
    cfg = guild_config_service.get_guild_config(guild_id)
    return str(cfg.get("league_prefix") or config.LEAGUE_PREFIX).upper()


def _generate_match_id(guild: dict, guild_id: int | str) -> str:
    chars = string.ascii_uppercase + string.digits
    prefix = _league_prefix(guild_id)
    for _ in range(20):
        suffix = "".join(random.choices(chars, k=4))
        match_id = f"{prefix}-{suffix}"
        if match_id not in guild["matches"]:
            guild["counters"]["match"] = int(guild["counters"].get("match", 0)) + 1
            return match_id
    raise ValueError("Could not generate a unique match ID.")


def _normalize_best_of(best_of: int | str) -> int:
    value = int(best_of)
    if value not in {1, 3, 5}:
        raise ValueError("best_of must be one of 1, 3, or 5.")
    return value


def _channel_key(channel_id: int | str) -> str:
    return str(channel_id)


def _active_context(guild: dict, channel_id: int | str) -> dict | None:
    return guild["active_match_contexts"].get(_channel_key(channel_id))


def _base_match(
    guild_id: int | str,
    channel_id: int | str,
    created_by: int | str,
    match_id: str,
    best_of: int,
    blue_team: str,
    red_team: str,
) -> dict:
    now = _now()
    return {
        "match_id": match_id,
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "status": "open",
        "best_of": best_of,
        "created_by": str(created_by),
        "teams": {
            "blue": blue_team.strip(),
            "red": red_team.strip(),
        },
        "result": {
            "winner": "",
            "score": "",
            "official_by": "",
            "official_at": 0,
        },
        "drafts": [],
        "created_at": now,
        "opened_at": now,
        "closed_at": 0,
        "updated_at": now,
    }


def create_or_open_match(
    guild_id: int | str,
    channel_id: int | str,
    created_by: int | str,
    best_of: int = 1,
    blue_team: str = "",
    red_team: str = "",
    match_id: str = "",
) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    existing = _active_context(guild, channel_id)
    if existing and existing.get("status") == "open":
        current = guild["matches"].get(existing["match_id"])
        if current:
            return {"created": False, "context": existing, "match": current}

    normalized_best_of = _normalize_best_of(best_of)
    normalized_match_id = match_id.upper().strip() if match_id else _generate_match_id(guild, guild_id)
    if normalized_match_id in guild["matches"]:
        match = guild["matches"][normalized_match_id]
        match["channel_id"] = str(channel_id)
        match["status"] = "open"
        match["best_of"] = normalized_best_of
        if blue_team.strip():
            match["teams"]["blue"] = blue_team.strip()
        if red_team.strip():
            match["teams"]["red"] = red_team.strip()
        match["updated_at"] = _now()
        match["opened_at"] = match.get("opened_at") or _now()
    else:
        match = _base_match(
            guild_id,
            channel_id,
            created_by,
            normalized_match_id,
            normalized_best_of,
            blue_team,
            red_team,
        )
        guild["matches"][normalized_match_id] = match

    context = {
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "match_id": normalized_match_id,
        "status": "open",
        "opened_at": match["opened_at"],
        "closed_at": 0,
    }
    guild["active_match_contexts"][_channel_key(channel_id)] = context
    _save_store(data)
    return {"created": True, "context": context, "match": match}


def close_active_match(guild_id: int | str, channel_id: int | str, closed_by: int | str) -> dict | None:
    del closed_by
    data = _load_store()
    guild = _guild(data, guild_id)
    context = _active_context(guild, channel_id)
    if not context:
        return None
    match = guild["matches"].get(context["match_id"])
    now = _now()
    context["status"] = "closed"
    context["closed_at"] = now
    if match:
        if match.get("status") != "official":
            match["status"] = "closed"
        match["closed_at"] = now
        match["updated_at"] = now
    _save_store(data)
    return {"context": context, "match": match}


def get_active_match_context(guild_id: int | str, channel_id: int | str) -> dict | None:
    data = _load_store()
    guild = _guild(data, guild_id)
    context = _active_context(guild, channel_id)
    if context and context.get("status") == "open":
        return context
    return None


def get_match(guild_id: int | str, match_id: str) -> dict | None:
    data = _load_store()
    guild = _guild(data, guild_id)
    return guild["matches"].get(match_id.upper().strip())


def find_match_by_draft(guild_id: int | str, draft_id: str) -> dict | None:
    data = _load_store()
    guild = _guild(data, guild_id)
    wanted = draft_id.strip()
    for match in guild["matches"].values():
        for draft in match.get("drafts", []):
            if draft.get("draft_id") == wanted:
                return match
    return None


def official_result(
    guild_id: int | str,
    match_id: str,
    winner: str,
    score: str,
    actor_id: int | str,
) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    normalized_match_id = match_id.upper().strip()
    match = guild["matches"].get(normalized_match_id)
    if match is None:
        match = _base_match(guild_id, "0", actor_id, normalized_match_id, 1, "", "")
        guild["matches"][normalized_match_id] = match
    now = _now()
    match["status"] = "official"
    match["result"] = {
        "winner": winner.strip(),
        "score": score.strip(),
        "official_by": str(actor_id),
        "official_at": now,
    }
    match["closed_at"] = match.get("closed_at") or now
    match["updated_at"] = now
    for context in guild["active_match_contexts"].values():
        if context.get("match_id") == normalized_match_id:
            context["status"] = "closed"
            context["closed_at"] = now
    _save_store(data)
    return match


def resolve_match_for_channel(
    guild_id: int | str,
    channel_id: int | str,
    explicit_match_id: str = "",
) -> dict | None:
    if explicit_match_id:
        match = get_match(guild_id, explicit_match_id)
        if match:
            return match
    context = get_active_match_context(guild_id, channel_id)
    if not context:
        return None
    return get_match(guild_id, context["match_id"])


def _import_key(source: str, guild_id: int | str, channel_id: int | str, draft_id: str, game_number: int | str) -> str:
    return "|".join([source, str(guild_id), str(channel_id), draft_id, str(game_number)])


def _extract_games(payload: dict) -> list[dict]:
    games = payload.get("games")
    if isinstance(games, list) and games:
        return games
    return [payload]


def _selected_gods(game: dict) -> list[str]:
    if isinstance(game.get("selected_gods"), list):
        return [str(item) for item in game.get("selected_gods", [])]
    picks = []
    for key in ("blue_picks", "red_picks", "order_picks", "chaos_picks"):
        values = game.get(key) or []
        if isinstance(values, list):
            picks.extend(str(item) for item in values)
    return picks


def _draft_payload(
    source: str,
    guild_id: int | str,
    channel_id: int | str,
    message_id: int | str,
    payload: dict,
    game: dict,
    imported_at: int,
    status: str,
    explicit_match_id: str = "",
) -> dict:
    draft_id = str(payload.get("draft_id") or game.get("draft_id") or "").strip()
    game_number = game.get("game_number") or payload.get("game_number") or 1
    return {
        "import_key": _import_key(source, guild_id, channel_id, draft_id, game_number),
        "draft_id": draft_id,
        "source": source,
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "message_id": str(message_id),
        "game_number": game_number,
        "draft_sequence": game.get("draft_sequence") or payload.get("draft_sequence") or "",
        "status": status,
        "picks": list(game.get("blue_picks") or game.get("order_picks") or []) + list(game.get("red_picks") or game.get("chaos_picks") or []),
        "bans": list(game.get("blue_bans") or game.get("order_bans") or []) + list(game.get("red_bans") or game.get("chaos_bans") or []),
        "selected_gods": _selected_gods(game),
        "imported_at": imported_at,
        "forgelens_match_id": explicit_match_id.upper().strip(),
        "linked_match_id": "",
    }


def import_godforge_draft(
    guild_id: int | str,
    channel_id: int | str,
    message_id: int | str,
    payload: dict,
) -> dict:
    if payload.get("producer") != "GodForge":
        raise ValueError("Only producer 'GodForge' payloads are importable.")
    draft_id = str(payload.get("draft_id") or "").strip()
    if not draft_id:
        raise ValueError("GodForge payload missing draft_id.")

    data = _load_store()
    guild = _guild(data, guild_id)
    explicit_match_id = str(payload.get("forgelens_match_id") or "").upper().strip()
    target_match = None
    if explicit_match_id:
        target_match = guild["matches"].get(explicit_match_id)
    if target_match is None:
        active = _active_context(guild, channel_id)
        if active and active.get("status") == "open":
            target_match = guild["matches"].get(active["match_id"])

    imported_at = _now()
    imported = []
    for game in _extract_games(payload):
        status = str(game.get("status") or game.get("game_status") or payload.get("draft_status") or "draft_complete")
        draft = _draft_payload(
            "GodForge",
            guild_id,
            channel_id,
            message_id,
            payload,
            game,
            imported_at,
            status,
            explicit_match_id,
        )
        existing = guild["drafts"].get(draft["import_key"])
        if existing:
            existing.update({
                "message_id": str(message_id),
                "draft_sequence": draft["draft_sequence"] or existing.get("draft_sequence", ""),
                "status": draft["status"] or existing.get("status", ""),
                "picks": draft["picks"] or existing.get("picks", []),
                "bans": draft["bans"] or existing.get("bans", []),
                "selected_gods": draft["selected_gods"] or existing.get("selected_gods", []),
            })
            draft = existing
        else:
            guild["drafts"][draft["import_key"]] = draft

        if target_match:
            draft["linked_match_id"] = target_match["match_id"]
            if not any(item.get("import_key") == draft["import_key"] for item in target_match["drafts"]):
                target_match["drafts"].append(dict(draft))
            else:
                for idx, item in enumerate(target_match["drafts"]):
                    if item.get("import_key") == draft["import_key"]:
                        target_match["drafts"][idx] = dict(draft)
                        break
            target_match["updated_at"] = imported_at
        imported.append(dict(draft))

    _save_store(data)
    return {
        "linked_match_id": target_match["match_id"] if target_match else "",
        "drafts": imported,
    }


def observe_godforge_status(
    guild_id: int | str,
    channel_id: int | str,
    message_id: int | str,
    status_fields: dict,
) -> dict | None:
    if str(status_fields.get("draft_status") or "").strip() != "draft_complete":
        return None
    payload = {
        "producer": "GodForge",
        "draft_id": status_fields.get("draft_id", ""),
        "forgelens_match_id": status_fields.get("forgelens_match_id", ""),
        "draft_sequence": status_fields.get("draft_sequence", ""),
        "draft_status": status_fields.get("draft_status", ""),
        "games": [{
            "game_number": status_fields.get("game_number", 1),
            "draft_sequence": status_fields.get("draft_sequence", ""),
            "status": status_fields.get("draft_status", ""),
            "selected_gods": [],
            "blue_picks": [],
            "red_picks": [],
            "blue_bans": [],
            "red_bans": [],
        }],
    }
    if not payload["draft_id"]:
        return None
    return import_godforge_draft(guild_id, channel_id, message_id, payload)


def export_guild_data(guild_id: int | str) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    matches = list(guild["matches"].values())
    contexts = list(guild["active_match_contexts"].values())
    unlinked = [draft for draft in guild["drafts"].values() if not draft.get("linked_match_id")]
    return {
        "guild_id": str(guild_id),
        "storage_path": str(matches_path()),
        "matches": matches,
        "active_match_contexts": contexts,
        "unlinked_drafts": unlinked,
    }


def get_match_status(guild_id: int | str, match_id: str) -> str | None:
    match = get_match(guild_id, match_id)
    if match:
        return match.get("status")
    linked = find_match_by_draft(guild_id, match_id)
    if linked:
        return linked.get("status")
    return None
