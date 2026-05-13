import discord
from discord import app_commands

from commands._checks import require_guild


USER_COMMANDS = [
    ("/help", "Show this command guide."),
    ("/wallet check", "Check your community-points wallet, or another user's wallet."),
    ("/bet", "Place community points on an open wager line."),
    ("/wagers", "Show active wager lines and your recent entries."),
    ("/leaderboard", "Show top community-points wallet balances."),
]

SETUP_COMMANDS = [
    ("/forgelens setup", "Configure channels, staff role, league prefix, Drive folder, confidence, and starting balance."),
    ("/forgelens config", "Show current guild configuration."),
    ("/forgelens channels", "Update screenshot, Draft JSON, and admin-report channels."),
    ("/forgelens admin-add", "Add a stat admin role or user."),
    ("/forgelens admin-remove", "Remove a stat admin role or user."),
    ("/forgelens confidence", "Update OCR confidence threshold metadata."),
    ("/forgelens drive", "Update the parent Google Drive folder for future seasons."),
    ("/forgelens prefix", "Update the match ID prefix used by /newmatch."),
    ("/forgelens starting-balance", "Update the default points for newly created wallets."),
    ("/forgelens economy-enable", "Enable community-points commands for this server."),
    ("/forgelens economy-disable", "Disable community-points commands while preserving data."),
]

MATCH_COMMANDS = [
    ("/newseason", "Create a new guild-scoped season sheet and make it active."),
    ("/newmatch", "Create a guild-scoped match ID shell."),
    ("/status", "Show match status, game rows, stat rows, winner, and score."),
    ("/link", "Reply to an unlinked screenshot and attach it to a match ID."),
    ("/reparse", "Reply to a screenshot and rerun OCR."),
    ("/result", "Mark a reviewed match official with winner and score."),
]

ECONOMY_ADMIN_COMMANDS = [
    ("/wager create", "Create a two-option wager line for a match."),
    ("/wager open", "Open a wager line for entries."),
    ("/wager close", "Close a wager line so no new entries can be placed."),
    ("/wager lock", "Lock a closed line while it waits for official settlement."),
    ("/wager void", "Void a wager line and refund placed entries."),
    ("/wager settle", "Settle a closed or locked line after the match is official."),
    ("/wallet adjust", "Apply an admin wallet adjustment with an audit reason."),
    ("/ledger post", "Post and record a manual community-points ledger notice."),
    ("/ledger transactions", "Show recent wallet and wager transactions."),
    ("/ledger audit", "Show recent economy audit events."),
    ("/ledger export", "Export guild economy data as JSON."),
    ("/ledger health", "Show economy storage path and record counts."),
]


def setup(tree: app_commands.CommandTree) -> None:
    if tree.get_command("help") is not None:
        return

    @tree.command(name="help", description="Show ForgeLens commands and what they do")
    async def help_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return

        embed = discord.Embed(
            title="ForgeLens Commands",
            description=(
                "ForgeLens handles Smite 2 stats, match evidence, official results, "
                "and fictional community-points wagers."
            ),
            color=0x3498DB,
        )
        embed.add_field(name="User Commands", value=_format_commands(USER_COMMANDS), inline=False)
        embed.add_field(name="Setup Commands", value=_format_commands(SETUP_COMMANDS), inline=False)
        embed.add_field(name="Match And OCR Commands", value=_format_commands(MATCH_COMMANDS), inline=False)
        embed.add_field(name="Economy Admin Commands", value=_format_commands(ECONOMY_ADMIN_COMMANDS), inline=False)
        embed.add_field(
            name="Result And Wager Safety",
            value=(
                "`/result` makes a match official. Wager settlement requires an official match "
                "and a closed or locked line. Community points are fictional only; there is no "
                "payment integration or real-money wagering. Economy commands require `/forgelens economy-enable`; "
                "`/ledger health` remains available for storage checks."
            ),
            inline=False,
        )
        embed.set_footer(text="Use Discord's slash-command picker to see required options for each command.")
        await interaction.followup.send(embed=embed)


def _format_commands(commands: list[tuple[str, str]]) -> str:
    return "\n".join(f"`{name}` - {description}" for name, description in commands)
