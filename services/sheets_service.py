import json
from datetime import datetime, timezone
from pathlib import Path

import config
from services import guild_config_service

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

ACTIVE_SEASON_FILE = "active_season.json"

MATCH_STATUSES = {
    "created",
    "evidence_uploaded",
    "parsed",
    "review_required",
    "confirmed",
    "official",
    "exported",
    "archived",
}

MATCH_LOG_HEADERS = [
    "Draft ID", "Game Number", "Submitted At",
    "Blue Captain", "Red Captain",
    "Blue Picks", "Red Picks",
    "Blue Bans", "Red Bans",
    "Fearless Pool", "Game Status", "Winner", "Series Score",
    "Guild ID", "Match Status", "Evidence Fingerprints", "Review Notes",
]

PLAYER_STATS_HEADERS = [
    "Draft ID", "Game Number", "Date",
    "Player Name", "God", "Role", "Team",
    "K", "D", "A", "GPM",
    "Player Damage", "Minion Damage", "Jungle Damage", "Structure Damage",
    "Damage Taken", "Damage Mitigated", "Self Healing", "Ally Healing",
    "Wards Placed", "Win",
    "Guild ID", "Match Status", "Evidence Fingerprint", "Confidence", "Review Notes",
]

UNLINKED_HEADERS = [
    "Timestamp", "Discord Message ID", "Parsed Player Names",
    "Raw Stats JSON", "Notes",
    "Guild ID", "Evidence Fingerprint", "Fuzzy Match Candidate",
]

EVIDENCE_HEADERS = [
    "Guild ID", "Match ID", "Evidence Fingerprint", "Evidence Type",
    "Discord Message ID", "Filename", "Uploaded At", "Parsed Player Names",
    "Status", "Notes",
]


def _credentials():
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_file(
        config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )


def _sheets():
    from googleapiclient.discovery import build

    return build("sheets", "v4", credentials=_credentials())


def _drive():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_credentials())


# ── Active season persistence ──────────────────────────────────────────────

def get_active_season(guild_id: int | str | None = None) -> dict | None:
    if guild_id is not None:
        return guild_config_service.get_active_season(guild_id)
    if not Path(ACTIVE_SEASON_FILE).exists():
        return None
    with open(ACTIVE_SEASON_FILE) as f:
        return json.load(f)


def get_active_sheet_id(guild_id: int | str | None = None) -> str | None:
    season = get_active_season(guild_id)
    return season["sheet_id"] if season else None


def _save_active_season(sheet_id: str, season_name: str, guild_id: int | str | None = None) -> None:
    if guild_id is not None:
        guild_config_service.save_active_season(guild_id, sheet_id, season_name)
        return
    with open(ACTIVE_SEASON_FILE, "w") as f:
        json.dump({"sheet_id": sheet_id, "season_name": season_name}, f)


# ── Season creation ────────────────────────────────────────────────────────

def create_season_sheet(
    season_name: str,
    drive_folder_id: str | None = None,
    guild_id: int | str | None = None,
) -> str:
    """Create a new season spreadsheet with all four tabs. Returns spreadsheet ID."""
    sheets = _sheets()
    now = _now()

    spreadsheet = sheets.spreadsheets().create(body={
        "properties": {"title": f"{config.LEAGUE_SLUG} — {season_name}"},
        "sheets": [
            {"properties": {"title": "Match Log",     "index": 0}},
            {"properties": {"title": "Player Stats",  "index": 1}},
            {"properties": {"title": "Unlinked",      "index": 2}},
            {"properties": {"title": "Season Config", "index": 3}},
            {"properties": {"title": "Evidence",      "index": 4}},
        ],
    }).execute()

    sheet_id = spreadsheet["spreadsheetId"]

    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "RAW", "data": [
            {"range": "Match Log!A1",     "values": [MATCH_LOG_HEADERS]},
            {"range": "Player Stats!A1",  "values": [PLAYER_STATS_HEADERS]},
            {"range": "Unlinked!A1",      "values": [UNLINKED_HEADERS]},
            {"range": "Evidence!A1",      "values": [EVIDENCE_HEADERS]},
            {"range": "Season Config!A1", "values": [
                ["Field", "Value"],
                ["Active Season Name",  season_name],
                ["Guild ID",            str(guild_id or "")],
                ["Confidence Threshold", str(config.CONFIDENCE_THRESHOLD)],
                ["Betting Enabled",      "false"],
                ["Sheet Created",       now],
                ["Last Updated",        now],
                ["Total Games Logged",  "0"],
                ["Bot Version",         "1.0.0"],
            ]},
        ]},
    ).execute()

    if drive_folder_id:
        drive = _drive()
        parents = drive.files().get(fileId=sheet_id, fields="parents").execute().get("parents", [])
        drive.files().update(
            fileId=sheet_id,
            addParents=drive_folder_id,
            removeParents=",".join(parents),
            fields="id,parents",
        ).execute()

    _save_active_season(sheet_id, season_name, guild_id)
    return sheet_id


