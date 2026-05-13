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
    assert guild["betting_enabled"] is False

