import discord
from discord import app_commands

import config
from services import guild_config_service


async def require_guild(interaction: discord.Interaction) -> int | None:
    if interaction.guild_id is not None:
        return interaction.guild_id
    if not interaction.response.is_done():
        await interaction.response.send_message(
            "ForgeLens commands must be used inside a Discord server.", ephemeral=True
        )
    else:
        await interaction.followup.send(
            "ForgeLens commands must be used inside a Discord server.", ephemeral=True
        )
    return None


def staff_only():
    """App command check: interaction user must be a guild-scoped stat admin."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "ForgeLens commands must be used inside a Discord server.", ephemeral=True
            )
            return False

        guild_cfg = guild_config_service.get_guild_config(interaction.guild_id)
        admin_role_ids = set(guild_cfg.get("stat_admin_role_ids") or config.STAFF_ROLE_IDS)
        admin_user_ids = set(guild_cfg.get("stat_admin_user_ids") or config.STAT_ADMIN_USER_IDS)
        user_role_ids = {r.id for r in interaction.user.roles}
        if interaction.user.id in admin_user_ids or user_role_ids & admin_role_ids:
            return True
        await interaction.response.send_message(
            "You need a stat admin role to use this command.", ephemeral=True
        )
        return False

    return app_commands.check(predicate)
