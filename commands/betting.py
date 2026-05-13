import discord
from discord import app_commands

from commands._checks import economy_enabled, require_guild
from services import economy_service


def setup(tree: app_commands.CommandTree) -> None:
    if tree.get_command("bet") is None:
        tree.add_command(_bet_command)
    if tree.get_command("wagers") is None:
        tree.add_command(_wagers_command)
    if tree.get_command("leaderboard") is None:
        tree.add_command(_leaderboard_command)


@app_commands.command(name="bet", description="Place community points on an open ForgeLens wager line")
@app_commands.describe(option="Option label exactly as shown on the line", amount="Community points to place")
@economy_enabled()
async def _bet_command(interaction: discord.Interaction, line_id: str, option: str, amount: app_commands.Range[int, 1, 1_000_000]):
    await interaction.response.defer(ephemeral=True)
    guild_id = await require_guild(interaction)
    if guild_id is None:
        return
    try:
        result = economy_service.place_wager(
            guild_id,
            line_id,
            interaction.user.id,
            interaction.user.display_name,
            option,
            amount,
        )
    except economy_service.EconomyError as exc:
        await interaction.followup.send(f"Could not place entry: {exc}")
        return
    await interaction.followup.send(
        f"Placed **{amount}** community points on **{result['wager']['option']}** "
        f"for `{result['line']['line_id']}`. Balance: **{result['wallet']['balance']}**."
    )


@app_commands.command(name="wagers", description="Show open ForgeLens wager lines")
@economy_enabled()
async def _wagers_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = await require_guild(interaction)
    if guild_id is None:
        return
    lines = [line for line in economy_service.list_lines(guild_id) if line["status"] in {"created", "open", "closed", "locked"}]
    user_wagers = economy_service.list_wagers(guild_id, interaction.user.id)[:5]
    if not lines and not user_wagers:
        await interaction.followup.send("No active wager lines or recent entries.")
        return
    embed = discord.Embed(title="ForgeLens Wager Lines", color=0x3498DB)
    for line in lines[:10]:
        embed.add_field(
            name=f"{line['line_id']} - {line['status']}",
            value=(
                f"Match `{line['match_id']}`\n"
                f"{' / '.join(line['options'])}\n"
                f"Max: {line['max_wager']} points"
            ),
            inline=False,
        )
    if user_wagers:
        recent = [
            f"`{wager['line_id']}` {wager['option']} - {wager['amount']} points ({wager['status']})"
            for wager in user_wagers
        ]
        embed.add_field(name="Your Recent Entries", value="\n".join(recent), inline=False)
    embed.set_footer(text="Community fantasy points only. No real-money wagering.")
    await interaction.followup.send(embed=embed)


@app_commands.command(name="leaderboard", description="Show top community point balances")
@economy_enabled()
async def _leaderboard_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = await require_guild(interaction)
    if guild_id is None:
        return
    wallets = economy_service.list_wallets(guild_id)[:10]
    if not wallets:
        await interaction.followup.send("No wallets yet.")
        return
    lines = [
        f"{index}. **{wallet.get('display_name') or wallet['user_id']}** - {wallet['balance']} points"
        for index, wallet in enumerate(wallets, start=1)
    ]
    await interaction.followup.send("\n".join(lines))
