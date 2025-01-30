import discord
from discord.ext import commands
from discord import app_commands, ui
import os
from dotenv import load_dotenv
from functions import get_post_creator_id
import aiohttp
import asyncio

load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
TOKEN = os.getenv("BOT_TOKEN")

epi_users: list[discord.Member|discord.User] = []

class get_notified(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Notify me when this issue is resolved", custom_id="epi-get-notified", style=discord.ButtonStyle.grey)
    async def on_get_notified_click(self, interaction: discord.Interaction, button: ui.button):
        if interaction.user not in epi_users:
            epi_users.append(interaction.user)
            await interaction.response.send_message(content="You will now be notified when this issue is fixed!", ephemeral=True)
        else:
            epi_users.remove(interaction.user)
            await interaction.response.send_message(content="You will no longer be notified for this issue!", ephemeral=True)

class epi(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
    
    epi_data: dict[discord.Message|str, list[discord.Message]] = {} # the custom set message: list of mssages to be edited to remove the get notified button
    group = app_commands.Group(name="epi", description="Commands related to Extra Post Information system")

    @group.command(name="enable", description="Enables EPI mode with the given text/message id")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(info="The text to be displayed on a post creation or message id from #status to be forwarded")
    async def epi_enable(self, interaction: discord.Interaction, info: str):
        await interaction.response.defer(ephemeral=True)
        if not self.epi_data: # Make sure epi mode is not already enabled
            if not info.isdigit():
                self.epi_data[info] = []
                await interaction.followup.send(content=f"Successfully enabled EPI mode with the following text `{info}`", ephemeral=True)
            elif info.isdigit():
                status_channel = discord.utils.get(interaction.guild.channels, name="status")
                try:
                    message = await status_channel.fetch_message(int(info))
                except discord.NotFound or discord.HTTPException as exc:
                    return await interaction.followup.send(content=f"Unable to fetch message from {status_channel.mention} with ID of `{info}`.\n`{exc.status}`, `{exc.text}`", ephemeral=True)
                self.epi_data[message] = []
                await interaction.followup.send(content=f"Successfully enabled EPI mode with {message.jump_url}", ephemeral=True)
        else:
            url_or_text = list(self.epi_data)[0]
            if isinstance(url_or_text, str):
                url_or_text = f'`{url_or_text}`'
            elif isinstance(url_or_text, discord.Message):
                url_or_text = url_or_text.jump_url
            await interaction.followup.send(content=f"EPI Mode is already enabled!\n{url_or_text}", ephemeral=True)
    
    @group.command(name="disable", description="Disable EPI mode- mark the issue as solved & ping all users that asked to be pinged")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID)
    @app_commands.describe(post="In what post should Sapphire Helper ping all users that clicked get notified button?")
    async def epi_disable(self, interaction: discord.Interaction, post: discord.Thread):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Click here to confirm",
                custom_id="epi-disable-confirm"
            )
            async def on_button_click(i: discord.Interaction):
                await i.response.defer(ephemeral=True)
                await i.delete_original_response()
                index = list(self.epi_data)[0]
                for message in self.epi_data[index]:
                    await message.edit(view=None)
                    await message.reply(
                        content="Hey, this issue is fixed now!\n-# Thank you for your patience."
                    )
                if epi_users:
                    mentions = [user.mention for user in epi_users]
                    mentions_separated = ', '.join(mentions)
                    await post.send(content=f"Hey, the issue is now solved!\n-# Thank you for your patience.\n{mentions_separated}")
                    epi_users.clear()
                    mentioned = True
                else:
                    mentioned = False
                epi_users.clear()
                self.epi_data.clear() # remove the custom status/message
                await interaction.channel.send(content=f"EPI mode successfully disabled by {interaction.user.name}.\nMentioned users: {mentioned}")
            button.callback = on_button_click
            view = discord.ui.View()
            view.add_item(button)
            await interaction.followup.send(view=view, content=f"Are you sure you want to disable EPI mode? This will ping `{len(epi_users)}` user(s) that clicked the 'Get notified when this issue is resolved' button.\n-# Dismiss this message to cancel.", ephemeral=True)
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled...", ephemeral=True)

    @group.command(name="view", description="View the current EPI mode status")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def epi_view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            msg_or_txt = list(self.epi_data.keys())[0]
            if isinstance(msg_or_txt, str):
                msg_or_txt = f"`{msg_or_txt}`"
            elif isinstance(msg_or_txt, discord.Message):
                msg_or_txt = msg_or_txt.jump_url
            if epi_users: # there's at least one user that clicked the 'get notified' button
                mentions_separated = ', '.join([user.mention for user in epi_users])
            else:
                mentions_separated = "No users clicked the get notified button"
            await interaction.followup.send(
                content=f"Current EPI mode info: {msg_or_txt}\nUsers: {mentions_separated}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled... Try again later.")

    @commands.Cog.listener('on_thread_create')
    async def send_epi_info(self, thread: discord.Thread):
        if thread.parent_id == SUPPORT_CHANNEL_ID and self.epi_data:
            await asyncio.sleep(3) # wait 3 seconds to make sure that epi messages will be sent last (after more info message)
            owner_id = await get_post_creator_id(thread.id) or thread.owner_id
            msg_or_txt = list(self.epi_data.keys())[0]
            if isinstance(msg_or_txt, str):
                message = await thread.send(content=f"Hey <@{owner_id}>, the following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {msg_or_txt}", view=get_notified())                
            elif isinstance(msg_or_txt, discord.Message):
                message = await thread.send(content=f"Hey <@{owner_id}>, Sapphire is currently having some trouble. Take a look at the message below for more details:\n-# The devs are already on it - thanks for your patience!", view=get_notified())
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
                            pass
                        else:
                            alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
                            await alerts_thread.send(f"<@1105414178937774150> Forward request failed (status >= 400).\nStatus: `{req.status}` ```json\n{await req.json()}```")
            self.epi_data[msg_or_txt].append(message)

async def setup(client):
    await client.add_cog(epi(client=client))