def create_drive_folder(folder_name: str, parent_id: str | None = None) -> str:
    """Create a Drive folder (optionally nested inside parent_id) and return its ID."""
    body = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    return _drive().files().create(body=body, fields="id").execute()["id"]


# ── Internal helpers ───────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col_letter(zero_index: int) -> str:
    """Convert 0-based column index to A1 letter notation."""
    letters = ""
    n = zero_index
    while True:
        letters = chr(65 + n % 26) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return letters


def _append(sheet_id: str, tab: str, values: list[list]) -> None:
    _sheets().spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"{tab}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()


def _get_all_rows(sheet_id: str, tab: str) -> list[list]:
    result = _sheets().spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab}!A1:ZZ",
    ).execute()
    return result.get("values", [])


def _ensure_tab(sheet_id: str, tab: str, headers: list[str]) -> None:
    sheets = _sheets()
    meta = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    titles = {s["properties"]["title"] for s in meta["sheets"]}
    if tab not in titles:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
        ).execute()
        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


def _ensure_headers(sheet_id: str, tab: str, headers: list[str]) -> None:
    _ensure_tab(sheet_id, tab, headers)
    rows = _get_all_rows(sheet_id, tab)
    if not rows:
        _sheets().spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()
        return

    existing = list(rows[0])
    missing = [header for header in headers if header not in existing]
    if not missing:
        return

    start_col = len(existing)
    end_col = start_col + len(missing) - 1
    _sheets().spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab}!{_col_letter(start_col)}1:{_col_letter(end_col)}1",
        valueInputOption="RAW",
        body={"values": [missing]},
    ).execute()


def ensure_sheet_schema(sheet_id: str) -> None:
    _ensure_headers(sheet_id, "Match Log", MATCH_LOG_HEADERS)
    _ensure_headers(sheet_id, "Player Stats", PLAYER_STATS_HEADERS)
    _ensure_headers(sheet_id, "Unlinked", UNLINKED_HEADERS)
    _ensure_headers(sheet_id, "Evidence", EVIDENCE_HEADERS)


def _touch(sheet_id: str) -> None:
    _update_config_value(sheet_id, "Last Updated", _now())


def _increment_game_count(sheet_id: str) -> None:
    config_rows = _get_all_rows(sheet_id, "Season Config")
    current = 0
    for row in config_rows[1:]:
        if len(row) >= 2 and row[0] == "Total Games Logged":
            current = int(row[1] or "0")
            break
    _update_config_value(sheet_id, "Total Games Logged", str(current + 1))


def _update_config_value(sheet_id: str, field: str, value: str) -> None:
    rows = _get_all_rows(sheet_id, "Season Config")
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == field:
            _sheets().spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"Season Config!B{i}",
                valueInputOption="RAW",
                body={"values": [[value]]},
            ).execute()
            return

    _append(sheet_id, "Season Config", [[field, value]])


def _get_sheet_tab_id(sheet_id: str, tab_title: str) -> int:
    meta = _sheets().spreadsheets().get(spreadsheetId=sheet_id).execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == tab_title:
            return s["properties"]["sheetId"]
    raise ValueError(f"Tab '{tab_title}' not found in spreadsheet {sheet_id}")


def _row_values(headers: list[str], row: dict, field_map: dict[str, str]) -> list:
    return [row.get(field_map.get(header, header), "") for header in headers]


# ── Match Log ──────────────────────────────────────────────────────────────

MATCH_LOG_FIELD_MAP = {
    "Draft ID": "draft_id",
    "Game Number": "game_number",
    "Submitted At": "submitted_at",
    "Blue Captain": "blue_captain",
    "Red Captain": "red_captain",
    "Blue Picks": "blue_picks",
    "Red Picks": "red_picks",
    "Blue Bans": "blue_bans",
    "Red Bans": "red_bans",
    "Fearless Pool": "fearless_pool",
    "Game Status": "game_status",
    "Winner": "winner",
    "Series Score": "series_score",
    "Guild ID": "guild_id",
    "Match Status": "match_status",
    "Evidence Fingerprints": "evidence_fingerprints",
    "Review Notes": "review_notes",
}

