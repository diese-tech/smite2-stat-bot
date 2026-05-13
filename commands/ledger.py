import io
import json

import discord
from discord import app_commands

from commands._checks import economy_enabled, require_guild, staff_only
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
    @economy_enabled()
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

    @group.command(name="transactions", description="Show recent community point transactions")
    @app_commands.describe(user="Optional user filter", limit="Number of transactions to show")
    @economy_enabled()
    @staff_only()
    async def transactions(
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        limit: app_commands.Range[int, 1, 25] = 10,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        txs = economy_service.transactions(guild_id, user.id if user else None, int(limit))
        if not txs:
            await interaction.followup.send("No ledger transactions found.")
            return
        lines = [_format_transaction(tx) for tx in txs]
        await interaction.followup.send("\n".join(lines))

    @group.command(name="audit", description="Show recent economy audit events")
    @app_commands.describe(target="Optional line, wager, wallet, or message ID target", limit="Number of events to show")
    @economy_enabled()
    @staff_only()
    async def audit(
        interaction: discord.Interaction,
        target: str = "",
        limit: app_commands.Range[int, 1, 25] = 10,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        events = economy_service.audit_events(guild_id, target, int(limit))
        if not events:
            await interaction.followup.send("No audit events found.")
            return
        lines = [_format_audit_event(event) for event in events]
        await interaction.followup.send("\n".join(lines))

    @group.command(name="export", description="Export guild economy data as JSON")
    @economy_enabled()
    @staff_only()
    async def export(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        payload = economy_service.export_data(guild_id)
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        file = discord.File(
            io.BytesIO(data),
            filename=f"forgelens-economy-{guild_id}.json",
        )
        await interaction.followup.send(
            "ForgeLens economy export generated. Treat this file as league operational data.",
            file=file,
        )

    @group.command(name="health", description="Show ForgeLens economy storage and record counts")
    @staff_only()
    async def health(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        status = economy_service.health(guild_id)
        embed = discord.Embed(title="ForgeLens Economy Health", color=0x3498DB)
        embed.add_field(name="Enabled", value=str(status["economy_enabled"]), inline=True)
        embed.add_field(name="Storage Exists", value=str(status["storage_exists"]), inline=True)
        embed.add_field(name="Storage Path", value=f"`{status['storage_path']}`", inline=False)
        embed.add_field(name="Wallets", value=str(status["wallet_count"]), inline=True)
        embed.add_field(name="Lines", value=str(status["line_count"]), inline=True)
        embed.add_field(name="Active Lines", value=str(status["active_line_count"]), inline=True)
        embed.add_field(name="Placed Wagers", value=str(status["placed_wager_count"]), inline=True)
        embed.add_field(name="Transactions", value=str(status["transaction_count"]), inline=True)
        embed.add_field(name="Audit Events", value=str(status["audit_count"]), inline=True)
        embed.add_field(name="Ledger Posts", value=str(status["ledger_post_count"]), inline=True)
        await interaction.followup.send(embed=embed)

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


def _format_transaction(tx: dict) -> str:
    amount = int(tx.get("amount", 0))
    sign = "+" if amount > 0 else ""
    return (
        f"`{tx['transaction_id']}` {tx['kind']} "
        f"{sign}{amount} -> {tx['balance_after']} "
        f"for **{tx.get('display_name') or tx['user_id']}** "
        f"({tx.get('reason', 'no reason')})"
    )


def _format_audit_event(event: dict) -> str:
    return (
        f"`{event['audit_id']}` {event['action']} "
        f"target `{event['target']}` by `{event['actor_id']}`"
    )
