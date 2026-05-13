from services import economy_service, match_service


def _godforge_payload(draft_id: str, game_number: int, explicit_match_id: str = "") -> dict:
    return {
        "producer": "GodForge",
        "draft_id": draft_id,
        "forgelens_match_id": explicit_match_id,
        "draft_status": "draft_complete",
        "games": [{
            "game_number": game_number,
            "draft_sequence": f"seq-{game_number}",
            "status": "draft_complete",
            "blue_picks": ["Athena"],
            "red_picks": ["Thor"],
            "blue_bans": ["Ares"],
            "red_bans": ["Anhur"],
            "selected_gods": ["Athena", "Thor"],
        }],
    }


def test_match_start_creates_active_channel_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    created = match_service.create_or_open_match(111, 222, 999, best_of=3, blue_team="Blue", red_team="Red")
    context = match_service.get_active_match_context(111, 222)

    assert created["match"]["best_of"] == 3
    assert created["match"]["status"] == "open"
    assert context["match_id"] == created["match"]["match_id"]
    assert context["status"] == "open"


def test_match_close_closes_context_without_touching_economy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    created = match_service.create_or_open_match(111, 222, 999)
    line = economy_service.create_line(111, created["match"]["match_id"], "Final", "Blue", "Red", 100, "manual", 999)
    economy_service.open_line(111, line["line_id"], 999)

    closed = match_service.close_active_match(111, 222, 999)

    assert closed["context"]["status"] == "closed"
    assert economy_service.get_line(111, line["line_id"])["status"] == "open"


def test_godforge_json_links_to_explicit_forgelens_match_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    first = match_service.create_or_open_match(111, 222, 999)
    second = match_service.create_or_open_match(111, 333, 999)
    payload = _godforge_payload("GF-1001", 1, explicit_match_id=first["match"]["match_id"])

    imported = match_service.import_godforge_draft(111, 333, 444, payload)

    assert imported["linked_match_id"] == first["match"]["match_id"]
    assert len(match_service.get_match(111, first["match"]["match_id"])["drafts"]) == 1
    assert len(match_service.get_match(111, second["match"]["match_id"])["drafts"]) == 0


def test_godforge_json_links_to_active_channel_match_without_explicit_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    created = match_service.create_or_open_match(111, 222, 999, best_of=3)
    imported = match_service.import_godforge_draft(111, 222, 444, _godforge_payload("GF-1002", 1))

    assert imported["linked_match_id"] == created["match"]["match_id"]
    assert match_service.get_match(111, created["match"]["match_id"])["drafts"][0]["draft_id"] == "GF-1002"


def test_duplicate_godforge_json_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    created = match_service.create_or_open_match(111, 222, 999)
    payload = _godforge_payload("GF-1003", 1)

    first = match_service.import_godforge_draft(111, 222, 444, payload)
    second = match_service.import_godforge_draft(111, 222, 555, payload)
    match = match_service.get_match(111, created["match"]["match_id"])

    assert first["linked_match_id"] == second["linked_match_id"] == created["match"]["match_id"]
    assert len(match["drafts"]) == 1
    assert match["drafts"][0]["message_id"] == "555"


def test_bo5_match_can_link_multiple_drafts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    created = match_service.create_or_open_match(111, 222, 999, best_of=5)
    match_service.import_godforge_draft(111, 222, 444, _godforge_payload("GF-2001", 1))
    match_service.import_godforge_draft(111, 222, 445, _godforge_payload("GF-2002", 2))
    match_service.import_godforge_draft(111, 222, 446, _godforge_payload("GF-2003", 3))
    match = match_service.get_match(111, created["match"]["match_id"])

    assert match["best_of"] == 5
    assert [draft["game_number"] for draft in match["drafts"]] == [1, 2, 3]


def test_settlement_uses_official_forgelens_result_without_godforge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    created = match_service.create_or_open_match(111, 222, 999)
    line = economy_service.create_line(111, created["match"]["match_id"], "Final", "Blue", "Red", 100, "manual", 999)
    economy_service.open_line(111, line["line_id"], 999)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Blue", 50)
    economy_service.close_line(111, line["line_id"], 999)

    try:
        economy_service.settle_line(111, line["line_id"], "Blue", 999)
        settled_early = False
    except economy_service.EconomyError:
        settled_early = True

    match_service.official_result(111, created["match"]["match_id"], "Blue", "2-0", 999)
    settled = economy_service.settle_line(111, line["line_id"], "Blue", 999)

    assert settled_early is True
    assert settled["line"]["status"] == "settled"
    assert economy_service.get_wallet(111, 1)["balance"] == 500


def test_export_contains_match_context_and_unlinked_drafts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    created = match_service.create_or_open_match(111, 222, 999)
    match_service.import_godforge_draft(111, 999, 444, _godforge_payload("GF-3001", 1))

    export = economy_service.export_data(111)

    assert export["matches"][0]["match_id"] == created["match"]["match_id"]
    assert export["active_match_contexts"][0]["channel_id"] == "222"
    assert export["unlinked_drafts"][0]["draft_id"] == "GF-3001"
