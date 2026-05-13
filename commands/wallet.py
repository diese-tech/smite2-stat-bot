import discord
from discord import app_commands

from commands._checks import economy_enabled, require_guild, staff_only
from services import economy_service


def setup(tree: app_commands.CommandTree) -> None:
    if tree.get_command("wallet") is not None:
        return

    group = app_commands.Group(name="wallet", description="Manage ForgeLens community point wallets")

    @group.command(name="check", description="Check a community point wallet")
    @economy_enabled()
    async def check(interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        target = user or interaction.user
        wallet = economy_service.ensure_wallet(guild_id, target.id, target.display_name, interaction.user.id)
        await interaction.followup.send(
            f"**{target.display_name}** has **{wallet['balance']}** community points."
        )

    @group.command(name="adjust", description="Adjust a community point wallet")
    @app_commands.describe(amount="Positive or negative point adjustment", reason="Audit reason for the adjustment")
    @economy_enabled()
    @staff_only()
    async def adjust(interaction: discord.Interaction, user: discord.Member, amount: int, reason: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        result = economy_service.adjust_wallet(
            guild_id,
            user.id,
            user.display_name,
            amount,
            reason,
            interaction.user.id,
        )
        await interaction.followup.send(
            f"Adjusted **{user.display_name}** by **{amount}** points. "
            f"New balance: **{result['wallet']['balance']}**."
        )

    tree.add_command(group)
