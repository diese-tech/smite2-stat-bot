import re

import discord
from discord import app_commands

from commands._checks import require_guild, setup_allowed
from services import guild_config_service


GROUP_NAME = "forgelens"


def setup(tree: app_commands.CommandTree) -> None:
    if tree.get_command(GROUP_NAME) is not None:
        return

    group = app_commands.Group(
        name=GROUP_NAME,
        description="Configure ForgeLens for this Discord server",
    )

    @group.command(name="setup", description="Configure ForgeLens channels, admins, and league defaults")
    @app_commands.describe(
        screenshot_channel="Channel where players upload match screenshots",
        json_channel="Channel where GodForge posts Draft JSON files",
        admin_channel="Channel where ForgeLens posts warnings and review notices",
        stat_admin_role="Role allowed to run ForgeLens staff commands",
        league_prefix="2-4 letter prefix for /newmatch IDs, such as FRH or OWL",
        parent_drive_folder_id="Optional Google Drive folder ID for season folders",
        confidence_threshold="OCR confidence threshold for review metadata, 1-100",
        starting_balance="Starting community points for newly created wallets",
    )
    @setup_allowed()
    async def setup_command(
        interaction: discord.Interaction,
        screenshot_channel: discord.TextChannel,
        json_channel: discord.TextChannel,
        admin_channel: discord.TextChannel,
        stat_admin_role: discord.Role,
        league_prefix: str = "",
        parent_drive_folder_id: str = "",
        confidence_threshold: app_commands.Range[int, 1, 100] = 90,
        starting_balance: app_commands.Range[int, 0, 1_000_000] = 500,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return

        existing = guild_config_service.get_guild_config(guild_id)
        clean_prefix = _clean_prefix(league_prefix, existing.get("league_prefix") or "FRH")
        if clean_prefix is None:
            await interaction.followup.send("league_prefix must be 2-4 letters, such as FRH or OWL.")
            return

        guild = guild_config_service.update_guild_config(guild_id, {
            "screenshot_channel_id": screenshot_channel.id,
            "json_channel_id": json_channel.id,
            "admin_report_channel_id": admin_channel.id,
            "stat_admin_role_ids": [stat_admin_role.id],
            "confidence_threshold": int(confidence_threshold),
            "league_prefix": clean_prefix,
            "parent_drive_folder_id": _clean_text(parent_drive_folder_id),
            "starting_balance": int(starting_balance),
            "betting_enabled": bool(existing.get("betting_enabled")),
        })

        await interaction.followup.send(_format_setup_summary(guild, interaction.guild))

    @group.command(name="config", description="Show the current ForgeLens config for this server")
    @setup_allowed()
    async def config_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        guild = guild_config_service.get_guild_config(guild_id)
        await interaction.followup.send(_format_config_summary(guild, interaction.guild))

    @group.command(name="channels", description="Update ForgeLens channel configuration")
    @app_commands.describe(
        screenshot_channel="Channel where players upload match screenshots",
        json_channel="Channel where GodForge posts Draft JSON files",
        admin_channel="Channel where ForgeLens posts warnings and review notices",
    )
    @setup_allowed()
    async def channels_command(
        interaction: discord.Interaction,
        screenshot_channel: discord.TextChannel,
        json_channel: discord.TextChannel,
        admin_channel: discord.TextChannel,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        guild = guild_config_service.update_guild_config(guild_id, {
            "screenshot_channel_id": screenshot_channel.id,
            "json_channel_id": json_channel.id,
            "admin_report_channel_id": admin_channel.id,
        })
        await interaction.followup.send(
            "ForgeLens channels updated.\n\n"
            f"Screenshot channel: {_mention_channel(interaction.guild, guild.get('screenshot_channel_id'))}\n"
            f"Draft JSON channel: {_mention_channel(interaction.guild, guild.get('json_channel_id'))}\n"
            f"Admin reports: {_mention_channel(interaction.guild, guild.get('admin_report_channel_id'))}"
        )

    @group.command(name="admin-add", description="Add a stat admin role or user")
    @app_commands.describe(
        role="Role allowed to run ForgeLens staff commands",
        user="User allowed to run ForgeLens staff commands",
    )
    @setup_allowed()
    async def admin_add_command(
        interaction: discord.Interaction,
        role: discord.Role | None = None,
        user: discord.Member | None = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        if role is None and user is None:
            await interaction.followup.send("Choose a role, a user, or both.")
            return

        guild = guild_config_service.get_guild_config(guild_id)
        role_ids = _add_id(guild.get("stat_admin_role_ids"), role.id if role else None)
        user_ids = _add_id(guild.get("stat_admin_user_ids"), user.id if user else None)
        guild = guild_config_service.update_guild_config(guild_id, {
            "stat_admin_role_ids": role_ids,
            "stat_admin_user_ids": user_ids,
        })
        await interaction.followup.send(_format_admin_summary("Stat admin added.", guild, interaction.guild))

    @group.command(name="admin-remove", description="Remove a stat admin role or user")
    @app_commands.describe(
        role="Role to remove from ForgeLens staff command access",
        user="User to remove from ForgeLens staff command access",
    )
    @setup_allowed()
    async def admin_remove_command(
        interaction: discord.Interaction,
        role: discord.Role | None = None,
        user: discord.Member | None = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        if role is None and user is None:
            await interaction.followup.send("Choose a role, a user, or both.")
            return

        guild = guild_config_service.get_guild_config(guild_id)
        role_ids = _remove_id(guild.get("stat_admin_role_ids"), role.id if role else None)
        user_ids = _remove_id(guild.get("stat_admin_user_ids"), user.id if user else None)
        guild = guild_config_service.update_guild_config(guild_id, {
            "stat_admin_role_ids": role_ids,
            "stat_admin_user_ids": user_ids,
        })
        await interaction.followup.send(_format_admin_summary("Stat admin removed.", guild, interaction.guild))

    @group.command(name="confidence", description="Update the OCR confidence threshold metadata")
    @app_commands.describe(threshold="Review threshold, 1-100")
    @setup_allowed()
    async def confidence_command(
        interaction: discord.Interaction,
        threshold: app_commands.Range[int, 1, 100],
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        guild = guild_config_service.update_guild_config(guild_id, {
            "confidence_threshold": int(threshold),
        })
        await interaction.followup.send(
            f"ForgeLens confidence threshold set to `{guild.get('confidence_threshold')}`.\n\n"
            "Note: field-level confidence review is still roadmap work."
        )

    @group.command(name="drive", description="Update the parent Google Drive folder ID")
    @app_commands.describe(parent_drive_folder_id="Google Drive folder ID for season folders")
    @setup_allowed()
    async def drive_command(interaction: discord.Interaction, parent_drive_folder_id: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        folder_id = _clean_text(parent_drive_folder_id)
        if not folder_id:
            await interaction.followup.send("Provide a Google Drive folder ID.")
            return
        guild = guild_config_service.update_guild_config(guild_id, {
            "parent_drive_folder_id": folder_id,
        })
        await interaction.followup.send(
            f"ForgeLens Drive parent folder is now {_drive_status(guild)}.\n\n"
            "Next season folders will be created under this Drive folder."
        )

    @group.command(name="prefix", description="Update the /newmatch ID prefix")
    @app_commands.describe(league_prefix="2-4 letter prefix for /newmatch IDs, such as FRH or OWL")
    @setup_allowed()
    async def prefix_command(interaction: discord.Interaction, league_prefix: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        clean_prefix = _clean_prefix(league_prefix, "")
        if clean_prefix is None:
            await interaction.followup.send("league_prefix must be 2-4 letters, such as FRH or OWL.")
            return
        guild = guild_config_service.update_guild_config(guild_id, {
            "league_prefix": clean_prefix,
        })
        await interaction.followup.send(f"ForgeLens match ID prefix set to `{guild.get('league_prefix')}`.")

    @group.command(name="starting-balance", description="Update starting points for newly created wallets")
    @app_commands.describe(amount="Starting community points for new wallets")
    @setup_allowed()
    async def starting_balance_command(
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 0, 1_000_000],
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        guild = guild_config_service.update_guild_config(guild_id, {
            "starting_balance": int(amount),
        })
        await interaction.followup.send(
            f"New wallets will start with `{guild.get('starting_balance')}` community points."
        )

    @group.command(name="economy-enable", description="Enable ForgeLens community-points commands")
    @setup_allowed()
    async def economy_enable_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        guild = guild_config_service.update_guild_config(guild_id, {
            "betting_enabled": True,
        })
        await interaction.followup.send(
            "ForgeLens economy enabled for this server.\n\n"
            f"Starting balance for new wallets: `{guild.get('starting_balance')}` community points."
        )

    @group.command(name="economy-disable", description="Disable ForgeLens community-points commands")
    @setup_allowed()
    async def economy_disable_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        guild_config_service.update_guild_config(guild_id, {
            "betting_enabled": False,
        })
        await interaction.followup.send(
            "ForgeLens economy disabled for this server. Existing wallets, wagers, and ledger records are preserved."
        )

    tree.add_command(group)


def _clean_prefix(value: str, default: str) -> str | None:
    prefix = (value or "").strip().upper() or str(default or "FRH").upper()
    if not re.fullmatch(r"[A-Z]{2,4}", prefix):
        return None
    return prefix


def _clean_text(value: str) -> str:
    return str(value or "").strip()


def _add_id(existing: list[int] | None, value: int | None) -> list[int]:
    ids = {int(item) for item in (existing or [])}
    if value is not None:
        ids.add(int(value))
    return sorted(ids)


def _remove_id(existing: list[int] | None, value: int | None) -> list[int]:
    ids = {int(item) for item in (existing or [])}
    if value is not None:
        ids.discard(int(value))
    return sorted(ids)


def _mention_channel(guild: discord.Guild | None, channel_id: int | None) -> str:
    if not channel_id:
        return "not configured"
    channel = guild.get_channel(channel_id) if guild else None
    return channel.mention if channel else f"`{channel_id}`"


def _mention_roles(guild: discord.Guild | None, role_ids: list[int] | None) -> str:
    if not role_ids:
        return "not configured"
    mentions = []
    for role_id in role_ids:
        role = guild.get_role(int(role_id)) if guild else None
        mentions.append(role.mention if role else f"`{role_id}`")
    return ", ".join(mentions)


def _mention_users(guild: discord.Guild | None, user_ids: list[int] | None) -> str:
    if not user_ids:
        return "not configured"
    mentions = []
    for user_id in user_ids:
        member = guild.get_member(int(user_id)) if guild else None
        mentions.append(member.mention if member else f"`{user_id}`")
    return ", ".join(mentions)


def _format_setup_summary(config: dict, guild: discord.Guild | None) -> str:
    return (
        "ForgeLens configured for this server.\n\n"
        f"Screenshot channel: {_mention_channel(guild, config.get('screenshot_channel_id'))}\n"
        f"Draft JSON channel: {_mention_channel(guild, config.get('json_channel_id'))}\n"
        f"Admin reports: {_mention_channel(guild, config.get('admin_report_channel_id'))}\n"
        f"Stat admin role: {_mention_roles(guild, config.get('stat_admin_role_ids'))}\n"
        f"Match ID prefix: `{config.get('league_prefix')}`\n"
        f"Confidence threshold: `{config.get('confidence_threshold')}`\n"
        f"Starting balance: `{config.get('starting_balance')}`\n"
        f"Drive parent folder: {_drive_status(config)}\n"
        f"Community points: `{_economy_status(config)}`\n\n"
        "Next: run `/newseason name:Season 1`."
    )


def _format_config_summary(config: dict, guild: discord.Guild | None) -> str:
    active = config.get("active_season") or {}
    active_label = active.get("season_name") or "not configured"
    return (
        "ForgeLens config for this server:\n\n"
        f"Screenshot channel: {_mention_channel(guild, config.get('screenshot_channel_id'))}\n"
        f"Draft JSON channel: {_mention_channel(guild, config.get('json_channel_id'))}\n"
        f"Admin reports: {_mention_channel(guild, config.get('admin_report_channel_id'))}\n"
        f"Stat admin roles: {_mention_roles(guild, config.get('stat_admin_role_ids'))}\n"
        f"Match ID prefix: `{config.get('league_prefix')}`\n"
        f"Confidence threshold: `{config.get('confidence_threshold')}`\n"
        f"Starting balance: `{config.get('starting_balance')}`\n"
        f"Drive parent folder: {_drive_status(config)}\n"
        f"Active season: `{active_label}`\n"
        f"Community points: `{_economy_status(config)}`"
    )


def _format_admin_summary(prefix: str, config: dict, guild: discord.Guild | None) -> str:
    return (
        f"{prefix}\n\n"
        f"Stat admin roles: {_mention_roles(guild, config.get('stat_admin_role_ids'))}\n"
        f"Stat admin users: {_mention_users(guild, config.get('stat_admin_user_ids'))}"
    )


def _drive_status(config: dict) -> str:
    return "configured" if config.get("parent_drive_folder_id") else "not configured"


def _economy_status(config: dict) -> str:
    return "enabled - fictional points only" if config.get("betting_enabled") else "disabled"