PLAYER_STATS_FIELD_MAP = {
    "Draft ID": "draft_id",
    "Game Number": "game_number",
    "Date": "date",
    "Player Name": "player_name",
    "God": "god",
    "Role": "role",
    "Team": "team",
    "K": "k",
    "D": "d",
    "A": "a",
    "GPM": "gpm",
    "Player Damage": "player_damage",
    "Minion Damage": "minion_damage",
    "Jungle Damage": "jungle_damage",
    "Structure Damage": "structure_damage",
    "Damage Taken": "damage_taken",
    "Damage Mitigated": "damage_mitigated",
    "Self Healing": "self_healing",
    "Ally Healing": "ally_healing",
    "Wards Placed": "wards_placed",
    "Win": "win",
    "Guild ID": "guild_id",
    "Match Status": "match_status",
    "Evidence Fingerprint": "evidence_fingerprint",
    "Confidence": "confidence",
    "Review Notes": "review_notes",
}

UNLINKED_FIELD_MAP = {
    "Timestamp": "timestamp",
    "Discord Message ID": "message_id",
    "Parsed Player Names": "parsed_player_names",
    "Raw Stats JSON": "raw_stats_json",
    "Notes": "notes",
    "Guild ID": "guild_id",
    "Evidence Fingerprint": "evidence_fingerprint",
    "Fuzzy Match Candidate": "fuzzy_match_candidate",
}

EVIDENCE_FIELD_MAP = {
    "Guild ID": "guild_id",
    "Match ID": "match_id",
    "Evidence Fingerprint": "evidence_fingerprint",
    "Evidence Type": "evidence_type",
    "Discord Message ID": "message_id",
    "Filename": "filename",
    "Uploaded At": "uploaded_at",
    "Parsed Player Names": "parsed_player_names",
    "Status": "status",
    "Notes": "notes",
}


def append_match_log(sheet_id: str, row: dict) -> None:
    ensure_sheet_schema(sheet_id)
    row = {
        "winner": "TBD",
        "series_score": "TBD",
        "match_status": "created",
        **row,
    }
    _append(sheet_id, "Match Log", [_row_values(MATCH_LOG_HEADERS, row, MATCH_LOG_FIELD_MAP)])
    _touch(sheet_id)


def update_match_result(
    sheet_id: str,
    draft_id: str,
    winner: str,
    series_score: str,
    guild_id: int | str | None = None,
    match_status: str = "confirmed",
) -> bool:
    """Update result for guild-scoped Match Log rows with this draft_id."""
    ensure_sheet_schema(sheet_id)
    sheets = _sheets()
    rows = _get_all_rows(sheet_id, "Match Log")
    if not rows:
        return False

    headers = rows[0]
    try:
        uid_col    = headers.index("Draft ID")
        winner_col = headers.index("Winner")
        score_col  = headers.index("Series Score")
        guild_col  = headers.index("Guild ID") if "Guild ID" in headers else None
        status_col = headers.index("Match Status") if "Match Status" in headers else None
    except ValueError:
        return False

    updated = False
    for i, row in enumerate(rows[1:], start=2):  # sheet rows are 1-indexed; row 1 is header
        if len(row) <= uid_col or row[uid_col] != draft_id:
            continue
        if guild_id is not None and guild_col is not None and len(row) > guild_col and row[guild_col] not in {"", str(guild_id)}:
            continue

        updates = [
            {"range": f"Match Log!{_col_letter(winner_col)}{i}", "values": [[winner]]},
            {"range": f"Match Log!{_col_letter(score_col)}{i}", "values": [[series_score]]},
        ]
        if status_col is not None:
            updates.append({
                "range": f"Match Log!{_col_letter(status_col)}{i}",
                "values": [[match_status]],
            })
        sheets.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()
        updated = True

    if updated:
        update_player_stats_status(sheet_id, draft_id, guild_id, match_status)
        _touch(sheet_id)
    return updated


# ── Player Stats ───────────────────────────────────────────────────────────

