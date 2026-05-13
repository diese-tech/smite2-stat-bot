import json
from pathlib import Path

import config

GUILD_CONFIG_FILE = "guild_config.json"


def _empty_store() -> dict:
    return {"guilds": {}}


def _load_store() -> dict:
    path = Path(GUILD_CONFIG_FILE)
    if not path.exists():
        return _empty_store()
    with path.open() as f:
        data = json.load(f)
    if "guilds" not in data:
        data["guilds"] = {}
    return data


def _save_store(data: dict) -> None:
    with Path(GUILD_CONFIG_FILE).open("w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _guild_key(guild_id: int | str) -> str:
    return str(guild_id)


def _bootstrap_config(guild_id: int | str) -> dict:
    return {
        "guild_id": _guild_key(guild_id),
        "screenshot_channel_id": config.SCREENSHOT_CHANNEL_ID,
        "json_channel_id": config.JSON_CHANNEL_ID,
        "admin_report_channel_id": config.ADMIN_REPORT_CHANNEL_ID,
        "stat_admin_role_ids": config.STAFF_ROLE_IDS,
        "stat_admin_user_ids": config.STAT_ADMIN_USER_IDS,
        "confidence_threshold": config.CONFIDENCE_THRESHOLD,
        "betting_enabled": False,
        "parent_drive_folder_id": config.PARENT_DRIVE_FOLDER_ID,
        "active_season": None,
    }


def get_guild_config(guild_id: int | str) -> dict:
    store = _load_store()
    key = _guild_key(guild_id)
    guild = store["guilds"].get(key)
    if guild is None:
        guild = _bootstrap_config(key)
        store["guilds"][key] = guild
        _save_store(store)
    else:
        defaults = _bootstrap_config(key)
        changed = False
        for field, value in defaults.items():
            if field not in guild:
                guild[field] = value
                changed = True
        if changed:
            _save_store(store)
    return guild


def save_active_season(guild_id: int | str, sheet_id: str, season_name: str) -> None:
    store = _load_store()
    key = _guild_key(guild_id)
    guild = store["guilds"].get(key) or _bootstrap_config(key)
    guild["active_season"] = {
        "guild_id": key,
        "sheet_id": sheet_id,
        "season_name": season_name,
    }
    store["guilds"][key] = guild
    _save_store(store)


def get_active_season(guild_id: int | str) -> dict | None:
    guild = get_guild_config(guild_id)
    return guild.get("active_season") or _legacy_active_season(guild_id)


def get_active_sheet_id(guild_id: int | str) -> str | None:
    season = get_active_season(guild_id)
    return season["sheet_id"] if season else None


def _legacy_active_season(guild_id: int | str) -> dict | None:
    path = Path("active_season.json")
    if not path.exists():
        return None
    with path.open() as f:
        legacy = json.load(f)
    if not legacy.get("sheet_id"):
        return None
    season = {
        "guild_id": _guild_key(guild_id),
        "sheet_id": legacy["sheet_id"],
        "season_name": legacy.get("season_name", ""),
    }
    save_active_season(guild_id, season["sheet_id"], season["season_name"])
    return season

