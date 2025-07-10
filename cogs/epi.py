import discord
from discord.ext import commands
from discord import app_commands, ui
import os
from dotenv import load_dotenv
from functions import get_post_creator_id, save_channel_permissions, get_channel_permissions, delete_channel_permissions, get_locked_channels, generate_random_id
import asyncio
import aiohttp, json
import datetime
import re
from typing import Literal

load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
EPI_LOG_THREAD_ID = int(os.getenv("EPI_LOG_THREAD_ID"))
NTFY_TOPIC_NAME = os.getenv("NTFY_TOPIC_NAME")
NTFY_SECOND_TOPIC = os.getenv("NTFY_SECOND_TOPIC")

epi_users: list[int] = []

class get_notified(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Notify me when this issue is resolved", custom_id="epi-get-notified", style=discord.ButtonStyle.grey)
    async def on_get_notified_click(self, interaction: discord.Interaction, button: ui.button):
        if interaction.user.id not in epi_users:
            epi_users.append(interaction.user.id)
            await interaction.response.send_message(content="You will now be notified when this issue is fixed!", ephemeral=True)
        else:
            epi_users.remove(interaction.user.id)
            await interaction.response.send_message(content="You will no longer be notified for this issue!", ephemeral=True)

class select_channels(ui.ChannelSelect):
    def __init__(self, action: str, reason: str,i: discord.Interaction ,slowmode: int = None):
        super().__init__(
            channel_types=[discord.ChannelType.text, discord.ChannelType.forum],
            placeholder=f"Select channels to",
            min_values=1,
            max_values=5
        )
        self.action = action
        self.reason = reason
        self.slowmode = slowmode
        self.i = i

    async def lock_channels(self, channels: list[discord.TextChannel|discord.ForumChannel], interaction: discord.Interaction):
        for channel in channels:
            previous_permissions = channel.overwrites_for(channel.guild.default_role).pair()
            await save_channel_permissions(channel.id, allow=previous_permissions[0].value, deny=previous_permissions[1].value)
            permissions = discord.PermissionOverwrite(send_messages=False, create_public_threads=False, create_private_threads=False, send_messages_in_threads=False)
            experts_mods_overwrites = discord.PermissionOverwrite(send_messages=True, create_public_threads=True, send_messages_in_threads=True)
            experts = channel.guild.get_role(EXPERTS_ROLE_ID)
            mods = channel.guild.get_role(MODERATORS_ROLE_ID)
            overwrites = {
                channel.guild.default_role: permissions,
                experts: experts_mods_overwrites,
                mods: experts_mods_overwrites
            } 
            await channel.edit(overwrites=overwrites, reason=f"{interaction.user.name} ({interaction.user.id}) used /lock. Reason: {self.reason}")
            if isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    title="Channel locked.",
                    description=f"> {self.reason}",
                    colour=0xFFA800 # Default 'warning' colour in Sapphire's default messages which I find quite nice and fitting
                )
                embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.avatar.url)
                await channel.send(embed=embed)
            await interaction.followup.send(content=f"Successfully locked {channel.mention} with reason `{self.reason}`", ephemeral=True)

    async def unlock_channels(self, channels: list[discord.TextChannel|discord.ForumChannel], interaction: discord.Interaction):
        for channel in channels:
            allow_deny = await get_channel_permissions(channel.id)
            allow = discord.Permissions()._from_value(allow_deny[0])
            deny = discord.Permissions()._from_value(allow_deny[1])
            overwrites = discord.PermissionOverwrite().from_pair(allow=allow, deny=deny)
            await channel.edit(overwrites={channel.guild.default_role: overwrites}, reason=f"{interaction.user.name} ({interaction.user.id}) used /unlock. Reason: {self.reason}")
            if isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    title="Channel unlocked",
                    description=f"> {self.reason}",
                    colour=0x36CE36
                    )
                embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.avatar.url)
                await channel.send(embed=embed)
            await delete_channel_permissions(channel.id)
            await interaction.followup.send(f"Successfully unlocked {channel.mention} with reason `{self.reason}`", ephemeral=True)

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        channels = self.values # the selected channels
        fetched_channels: list[discord.TextChannel|discord.ForumChannel] = []
        for c in channels:
            try:
                channel = interaction.guild.get_channel(c.id) or await channel.fetch() # try to get the channel from the internal cache or fetch it if it isn't found
            except discord.HTTPException:
                await interaction.followup.send(f"Couldn't fetch {c.mention}", ephemeral=True)
                continue
            if channel.permissions_for(interaction.user).send_messages and channel.permissions_for(interaction.guild.default_role).view_channel:                    
                match self.action:
                    case "lock":
                        if channel.id not in await get_locked_channels():
                            fetched_channels.append(channel)
                        else:
                            await interaction.followup.send(f"You cannot lock {channel.mention} as its already locked!", ephemeral=True)
                    case "unlock":
                        if channel.id in await get_locked_channels():
                            fetched_channels.append(channel)
                        else:
                            await interaction.followup.send(f"You cannot unlock {channel.mention} as it isn't locked!", ephemeral=True)
                    case "slowmode":
                        await channel.edit(slowmode_delay=self.slowmode, reason=f"/slowmode used by {interaction.user.name} ({interaction.user.id}). Reason: {self.reason}")
                        if self.slowmode > 0:
                            await interaction.followup.send(f"Successfully set slowmode in {channel.mention} to {self.slowmode} seconds with reason: {self.reason}", ephemeral=True)
                        elif self.slowmode == 0:
                            await interaction.followup.send(f"Successfully disabled slowmode in {channel.mention}!", ephemeral=True)
            else:
                await interaction.followup.send(f"You can only {self.action} channels you can send messages in and `@everyone` can view!\n-# {channel.mention}", ephemeral=True)
        epi_thread = interaction.guild.get_thread(EPI_LOG_THREAD_ID)
        webhooks = await epi_thread.parent.webhooks()
        webhook = webhooks[0] or await epi_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        if epi_thread.archived:
            await epi_thread.edit(archived=False)
        if fetched_channels:
            match self.action:
                case "lock":
                    await self.lock_channels(fetched_channels, interaction)
                    await webhook.send(
                    content=f"{interaction.user.name} locked {','.join(c.mention for c in fetched_channels)}. Reason: {self.reason}",
                    username="EPI logging",
                    avatar_url=interaction.client.user.avatar.url,
                    thread=discord.Object(id=EPI_LOG_THREAD_ID),
                    wait=False
                    )
                case "unlock":
                    await self.unlock_channels(fetched_channels, interaction)
                    await webhook.send(
                    content=f"{interaction.user.name} unlocked {','.join(c.mention for c in fetched_channels)}. Reason: `{self.reason}`",
                    username="EPI logging",
                    avatar_url=interaction.client.user.avatar.url,
                    thread=epi_thread,
                    wait=False
                    )
                case "slowmode":
                    await webhook.send(
                        content=f"{interaction.user.name} {'set slowmode of' + self.slowmode if self.slowmode > 0 else 'disabled slowmode'} in {','.join(c.mention for c in fetched_channels)}",
                        username="EPI logging",
                        avatar_url=interaction.client.user.avatar.url,
                        thread=epi_thread,
                        wait=False
                    )
        await self.i.edit_original_response(view=None)