def append_player_stats(sheet_id: str, rows: list[dict]) -> None:
    ensure_sheet_schema(sheet_id)
    values = [
        _row_values(
            PLAYER_STATS_HEADERS,
            {"match_status": "parsed", **r},
            PLAYER_STATS_FIELD_MAP,
        )
        for r in rows
    ]
    _append(sheet_id, "Player Stats", values)
    _touch(sheet_id)
    _increment_game_count(sheet_id)


# ── Unlinked ───────────────────────────────────────────────────────────────

def append_unlinked(sheet_id: str, row: dict) -> None:
    ensure_sheet_schema(sheet_id)
    _append(sheet_id, "Unlinked", [_row_values(UNLINKED_HEADERS, row, UNLINKED_FIELD_MAP)])


def get_unlinked_rows(sheet_id: str, guild_id: int | str | None = None) -> list[dict]:
    ensure_sheet_schema(sheet_id)
    rows = _get_all_rows(sheet_id, "Unlinked")
    if len(rows) < 2:
        return []
    headers = rows[0]
    results = [dict(zip(headers, row)) for row in rows[1:]]
    if guild_id is None:
        return results
    return [row for row in results if row.get("Guild ID", str(guild_id)) in {"", str(guild_id)}]


def remove_unlinked_by_message_id(
    sheet_id: str,
    message_id: str,
    guild_id: int | str | None = None,
) -> dict | None:
    """Find, remove, and return the Unlinked row for message_id. Returns None if not found."""
    ensure_sheet_schema(sheet_id)
    sheets = _sheets()
    rows = _get_all_rows(sheet_id, "Unlinked")
    if len(rows) < 2:
        return None

    headers = rows[0]
    try:
        mid_col = headers.index("Discord Message ID")
        guild_col = headers.index("Guild ID") if "Guild ID" in headers else None
    except ValueError:
        return None

    for i, row in enumerate(rows[1:], start=1):
        if len(row) <= mid_col or row[mid_col] != message_id:
            continue
        if guild_id is not None and guild_col is not None and len(row) > guild_col and row[guild_col] not in {"", str(guild_id)}:
            continue

        matched = dict(zip(headers, row))
        tab_id = _get_sheet_tab_id(sheet_id, "Unlinked")
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"deleteDimension": {"range": {
                "sheetId":    tab_id,
                "dimension":  "ROWS",
                "startIndex": i,        # 0-indexed; 0 = header, 1 = first data row
                "endIndex":   i + 1,
            }}}]},
        ).execute()
        return matched

    return None


# ── Status query ───────────────────────────────────────────────────────────

def append_evidence(sheet_id: str, row: dict) -> None:
    ensure_sheet_schema(sheet_id)
    _append(sheet_id, "Evidence", [_row_values(EVIDENCE_HEADERS, row, EVIDENCE_FIELD_MAP)])
    _touch(sheet_id)


def evidence_exists(
    sheet_id: str,
    guild_id: int | str,
    match_id: str,
    evidence_fingerprint: str,
) -> bool:
    ensure_sheet_schema(sheet_id)
    rows = _get_all_rows(sheet_id, "Evidence")
    if len(rows) < 2:
        return False
    headers = rows[0]
    try:
        guild_col = headers.index("Guild ID")
        match_col = headers.index("Match ID")
        fp_col = headers.index("Evidence Fingerprint")
    except ValueError:
        return False
    for row in rows[1:]:
        if (
            len(row) > max(guild_col, match_col, fp_col)
            and row[guild_col] == str(guild_id)
            and row[match_col] == match_id
            and row[fp_col] == evidence_fingerprint
        ):
            return True
    return False


