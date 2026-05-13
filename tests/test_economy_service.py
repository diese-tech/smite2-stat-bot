import pytest

from services import economy_service, guild_config_service


def test_wallet_seed_and_adjust_are_guild_scoped_transactions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    guild_config_service.update_guild_config(111, {"starting_balance": 750})

    wallet = economy_service.ensure_wallet(111, 42, "Player")
    other = economy_service.ensure_wallet(222, 42, "Player")
    adjusted = economy_service.adjust_wallet(111, 42, "Player", 25, "bonus", created_by=99)

    assert wallet["balance"] == 750
    assert other["balance"] == 500
    assert adjusted["wallet"]["balance"] == 775

    txs = economy_service.transactions(111)
    assert [tx["kind"] for tx in txs] == ["wallet_adjust", "wallet_seed"]
    assert all(tx["guild_id"] == "111" for tx in txs)


def test_line_lifecycle_and_bet_validation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(
        111,
        "GF-0001",
        "Final",
        "Order",
        "Chaos",
        max_wager=100,
        close_condition="manual",
        created_by=99,
    )
    with pytest.raises(economy_service.EconomyError, match="already exists"):
        economy_service.create_line(111, "gf-0001", "Duplicate", "A", "B", 100, "manual", 99)
    same_match_other_guild = economy_service.create_line(222, "GF-0001", "Other", "A", "B", 100, "manual", 99)
    assert same_match_other_guild["match_id"] == "GF-0001"

    with pytest.raises(economy_service.EconomyError, match="not open"):
        economy_service.place_wager(111, line["line_id"], 42, "Player", "Order", 10)

    economy_service.open_line(111, line["line_id"], 99)
    placed = economy_service.place_wager(111, line["line_id"], 42, "Player", "Order", 50)

    assert placed["wallet"]["balance"] == 450
    with pytest.raises(economy_service.EconomyError, match="already have"):
        economy_service.place_wager(111, line["line_id"], 42, "Player", "Chaos", 10)

    economy_service.close_line(111, line["line_id"], 99)
    with pytest.raises(economy_service.EconomyError, match="not open"):
        economy_service.place_wager(111, line["line_id"], 43, "Other", "Chaos", 10)


def test_settlement_requires_official_match_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Order", 50)
    economy_service.place_wager(111, line["line_id"], 2, "B", "Chaos", 50)

    with pytest.raises(economy_service.EconomyError, match="closed or locked"):
        economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")

    economy_service.lock_line(111, line["line_id"], 99)

    with pytest.raises(economy_service.EconomyError, match="must be official"):
        economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "confirmed")

    result = economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")

    assert result["payouts"] == [{"wager_id": "WG-0001", "user_id": "1", "payout": 100}]
    assert economy_service.get_wallet(111, 1)["balance"] == 550
    assert economy_service.get_wallet(111, 2)["balance"] == 450

    with pytest.raises(economy_service.EconomyError, match="already settled"):
        economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")