class epi(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    epi_data: dict[discord.Message|str, list[discord.Message]] = {} # the custom set message: list of mssages to be edited to remove the get notified button
    group = app_commands.Group(name="epi", description="Commands related to Emergency Post Information system")
    sticky_message: discord.Message|None = None
    recent_page: dict | None = None # {"user_id": 1234, "message": "low taper fade is still massive", "timestamp": 1234.56, "priority": 1, "service": "Sapphire - bot", "cb_affected": False, "id": "AbC123"}

    async def send_epi_log(self, content: str):
        epi_thread = self.client.get_channel(EPI_LOG_THREAD_ID)
        webhooks = await epi_thread.parent.webhooks()
        webhook = webhooks[0] or await epi_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        if epi_thread.archived:
            await epi_thread.edit(archived=False)
        await webhook.send(
            content=content,
            username=self.client.user.name,
            avatar_url=self.client.user.avatar.url,
            thread=discord.Object(id=EPI_LOG_THREAD_ID),
            wait=False,
            allowed_mentions=discord.AllowedMentions.none()
        )

    @group.command(name="enable", description="Enables EPI mode with the given text/message id")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(info="The text to be displayed on a post creation or message id from #status to be forwarded", sticky="Should a sticky message be created in #general?")
    async def epi_enable(self, interaction: discord.Interaction, info: str, sticky: bool):
        await interaction.response.defer(ephemeral=True)
        if not self.epi_data: # Make sure epi mode is not already enabled
            if not info.isdigit():
                self.epi_data[info] = []
                await interaction.followup.send(content=f"Successfully enabled EPI mode with the following text `{info}`", ephemeral=True)
                await self.send_epi_log(content=f"EPI mode enabled by {interaction.user.mention}\n`{info}`")
                if sticky:
                    general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                    msg = await general.send(f"## The following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {info}", view=get_notified())
                    self.sticky_message = msg
            elif info.isdigit():
                status_channel = discord.utils.get(interaction.guild.channels, name="status", type=discord.ChannelType.news)
                try:
                    message = await status_channel.fetch_message(int(info))
                except discord.NotFound or discord.HTTPException as exc:
                    return await interaction.followup.send(content=f"Unable to fetch message from {status_channel.mention} with ID of `{info}`.\n`{exc.status}`, `{exc.text}`", ephemeral=True)
                self.epi_data[message] = []
                await interaction.followup.send(content=f"Successfully enabled EPI mode with {message.jump_url}", ephemeral=True)
                await self.send_epi_log(content=f"EPI mode enabled by {interaction.user.mention}\n{message.jump_url}")
                if sticky:
                    general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                    msg = await general.send(f"## Sapphire is currently experiencing some issues. The developers are aware.\nYou can view more information here {message.jump_url}", view=get_notified())
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
    async def epi_disable(self, interaction: discord.Interaction, message: str = None):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Click here to confirm",
                custom_id="epi-disable-confirm"
            )
            async def on_button_click(i: discord.Interaction):
                await i.channel.typing()
                await i.response.defer(ephemeral=True)
                await i.delete_original_response()
                index = list(self.epi_data)[0]
                for msg in self.epi_data[index]:
                    if msg.channel:
                        content = "Hey, this issue is fixed now!\n-# Thank you for your patience."
                        if message:
                            content += f"\n> {message}"
                        if not msg.channel.archived:
                            await msg.edit(view=None)
                            await msg.reply(
                                content= content,
                                mention_author=False
                            )
                        else:
                            await msg.channel.edit(archived=False)
                            msg.edit(view=None)
                            await msg.reply(
                                content= content,
                                mention_author=False
                            )
                            await msg.channel.edit(archived=True)
                    else:
                        continue
                general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                main_message = await general.send(content="Hey, this issue is now fixed!\n-# Thank you for your patience.")
                if epi_users:
                    mentions: list[discord.Member|discord.User] = []
                    for user_id in epi_users:
                        if len(", ".join(mentions)) + len(f"<@{user_id}>") + 2 < 2000: # + 2 is for the space and comma (,) next to each mention
                            mentions.append(f"<@{user_id}>")
                        else:
                            await main_message.reply(content=", ".join(mentions), mention_author=False)
                            mentions = [] # reset both for another pinging message
                    if mentions:
                        await main_message.reply(content=", ".join(mentions), mention_author=False)
                    mentioned = True
                else:
                    mentioned = False
                epi_users.clear()
                self.epi_data.clear() # remove the custom status/message
                if self.sticky_message:
                    await self.sticky_message.delete()
                    self.sticky_message = None
                await interaction.channel.send(content=f"EPI mode successfully disabled by {interaction.user.name}.\nMentioned users: {mentioned}")
                await self.send_epi_log(f"EPI mode disabled by {interaction.user.mention}")
            button.callback = on_button_click
            view = discord.ui.View()
            view.add_item(button)
            await interaction.followup.send(view=view, content=f"Are you sure you want to disable EPI mode? This will ping `{len(epi_users)}` user(s) that clicked the 'Get notified when this issue is resolved' button.\n-# Dismiss this message to cancel.", ephemeral=True)
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled!", ephemeral=True)

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
            await interaction.followup.send(
                content=f"Current EPI mode info: {msg_or_txt}\nEPI-User count: {len(epi_users)}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled! Run the command again if EPI mode is activated.")

    @group.command(name="edit", description="Edit current EPI information")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(info="The new text to be displayed or message ID from #status to be forwarded. Leave empty to not edit.", sticky="Whether a sticky message should be created in #general. Leave empty to not edit.")
    async def edit(self, interaction: discord.Interaction, info: str = None, sticky: bool = None):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            if info:
                previous = list(self.epi_data.keys())[0]
                if not info.isdigit():
                    msg_or_text = info
                elif info.isdigit():
                    status_channel = discord.utils.get(interaction.guild.channels, name="status", type=discord.ChannelType.news)
                    try:
                        msg_or_text = await status_channel.fetch_message(int(info))
                    except discord.NotFound or discord.HTTPException as exc:
                        return await interaction.followup.send(content=f"Unable to fetch message from {status_channel.mention} with ID `{info}`.\n`{exc.status}`, `{exc.text}`", ephemeral=True)
                if isinstance(msg_or_text, str):
                    url_or_text = f"`{msg_or_text}`"
                elif isinstance(msg_or_text, discord.Message):
                    url_or_text = msg_or_text.jump_url
                messages = list(self.epi_data.values())[0]
                self.epi_data.pop(previous)
                self.epi_data.update({msg_or_text: messages})
                await interaction.followup.send(f"Successfully updated EPI info to {url_or_text}", ephemeral=True)
                await self.send_epi_log(f"EPI mode edited by {interaction.user.mention} - Changed info to {url_or_text}")
            if sticky != None:
                if sticky:
                    if not self.sticky_message:
                        general = self.client.get_channel(GENERAL_CHANNEL_ID)
                        msg_or_text = list(self.epi_data.keys())[0]
                        if isinstance(msg_or_text, str):
                            msg = await general.send(f"## The following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {msg_or_text}", view=get_notified())
                        elif isinstance(msg_or_text, discord.Message):
                            msg = await general.send(f"## Sapphire is currently experiencing some issues. The developers are aware.\nYou can view more information here {msg_or_text.jump_url}", view=get_notified())
                        self.sticky_message = msg
                        await interaction.followup.send("Successfully enabled sticky messages!", ephemeral=True)
                        await self.send_epi_log(f"EPI mode edited by {interaction.user.mention} - Enabled sticky messages.")
                    elif self.sticky_message:
                        await interaction.followup.send("Cannot enable sticky messages as its already enabled!", ephemeral=True)
                elif sticky == False:
                    if self.sticky_message:
                        await self.sticky_message.delete()
                        self.sticky_message = None
                        await interaction.followup.send("Successfully disabled sticky messages!", ephemeral=True)
                        await self.send_epi_log(f"EPI edited by {interaction.user.mention} - disabled sticky messages.")
                    elif not self.sticky_message:
                        await interaction.followup.send("Cannot disable sticky messages as its already disabled!", ephemeral=True)
            if info == None and sticky == None:
                await interaction.followup.send("You must provide at least one of `info` or `sticky` parameters and both were left empty.", ephemeral=True)
        else:
            await interaction.followup.send("EPI must be enabled for you to edit it! Use /epi enable to enable it.", ephemeral=True)

    @commands.Cog.listener('on_thread_create')
    async def send_epi_info(self, thread: discord.Thread):
        if thread.parent_id == SUPPORT_CHANNEL_ID and self.epi_data:
            await asyncio.sleep(3) # make sure that epi messages will be sent last (after more info message)
            owner_id = await get_post_creator_id(thread.id) or thread.owner_id
            msg_or_txt = list(self.epi_data.keys())[0]
            if isinstance(msg_or_txt, str):
                message = await thread.send(content=f"## Hey <@{owner_id}>, the following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {msg_or_txt}", view=get_notified())                
            elif isinstance(msg_or_txt, discord.Message):
                message = await thread.send(content=f"## Hey <@{owner_id}>, Sapphire is currently having some trouble. Take a look at the message below for more details:\n-# The devs are already on it - thanks for your patience!", view=get_notified())
                await msg_or_txt.forward(thread)
            self.epi_data[msg_or_txt].append(message)

    @commands.Cog.listener('on_message')
    async def epi_sticky_message(self, message: discord.Message):
        if self.epi_data and not message.author.bot and message.channel.id == GENERAL_CHANNEL_ID and self.sticky_message:
            await self.sticky_message.delete()
            msg_or_text = list(self.epi_data.keys())[0]
            if isinstance(msg_or_text, str):
                msg = await message.channel.send(f"## The following notice has been put up. Any issues you may be experiencing are most likely related to this:\n-# The devs are already notified - thanks for your patience!\n\n> {msg_or_text}", view=get_notified())
            elif isinstance(msg_or_text, discord.Message):
                msg = await message.channel.send(f"## Sapphire is currently experiencing some issues. The developers are aware.\nYou can view more information here {msg_or_text.jump_url}", view=get_notified())
            self.sticky_message = msg

    channel_permissions: dict[discord.TextChannel | discord.ForumChannel, dict[discord.Role|discord.Member|discord.Object, discord.PermissionOverwrite]] = {}

    @app_commands.command(name="lock", description="Lock the given channels. Should only be used in emergencies.")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(reason="The reason for locking the channels.")
    async def lock(self, interaction: discord.Interaction, reason: str):
        await interaction.response.defer(ephemeral=True)
        if len(reason) < 200:
            view = ui.View()
            view.add_item(select_channels("lock", reason, interaction))
            await interaction.followup.send(content="Select the channels to be locked below.\n-# Minimum of 1, maximum of 5.", view=view)
        else:
            await interaction.followup.send(content="The `reason` parameter must be less than 200 characters!", ephemeral=True)
                
    @app_commands.command(name="unlock", description="Unlock the given channels. Should only be used in emergencies.")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID)
    @app_commands.describe(reason="What is the reason for unlocking the channels?")
    async def unlock(self, interaction: discord.Interaction, reason: str):
        await interaction.response.defer(ephemeral=True)
        if len(reason) < 200:
            view = ui.View()
            view.add_item(select_channels("unlock", reason, interaction))
            await interaction.followup.send("Select the channels that should be unlocked below.\n-# Minimum of 1, maximum of 5.", view=view, ephemeral=True)
        else:
            await interaction.followup.send(content="The `reason` parameter must be less than 200 characters!", ephemeral=True)

    @app_commands.command(name="slowmode", description="Set a specified slowmode time for the given channels. Should only be used in emergencies")
    @app_commands.describe(time="The new slowmode time for the channel, in seconds. Max 21600. Put 0 to disable slowmode.", reason="What's the reason for this slowmode?")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def slowmode(self, interaction: discord.Interaction, time: int, reason: str):
        await interaction.response.defer(ephemeral=True)
        if len(reason) < 200:
            if time >= 0:
                if time <= 21600:
                    view = ui.View()
                    view.add_item(select_channels("slowmode", reason,interaction ,time))
                    await interaction.followup.send(content="Select the channels where the given slowmode should be applied below.\n-# Minimum of 1, maximum of 5.", view=view)
                else:
                    await interaction.followup.send(content=f"The highest slowmode possible is 21600 and you provided `{time}`.")
            else:
                await interaction.followup.send("Achievement unlocked: How did we get here?", ephemeral=True)
        else:
            await interaction.followup.send(content="The `reason` parameter must be less than 200 characters!", ephemeral=True)

    page_websockets: dict[str, asyncio.Task] = {} # id: task

    async def handle_websocket(self, message: discord.WebhookMessage|discord.Message, id: str):
        await self.send_epi_log(f"Attempting to connect to WS.\nID: `{id}`")
        async with aiohttp.ClientSession() as cs:
            async with cs.ws_connect(f"https://ntfy.sh/{NTFY_SECOND_TOPIC}/ws") as ws:
                await self.send_epi_log(f"WS connected.\nID: `{id}`")
                async for msg in ws:
                    types = {
                        1: "TEXT",
                        2: "BINARY",
                        3: "CLOSE",
                        4: "PING",
                        5: "PONG"
                    }
                    await self.send_epi_log(f"WS event received.\nType: `{types.get(msg.type, '?')}` | ID: `{id}`")
                    exception_types = [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR] 
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data["event"] == "message":
                            if data["message"] == id:
                                await self.send_epi_log(f"WS `message` event received. response: `{data['title']}` | ID: `{data['message']}`")
                                await ws.close(code=aiohttp.WSCloseCode.OK)
                                await self.send_epi_log(f"Attempted to close WS. Closed: `{ws.closed}` | ID: `{data['message']}`")
                                response = data["title"] # the button that Xge clicked in the notification
                                channel = self.client.get_channel(message.channel.id)
                                webhooks = await channel.webhooks()
                                webhook = webhooks[0] or await channel.create_webhook(name="Created by Sapphire helper")
                                xge = self.client.get_user(265236642476982273) or await self.client.fetch_user(265236642476982273) # xge's user id, use get to get from the cache and fetch if couldn't find in cache
                                await webhook.send(
                                    content=f"{response}\n-# Reply to {message.jump_url}",
                                    username=xge.global_name or xge.name, # global name or username if global name doesn't exist (is none)
                                    avatar_url=xge.avatar.url
                                )
                                del self.page_websockets[id]
                                return
                            else:
                                await self.send_epi_log(f"WS `message` received with another random ID (expected `{id}`, received `{data['message']}`). Ignoring.")
                    elif msg.type in exception_types:
                        await ws.close(code=aiohttp.WSCloseCode.INTERNAL_ERROR)
                        await self.send_epi_log(f"Received invalid WSMsgType - `{msg.type}`.\n`{msg}`.\nWS closed: {ws.closed}")

    async def send_page(self, 
                        title: str, 
                        message: str, 
                        priority: int, 
                        followup: discord.Message, 
                        cb_affected: bool = False,
                        user: discord.Member = None, 
                        ratelimit_url: str = None
                        ):
        severity_emojis = {
            1: "green_circle",  # information
            2: "yellow_circle",  # Medium
            3: "orange_circle",  # High
            4: "red_circle"   # Critical - night
        }
        tags = [severity_emojis.get(priority, "question")]
        if cb_affected:
            tags.append("moneybag")
        if not user:
            tags.append("robot")
        if user:
            title.join(f" | Sent by @{user.name}")
        async with aiohttp.ClientSession(trust_env=True) as cs:
            random_id = generate_random_id()
            self.recent_page["id"] = random_id
            data = {
                "topic": NTFY_TOPIC_NAME,
                "message": message,
                "title": title,
                "tags": tags,
                "click": followup.jump_url,
                "actions": [
                    {
                        "action": "http",
                        "label": "On it",
                        "url": f"https://ntfy.sh/{NTFY_SECOND_TOPIC}",
                        "headers": {"Title": "On it", "message": random_id},
                        "clear": True
                    },
                    {
                        "action": "http",
                        "label": "Soon (Next 30mins)",
                        "url": f"https://ntfy.sh/{NTFY_SECOND_TOPIC}",
                        "headers": {"Title": "Soon (Next 30 mins)", "message": random_id},
                        "clear": True
                    },
                    {
                        "action": "http",
                        "label": "Later (>1 hour)",
                        "url": f"https://ntfy.sh/{NTFY_SECOND_TOPIC}",
                        "headers": {"Title": "Later (> 1 hour)", "message": random_id},
                        "clear": True
                    }
                ] 
            }
            if priority == 4:
                data["priority"] = 5
            if user:
                data["icon"] = user.avatar.url
            try:
                async with cs.post("https://ntfy.sh/", data=json.dumps(data)) as req:
                    if req.status == 200:
                        if user:
                            service = title.removesuffix(f" | Sent by @{user.name}")
                            await self.send_epi_log(f"{user.mention} used /page. Service: {service} | Message: `{message}` | Priority: {priority} | Custom Branding Affected: {cb_affected}.\n-# ID: {random_id}")
                            await followup.edit(content=f"Notification sent successfully.\n-# Message: {message} | Priority: {priority} | Service: {service} | ID: {random_id}")
                        else:
                            await followup.edit(content=f"Automated page for [ratelimits]({ratelimit_url}) sent successfully.\n-# Priority: {priority} | ID: {random_id}")
                            await self.send_epi_log(f"Sent automated page for rate limits. Priority: {priority}.\n-# ID: {random_id}")    
                        task = asyncio.create_task(self.handle_websocket(followup, random_id))
                        self.page_websockets[random_id] = task
                    else:
                        response = await req.text()
                        await followup.edit(f"An error occured while trying to send the notification...\nStatus: {req.status}, Response: {response}")
            except Exception as e:
                await followup.edit(content=f"An error occured while trying to send the notification... {e}")
                raise e

    @app_commands.command(name="page", description="Alert the developer of any downtime or critical issues")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(
        service="The affected service(s) - Sapphire- bot/dashboard | appeal.gg | All",
        message="The message to send", 
        priority="The severity, 1 = lowest, 4 = critical (highest)", 
        cb_affected="Whether custom branding is affected or not (for Sapphire outages)"
    )
    async def page(self, interaction: discord.Interaction, service: Literal["Sapphire - bot", "Sapphire - dashboard", "appeal.gg", "All"], message: str, priority: int, cb_affected: bool):
        if 1 <= priority <= 4:
            fifteen_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=15)
            if self.recent_page and datetime.datetime.fromtimestamp(self.recent_page["timestamp"]) > fifteen_minutes_ago:
                await interaction.response.defer(ephemeral=True)
                button = ui.Button(style=discord.ButtonStyle.danger, label="Confirm", custom_id="page-confirm")
                async def callback(i: discord.Interaction):
                    if i.user.id == interaction.user.id:
                        followup = await i.channel.send("Sending...")
                        await interaction.delete_original_response()
                        self.recent_page = {
                        "user_id": interaction.user.id,
                        "message": message,
                        "timestamp": round(datetime.datetime.now().timestamp()),
                        "priority": priority,
                        "service": service,
                        "cb_affected": cb_affected
                        }
                        await self.send_page(f"{service} | Sent by @{interaction.user.name}", message, priority, followup, cb_affected, interaction.user)
                    else:
                        await i.followup.send(f"Only the user who executed the command ({interaction.user.mention}) can use this button.", ephemeral=True)
                button.callback = callback
                view = ui.View()
                view.add_item(button)
                await interaction.followup.send(f"A page was sent <t:{self.recent_page['timestamp']}:R> by <@{self.recent_page['user_id']}>. Service: `{self.recent_page['service']}` | Message: `{self.recent_page['message']}` | Priority: `{self.recent_page['priority']}` | CB affected: `{self.recent_page['cb_affected']}` | ID: `{self.recent_page['id']}`.\nAre you sure you would like to send this one?\n-# Click *confirm* button to confirm, dismiss message to cancel.", ephemeral=True, view=view)
            else:
                await interaction.response.defer()
                followup = await interaction.followup.send("Sending...", wait=True)
                self.recent_page = {
                "user_id": interaction.user.id,
                "message": message,
                "timestamp": round(datetime.datetime.now().timestamp()),
                "priority": priority,
                "service": service,
                "cb_affected": cb_affected
                }
                await self.send_page(f"{service} | Sent by @{interaction.user.name}", message, priority, followup, cb_affected, interaction.user)
        else:
            await interaction.response.send_message(content=f"Priority argument must be between 1 and 4.")
    
    @page.autocomplete("priority")
    async def page_autocomplete_priority(self, interaction: discord.Interaction, current: int):
        return [
            app_commands.Choice(name="4 | Night", value=4),
            app_commands.Choice(name="3 | Major issue", value=3),
            app_commands.Choice(name="2 | Minor issue", value=2),
            app_commands.Choice(name="1 | Information", value=1)
        ]

    @commands.Cog.listener("on_message")
    async def autopage_on_ratelimit(self, message: discord.Message):
        if message.channel.id in [1023568468206956554, 1146016865345343531] and message.author.bot: # #cluster-log and the id of the channel in testing server as I don't want to add another .env variable
            if 265236642476982273 in [user.id for user in message.mentions]: #! IMPORTANT: please make sure that this is Xge's user ID. For testing I had to switch it with my own as messages' mentions field only shows for users who are in the server
                experts_channel = self.client.get_channel(EPI_LOG_THREAD_ID).parent
                msg = await experts_channel.send(f"Sending automated page for {message.jump_url}")
                priority = 3
                if datetime.datetime.now().hour > 21 or datetime.datetime.now().hour < 7: # 20 and 7 instead of 21 and 8 because it starts from 0 (0-23 rather than 1-24)
                    priority = 4
                h_pattern = r"\[ H\d+ ]" # [ H<some number> ] e.g. [ H16 ] from the message 
                resets_pattern = r"<t:(\d+):R>"
                h = re.findall(pattern=h_pattern, string=message.content)
                h = h[0] if h else "Unknown"
                _resets_timestamp = re.findall(resets_pattern, string=message.content)
                resets_timestamp = _resets_timestamp[0] if _resets_timestamp else None
                if resets_timestamp:
                    time = datetime.datetime.fromtimestamp(int(resets_timestamp))
                    page_msg = f"Resets at: {time.hour}:{time.minute}:{time.second}"
                else:
                    page_msg = "Resets at: Unknown"
                self.recent_page = {
                "user_id": self.client.user.id,
                "message": page_msg,
                "timestamp": round(datetime.datetime.now().timestamp()),
                "priority": priority,
                "service": f"{h} Ratelimited",
                "cb_affected": False
                }
                await self.send_page(f"{h} Ratelimited", page_msg, priority, msg, False, ratelimit_url=message.jump_url)

    @app_commands.command(name="page-ws-close", description="Manually close a websocket created after a /page")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(id="The id of the websocket to close. If none is provided all currently open websockets will be closed.")
    async def page_websockets_close(self, interaction: discord.Interaction, id: str = None):
        await interaction.response.defer(ephemeral=True)
        if self.page_websockets:
            if id:
                if id in self.page_websockets.keys():
                    close = self.page_websockets[id].cancel()
                    if close:
                        await interaction.followup.send(f"Successfully closed websocket with id `{id}`.")
                        await self.send_epi_log(f"{interaction.user.mention} closed page websocket with id `{id}`")
                    else:
                        await interaction.followup.send("Websocket could not be closed... This could be due to it already being done (Xge responded) or someone else already cancelled it.")
                else:
                    await interaction.followup.send(f"Invalid key provided. Received `{id}`. Available keys: `{', '.join([key for key in self.page_websockets.keys()]) or 'None'}`")
            else:
                confirm = ui.Button(style=discord.ButtonStyle.danger, label="Confirm", custom_id="page_websocket_close_confirm")
                async def callback(i: discord.Interaction):
                    await i.response.defer(ephemeral=True)
                    keys = self.page_websockets.keys()
                    if keys:
                        closed: list[str] = []
                        not_closed: list[str] = []
                        for key in keys:
                            close = self.page_websockets[key].cancel()
                            closed.append(key) if close else not_closed.append(key)
                            continue
                        closed_str = ", ".join(closed) if closed else None
                        not_closed_str = ",".join(not_closed) if not_closed else None
                        await i.followup.send(
                            content=f"{'Successfully closed: ' + closed_str if closed_str else ''}.\n{'Not closed: ' + not_closed_str if not_closed_str else ''}",
                            ephemeral=True
                        )
                        await interaction.edit_original_response(view=None)
                        await self.send_epi_log(f"{i.user.mention} manually closed all currently open websockets ({len(keys)})")
                confirm.callback = callback
                view = ui.View()
                view.add_item(confirm)
                await interaction.followup.send("Are you sure you would like to close all currently open page web sockets?\n**This action can't be undone**", view=view)
        else:
            await interaction.followup.send(f"There aren't any websockets open right now...")

async def setup(client):
    await client.add_cog(epi(client=client))
