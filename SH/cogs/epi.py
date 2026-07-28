from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from dotenv import load_dotenv
from functions import save_channel_permissions, get_channel_permissions, delete_channel_permissions, get_locked_channels, \
    generate_random_id, get_epi_users, save_epi_config, get_epi_config, get_epi_messages, add_epi_message, clear_epi_users, \
    clear_epi_config, add_epi_user, delete_epi_user, clear_epi_messages, update_sticky_message_id, update_epi_message, \
    update_epi_message_id, update_epi_sticky, check_time_more_than, DB_PATH
import aiohttp, json, os, asyncio, re, datetime, asqlite as sql
from typing import Literal, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from main import SHBot

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

XGE_USER_ID = 265236642476982273



class GetNotifiedButton(ui.ActionRow):
    def __init__(self, epi_users: list[int]):
        super().__init__()
        self.epi_users = epi_users
    @ui.button(label="Notify me when this issue is resolved", custom_id="epi-get-notified", style=discord.ButtonStyle.grey)
    async def on_get_notified_click(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id not in self.epi_users:
            await add_epi_user(interaction.user.id)
            self.epi_users.append(interaction.user.id)
            await interaction.response.send_message(content="You will now be notified when this issue is fixed!", ephemeral=True)
        else:
            await delete_epi_user(interaction.user.id)
            self.epi_users.remove(interaction.user.id)
            await interaction.response.send_message(content="You will no longer be notified for this issue!", ephemeral=True)


class GetNotifiedView(ui.LayoutView):
    def __init__(self, description: str = "", *, epi_users: list[int], status_page: bool = True, status_message: discord.Message | None = None):
        super().__init__(timeout=None)
        self.description = description

        title = "## Some services are currently experiencing issues"
        accent_colour = 16749824
        footer = "We're sorry for the inconvenience caused and thank you for your patience!"
        get_notified_button = GetNotifiedButton(epi_users)

        container = ui.Container(accent_colour=accent_colour)

        container.add_item(ui.TextDisplay(title))
        if status_message is not None:
            container.add_item(ui.Separator(visible=False))
            container.add_item(ui.TextDisplay(f"### - [Official Status Update]({status_message.jump_url})"))
        if description:
            container.add_item(ui.TextDisplay(f"- {description.strip()}"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(footer))
        container.add_item(get_notified_button)
        if status_page:
            get_notified_button.add_item(discord.ui.Button(label="Status Page", url="https://sapph.xyz/status", style=discord.ButtonStyle.link))

        self.add_item(container)


class select_channels(ui.ChannelSelect):
    def __init__(self, action: str, reason: str, i: discord.Interaction, slowmode: int | None = None):
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

    async def callback(self, interaction: discord.Interaction[SHBot]):
        await interaction.response.defer(ephemeral=True)
        channels = self.values # the selected channels
        fetched_channels: list[discord.TextChannel|discord.ForumChannel] = [interaction.guild.get_channel(c.id) or await c.fetch() for c in channels]
        successful: list[int] = [] # list of channel ids that were successfully locked/unlocked/set slowmode in
        for channel in fetched_channels:
            if not (channel.permissions_for(interaction.user).send_messages and channel.permissions_for(interaction.guild.default_role).view_channel):
                await interaction.followup.send(f"You can only {self.action} channels you can send messages in and `@everyone` can view!\n-# {channel.mention}", ephemeral=True)
                continue
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
        if successful: # Check that channels were successfully edited
            action_str = self.action + "ed" if self.slowmode is None else f"set slowmode to {self.slowmode}" if self.slowmode > 0 else "disabled slowmode"
            await interaction.client.send_log(EPI_LOG_THREAD_ID, content=f"{interaction.user.mention} {action_str} in {', '.join([f'<#{c}>' for c in successful])}. Reason: {self.reason}")
            await self.i.edit_original_response(view=None)



class EpiData:
    """
    The object that holds the data for EPI.


    Attributes
    -----------
    started_at: :class:`int`
        The timestamp in UTC of when the EPI was started.
    sticky_message: :class:`discord.Message` | ``None``
        The sticky_message sent, or ``None`` if not available.
    sticky_task: :class:`asyncio.Task` | ``None``
        The task to handle sending sticky messages and deleting it. ``None`` if not avaiable/completed.
    is_being_executed: :class:`bool`
        Whether the `sticky_task` is currently executing.
    message: :class:`str` | ``None``
        The main message/description that is shown in the EPI message.
    thread_to_msgs_map: :class:`dict[int, int]`
        The mapping of the thread_id (i.e support post) to the message ID of the EPI message sent.
    status_page: :class:`bool`
        Whether the status page is available or not.
    status_message: :class:`discord.Message` | ``None``
        The official status message to show in the EPI message, ``None`` if not available.
    users: :class:`list[int]`
        The users to be pinged.
    _enabled: :class:`bool`
        Whether the EPI is currently enabled or not.
    """
    __slots__ = ('started_at', 'sticky_message', 'sticky_task', 'is_being_executed', 'message',
                 'status_message', 'thread_to_msgs_map', 'status_page', 'users', '_enabled')
    def __init__(self):
        self.started_at: int = 0

        self.sticky_message: discord.Message | discord.PartialMessage | None = None
        self.sticky_task: asyncio.Task | None = None
        self.is_being_executed: bool = False

        self.message: str | None = None

        self.thread_to_msgs_map: dict[int, int] = {}

        self.status_message: discord.Message | None = None
        self.status_page: bool = True # true if its working, false if its not working

        self.users: list[int] = [] # Users who want to get notified

        self._enabled: bool = False


    async def update_from_epi_config(self, epi_config: dict[str, Any], cog: EPI) -> None:
        self._enabled = True

        self.started_at = epi_config['started_at']
        self.thread_to_msgs_map = await get_epi_messages(cog.pool)

        message: str = epi_config["message"]
        self.message = message if message != "-" else None

        status_message_id: int = epi_config["message_id"]
        if status_message_id != 0:
            status = discord.utils.get(cog.bot.get_all_channels(), name="status", type=discord.ChannelType.news)
            if status is not None:
                try:
                    status_message = await status.fetch_message(status_message_id)
                except discord.NotFound as e:
                    await update_epi_message_id(cog.pool, 0) # remove the message id from the db
                    await cog.bot.send_log(ALERTS_THREAD_ID,
                                            content=f"Tried to fetch status message from {status.mention} with id {epi_config['message_id']}.\n{e.status} {e.text}")
                else:
                    self.status_message = status_message

        self.users.extend(await get_epi_users(cog.pool))

        if epi_config["sticky"]:
            general = cog.bot.get_partial_messageable(GENERAL_CHANNEL_ID)
            sticky_message_id = epi_config["sticky_message_id"]
            if sticky_message_id:
                self.sticky_message = general.get_partial_message(epi_config["sticky_message_id"])
            await cog.handle_sticky_message(general, delay=0)


    def clear(self) -> None:
        """
        Clears the state of the data
        
        Note that sticky message related data should have been cleared already.
        """
        self.sticky_message = None
        self.sticky_task = None
        self.is_being_executed = False

        self.message = None

        self.status_message = None
        self.thread_to_msgs_map.clear()
        self.status_page = False
        self.users.clear()
        self._enabled = False


    def __bool__(self):
        return self._enabled


class EPI(commands.Cog):
    def __init__(self, bot: SHBot):
        self.bot = bot
        self.page_webhook_id: int | None = None
        self.page_webhook_token: str | None = None

        self.recent_page: dict[str, Any] = {} # {"user_id": 1234, "message": "low taper fade is still massive", "timestamp": 1234.56, "priority": 1, "service": "Sapphire - bot", "cb_affected": False, "id": "AbC123"} , used for "a page was made 3 minutes ago, are you sure you want to continue?" for pages up to 5 minutes old

        self.epi_data = EpiData()

        #self.sticky_message: Optional[discord.Message] = None
        #self.sticky_task: Optional[asyncio.Task] = None
        #self.is_being_executed: bool = False
        #self.epi_msg: Optional[str] = None
        #self.status_message: Optional[discord.Message] = None
        #self.epi_data: dict[str, dict[int, int]] = {} # {str(started_at: {int(thread_id): int(message_id)})}  would be way more efficient than saving full message objects, especially in high amounts
        #self.status_page: bool = True # true if its working, false if its not working
        #self.epi_users: list[int] = [] # Users who want to get notified

    group = app_commands.Group(name="epi", description="Commands related to Emergency Post Information system")

    def generate_epi_layout_view(self) -> GetNotifiedView:
        description: str = ""
        if self.epi_data.message:
            description += self.epi_data.message

        return GetNotifiedView(description, epi_users=self.epi_data.users, status_page=self.epi_data.status_page, status_message=self.epi_data.status_message)

    async def handle_sticky_message(self, channel: discord.TextChannel | discord.PartialMessageable, delay: float = 4.0):
        view = self.generate_epi_layout_view()
        await asyncio.sleep(delay)
        self.epi_data.is_being_executed = True
        if self.epi_data.sticky_message:
            try:
                await self.epi_data.sticky_message.delete()
            except discord.NotFound:
                pass
        self.epi_data.sticky_message = await channel.send(view=view)
        await update_sticky_message_id(self.pool, self.epi_data.sticky_message.id)
        self.epi_data.sticky_task = None
        self.epi_data.is_being_executed = False

    async def disable_sticky_message(self):
        while self.epi_data.is_being_executed:
            await asyncio.sleep(0.1) # self.is_being_executed is true at lines 196-197 - async handle_sticky_message, when the previous sticky message is deleted and the new one is being sent. 0.1 should probably be enough for these things to happen
        try:
            await self.epi_data.sticky_message.delete()
        except discord.NotFound:
            pass # message was not found, probably already deleted - do nothing
        self.epi_data.sticky_message = None
        self.epi_data.sticky_task = None


    async def cog_unload(self):
        await self.pool.close()

    async def cog_load(self):
        self.pool = await sql.create_pool(DB_PATH)
        epi_config = await get_epi_config(self.pool)
        if not epi_config:
            return

        await self.epi_data.update_from_epi_config(epi_config, self)

        self.bot.add_view(GetNotifiedView(epi_users=self.epi_data.users))

    @group.command(name="enable", description="Enables EPI mode with the given text/message id")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(message="[Optional] A custom text message to be displayed", message_id="[Optional] ID of a message from #status to be displayed", sticky="Should a sticky message be created in #general?")
    async def epi_enable(self, interaction: discord.Interaction, message: Optional[app_commands.Range[str, 1, 1000]], message_id: Optional[str], sticky: bool):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data: # Make sure epi mode is not already enabled
            await interaction.followup.send(content=f"EPI Mode is already enabled!", ephemeral=True)
            return
        self.epi_data._enabled = True
        command_response = "Successfully enabled EPI mode!"
        self.ping_status_page.start()
        if message:
            self.epi_data.message = message
            command_response += f"\nCustom message: {message}"

        status_message = None
        if message_id:
            if message_id.isdigit():
                status = discord.utils.get(interaction.guild.text_channels, name="status")
                if status:
                    try:
                        status_message = await status.fetch_message(int(message_id))
                    except discord.NotFound as e:
                        command_response += f"\nStatus message: Failed. Tried fetching `{message_id}` from {status.mention}. `{e.text}` `{e.status}`\n"
                    else: # the message was fetched successfully
                        self.epi_data.status_message = status_message
                        command_response += f"\nStatus message: {status_message.jump_url}\n"                    
                else:
                    command_response += "\nStatus message: Failed - status channel not found.\n"
            else:
                command_response += "\nStatus message: Failed - message_id is not a valid ID.\n"


        await save_epi_config(self.pool, datetime.datetime.now(datetime.UTC).isoformat(),
                              sticky=sticky, message=message or "-", 
                              message_id=status_message.id if status_message else 0) # message arg defaults to '-' if its None (not provided) and message id to 0
        if sticky:
            general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
            await self.handle_sticky_message(general)
        command_response += f"\nSticky: {sticky}"

        content = f"EPI mode enabled by {interaction.user.mention}.\nCustom message: {message or 'not set'} | Status message: {status_message.jump_url if status_message else 'Not set'} | Sticky: {sticky}"
        await self.bot.send_log(EPI_LOG_THREAD_ID, content=content)
        await interaction.followup.send(command_response, ephemeral=True)

    def find_message(self, message_id: int) -> discord.Message | None:
        if self.bot.cached_messages:
            for message in reversed(self.bot.cached_messages):
                if message.id == message_id:
                    return message

        return None

    @group.command(name="disable", description="Disable EPI mode- mark the issue as solved & ping all users that asked to be pinged")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(message="[Optional] A custom message to be displayed with the \"Hey, this is fixed now!\" message")
    async def epi_disable(self, interaction: discord.Interaction, message: Optional[app_commands.Range[str, 1, 1000]]):
        await interaction.response.defer(ephemeral=True)
        if not self.epi_data:
            await interaction.followup.send(content="EPI mode is not currently enabled!", ephemeral=True)
            return

        async def on_button_click(i: discord.Interaction):
            await i.response.defer(ephemeral=True)

            self.epi_data._enabled = False
            self.ping_status_page.cancel()

            await i.delete_original_response()

            content = "Hey, this issue is fixed now!\n-# Thank you for your patience."
            if message:
                content += f"\n> {message}"

            for thread_id, message_id in self.epi_data.thread_to_msgs_map.items():
                thread = self.bot.get_channel(thread_id)
                if thread is None:
                    continue
                try:
                    msg = self.find_message(message_id) or await thread.fetch_message(message_id)
                except discord.HTTPException:
                    continue
                new_view = ui.LayoutView.from_message(msg)
                for child in new_view.walk_children():
                    if hasattr(child, "disabled"):
                        child.disabled = True
                        break

                was_archived = thread.archived
                try:
                    await msg.edit(view=new_view)
                    await msg.reply(
                        content=content,
                        mention_author=False
                    )
                except discord.NotFound:
                    pass # Message was most likely already deleted
                else:
                    if was_archived:
                        try:
                            await thread.edit(archived=True)
                        except discord.HTTPException:
                            pass

            await clear_epi_messages(self.pool)

            general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
            main_message = await general.send(content=content)
            if self.epi_data.users:
                mentions: list[str] = []
                for user_id in self.epi_data.users:
                    if len(", ".join(mentions)) + len(f"<@{user_id}>") + 2 < 2000: # + 2 is for the space and comma (,) next to each mention
                        mentions.append(f"<@{user_id}>")
                    else:
                        await main_message.reply(content=", ".join(mentions), mention_author=False)
                        mentions = [] # reset list for another pinging message with other users
                if mentions:
                    await main_message.reply(content=", ".join(mentions), mention_author=False)
            await clear_epi_users(self.pool)

            await self.disable_sticky_message()

            await interaction.channel.send(f"EPI mode successfully disabled by {interaction.user.name}.\nUsers mentioned: {len(self.epi_data.users)}")
            await self.bot.send_log(EPI_LOG_THREAD_ID, content=f"EPI mode disabled by {interaction.user.mention}\nCustom message: {message or 'not set'}")
    
            self.epi_data.clear()
            await clear_epi_config(self.pool)

        button = ui.Button(
            style=discord.ButtonStyle.danger,
            label="Confirm",
            custom_id="epi-disable-confirm"
        )
        button.callback = on_button_click
        view = ui.View().add_item(button)
        await interaction.followup.send(f"Are you sure you want to disable EPI mode? This will ping `{len(self.epi_data.users)}` user(s) that clicked the 'Get notified when this issue is resolved' button.\n-# Dismiss this message to cancel.",
                                        view=view, ephemeral=True)

    @group.command(name="view", description="View the current EPI mode status")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def epi_view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.epi_data:
            status_msg_url = "Not set"
            if self.epi_data.status_message:
                status_msg_url = self.epi_data.status_message.jump_url
            message = "Not set"
            if self.epi_data.message:
                message = self.epi_data.message
            await interaction.followup.send(
                content=f"- **Status message:** {status_msg_url}\n- **Custom message:** {message}\n- **User count:** {len(self.epi_data.users)}\n- **Sticky:** {bool(self.epi_data.sticky_message)}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(content="EPI mode is not currently enabled! Run the command again if EPI mode is activated.")

    @group.command(name="edit", description="Edit current EPI information")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(message="A custom text message to be displayed. Leave empty to not edit or '-' to remove.", message_id="ID of a message from #status to be displayed. Leave empty to not edit or 0 to remove", sticky="Should a sticky message be created in #general? Leave empty to not edit.")
    async def edit(self, interaction: discord.Interaction, message: str | None = None, message_id: str | None = None, sticky: bool | None = None):
        await interaction.response.defer(ephemeral=True)
        if not self.epi_data:
            await interaction.followup.send("EPI must be enabled for you to edit it! Use /epi enable to enable it.", ephemeral=True)
            return
        
        if message is None and message_id is None and sticky is None:
            await interaction.followup.send("At least one of `message`, `message_id`, `sticky` argument must be provided!")
            return

        command_response = "Successfully updated EPI mode!"
        if message:
            await update_epi_message(self.pool, message)
            if message == "-":
                self.epi_data.message = None
                command_response += "\n Custom message: Disabled"
            else:
                self.epi_data.message = message
                command_response += f"\nCustom message: `{message}`"
        if message_id:
            if message_id == '-':
                command_response += "\n Status message: Disabled"
                self.epi_data.status_message = None
                await update_epi_message_id(self.pool, 0)
            elif message_id.isdigit():
                message_id_int = int(message_id)
                status_channel = discord.utils.get(interaction.guild.text_channels, name="status")
                if status_channel is not None:
                    try:
                        status_message = await status_channel.fetch_message(message_id_int)
                    except discord.NotFound:
                        command_response += f"\nCouldn't fetch message from {status_channel.mention} with id `{message_id}`."
                    else: # the message was fetched successfully
                        await update_epi_message_id(self.pool, message_id_int)
                        self.epi_data.status_message = status_message
                        command_response += f"\nStatus message: {status_message.jump_url}"
                else:
                    command_response += "\nCouldn't get status channel..."
            else:
                command_response += f"\nCouldn't fetch status message: `message_id` is invalid (received `{message_id}`)"
        if sticky:
            if not self.epi_data.sticky_message or not self.epi_data.sticky_task:
                await update_epi_sticky(self.pool, sticky)
                general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                await self.handle_sticky_message(general)
                command_response += "\nEnabled sticky message"
            else:
                command_response += "\nCouldn't enable sticky message: Already enabled."
        elif sticky is False:
            if self.epi_data.sticky_message or self.epi_data.sticky_task:
                await update_epi_sticky(self.pool, sticky)
                await self.disable_sticky_message()
                command_response += "\nSticky Message: Disabled"
            else:
                command_response += "\nCouldn't disable sticky message: Already disabled."
        await interaction.followup.send(command_response, ephemeral=True)

    @commands.Cog.listener('on_thread_create')
    async def send_epi_info(self, thread: discord.Thread):
        if thread.parent_id == SUPPORT_CHANNEL_ID and self.epi_data:
            await asyncio.sleep(3) # make sure that epi messages will be sent last (after more info message)
            view = self.generate_epi_layout_view()
            message = await thread.send(view=view)
            await add_epi_message(self.pool, message.id, thread.id)
            self.epi_data.thread_to_msgs_map[thread.id] = message.id

    @commands.Cog.listener('on_message')
    async def epi_sticky_message(self, message: discord.Message):
        if self.epi_data and not message.author.bot and message.channel.id == GENERAL_CHANNEL_ID and self.epi_data.sticky_message:
            if self.epi_data.is_being_executed:
                return
            if self.epi_data.sticky_task:
                self.epi_data.sticky_task.cancel()
            self.epi_data.sticky_task = asyncio.create_task(self.handle_sticky_message(message.channel))

    channel_permissions: dict[discord.TextChannel | discord.ForumChannel, dict[discord.Role|discord.Member|discord.Object, discord.PermissionOverwrite]] = {}

    @app_commands.command(name="lock", description="Lock the given channels through the select menu sent. Should only be used in emergencies.")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(reason="The reason for locking the channels.")
    async def lock(self, interaction: discord.Interaction, reason: app_commands.Range[str, 1, 200]):
        await interaction.response.defer(ephemeral=True)
        view = ui.View()
        view.add_item(select_channels("lock", reason, interaction))
        await interaction.followup.send(content="Select the channels to be locked below.\n-# Minimum of 1, maximum of 5.", view=view)
                
    @app_commands.command(name="unlock", description="Unlock the given channels through the select menu sent. Should only be used in emergencies.")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(reason="What is the reason for unlocking the channels?")
    async def unlock(self, interaction: discord.Interaction, reason: app_commands.Range[str, 1, 200]):
        await interaction.response.defer(ephemeral=True)
        view = ui.View()
        view.add_item(select_channels("unlock", reason, interaction))
        await interaction.followup.send("Select the channels that should be unlocked below.\n-# Minimum of 1, maximum of 5.", view=view, ephemeral=True)

    @app_commands.command(name="slowmode", description="Set a slowmode to channels using the select menu sent. Should only be used in emergencies.")
    @app_commands.describe(time="The new slowmode time for the channel, in seconds. Max 21600. Put 0 to disable slowmode.", reason="What's the reason for this slowmode?")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def slowmode(self, interaction: discord.Interaction, time: app_commands.Range[int, 0, 21600], reason: app_commands.Range[str, 1, 200]):
        await interaction.response.defer(ephemeral=True)
        view = ui.View()
        view.add_item(select_channels("slowmode", reason,interaction ,time))
        await interaction.followup.send(content="Select the channels where the given slowmode should be applied below.\n-# Minimum of 1, maximum of 5.", view=view)

    async def set_webhook_page(self, partial_channel: discord.PartialMessageable) -> None:
        """
        Set the webhook used for paging
        """
        if self.page_webhook_id is not None:
            try:
                webhook = await self.bot.fetch_webhook(self.page_webhook_id)
            except discord.NotFound:
                pass
            else:
                if webhook.channel_id == partial_channel.id:
                    return

        channel = self.bot.get_channel(partial_channel.id)
        if isinstance(channel, discord.Thread):
            channel = channel.parent

        for wb in await channel.webhooks():
            if wb.token:
                webhook = wb
                break
        else:
            webhook = await channel.create_webhook(name="Created by Sapphire helper")

        self.page_webhook_id = webhook.id
        self.page_webhook_token = webhook.token
    

    async def send_page(self, 
                        title: str, 
                        description: str, 
                        priority: int, 
                        followup: discord.WebhookMessage | discord.Message,
                        case_id: str,
                        cb_affected: bool = False,
                        *,
                        user: discord.Member | discord.User | None = None,
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

        # set the webhook ID and token (if needed)
        await self.set_webhook_page(followup.channel)

        xge = await self.bot.fetch_user(XGE_USER_ID) 
        async with aiohttp.ClientSession(trust_env=True) as session:
            data = {
                "topic": NTFY_TOPIC_NAME,
                "title": title,
                "message": description,
                "tags": tags,
                "click": followup.jump_url,
                "actions": [
                    {
                        "action": "http",
                        "label": "On it",
                        "url": f"https://discord.com/api/v10/webhooks/{self.page_webhook_id}/{self.page_webhook_token}",
                        "headers": {'content-type': 'application/json'},
                        "method": "POST",
                        "body": json.dumps({'content': f'On it\n-# Reply to {followup.jump_url}', 'username': xge.display_name, 'avatar_url': xge.display_avatar.url}),
                        "clear": True
                    },
                    {
                        "action": "http",
                        "label": "Soon (Next 30min)",
                        "url": f"https://discord.com/api/v10/webhooks/{self.page_webhook_id}/{self.page_webhook_token}",
                        "headers": {'content-type': 'application/json'},
                        "method": "POST",
                        "body": json.dumps({'content': f'Soon (Next 30min)\n-# Reply to {followup.jump_url}', 'username': xge.display_name, 'avatar_url': xge.display_avatar.url}),
                        "clear": True
                    },
                    {
                        "action": "http",
                        "label": "Later (>1 hour)",
                        "url": f"https://discord.com/api/v10/webhooks/{self.page_webhook_id}/{self.page_webhook_token}",
                        "headers": {'content-type': 'application/json'},
                        "method": "POST",
                        "body": json.dumps({'content': f'Later (>1 hour)\n-# Reply to {followup.jump_url}', 'username': xge.display_name, 'avatar_url': xge.display_avatar.url}),
                        "clear": True
                    }
                ] 
            }
            if priority == 4:
                data["priority"] = 5
            if user:
                data["icon"] = user.display_avatar.url

            async with session.post("https://ntfy.sh/", data=json.dumps(data)) as res:
                if res.status == 200: # OK
                    if user:
                        service = title.removesuffix(f" | Sent by @{user.name}")
                        await self.bot.send_log(EPI_LOG_THREAD_ID, content=f"{user.mention} used /page. Service: {service} | Message: `{description}` | Priority: {priority} | Custom Branding Affected: {cb_affected}\n-# ID: [{case_id}]({followup.jump_url})")
                    else:
                        await self.bot.send_log(EPI_LOG_THREAD_ID, content=f"Sent automated page for ratelimits | Priority: {priority}\n-# ID: [{case_id}]({followup.jump_url})")    
                else:
                    raise Exception(await res.text())

    @app_commands.command(name="page", description="Alert the lead developer of any downtime or critical issues")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(
        service="The affected service(s) - Sapphire- bot/dashboard | appeal.gg | All",
        message="The message to send", 
        priority="1 - lowest, 4 - highest (most critical)", 
        cb_affected="Whether custom branding is affected or not (for Sapphire outages)"
    )
    async def page(self, interaction: discord.Interaction, service: Literal["Sapphire - bot", "Sapphire - dashboard", "appeal.gg", "All"], message: str, 
                   priority: Literal["4 | Night", "3 | Major issue", "2 | Minor issue", "1 | Information"], cb_affected: bool):
        priority_dict : dict[str, int] = {
            "4 | Night": 4,
            "3 | Major issue": 3,
            "2 | Minor issue": 2,
            "1 | Information": 1
        }

        case_id = generate_random_id()
        priority_num = priority_dict[priority]
        new_content = f"Notification sent successfully.\n-# Message: {message} | Priority: {priority_num} | Service: {service} | CB affected: {cb_affected} | ID: {case_id}"

        if self.recent_page and not check_time_more_than(self.recent_page['timestamp'], datetime.timedelta(minutes=15)):
            await interaction.response.defer(ephemeral=True)
            async def callback(i: discord.Interaction):
                followup_msg = await i.channel.send("Sending...")
                await interaction.delete_original_response()
                self.recent_page = {
                    "user_id": interaction.user.id,
                    "message": message,
                    "timestamp": round(datetime.datetime.now(datetime.UTC).timestamp()),
                    "priority": priority_num,
                    "service": service,
                    "cb_affected": cb_affected,
                    "id": case_id
                }
                await self.send_page(f"{service} | Sent by @{interaction.user.name}", message, priority_num, followup_msg, case_id, cb_affected, user=interaction.user)
                await followup_msg.edit(content=new_content)

            button = ui.Button(style=discord.ButtonStyle.danger, label="Confirm", custom_id="page-confirm")
            button.callback = callback
            view = ui.View(timeout=60 * 15).add_item(button)
            await interaction.followup.send(f"A page was sent <t:{self.recent_page['timestamp']}:R> by <@{self.recent_page['user_id']}>:"
                                            f"\n- Service: `{self.recent_page['service']}`\n- Message: `{self.recent_page['message']}`\n- Priority: `{self.recent_page['priority']}`\n- CB affected: `{self.recent_page['cb_affected']}`\n- ID: `{self.recent_page['id']}`"
                                            "\nAre you sure you would like to send this one?\n-# Click *confirm* to page, dismiss message to cancel.", 
                                            ephemeral=True, view=view)
        else:
            await interaction.response.defer()
            followup = await interaction.followup.send("Sending...", wait=True)
            self.recent_page = {
                "user_id": interaction.user.id,
                "message": message,
                "timestamp": round(datetime.datetime.now(datetime.UTC).timestamp()),
                "priority": priority_num,
                "service": service,
                "cb_affected": cb_affected,
                "id": case_id
            }
            await self.send_page(f"{service} | Sent by @{interaction.user.name}", message, priority_num, followup, case_id, cb_affected, user=interaction.user)
            await followup.edit(content=new_content)

    @commands.Cog.listener("on_message")
    async def autopage_on_ratelimit(self, ratelimit_message: discord.Message):
        if not ratelimit_message.channel.id in (1023568468206956554, 1146016865345343531) or not ratelimit_message.author.bot: # #cluster-log and the id of the channel in testing server as I don't want to add another .env variable
            return
        if XGE_USER_ID not in ratelimit_message.raw_mentions:
            return
        experts_channel = discord.utils.get(ratelimit_message.guild.text_channels, name="sapphire-experts") or self.bot.get_channel(EPI_LOG_THREAD_ID).parent
        if experts_channel is None:
            return
        msg = await experts_channel.send(f"Sending automated page for {ratelimit_message.jump_url}")
        if datetime.datetime.now().hour > 21 or datetime.datetime.now().hour < 7: # from 10 PM to 7 AM
            priority = 4
        else:
            priority = 3
        h_pattern = r"\[ H\d+ ]" # [ H<some number> ] e.g. [ H16 ] from the message 
        resets_pattern = r"<t:(\d+):R>"
        h = re.findall(pattern=h_pattern, string=ratelimit_message.content)
        h = h[0] if h else "Unknown"
        _resets_timestamp = re.findall(resets_pattern, string=ratelimit_message.content)
        resets_timestamp = _resets_timestamp[0] if _resets_timestamp else None
        if resets_timestamp:
            time = datetime.datetime.fromtimestamp(int(resets_timestamp))
            page_msg = f"Resets at: {time.hour}:{time.minute}:{time.second}"
        else:
            page_msg = "Resets at: Unknown"

        case_id = generate_random_id()
        self.recent_page = {
            "user_id": ratelimit_message.author.id,
            "message": page_msg,
            "timestamp": round(datetime.datetime.now(datetime.UTC).timestamp()),
            "priority": priority,
            "service": f"{h} Ratelimited",
            "cb_affected": False,
            "id": case_id
        }
        await self.send_page(f"{h} Ratelimited", page_msg, priority, msg, case_id)
        await msg.edit(content=f"Automated page for [ratelimits]({ratelimit_message.jump_url}) sent successfully.\n-# Priority: {priority} | ID: {case_id}")

    @tasks.loop(minutes=2.5)
    async def ping_status_page(self):
        async with aiohttp.ClientSession(trust_env=True) as cs:
            async with cs.get("https://sapph.xyz/status", timeout=aiohttp.ClientTimeout(total=15)) as req:
                print(req.status)
                self.epi_data.status_page = req.status == 200 # true if the status is 200 - OK, else false

async def setup(bot: SHBot):
    await bot.add_cog(EPI(bot))