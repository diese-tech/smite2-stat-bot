from services import sheets_service


def test_match_status_filters_same_match_id_by_guild(monkeypatch):
    match_rows = [
        ["Draft ID", "Game Number", "Game Status", "Winner", "Series Score", "Guild ID", "Match Status"],
        ["GF-0001", "1", "Done", "Order", "1-0", "111", "confirmed"],
        ["GF-0001", "1", "Done", "Chaos", "1-0", "222", "review_required"],
    ]
    stats_rows = [
        ["Draft ID", "Player Name", "Guild ID", "Match Status"],
        ["GF-0001", "Alpha", "111", "confirmed"],
        ["GF-0001", "Bravo", "222", "review_required"],
    ]

    monkeypatch.setattr(sheets_service, "ensure_sheet_schema", lambda sheet_id: None)
    monkeypatch.setattr(
        sheets_service,
        "_get_all_rows",
        lambda sheet_id, tab: match_rows if tab == "Match Log" else stats_rows,
    )

    guild_111 = sheets_service.get_match_status("sheet", "GF-0001", 111)
    guild_222 = sheets_service.get_match_status("sheet", "GF-0001", 222)

    assert guild_111["winner"] == "Order"
    assert guild_111["match_status"] == "confirmed"
    assert guild_111["stats_rows_found"] == 1
    assert guild_222["winner"] == "Chaos"
    assert guild_222["match_status"] == "review_required"
    assert guild_222["stats_rows_found"] == 1


def test_evidence_duplicate_detection_is_guild_scoped(monkeypatch):
    evidence_rows = [
        ["Guild ID", "Match ID", "Evidence Fingerprint"],
        ["111", "GF-0001", "abc"],
        ["222", "GF-0001", "def"],
    ]

    monkeypatch.setattr(sheets_service, "ensure_sheet_schema", lambda sheet_id: None)
    monkeypatch.setattr(sheets_service, "_get_all_rows", lambda sheet_id, tab: evidence_rows)

    assert sheets_service.evidence_exists("sheet", 111, "GF-0001", "abc") is True
    assert sheets_service.evidence_exists("sheet", 222, "GF-0001", "abc") is False


def test_exportable_stats_are_guild_scoped_and_confirmed(monkeypatch):
    stats_rows = [
        ["Draft ID", "Player Name", "Guild ID", "Match Status"],
        ["GF-0001", "Alpha", "111", "confirmed"],
        ["GF-0002", "Bravo", "111", "parsed"],
        ["GF-0001", "Charlie", "222", "official"],
    ]

    monkeypatch.setattr(sheets_service, "ensure_sheet_schema", lambda sheet_id: None)
    monkeypatch.setattr(sheets_service, "_get_all_rows", lambda sheet_id, tab: stats_rows)

    rows = sheets_service.get_exportable_player_stats("sheet", 111)

    assert [row["Player Name"] for row in rows] == ["Alpha"]

