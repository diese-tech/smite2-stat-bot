from services import guild_config_service


def test_active_season_is_scoped_by_guild(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    guild_config_service.save_active_season(111, "sheet-a", "Season A")
    guild_config_service.save_active_season(222, "sheet-b", "Season B")

    assert guild_config_service.get_active_sheet_id(111) == "sheet-a"
    assert guild_config_service.get_active_sheet_id(222) == "sheet-b"


def test_new_guild_config_defaults_disable_betting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    guild = guild_config_service.get_guild_config(111)

    assert guild["guild_id"] == "111"
    assert guild["confidence_threshold"] == 90
    assert guild["starting_balance"] == 500
    assert guild["betting_enabled"] is False


def test_update_guild_config_persists_setup_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    guild_config_service.update_guild_config(111, {
        "screenshot_channel_id": 10,
        "json_channel_id": 20,
        "admin_report_channel_id": 30,
        "stat_admin_role_ids": [40],
        "league_prefix": "OWL",
        "parent_drive_folder_id": "drive-folder",
        "confidence_threshold": 95,
        "starting_balance": 750,
    })

    guild = guild_config_service.get_guild_config(111)

    assert guild["screenshot_channel_id"] == 10
    assert guild["json_channel_id"] == 20
    assert guild["admin_report_channel_id"] == 30
    assert guild["stat_admin_role_ids"] == [40]
    assert guild["league_prefix"] == "OWL"
    assert guild["parent_drive_folder_id"] == "drive-folder"
    assert guild["confidence_threshold"] == 95
    assert guild["starting_balance"] == 750


def test_new_guild_uses_betting_enabled_bootstrap_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(guild_config_service.config, "BETTING_ENABLED", True)

    guild = guild_config_service.get_guild_config(111)

    assert guild["betting_enabled"] is True


def test_update_guild_config_persists_economy_enable_disable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    enabled = guild_config_service.update_guild_config(111, {"betting_enabled": True})
    disabled = guild_config_service.update_guild_config(111, {"betting_enabled": False})

    assert enabled["betting_enabled"] is True
    assert disabled["betting_enabled"] is False
    assert guild_config_service.get_guild_config(111)["betting_enabled"] is False


def test_guild_config_updates_do_not_leak_between_guilds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    guild_config_service.update_guild_config(111, {"betting_enabled": True, "starting_balance": 900})
    guild_config_service.update_guild_config(222, {"betting_enabled": False, "starting_balance": 300})

    assert guild_config_service.get_guild_config(111)["betting_enabled"] is True
    assert guild_config_service.get_guild_config(111)["starting_balance"] == 900
    assert guild_config_service.get_guild_config(222)["betting_enabled"] is False
    assert guild_config_service.get_guild_config(222)["starting_balance"] == 300
