import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from functions import get_post_creator_id
import aiohttp

load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
TOKEN = os.getenv("BOT_TOKEN")

class epi(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    epi_data: None|discord.Message|str = None
    group = app_commands.Group(name="epi", description="Commands related to Extra Post Information system")

    @group.command(name="enable", description="Enables EPI mode with the given text/message id")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(info="The text to be displayed on a post creation or message id from #status to be forwarded")
    async def epi_enable(self, interaction: discord.Interaction, info: str):
        if self.epi_data is None: # Make sure epi mode is not already enabled
            if not info.isdigit():
                self.epi_data = info
                await interaction.response.send_message(content=f"Successfully enabled EPI mode with the following text `{info}`")
            elif info.isdigit():
                status_channel = discord.utils.get(interaction.guild.channels, name="status")
                try:
                    message = await status_channel.fetch_message(int(info))
                except discord.NotFound or discord.HTTPException as exc:
                    return await interaction.response.send_message(content=f"Unable to fetch message from {status_channel.mention} with ID of `{info}`.\n`{exc.status}`, `{exc.text}`, `{exc.response}`")
                self.epi_data = message
                await interaction.response.send_message(content=f"Successfully enabled EPI mode with {message.jump_url}")
        else:
            url_or_text = self.epi_data
            if isinstance(url_or_text, str):
                url_or_text = f'`{url_or_text}`'
            elif isinstance(url_or_text, discord.Message):
                url_or_text = url_or_text.jump_url
            await interaction.response.send_message(content=f"EPI Mode is already ebabled!\n{url_or_text}", ephemeral=True)
    
    @group.command(name="disable", description="Disable EPI mode")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID)
    async def epi_disable(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Click here to confirm",
                custom_id="epi-disable-confirm"
            )
            async def on_button_click(Interaction: discord.Interaction):
                await Interaction.response.defer(ephemeral=True)
                self.epi_data = None
                await Interaction.delete_original_response()
                await interaction.channel.send(content=f"EPI mode successfully disabled by {Interaction.user.mention}")
            button.callback = on_button_click
            view = discord.ui.View()
            view.add_item(button)
            await interaction.followup.send(view=view, content="Are you sure you want to disable EPI mode?\n-# Dismiss this message to cancel.", ephemeral=True)
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled...", ephemeral=True)

    @group.command(name="view", description="View the current EPI mode status")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def epi_view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            msg_or_txt = self.epi_data
            if isinstance(msg_or_txt, discord.Message):
                msg_or_txt = msg_or_txt.jump_url
            await interaction.followup.send(
                content=f"Current EPI mode info: `{msg_or_txt}`",
                ephemeral=True
            )
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled... Try again later.")

    @commands.Cog.listener('on_thread_create')
    async def send_epi_info(self, thread: discord.Thread):
        if thread.parent_id == SUPPORT_CHANNEL_ID and self.epi_data:
            owner_id = await get_post_creator_id(thread.id) or thread.owner_id
            msg_or_txt = self.epi_data
            if isinstance(msg_or_txt, str):
                await thread.send(content=f"Hey <@{owner_id}>, the following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {msg_or_txt}")                
            elif isinstance(msg_or_txt, discord.Message):
                await thread.send(content=f"Hey <@{owner_id}>, Sapphire is currently having some trouble. Take a look at the message below for more details:\n-# The devs are already on it - thanks for your patience!")
                json = {
                'message_reference': {
                    'type': 1, # type 1 = message forward
                    'message_id': msg_or_txt.id,
                    'channel_id': msg_or_txt.channel.id,
                    'guild_id': msg_or_txt.guild.id
                    }
                }
                headers = {
                    'Authorization': f'Bot {TOKEN}'
                }
                async with aiohttp.ClientSession() as cs:
                    async with cs.post(url=f"https://discord.com/api/v9/channels/{thread.id}/messages", json=json, headers=headers) as req:
                        if req.ok:
                            return
                        else:
                            alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
                            await alerts_thread.send(f"Forward request failed (status >= 400).\nStatus: {req.status}. JSON: {await req.json()}. {await req.text(encoding='UTF-8')}")
                
async def setup(client):
    await client.add_cog(epi(client))