def get_match_status(sheet_id: str, draft_id: str, guild_id: int | str | None = None) -> dict:
    ensure_sheet_schema(sheet_id)
    match_rows = _get_all_rows(sheet_id, "Match Log")
    stats_rows = _get_all_rows(sheet_id, "Player Stats")

    def filter_uid(rows, col_name):
        if not rows:
            return []
        headers = rows[0]
        if col_name not in headers:
            return []
        col = headers.index(col_name)
        guild_col = headers.index("Guild ID") if "Guild ID" in headers else None
        matches = []
        for row in rows[1:]:
            if len(row) <= col or row[col] != draft_id:
                continue
            if guild_id is not None and guild_col is not None and len(row) > guild_col and row[guild_col] not in {"", str(guild_id)}:
                continue
            matches.append(row)
        return matches

    matched_logs  = filter_uid(match_rows, "Draft ID")
    matched_stats = filter_uid(stats_rows, "Draft ID")

    result: dict = {
        "draft_id":         draft_id,
        "games":            [],
        "winner":           "TBD",
        "series_score":     "TBD",
        "match_status":     "created",
        "stats_rows_found": len(matched_stats),
    }

    if match_rows and matched_logs:
        headers = match_rows[0]

        def col(name):
            return headers.index(name) if name in headers else None

        game_col   = col("Game Number")
        status_col = col("Game Status")
        match_status_col = col("Match Status")
        winner_col = col("Winner")
        score_col  = col("Series Score")

        for row in matched_logs:
            result["games"].append({
                "game_number": row[game_col]   if game_col   is not None and len(row) > game_col   else "",
                "game_status": row[status_col] if status_col is not None and len(row) > status_col else "",
            })

        last = matched_logs[-1]
        if winner_col is not None and len(last) > winner_col:
            result["winner"] = last[winner_col]
        if score_col is not None and len(last) > score_col:
            result["series_score"] = last[score_col]
        if match_status_col is not None and len(last) > match_status_col and last[match_status_col]:
            result["match_status"] = last[match_status_col]

    return result


def match_exists(sheet_id: str, draft_id: str, guild_id: int | str) -> bool:
    return bool(get_match_status(sheet_id, draft_id, guild_id)["games"])


def update_match_status(
    sheet_id: str,
    draft_id: str,
    guild_id: int | str,
    match_status: str,
    review_notes: str = "",
) -> bool:
    if match_status not in MATCH_STATUSES:
        raise ValueError(f"Unknown match status: {match_status}")
    ensure_sheet_schema(sheet_id)
    sheets = _sheets()
    rows = _get_all_rows(sheet_id, "Match Log")
    if len(rows) < 2:
        return False
    headers = rows[0]
    try:
        uid_col = headers.index("Draft ID")
        guild_col = headers.index("Guild ID")
        status_col = headers.index("Match Status")
        notes_col = headers.index("Review Notes")
    except ValueError:
        return False

    updated = False
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= max(uid_col, guild_col) or row[uid_col] != draft_id or row[guild_col] != str(guild_id):
            continue
        data = [{"range": f"Match Log!{_col_letter(status_col)}{i}", "values": [[match_status]]}]
        if review_notes:
            data.append({"range": f"Match Log!{_col_letter(notes_col)}{i}", "values": [[review_notes]]})
        sheets.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()
        updated = True
    if updated:
        update_player_stats_status(sheet_id, draft_id, guild_id, match_status)
        _touch(sheet_id)
    return updated


def update_player_stats_status(
    sheet_id: str,
    draft_id: str,
    guild_id: int | str | None,
    match_status: str,
) -> bool:
    ensure_sheet_schema(sheet_id)
    rows = _get_all_rows(sheet_id, "Player Stats")
    if len(rows) < 2:
        return False
    headers = rows[0]
    try:
        uid_col = headers.index("Draft ID")
        status_col = headers.index("Match Status")
        guild_col = headers.index("Guild ID") if "Guild ID" in headers else None
    except ValueError:
        return False

    data = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= uid_col or row[uid_col] != draft_id:
            continue
        if guild_id is not None and guild_col is not None and len(row) > guild_col and row[guild_col] not in {"", str(guild_id)}:
            continue
        data.append({"range": f"Player Stats!{_col_letter(status_col)}{i}", "values": [[match_status]]})

    if not data:
        return False
    _sheets().spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()
    return True


def get_exportable_player_stats(sheet_id: str, guild_id: int | str) -> list[dict]:
    ensure_sheet_schema(sheet_id)
    rows = _get_all_rows(sheet_id, "Player Stats")
    if len(rows) < 2:
        return []
    headers = rows[0]
    guild_col = headers.index("Guild ID") if "Guild ID" in headers else None
    status_col = headers.index("Match Status") if "Match Status" in headers else None
    if status_col is None:
        return []
    exportable = []
    for row in rows[1:]:
        item = dict(zip(headers, row))
        if guild_col is not None and len(row) > guild_col and row[guild_col] not in {"", str(guild_id)}:
            continue
        if len(row) <= status_col or row[status_col] not in {"confirmed", "official"}:
            continue
        exportable.append(item)
    return exportable


# ── Season Config ──────────────────────────────────────────────────────────

def get_season_config(sheet_id: str) -> dict:
    rows = _get_all_rows(sheet_id, "Season Config")
    return {row[0]: row[1] for row in rows[1:] if len(row) >= 2}
