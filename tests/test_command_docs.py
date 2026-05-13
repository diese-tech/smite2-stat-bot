from commands import help as help_command


def test_help_embed_fields_stay_under_discord_limits():
    groups = [
        help_command.USER_COMMANDS,
        help_command.SETUP_COMMANDS,
        help_command.MATCH_COMMANDS,
        help_command.ECONOMY_ADMIN_COMMANDS,
    ]

    assert all(len(help_command._format_commands(group)) <= 1024 for group in groups)


def test_help_lists_economy_controls_and_reconciliation_commands():
    all_commands = {
        name
        for group in (
            help_command.USER_COMMANDS,
            help_command.SETUP_COMMANDS,
            help_command.MATCH_COMMANDS,
            help_command.ECONOMY_ADMIN_COMMANDS,
        )
        for name, _description in group
    }

    assert "/forgelens economy-enable" in all_commands
    assert "/forgelens economy-disable" in all_commands
    assert "/match start" in all_commands
    assert "/match close" in all_commands
    assert "/ledger transactions" in all_commands
    assert "/ledger audit" in all_commands
    assert "/ledger export" in all_commands
    assert "/ledger health" in all_commands


def test_help_safety_text_mentions_official_match_and_storage_health():
    text = (
        " ".join(description for _name, description in help_command.ECONOMY_ADMIN_COMMANDS)
        + " "
        + " ".join(description for _name, description in help_command.MATCH_COMMANDS)
    )

    assert "official" in text
    assert "GodForge" in text
    assert "storage" in dict(help_command.ECONOMY_ADMIN_COMMANDS)["/ledger health"]


def test_readme_documents_railway_volume_and_enable_gate():
    with open("README.md", encoding="utf-8") as f:
        readme = f.read()

    assert "FORGELENS_ECONOMY_PATH=/app/data/forgelens_economy.json" in readme
    assert "/match start" in readme
    assert "GodForge is draft-only" in readme
    assert "/forgelens economy-enable" in readme
    assert "/ledger health" in readme


def test_setup_documents_railway_mount_path():
    with open("SETUP.md", encoding="utf-8") as f:
        setup = f.read()

    assert "Mount path: /app/data" in setup
    assert "FORGELENS_ECONOMY_PATH=/app/data/forgelens_economy.json" in setup
