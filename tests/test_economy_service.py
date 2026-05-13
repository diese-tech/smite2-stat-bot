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
