import asyncio

import discord
from discord import app_commands

from commands._checks import require_guild, staff_only
from services import match_service


def setup(tree: app_commands.CommandTree) -> None:
    if tree.get_command("match") is not None:
        return

    group = app_commands.Group(name="match", description="Manage ForgeLens match lifecycle and channel context")

    @group.command(name="start", description="Create or reopen the active ForgeLens match context for this channel")
    @app_commands.describe(
        best_of="Series length",
        blue_team="Blue or Order team label",
        red_team="Red or Chaos team label",
    )
    @app_commands.choices(best_of=[
        app_commands.Choice(name="Bo1", value=1),
        app_commands.Choice(name="Bo3", value=3),
        app_commands.Choice(name="Bo5", value=5),
    ])
    @staff_only()
    async def start(
        interaction: discord.Interaction,
        best_of: app_commands.Choice[int],
        blue_team: str = "",
        red_team: str = "",
    ):
        await interaction.response.defer(ephemeral=False)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        result = await asyncio.to_thread(
            match_service.create_or_open_match,
            guild_id,
            interaction.channel_id,
            interaction.user.id,
            best_of.value,
            blue_team,
            red_team,
        )
        match = result["match"]
        status_line = "Opened" if result["created"] else "Reused"
        await interaction.followup.send(
            f"{status_line} active match `{match['match_id']}` in this channel.\n"
            f"Series: Bo{match['best_of']} | Teams: {match['teams']['blue'] or 'Blue'} vs {match['teams']['red'] or 'Red'}"
        )

    @group.command(name="close", description="Close the active match window for this channel without settlement")
    @staff_only()
    async def close(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        closed = await asyncio.to_thread(
            match_service.close_active_match,
            guild_id,
            interaction.channel_id,
            interaction.user.id,
        )
        if not closed:
            await interaction.followup.send("No active match context is open in this channel.")
            return
        await interaction.followup.send(
            f"Closed active match `{closed['context']['match_id']}` for this channel. "
            "Wagers and settlement were not changed."
        )

    tree.add_command(group)
