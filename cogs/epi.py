import discord
from discord.ext import commands
from discord import app_commands, ui
from dotenv import load_dotenv
from functions import save_channel_permissions, get_channel_permissions, delete_channel_permissions, get_locked_channels, generate_random_id, get_epi_users, save_epi_config, get_epi_config, get_epi_messages, add_epi_message, clear_epi_users, clear_epi_config, add_epi_user, delete_epi_user, clear_epi_messages, update_sticky_message_id, update_epi_message, update_epi_message_id, update_epi_sticky, update_epi_iso
import aiohttp, json, os, asyncio, re, datetime, asqlite as sql
from typing import Literal, Optional

load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
EPI_LOG_THREAD_ID = int(os.getenv("EPI_LOG_THREAD_ID"))
NTFY_TOPIC_NAME = os.getenv("NTFY_TOPIC_NAME")
NTFY_SECOND_TOPIC = os.getenv("NTFY_SECOND_TOPIC")
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

epi_users: list[int] = []

class get_notified(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Notify me when this issue is resolved", custom_id="epi-get-notified", style=discord.ButtonStyle.grey)
    async def on_get_notified_click(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id not in epi_users:
            await add_epi_user(interaction.user.id)
            epi_users.append(interaction.user.id)
            await interaction.response.send_message(content="You will now be notified when this issue is fixed!", ephemeral=True)
        else:
            await delete_epi_user(interaction.user.id)
            epi_users.remove(interaction.user.id)
            await interaction.response.send_message(content="You will no longer be notified for this issue!", ephemeral=True)

class select_channels(ui.ChannelSelect):
    def __init__(self, action: str, reason: str,i: discord.Interaction ,slowmode: int | None = None):
        super().__init__(
            channel_types=[discord.ChannelType.text, discord.ChannelType.forum],
            placeholder=f"Select channels to",
            min_values=1,
            max_values=5
        )
        self.action = action
        self.reason = reason
        self.slowmode = slowmode or 0
        self.i = i

    async def send_log(self, content: str):
        try:
            epi_thread = self.i.guild.get_thread(EPI_LOG_THREAD_ID) or await self.i.guild.fetch_channel(EPI_LOG_THREAD_ID)
        except discord.NotFound as e:
            raise e
        webhooks = [webhook for webhook in await epi_thread.parent.webhooks() if webhook.token]
        try:
            webhook = webhooks[0]
        except IndexError:
            webhook = await epi_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        if epi_thread.archived:
            await epi_thread.edit(archived=False)
        await webhook.send(
            content,
            username=self.i.client.user.name,
            avatar_url=self.i.client.user.display_avatar.url,
            allowed_mentions=discord.AllowedMentions.none(),
            thread=epi_thread,
            wait=False            
            )

    async def lock_channel(self, channel: discord.TextChannel|discord.ForumChannel, interaction: discord.Interaction):
        previous_permissions = channel.overwrites_for(channel.guild.default_role).pair() # permissions bit of (allow, deny)
        await save_channel_permissions(channel.id, allow=previous_permissions[0].value, deny=previous_permissions[1].value)
        permissions = discord.PermissionOverwrite(send_messages=False, create_public_threads=False, create_private_threads=False, send_messages_in_threads=False) # the channel permissions for @everyone role
        experts_mods_overwrites = discord.PermissionOverwrite(send_messages=True, create_public_threads=True, send_messages_in_threads=True)
        experts = channel.guild.get_role(EXPERTS_ROLE_ID)
        mods = channel.guild.get_role(MODERATORS_ROLE_ID)
        devs = channel.guild.get_role(DEVELOPERS_ROLE_ID)
        overwrites = {
            channel.guild.default_role: permissions, # @everyone role
            experts: experts_mods_overwrites,
            mods: experts_mods_overwrites,
            devs: experts_mods_overwrites
        }
        await channel.edit(overwrites=overwrites, reason=f"{interaction.user.name} ({interaction.user.id}) used /lock. Reason: {self.reason}")
        if isinstance(channel, discord.TextChannel):
            embed = discord.Embed(
                title="Channel locked.",
                description=f"> {self.reason}",
                colour=0xFFA800 # Default 'warning' colour in Sapphire's default messages which I find quite nice and fitting
            )
            embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            await channel.send(embed=embed)
        await interaction.followup.send(content=f"Successfully locked {channel.mention} with reason `{self.reason}`", ephemeral=True)

    async def unlock_channel(self, channel: discord.TextChannel|discord.ForumChannel, interaction: discord.Interaction):
        allow_deny = await get_channel_permissions(channel.id) # returns in the same way that TextChannel.overwrites_for(...).pair() does - (allow_bit, deny_bit)
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
            embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            await channel.send(embed=embed)
        await delete_channel_permissions(channel.id)
        await interaction.followup.send(f"Successfully unlocked {channel.mention} with reason `{self.reason}`", ephemeral=True)

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        channels = self.values # the selected channels
        fetched_channels: list[discord.TextChannel|discord.ForumChannel] = [interaction.guild.get_channel(c.id) or await c.fetch() for c in channels]
        successful: list[int] = [] # list of channel ids that were successfully locked/unlocked/set slowmode in
        for channel in fetched_channels:
            if channel.permissions_for(interaction.user).send_messages and channel.permissions_for(interaction.guild.default_role).view_channel:                    
                match self.action:
                    case "lock":
                        if channel.id not in await get_locked_channels():
                            await self.lock_channel(channel, interaction)
                            successful.append(channel.id)
                        else:
                            await interaction.followup.send(f"You cannot lock {channel.mention} as its already locked!", ephemeral=True)
                    case "unlock":
                        if channel.id in await get_locked_channels():
                            await self.unlock_channel(channel, interaction)
                            successful.append(channel.id)
                        else:
                            await interaction.followup.send(f"You cannot unlock {channel.mention} as it isn't locked!", ephemeral=True)
                    case "slowmode":
                        await channel.edit(slowmode_delay=self.slowmode, reason=f"/slowmode used by {interaction.user.name} ({interaction.user.id}). Reason: {self.reason}")
                        if self.slowmode > 0:
                            await interaction.followup.send(f"Successfully set slowmode in {channel.mention} to {self.slowmode} seconds with reason: {self.reason}", ephemeral=True)
                        elif self.slowmode == 0:
                            await interaction.followup.send(f"Successfully disabled slowmode in {channel.mention}!", ephemeral=True)
                        successful.append(channel.id)
            else:
                await interaction.followup.send(f"You can only {self.action} channels you can send messages in and `@everyone` can view!\n-# {channel.mention}", ephemeral=True)
        action_str = self.action + "ed" if self.slowmode is None else f"set slowmode to {self.slowmode}" if self.slowmode > 0 else "disabled slowmode"
        await self.send_log(f"{interaction.user.mention} {action_str} in {', '.join([f'<#{c}>' for c in successful])}. Reason: {self.reason}")
        await self.i.edit_original_response(view=None)

class epi(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    group = app_commands.Group(name="epi", description="Commands related to Emergency Post Information system")
    recent_page: Optional[dict] = None # {"user_id": 1234, "message": "low taper fade is still massive", "timestamp": 1234.56, "priority": 1, "service": "Sapphire - bot", "cb_affected": False, "id": "AbC123"} , used for "a page was made 3 minutes ago, are you sure you want to continue?" for pages up to 5 minutes old
    sticky_message: Optional[discord.Message] = None
    sticky_task: Optional[asyncio.Task] = None
    is_being_executed: bool = False
    epi_msg: Optional[str] = None
    epi_Message: Optional[discord.Message] = None
    epi_data: dict[str, dict[int, int]] = {} # {str(started_iso_format: {int(thread_id): int(message_id)})}  would be way more efficient than saving full message objects, especially in high amounts

    def generate_epi_embed(self) -> discord.Embed:
        embed_data = {
            "title": "Some services are currently experiencing issues",
            "description": "",
            "timestamp": list(self.epi_data.keys())[0],
            "color": 16749824,
            "footer": {
                "text": "We're sorry for the inconvenience caused and thank you for your patience!"
                }
            }
        if self.epi_msg:
            embed_data["description"] += self.epi_msg
        if self.epi_Message:
            embed_data["description"] += f"\n\n> ### An official status update has been posted: {self.epi_Message.jump_url}\n> {self.epi_Message.content if len(self.epi_Message.content) + len(self.epi_msg or '') + len(self.epi_Message.jump_url) < 1024 else self.epi_Message.content[:205:]+'*[...]*'}"
        if self.epi_Message or self.epi_msg:
            embed_data["description"] += "\n\n"
        embed_data["description"] += "-# You can also always check the [Sapphire status page](https://sapph.xyz/status)"
        return discord.Embed().from_dict(embed_data)

    async def send_epi_log(self, content: str):
        try:
            epi_thread = self.client.get_channel(EPI_LOG_THREAD_ID) or await self.client.fetch_channel(EPI_LOG_THREAD_ID)
        except discord.NotFound as e:
            raise e
        webhooks = [webhook for webhook in await epi_thread.parent.webhooks() if webhook.token]
        try:
            webhook = webhooks[0] 
        except IndexError:
            webhook = await epi_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        if epi_thread.archived:
            await epi_thread.edit(archived=False)
        await webhook.send(
            content=content,
            username=self.client.user.name,
            avatar_url=self.client.user.display_avatar.url,
            thread=discord.Object(id=EPI_LOG_THREAD_ID),
            wait=False,
            allowed_mentions=discord.AllowedMentions.none()
        )

    async def handle_sticky_message(self, channel: discord.TextChannel | discord.PartialMessageable, delay: float = 4):
        embed = self.generate_epi_embed()
        await asyncio.sleep(delay)
        self.is_being_executed = True
        if self.sticky_message:
            try:
                await self.sticky_message.delete()
            except discord.NotFound:
                pass
        self.sticky_message = await channel.send(embed=embed, view=get_notified())
        await update_sticky_message_id(self.pool, self.sticky_message.id)
        self.sticky_task = None
        self.is_being_executed = False

    async def disable_sticky_message(self):
        while self.is_being_executed:
            await asyncio.sleep(0.1) # self.is_being_executed is true at lines 196-197 - async handle_sticky_message, when the previous sticky message is deleted and the new one is being sent. 0.1 should probably be enough for these things to happen
        try:
            await self.sticky_message.delete()
        except discord.NotFound:
            pass # message was not found, probably already deleted - do nothing
        self.sticky_message = None
        self.sticky_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.client.add_view(get_notified())

    async def cog_unload(self):
        await self.pool.close()

    async def cog_load(self):
        self.pool = await sql.create_pool("database\data.db")
        epi_config = await get_epi_config(self.pool)
        if epi_config:
            raw_messages = await get_epi_messages(self.pool)
            messages = {}
            for thread_id, message_id in raw_messages.items():
                messages[thread_id] = message_id
            self.epi_data[epi_config["started_iso"]] = messages
            msg = epi_config["message"]
            self.epi_msg = msg if msg != "-" else None
            if epi_config["message_id"] and epi_config["message_id"] != 0:
                status = discord.utils.get(self.client.get_all_channels(), name="status", type=discord.ChannelType.news)
                if status:
                    try:
                        Message = await status.fetch_message(epi_config["message_id"])
                    except discord.NotFound as e:
                        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
                        await alerts_thread.send(f"Tried to fetch epi Message from {status.mention} with id {epi_config['message_id']}.\n{e.status} {e.text}")
                    else:
                        self.epi_Message = Message
            for user_id in await get_epi_users(self.pool):
                epi_users.append(user_id)
            if epi_config["sticky"]:
                general = self.client.get_partial_messageable(GENERAL_CHANNEL_ID)
                if epi_config["sticky_message_id"]:
                    self.sticky_message = general.get_partial_message(epi_config["sticky_message_id"])
                await self.handle_sticky_message(general, delay=0)

    @group.command(name="enable", description="Enables EPI mode with the given text/message id")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(message="[Optional] A custom text message to be displayed", message_id="[Optional] ID of a message from #status to be displayed", sticky="Should a sticky message be created in #general?")
    async def epi_enable(self, interaction: discord.Interaction, message: Optional[app_commands.Range[str, 1, 1000]], message_id: Optional[str], sticky: bool):
        await interaction.response.defer(ephemeral=True)
        if not self.epi_data: # Make sure epi mode is not already enabled
            command_response = "Successfully enabled EPI mode!"
            self.epi_data[datetime.datetime.now(tz=datetime.timezone.utc).isoformat()] = {}
            if message:
                self.epi_msg = message
                command_response += f"\nCustom message: {message}"
            _message = None
            if message_id:
                if message_id.isdigit():
                    status = discord.utils.get(interaction.guild.text_channels, name="status")
                    if status:
                        try:
                            _message = await status.fetch_message(int(message_id))
                        except discord.NotFound as e:
                            command_response += f"\nStatus message: Failed. Tried fetching `{message_id}` from {status.mention}. `{e.text}` `{e.status}`\n"
                            _message = None
                        else: # the message was fetched successfully
                            self.epi_Message = _message
                            command_response += f"\nStatus message: {_message.jump_url}\n"                    
                    else:
                        command_response += "\nStatus message: Failed - status channel not found.\n"
                else:
                    command_response += "\nStatus message: Failed - message_id argument must be made of digits only.\n"
            saved_message_id = message_id if _message else 0
            await save_epi_config(self.pool, sticky=sticky, message=message or "-", message_id=saved_message_id) # message arg defaults to '-' if its None (not provided) and message id to 0
            if sticky:
                general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                await self.handle_sticky_message(general)
            command_response += f"Sticky: {sticky}"
            await self.send_epi_log(f"EPI mode enabled by {interaction.user.mention}.\nCustom message: {message or 'not set'} | Status message: {_message.jump_url if _message else 'Not set'} | Sticky: {sticky}")
            await interaction.followup.send(command_response, ephemeral=True)
        else:
            await interaction.followup.send(content=f"EPI Mode is already enabled!", ephemeral=True)
    
    @group.command(name="disable", description="Disable EPI mode- mark the issue as solved & ping all users that asked to be pinged")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(message="[Optional] A custom message to be displayed with the \"Hey, this is fixed now!\" message")
    async def epi_disable(self, interaction: discord.Interaction, message: Optional[app_commands.Range[str, 1, 1000]]):
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
                content = "Hey, this issue is fixed now!\n-# Thank you for your patience."
                if message:
                    content += f"\n> {message}"
                for thread_id, message_id in list(self.epi_data.values())[0].items():
                    thread = self.client.get_channel(thread_id)
                    if thread:
                        msg = thread.get_partial_message(message_id)
                        if not thread.archived:
                            try:
                                await msg.edit(view=None)
                                await msg.reply(
                                    content= content,
                                    mention_author=False
                                )
                            except discord.NotFound:
                                pass # Message was most likely already deleted
                        else:
                            await thread.edit(archived=False)
                            try:
                                msg.edit(view=None)
                                await msg.reply(
                                    content= content,
                                    mention_author=False
                                )
                                await thread.edit(archived=True)
                            except discord.NotFound:
                                pass # message was most likely already deleted
                    else:
                        continue
                await clear_epi_messages(self.pool)
                general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                main_message = await general.send(content=content)
                if epi_users:
                    mentions: list[discord.Member|discord.User] = []
                    for user_id in epi_users:
                        if len(", ".join(mentions)) + len(f"<@{user_id}>") + 2 < 2000: # + 2 is for the space and comma (,) next to each mention
                            mentions.append(f"<@{user_id}>")
                        else:
                            await main_message.reply(content=", ".join(mentions), mention_author=False)
                            mentions = [] # reset list for another pinging message with other users
                    if mentions:
                        await main_message.reply(content=", ".join(mentions), mention_author=False)
                    mentioned = True
                else:
                    mentioned = False
                epi_users.clear()
                await clear_epi_users(self.pool)
                self.epi_data.clear() # remove the custom status/message
                await clear_epi_config(self.pool)
                if self.sticky_message:
                    try:
                        await self.sticky_message.delete()
                    except discord.NotFound:
                        pass
                    self.sticky_message = None
                await interaction.channel.send(content=f"EPI mode successfully disabled by {interaction.user.name}.\nMentioned users: {mentioned}")
                await self.send_epi_log(f"EPI mode disabled by {interaction.user.mention}\nCustom message: {message or 'not set'}")
            button.callback = on_button_click
            view = discord.ui.View()
            view.add_item(button)
            await interaction.followup.send(view=view, content=f"Are you sure you want to disable EPI mode? This will ping `{len(epi_users)}` user(s) that clicked the 'Get notified when this issue is resolved' button.\n-# Dismiss this message to cancel.", ephemeral=True)
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled!", ephemeral=True)

    @group.command(name="view", description="View the current EPI mode status")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def epi_view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            Message_url = "Not set"
            if self.epi_Message:
                Message_url = self.epi_Message.jump_url
            message = "Not set"
            if self.epi_msg:
                message = self.epi_msg
            await interaction.followup.send(
                content=f"Current EPI mode Status message: {Message_url} | Custom message: {message}\nEPI-User count: {len(epi_users)}. Sticky: {bool(self.sticky_message)}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled! Run the command again if EPI mode is activated.")

    @group.command(name="edit", description="Edit current EPI information")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(message="A custom text message to be displayed. Leave empty to not edit or '-' to remove.", message_id="ID of a message from #status to be displayed. Leave empty to not edit or 0 to remove", sticky="Should a sticky message be created in #general? Leave empty to not edit.")
    async def edit(self, interaction: discord.Interaction, message: str = None, message_id: str = None, sticky: bool = None):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            if message != None or message_id != None or sticky != None:
                command_response = "\nSuccessfully updated EPI mode!"
                new_key = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
                previous_key = list(self.epi_data.keys())[0]
                self.epi_data[new_key] = list(self.epi_data.values())[0]
                del self.epi_data[previous_key]
                await update_epi_iso(self.pool, new_key)
                _message = None
                if message:
                    await update_epi_message(self.pool, message)
                    if message == "-":
                        self.epi_msg = None
                        command_response += "\n Custom message: Disabled"
                    else:
                        self.epi_msg = message
                        command_response += f"\nCustom message: `{message}`"
                if message_id:
                    if message_id.isdigit():
                        if int(message_id) != 0:
                            status = discord.utils.get(interaction.guild.text_channels, name="status")
                            if status:
                                try:
                                    _message = await status.fetch_message(int(message_id))
                                except discord.NotFound as e:
                                    command_response += f"\nCouldn't fetch message from {status.mention} with id `{message_id}`. `{e.text}` `{e.status}"
                                else: # the message was fetched successfully
                                    await update_epi_message_id(self.pool, int(message_id))
                                    self.epi_Message = _message
                                    command_response += f"\nStatus message: {_message.jump_url}"
                            else:
                                command_response += "\nCouldn't get status channel, try again later..."
                        else:
                            self.epi_Message = None
                            await update_epi_message_id(self.pool, int(message_id))
                            command_response += "\nStatus message: Disabled"
                    else:
                        command_response += f"\nCouldn't fetch status message: `message_id` argument must be a valid integer (received `{message_id}`)"
                if sticky:
                    if not self.sticky_message or not self.sticky_task:
                        await update_epi_sticky(self.pool, sticky)
                        general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                        await self.handle_sticky_message(general)
                        command_response += "\nEnabled sticky message"
                    else:
                        command_response += "\nCouldn't enable sticky message: Already enabled."
                elif sticky == False:
                    if self.sticky_message or self.sticky_task:
                        await update_epi_sticky(self.pool, sticky)
                        await self.disable_sticky_message()
                        command_response += "\nDisabled sticky message"
                    else:
                        command_response += "\nCouldn't disable sticky message: Already disabled."
                await interaction.followup.send(command_response, ephemeral=True)
            else:
                await interaction.followup.send("At least one of `message`, `message_id`, `sticky` argument must be provided!")
        else:
            await interaction.followup.send("EPI must be enabled for you to edit it! Use /epi enable to enable it.", ephemeral=True)

    @commands.Cog.listener('on_thread_create')
    async def send_epi_info(self, thread: discord.Thread):
        if thread.parent_id == SUPPORT_CHANNEL_ID and self.epi_data:
            await asyncio.sleep(3) # make sure that epi messages will be sent last (after more info message)
            embed = self.generate_epi_embed()
            message = await thread.send(embed=embed, view=get_notified())
            await add_epi_message(self.pool, message.id, thread.id)
            index = list(self.epi_data.keys())[0]
            self.epi_data[index][thread.id] = message.id

    @commands.Cog.listener('on_message')
    async def epi_sticky_message(self, message: discord.Message):
        if self.epi_data and not message.author.bot and message.channel.id == GENERAL_CHANNEL_ID and self.sticky_message:
            if not self.is_being_executed and self.sticky_task:
                self.sticky_task.cancel()
                self.sticky_task = asyncio.create_task(self.handle_sticky_message(message.channel))
            elif not self.is_being_executed and not self.sticky_task:
                self.sticky_task = asyncio.create_task(self.handle_sticky_message(message.channel))

    channel_permissions: dict[discord.TextChannel | discord.ForumChannel, dict[discord.Role|discord.Member|discord.Object, discord.PermissionOverwrite]] = {}

    @app_commands.command(name="lock", description="Lock the given channels. Should only be used in emergencies.")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
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
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID)
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
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
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
        """  
        The way this system works is that a notification ("page") is sent to
        another ntfy topic (NTFY_SECOND_TOPIC_ID from .env) when a button from the notification
        is clicked while SH is listening to events in that topic
        """
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
                                webhooks = [webhook for webhook in await channel.webhooks() if webhook.token]
                                try:
                                    webhook = webhooks[0]
                                except IndexError: # webhooks is an empty list - that channel has no webhooks
                                    webhook = await channel.create_webhook(name="Created by Sapphire helper")
                                xge = self.client.get_user(265236642476982273) or await self.client.fetch_user(265236642476982273) # xge's user id, use get to get from the cache and fetch if couldn't find in cache
                                await webhook.send(
                                    content=f"{response}\n-# Reply to {message.jump_url}",
                                    username=xge.global_name or xge.name, # global name or username if global name doesn't exist (is none)
                                    avatar_url=xge.display_avatar.url
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
            tags.append("moneybag") # 💰
        if not user: # an automated page for rate limits
            tags.append("robot") # 🤖
        if user:
            title.join(f" | Sent by @{user.name}")
        async with aiohttp.ClientSession(trust_env=True) as cs:
            random_id = generate_random_id() # a unique random id for when there are multiple open websockets
            self.recent_page["id"] = random_id
            data = {
                "topic": NTFY_TOPIC_NAME,
                "message": message,
                "title": title,
                "tags": tags,
                "click": followup.jump_url,
                "actions": [ # the hedaers in each button is {"Title": "the message that will be sent in the channel", "message": "the unique id"}
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
                data["icon"] = user.display_avatar.url
            try:
                async with cs.post("https://ntfy.sh/", data=json.dumps(data)) as req:
                    if req.status == 200: # OK
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
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
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
            if 265236642476982273 in [user.id for user in message.mentions]: #! IMPORTANT: please make sure that this is Xge's user ID. For testing I had to switch it with my own as messages' .mentions field only shows for users who are in the server
                experts_channel = discord.utils.get(message.guild.text_channels, name="sapphire-experts") or self.client.get_channel(EPI_LOG_THREAD_ID).parent
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
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
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
