import discord
from discord.ext import commands
from discord import app_commands, ui
import os
from dotenv import load_dotenv
from functions import get_post_creator_id
import asyncio

load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
EPI_LOG_THREAD_ID = int(os.getenv("EPI_LOG_THREAD_ID"))

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
    sticky_message: discord.Message|None = None

    async def send_epi_log(self, content: str):
        epi_thread = self.client.get_channel(EPI_LOG_THREAD_ID)
        await epi_thread.send(content)

    @group.command(name="enable", description="Enables EPI mode with the given text/message id")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(info="The text to be displayed on a post creation or message id from #status to be forwarded", sticky="Should a sticky message be created in #general?")
    async def epi_enable(self, interaction: discord.Interaction, info: str, sticky: bool):
        await interaction.response.defer(ephemeral=True)
        if not self.epi_data: # Make sure epi mode is not already enabled
            if not info.isdigit():
                self.epi_data[info] = []
                await interaction.followup.send(content=f"Successfully enabled EPI mode with the following text `{info}`", ephemeral=True)
                await self.send_epi_log(content=f"EPI mode enabled by `{interaction.user.name}` (`{interaction.user.id}`)\n`{info}`")
                if sticky:
                    general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                    msg = await general.send(f"The following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {info}", view=get_notified())
                    self.sticky_message = msg
            elif info.isdigit():
                status_channel = discord.utils.get(interaction.guild.channels, name="status", type=discord.ChannelType.news)
                try:
                    message = await status_channel.fetch_message(int(info))
                except discord.NotFound or discord.HTTPException as exc:
                    return await interaction.followup.send(content=f"Unable to fetch message from {status_channel.mention} with ID of `{info}`.\n`{exc.status}`, `{exc.text}`", ephemeral=True)
                self.epi_data[message] = []
                await interaction.followup.send(content=f"Successfully enabled EPI mode with {message.jump_url}", ephemeral=True)
                await self.send_epi_log(content=f"EPI mode enabled by `{interaction.user.name}` (`{interaction.user.id}`)\n{message.jump_url}")
                if sticky:
                    general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                    msg = await general.send(f"Sapphire is currently experiencing some issues. The developers are aware.\nYou can view more information here {message.jump_url}", view=get_notified())
                    self.sticky_message = msg
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
                    await post.send(content=f"Hey, the issue is now fixed!\n-# Thank you for your patience.\n{mentions_separated}")
                    mentioned = True
                else:
                    mentioned = False
                    await post.send(content="Hey, this issue is now fixed!\n-# Thank you for your patience.")
                epi_users.clear()
                self.epi_data.clear() # remove the custom status/message
                if self.sticky_message:
                    await self.sticky_message.delete()
                    self.sticky_message = None
                await interaction.channel.send(content=f"EPI mode successfully disabled by {interaction.user.name}.\nMentioned users: {mentioned}")
                await self.send_epi_log(f"EPI mode disabled by `{interaction.user.name}` `({interaction.user.id})`")
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
            await asyncio.sleep(3) # make sure that epi messages will be sent last (after more info message)
            owner_id = await get_post_creator_id(thread.id) or thread.owner_id
            msg_or_txt = list(self.epi_data.keys())[0]
            if isinstance(msg_or_txt, str):
                message = await thread.send(content=f"Hey <@{owner_id}>, the following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {msg_or_txt}", view=get_notified())                
            elif isinstance(msg_or_txt, discord.Message):
                message = await thread.send(content=f"Hey <@{owner_id}>, Sapphire is currently having some trouble. Take a look at the message below for more details:\n-# The devs are already on it - thanks for your patience!", view=get_notified())
                await msg_or_txt.forward(thread)
            self.epi_data[msg_or_txt].append(message)

    """ @commands.Cog.listener('on_member_join')
    async def add_users_role(self, member: discord.Member):
        if self.epi_data: # only add jr if epi is enabled
            await asyncio.sleep(5) # wait for a few seconds as in some cases epi is enabled for things like dashboard issues while sapphire itself is fully operational
            refreshed_member = member.guild.get_member(member.id) # the original member parameter is like a snapshot from when the event was called, refresh the data in a new object/variable
            users_role = discord.utils.get(member.guild.roles, name="Users")
            if users_role not in refreshed_member.roles:
                refreshed_member.add_roles(refreshed_member, reason="Add join roles when EPI is enabled.") """

    @commands.Cog.listener('on_message')
    async def epi_sticky_message(self, message: discord.Message):
        if self.epi_data and not message.author.bot and message.channel.id == GENERAL_CHANNEL_ID and self.sticky_message:
            await self.sticky_message.delete()
            msg_or_text = list(self.epi_data.keys())[0]
            if isinstance(msg_or_text, str):
                msg = await message.channel.send(f"The following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {msg_or_text}", view=get_notified())
            elif isinstance(msg_or_text, discord.Message):
                msg = await message.channel.send(f"Sapphire is currently experiencing some issues. The developers are aware.\nYou can view more information here {msg_or_text.jump_url}", view=get_notified())
            self.sticky_message = msg

    channel_permissions: dict[discord.TextChannel | discord.ForumChannel, dict[discord.Role|discord.Member|discord.Object, discord.PermissionOverwrite]] = {}

    @app_commands.command(name="lock", description="Lock the given channel. Should only be used in emergencies.")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(channel="The channel to lock.", reason="The reason for locking the channels. This will be shown in the logs.")
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel|discord.ForumChannel, reason: str):
        await interaction.response.defer(ephemeral=True)
        if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.ForumChannel):
            if not channel in self.channel_permissions.keys():
                if channel.permissions_for(interaction.user).view_channel and channel.permissions_for(interaction.user).send_messages:
                    self.channel_permissions[channel] = channel.overwrites # save the permission overwritews from before locking the chnanel
                    permissions = discord.PermissionOverwrite()
                    permissions.send_messages = False
                    permissions.create_public_threads = False
                    permissions.create_private_threads = False
                    permissions.send_messages_in_threads = False
                    permissions.view_channel = channel.permissions_for(interaction.guild.default_role).view_channel
                    overwrites = {
                        interaction.guild.default_role: permissions
                    } 
                    await channel.edit(overwrites=overwrites, reason=f"{interaction.user.name} ({interaction.user.id}) used /lock. Reason: {reason}")
                    if isinstance(channel, discord.TextChannel):
                        embed = discord.Embed(
                        title="Channel locked.",
                        description=f"> {reason}",
                        colour=0xFFA800 # Default 'warning' colour in Sapphire's default messages which I find quite like
                        )
                        embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.avatar.url)
                        await channel.send(embed=embed)
                    await self.send_epi_log(f"/lock used by `{interaction.user.name}` (`{interaction.user.id}`) for {channel.mention}.\nReason: {reason}")
                    await interaction.followup.send(content=f"Successfully locked {channel.mention}", ephemeral=True)
                else:
                    await interaction.followup.send(content=f"You cannot lock {channel.mention} because you can't view it or can't send messages in it!", ephemeral=True)
            else:
                await interaction.followup.send(content=f"{channel.mention} is already locked! Use /unlock to unlock it.", ephemeral=True)
        else:
            await interaction.followup.send(content="You can only lock Text and Forum channel!", ephemeral=True)

    @app_commands.command(name="unlock", description="Unlock the given channel. Should only be used in emergencies.")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID)
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel|discord.ForumChannel, reason: str):
        await interaction.response.defer(ephemeral=True)
        if channel in self.channel_permissions.keys():
            await channel.edit(overwrites=self.channel_permissions[channel], reason=f"{interaction.user.name} ({interaction.user.id}) used /unlock. Reason: {reason}")
            embed = discord.Embed(
                title="Channel unlocked",
                description=f"> {reason}",
                colour=0x36CE36
            )
            embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.avatar.url)
            await channel.send(embed=embed)
            self.channel_permissions.pop(channel)
            await self.send_epi_log(f"/unlock used by `{interaction.user.name}` (`{interaction.user.id}` for {channel.mention}.\nReason: {reason})")
            await interaction.followup.send(content=f"Successfully unlocked {channel.mention}", ephemeral=True)
        else:
            await interaction.followup.send(content=f"The given channel wasn't locked by {self.client.user.mention} or it was unlocked already.")

    @app_commands.command(name="slowmode", description="Set a specified slowmode time for the given channel.")
    @app_commands.describe(channel="What channel?", time="The new slowmode time for the channel, in seconds. Max 21600. Put 0 to disable slowmode.", reason="What's the reason for this slowmode? This will be shown in logs")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def slowmode(self, interaction: discord.Interaction, channel: discord.TextChannel|discord.ForumChannel|discord.Thread, time: int, reason: str):
        await interaction.response.defer(ephemeral=True)
        if isinstance(channel, discord.ForumChannel) or isinstance(channel, discord.TextChannel) or isinstance(channel, discord.Thread):
            if channel.permissions_for(interaction.user).view_channel and channel.permissions_for(interaction.user).send_messages:
                if time <= 21600:
                    if 0 <= time:
                        await channel.edit(slowmode_delay=time, reason=f"{interaction.user.name} ({interaction.user.id}) used /slowmode. Reason: {reason}")
                        await self.send_epi_log(f"`{interaction.user.name}` (`{interaction.user.id}`) used /slowmode for {channel.mention} with a time of `{time}` seconds")
                        if time > 0:
                            await interaction.followup.send(content=f"Successfully set a slowmode of `{time}` seconds in {channel.mention}", ephemeral=True)
                        else:
                            await interaction.followup.send(content=f"Successfully disabled slowmode for {channel.mention}", ephemeral=True)
                    else:
                        await interaction.followup.send("Achievement unlocked: How did we get here?", ephemeral=True)
                else:
                    await interaction.followup.send(content=f"The highest slowmode possible is 21600 and you provided `{time}`.")
            else:
                await interaction.followup.send(content=f"You must be able to send messages and view {channel.mention} to be able to set a slowmode in it.")
        else:
            await interaction.followup.send(content="You can only set a slowmode for Forum channels, Text channels and Threads!", ephemeral=True)
        # does anyone even read these comments? Ping me with the funniest/weirdest emoji you have (from any server you're in) if you see this...
async def setup(client):
    await client.add_cog(epi(client=client))