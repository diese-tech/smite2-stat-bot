import discord
from discord import app_commands

from commands._checks import require_guild, staff_only


def setup(tree: app_commands.CommandTree) -> None:
    @tree.command(name="reparse", description="Re-send a screenshot message to Gemini for a fresh extraction")
    @staff_only()
    async def reparse(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return

        if not interaction.message or not interaction.message.reference:
            await interaction.followup.send(
                "Please **reply to the screenshot message** before running `/reparse`."
            )
            return

        ref = interaction.message.reference
        try:
            target = await interaction.channel.fetch_message(ref.message_id)
        except discord.NotFound:
            await interaction.followup.send("Could not find the replied-to message.")
            return

        from handlers.screenshot_handler import reparse_message
        success = await reparse_message(target)

        if success:
            await interaction.followup.send(f"✅ Reparsed message `{target.id}`.")
        else:
            await interaction.followup.send(
                f"No images found in message `{target.id}`, or no active season sheet."
            )
