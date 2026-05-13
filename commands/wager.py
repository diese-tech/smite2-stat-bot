import discord
from discord import app_commands

from commands._checks import economy_enabled, require_guild, staff_only
from services import economy_service


def setup(tree: app_commands.CommandTree) -> None:
    if tree.get_command("wager") is not None:
        return

    group = app_commands.Group(name="wager", description="Manage ForgeLens community point wager lines")

    @group.command(name="create", description="Create a community point wager line for a match")
    @app_commands.describe(
        match_id="ForgeLens/GodForge match ID",
        title="Short display title",
        option_a="First selectable option",
        option_b="Second selectable option",
        max_wager="Maximum points one user may place on this line",
        close_condition="When this should close, default is manual",
    )
    @economy_enabled()
    @staff_only()
    async def create(
        interaction: discord.Interaction,
        match_id: str,
        title: str,
        option_a: str,
        option_b: str,
        max_wager: app_commands.Range[int, 1, 1_000_000],
        close_condition: str = "manual close",
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        try:
            line = economy_service.create_line(
                guild_id,
                match_id,
                title,
                option_a,
                option_b,
                max_wager,
                close_condition,
                interaction.user.id,
            )
        except economy_service.EconomyError as exc:
            await interaction.followup.send(f"Could not create wager line: {exc}")
            return
        await interaction.followup.send(embed=_line_embed(line))

    @group.command(name="open", description="Open a wager line for community point entries")
    @economy_enabled()
    @staff_only()
    async def open_line(interaction: discord.Interaction, line_id: str):
        await _set_status(interaction, line_id, economy_service.open_line)

    @group.command(name="close", description="Close a wager line manually")
    @economy_enabled()
    @staff_only()
    async def close(interaction: discord.Interaction, line_id: str):
        await _set_status(interaction, line_id, economy_service.close_line)

    @group.command(name="lock", description="Lock a wager line before settlement")
    @economy_enabled()
    @staff_only()
    async def lock(interaction: discord.Interaction, line_id: str):
        await _set_status(interaction, line_id, economy_service.lock_line)

    @group.command(name="void", description="Void a wager line and refund placed entries")
    @economy_enabled()
    @staff_only()
    async def void(interaction: discord.Interaction, line_id: str, reason: str = "admin void"):
        await interaction.response.defer(ephemeral=False)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        try:
            result = economy_service.void_line(guild_id, line_id, interaction.user.id, reason)
        except economy_service.EconomyError as exc:
            await interaction.followup.send(f"Could not void wager line: {exc}")
            return
        await interaction.followup.send(
            f"Voided `{result['line']['line_id']}` and refunded {len(result['refunds'])} placed entries."
        )

    @group.command(name="settle", description="Settle an official match wager line")
    @app_commands.describe(winning_option="Winning option label, exactly as shown on the line")
    @economy_enabled()
    @staff_only()
    async def settle(interaction: discord.Interaction, line_id: str, winning_option: str):
        await interaction.response.defer(ephemeral=False)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        try:
            result = economy_service.settle_line(guild_id, line_id, winning_option, interaction.user.id)
        except economy_service.EconomyError as exc:
            await interaction.followup.send(f"Could not settle wager line: {exc}")
            return
        await interaction.followup.send(
            f"Settled `{result['line']['line_id']}` for **{result['line']['winning_option']}**. "
            f"{len(result['payouts'])} payout(s), total pool **{result['total_pool']}** points."
        )

    tree.add_command(group)


async def _set_status(interaction: discord.Interaction, line_id: str, fn):
    await interaction.response.defer(ephemeral=True)
    guild_id = await require_guild(interaction)
    if guild_id is None:
        return
    try:
        line = fn(guild_id, line_id, interaction.user.id)
    except economy_service.EconomyError as exc:
        await interaction.followup.send(f"Could not update wager line: {exc}")
        return
    await interaction.followup.send(embed=_line_embed(line))


def _line_embed(line: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"Wager Line {line['line_id']}",
        description=line.get("title") or line["match_id"],
        color=_status_color(line["status"]),
    )
    embed.add_field(name="Match", value=f"`{line['match_id']}`", inline=True)
    embed.add_field(name="Status", value=f"`{line['status']}`", inline=True)
    embed.add_field(name="Options", value=" / ".join(f"**{item}**" for item in line["options"]), inline=False)
    embed.add_field(name="Max Entry", value=f"{line['max_wager']} points", inline=True)
    embed.add_field(name="Payout", value=line["payout_model"], inline=True)
    embed.add_field(name="Close", value=line["close_condition"], inline=False)
    embed.set_footer(text="Community fantasy points only. No real-money wagering.")
    return embed


def _status_color(status: str) -> int:
    return {
        "created": 0x95A5A6,
        "open": 0x2ECC71,
        "closed": 0xF1C40F,
        "locked": 0xE67E22,
        "settled": 0x3498DB,
        "voided": 0xE74C3C,
        "archived": 0x7F8C8D,
    }.get(status, 0x95A5A6)
