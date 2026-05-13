import discord
from discord import app_commands

from commands._checks import require_guild, staff_only
from services import economy_service


def setup(tree: app_commands.CommandTree) -> None:
    if tree.get_command("ledger") is not None:
        return

    group = app_commands.Group(name="ledger", description="Post ForgeLens community point ledger summaries")

    @group.command(name="post", description="Post a community point ledger notice in this channel")
    @app_commands.describe(
        title="Short ledger notice title",
        body="Ledger notice body",
        line_id="Optional wager line to include",
    )
    @staff_only()
    async def post(interaction: discord.Interaction, title: str, body: str, line_id: str = ""):
        await interaction.response.defer(ephemeral=False)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        try:
            embed = _ledger_embed(guild_id, title, body, line_id)
        except economy_service.EconomyError as exc:
            await interaction.followup.send(f"Could not post ledger notice: {exc}", ephemeral=True)
            return
        message = await interaction.channel.send(embed=embed)
        economy_service.record_ledger_post(
            guild_id,
            interaction.channel_id,
            message.id,
            interaction.user.id,
            title,
            body,
            line_id,
        )
        await interaction.followup.send("Ledger notice posted.", ephemeral=True)

    tree.add_command(group)


def _ledger_embed(guild_id: int, title: str, body: str, line_id: str = "") -> discord.Embed:
    embed = discord.Embed(title=title, description=body, color=0x2ECC71)
    if line_id:
        line = economy_service.get_line(guild_id, line_id)
        if not line:
            raise economy_service.EconomyError(f"Line {line_id} not found.")
        embed.add_field(name="Line", value=f"`{line['line_id']}` - `{line['status']}`", inline=True)
        embed.add_field(name="Match", value=f"`{line['match_id']}`", inline=True)
        embed.add_field(name="Options", value=" / ".join(line["options"]), inline=False)
    embed.set_footer(text="Community fantasy points only. No real-money wagering or payment integration.")
    return embed
