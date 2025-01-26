import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import datetime

load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))

class epi(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    epi_data: dict[str, list[str|discord.Message|datetime.datetime]] = {} # mode: [epi message/info-text, time epi mode was enabled]

    group = app_commands.Group(name="epi", description="Commands related to Extra Post Information system")

    @group.command(name="enable", description="Enables EPI mode with the given text/message id")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(info="The text to be displayed on a post creation or message id from #status to be forwarded")
    async def epi_enable(self, interaction: discord.Interaction, info: str):
        if not self.epi_data[0]: # Make sure epi mode is not already enabled
            if info.isalpha:
                self.epi_data["Text"] = [info, datetime.datetime.now()]
                await interaction.response.send_message(content=f"Successfully enabled EPI mode with the following text `{info}`")
            elif info.isdigit:
                status_channel = discord.utils.get(interaction.guild.text_channels, name="status")
                try:
                    message = await status_channel.fetch_message(int(info))
                except discord.NotFound or discord.HTTPException as exc:
                    return await interaction.response.send_message(content=f"Unable to fetch message from {status_channel.mention} with ID of `{info}`.\n`{exc.status}`, `{exc.text}`, `{exc.response}`")
                self.epi_data["Message"] = [message, datetime.datetime.now()]
        else:
            await interaction.response.send_message(content=f"EPI Mode is already ebabled!\n`{self.epi_data[0][0].jump_url or self.epi_data[0][0]}`")
    
    @group.command(name="disable", description="Disable EPI mode")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID)
    async def epi_disable(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data[0]:
            button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Click here to confirm",
                custom_id="epi-disable-confirm"
            )
            async def on_button_click(Interaction: discord.Interaction):
                await Interaction.response.defer(ephemeral=True)
                self.epi_data.clear()
                await Interaction.delete_original_response()
                await interaction.delete_original_response()
                await interaction.channel.send(content=f"EPI mode successfully disabled by {Interaction.user.mention}")
            button.callback = on_button_click
            view = discord.ui.View()
            view.add_item(button)
            await interaction.followup.send(view=view, content="Are you sure you want to disable EPI mode?\n-#Dismiss this message to cancel, click confirm button to confirm.", ephemeral=True)
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled...", ephemeral=True)

    @group.command(name="view", description="View the current EPI mode status")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def epi_view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data[0]:
            epi_type = self.epi_data.keys[0]
            msg_or_txt = self.epi_data[0][0]
            started_at_timestamp = round(self.epi_data[0][1].timestamp())
            if isinstance(msg_or_txt, discord.Message):
                msg_or_txt = msg_or_txt.jump_url
            await interaction.followup.send(
                content=f"Current EPI mode info: Type: `{epi_type}`- {msg_or_txt}, started at: <t:{started_at_timestamp}:F> (<t:{started_at_timestamp}:R>)",
                ephemeral=True
            )
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled... Try again later.")

async def setup(client):
    await client.add_cog(epi(client))