def test_void_refunds_open_wagers_and_preserves_cross_guild(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    other = economy_service.create_line(222, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.open_line(222, other["line_id"], 99)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Order", 50)
    economy_service.place_wager(222, other["line_id"], 1, "A", "Order", 75)

    result = economy_service.void_line(111, line["line_id"], 99, "admin void")

    assert result["refunds"] == [{"wager_id": "WG-0001", "user_id": "1", "refund": 50}]
    assert economy_service.get_wallet(111, 1)["balance"] == 500
    assert economy_service.get_wallet(222, 1)["balance"] == 425


def test_transactions_audit_health_and_export_are_guild_scoped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    guild_config_service.update_guild_config(111, {"betting_enabled": True})
    guild_config_service.update_guild_config(222, {"betting_enabled": False})
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    other = economy_service.create_line(222, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.open_line(222, other["line_id"], 99)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Order", 50)
    economy_service.place_wager(111, line["line_id"], 2, "B", "Chaos", 25)
    economy_service.place_wager(222, other["line_id"], 1, "A", "Order", 75)

    user_txs = economy_service.transactions(111, user_id=1)
    events = economy_service.audit_events(111, target=line["line_id"])
    health = economy_service.health(111)
    export = economy_service.export_data(111)

    assert {tx["user_id"] for tx in user_txs} == {"1"}
    assert all(event["guild_id"] == "111" for event in events)
    assert health["economy_enabled"] is True
    assert health["wallet_count"] == 2
    assert health["placed_wager_count"] == 2
    assert health["storage_exists"] is True
    assert export["guild_id"] == "111"
    assert {wallet["user_id"] for wallet in export["wallets"]} == {"1", "2"}
    assert all(wager["guild_id"] == "111" for wager in export["wagers"])


def test_economy_path_can_use_configured_storage_file(tmp_path, monkeypatch):
    configured_path = tmp_path / "data" / "forgelens_economy.json"
    monkeypatch.setattr(economy_service.config, "FORGELENS_ECONOMY_PATH", str(configured_path))

    economy_service.ensure_wallet(111, 42, "Player")

    assert economy_service.economy_path() == configured_path
    assert configured_path.exists()


def test_repeated_wallet_check_does_not_duplicate_seed_transaction(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    first = economy_service.ensure_wallet(111, 42, "Player")
    second = economy_service.ensure_wallet(111, 42, "Renamed")

    assert first["balance"] == second["balance"] == 500
    assert second["display_name"] == "Renamed"
    assert [tx["kind"] for tx in economy_service.transactions(111)] == ["wallet_seed"]


def test_starting_balance_change_only_affects_new_wallets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    economy_service.ensure_wallet(111, 1, "A")
    guild_config_service.update_guild_config(111, {"starting_balance": 900})
    economy_service.ensure_wallet(111, 2, "B")

    assert economy_service.get_wallet(111, 1)["balance"] == 500
    assert economy_service.get_wallet(111, 2)["balance"] == 900


def test_admin_negative_adjustment_is_recorded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = economy_service.adjust_wallet(111, 1, "A", -150, "penalty", 99)

    assert result["wallet"]["balance"] == 350
    assert result["transaction"]["kind"] == "wallet_adjust"
    assert result["transaction"]["amount"] == -150
    assert result["transaction"]["reason"] == "penalty"


def test_create_line_rejects_unsupported_payout_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(economy_service.EconomyError, match="pool payout"):
        economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99, "odds")


def test_create_line_rejects_invalid_max_wager(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(economy_service.EconomyError, match="greater than zero"):
        economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 0, "manual", 99)


def test_create_line_rejects_blank_or_duplicate_options(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(economy_service.EconomyError, match="Both line options"):
        economy_service.create_line(111, "GF-0001", "Final", "Order", "", 100, "manual", 99)
    with pytest.raises(economy_service.EconomyError, match="must be different"):
        economy_service.create_line(111, "GF-0002", "Final", "Order", "order", 100, "manual", 99)


def test_place_wager_allows_exact_max_and_normalizes_option_case(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)

    result = economy_service.place_wager(111, line["line_id"], 1, "A", "order", 100)

    assert result["wager"]["amount"] == 100
    assert result["wager"]["option"] == "Order"
    assert result["wallet"]["balance"] == 400


def test_place_wager_rejects_invalid_option_over_max_and_insufficient_balance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    high_limit = economy_service.create_line(111, "GF-0002", "Final", "Order", "Chaos", 1_000, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.open_line(111, high_limit["line_id"], 99)

    with pytest.raises(economy_service.EconomyError, match="Option must be"):
        economy_service.place_wager(111, line["line_id"], 1, "A", "Blue", 50)
    with pytest.raises(economy_service.EconomyError, match="Maximum wager"):
        economy_service.place_wager(111, line["line_id"], 1, "A", "Order", 101)
    with pytest.raises(economy_service.EconomyError, match="Insufficient balance"):
        economy_service.place_wager(111, high_limit["line_id"], 1, "A", "Order", 501)


def test_void_refunds_closed_and_locked_lines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    closed = economy_service.create_line(111, "GF-0001", "Closed", "Order", "Chaos", 100, "manual", 99)
    locked = economy_service.create_line(111, "GF-0002", "Locked", "Order", "Chaos", 100, "manual", 99)

    economy_service.open_line(111, closed["line_id"], 99)
    economy_service.place_wager(111, closed["line_id"], 1, "A", "Order", 40)
    economy_service.close_line(111, closed["line_id"], 99)

    economy_service.open_line(111, locked["line_id"], 99)
    economy_service.place_wager(111, locked["line_id"], 2, "B", "Chaos", 70)
    economy_service.lock_line(111, locked["line_id"], 99)

    assert economy_service.void_line(111, closed["line_id"], 99, "rainout")["refunds"][0]["refund"] == 40
    assert economy_service.void_line(111, locked["line_id"], 99, "rainout")["refunds"][0]["refund"] == 70
    assert economy_service.get_wallet(111, 1)["balance"] == 500
    assert economy_service.get_wallet(111, 2)["balance"] == 500


def test_void_rejects_settled_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Order", 50)
    economy_service.lock_line(111, line["line_id"], 99)
    economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")

    with pytest.raises(economy_service.EconomyError, match="already settled"):
        economy_service.void_line(111, line["line_id"], 99, "too late")


def test_settle_line_with_no_wagers_is_empty_but_settled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.close_line(111, line["line_id"], 99)

    result = economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")

    assert result["line"]["status"] == "settled"
    assert result["payouts"] == []
    assert result["total_pool"] == 0


def test_settle_line_with_no_winning_wagers_pays_nobody(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Chaos", 75)
    economy_service.close_line(111, line["line_id"], 99)

    result = economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")

    assert result["payouts"] == []
    assert economy_service.get_wallet(111, 1)["balance"] == 425


def test_settle_line_splits_pool_proportionally_between_multiple_winners(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Order", 25)
    economy_service.place_wager(111, line["line_id"], 2, "B", "Order", 75)
    economy_service.place_wager(111, line["line_id"], 3, "C", "Chaos", 100)
    economy_service.lock_line(111, line["line_id"], 99)

    result = economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")

    assert result["payouts"] == [
        {"wager_id": "WG-0001", "user_id": "1", "payout": 50},
        {"wager_id": "WG-0002", "user_id": "2", "payout": 150},
    ]
    assert economy_service.get_wallet(111, 1)["balance"] == 525
    assert economy_service.get_wallet(111, 2)["balance"] == 575
    assert economy_service.get_wallet(111, 3)["balance"] == 400


def test_settle_line_rounds_proportional_pool_payouts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Order", 1)
    economy_service.place_wager(111, line["line_id"], 2, "B", "Order", 2)
    economy_service.place_wager(111, line["line_id"], 3, "C", "Chaos", 1)
    economy_service.close_line(111, line["line_id"], 99)

    result = economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")

    assert result["payouts"] == [
        {"wager_id": "WG-0001", "user_id": "1", "payout": 1},
        {"wager_id": "WG-0002", "user_id": "2", "payout": 3},
    ]


def test_settle_line_conserves_pool_when_rounding_equal_winners(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, line["line_id"], 99)
    economy_service.place_wager(111, line["line_id"], 1, "A", "Order", 1)
    economy_service.place_wager(111, line["line_id"], 2, "B", "Order", 1)
    economy_service.place_wager(111, line["line_id"], 3, "C", "Order", 1)
    economy_service.place_wager(111, line["line_id"], 4, "D", "Chaos", 2)
    economy_service.close_line(111, line["line_id"], 99)

    result = economy_service.settle_line(111, line["line_id"], "Order", 99, lambda _guild, _match: "official")

    assert sum(payout["payout"] for payout in result["payouts"]) == result["total_pool"] == 5
    assert [payout["payout"] for payout in result["payouts"]] == [2, 2, 1]


def test_pool_payouts_use_wager_id_as_deterministic_tiebreaker():
    wagers = [
        {"wager_id": "WG-0002", "amount": 1},
        {"wager_id": "WG-0001", "amount": 1},
    ]

    payouts = economy_service._pool_payouts(wagers, total_pool=3, winning_pool=2)

    assert payouts == {"WG-0002": 1, "WG-0001": 2}


def test_settle_line_rejects_missing_active_season_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(economy_service.sheets_service, "get_active_sheet_id", lambda guild_id: None)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.close_line(111, line["line_id"], 99)

    with pytest.raises(economy_service.EconomyError, match="missing_active_season"):
        economy_service.settle_line(111, line["line_id"], "Order", 99)


def test_archived_lines_are_hidden_from_default_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)

    economy_service.set_line_status(111, line["line_id"], "archived", 99)

    assert economy_service.list_lines(111) == []
    assert [item["line_id"] for item in economy_service.list_lines(111, include_archived=True)] == [line["line_id"]]


def test_line_status_rejects_mutation_after_void_except_archive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    line = economy_service.create_line(111, "GF-0001", "Final", "Order", "Chaos", 100, "manual", 99)
    economy_service.void_line(111, line["line_id"], 99, "bad line")

    with pytest.raises(economy_service.EconomyError, match="already voided"):
        economy_service.open_line(111, line["line_id"], 99)
    archived = economy_service.set_line_status(111, line["line_id"], "archived", 99)
    assert archived["status"] == "archived"


def test_transactions_limit_ordering(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    economy_service.adjust_wallet(111, 1, "A", 10, "one", 99)
    economy_service.adjust_wallet(111, 1, "A", 20, "two", 99)
    economy_service.adjust_wallet(111, 1, "A", 30, "three", 99)

    txs = economy_service.transactions(111, limit=2)

    assert [tx["reason"] for tx in txs] == ["three", "two"]


def test_audit_events_limit_ordering_and_target_filter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = economy_service.create_line(111, "GF-0001", "First", "Order", "Chaos", 100, "manual", 99)
    second = economy_service.create_line(111, "GF-0002", "Second", "Order", "Chaos", 100, "manual", 99)
    economy_service.open_line(111, first["line_id"], 99)

    latest = economy_service.audit_events(111, limit=1)
    filtered = economy_service.audit_events(111, target=first["line_id"], limit=10)

    assert latest[0]["action"] == "line.open"
    assert {event["target"] for event in filtered} == {first["line_id"]}
    assert all(event["target"] != second["line_id"] for event in filtered)


def test_health_before_store_exists_reports_zero_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    status = economy_service.health(111)

    assert status["storage_exists"] is False
    assert status["wallet_count"] == 0
    assert status["transaction_count"] == 0


def test_export_contains_ledger_post_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    economy_service.record_ledger_post(111, 10, 20, 99, "Title", "Body", "WL-0001")

    export = economy_service.export_data(111)

    assert export["ledger_posts"] == [{
        "guild_id": "111",
        "channel_id": "10",
        "message_id": "20",
        "created_by": "99",
        "title": "Title",
        "body": "Body",
        "line_id": "WL-0001",
        "created_at": export["ledger_posts"][0]["created_at"],
    }]
