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
            "betting_enabled": False,
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

    tree.add_command(group)


def _clean_prefix(value: str, default: str) -> str | None:
    prefix = (value or "").strip().upper() or str(default or "FRH").upper()
    if not re.fullmatch(r"[A-Z]{2,4}", prefix):
        return None
    return prefix


def _clean_text(value: str) -> str:
    return str(value or "").strip()


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


def _format_setup_summary(config: dict, guild: discord.Guild | None) -> str:
    return (
        "ForgeLens configured for this server.\n\n"
        f"Screenshot channel: {_mention_channel(guild, config.get('screenshot_channel_id'))}\n"
        f"Draft JSON channel: {_mention_channel(guild, config.get('json_channel_id'))}\n"
        f"Admin reports: {_mention_channel(guild, config.get('admin_report_channel_id'))}\n"
        f"Stat admin role: {_mention_roles(guild, config.get('stat_admin_role_ids'))}\n"
        f"Match ID prefix: `{config.get('league_prefix')}`\n"
        f"Confidence threshold: `{config.get('confidence_threshold')}`\n"
        f"Drive parent folder: {_drive_status(config)}\n"
        "Betting/ledger: `disabled`\n\n"
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
        f"Drive parent folder: {_drive_status(config)}\n"
        f"Active season: `{active_label}`\n"
        f"Betting/ledger: `{'enabled' if config.get('betting_enabled') else 'disabled'}`"
    )


def _drive_status(config: dict) -> str:
    return "configured" if config.get("parent_drive_folder_id") else "not configured"
