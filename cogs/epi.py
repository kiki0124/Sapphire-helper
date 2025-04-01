import discord
from discord.ext import commands
from discord import app_commands, ui
import os
from dotenv import load_dotenv
from functions import get_post_creator_id, save_channel_permissions, get_channel_permissions, delete_channel_permissions, get_locked_channels
import asyncio
import aiohttp, json

load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
EPI_LOG_THREAD_ID = int(os.getenv("EPI_LOG_THREAD_ID"))
NTFY_TOPIC_NAME = os.getenv("NTFY_TOPIC_NAME")

epi_users: list[discord.Member|discord.User] = []

async def lock_channel(channel: discord.TextChannel|discord.ForumChannel, user: discord.Member, reason: str):
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
    await channel.edit(overwrites=overwrites, reason=f"{user.name} ({user.id}) used /lock. Reason: {reason}")
    if isinstance(channel, discord.TextChannel):
        embed = discord.Embed(
            title="Channel locked.",
            description=f"> {reason}",
            colour=0xFFA800 # Default 'warning' colour in Sapphire's default messages which I find quite nice and fitting
        )
        embed.set_footer(text=f"@{user.name}", icon_url=user.avatar.url)
        await channel.send(embed=embed)
    epi_thread = channel.guild.get_thread(EPI_LOG_THREAD_ID)
    await epi_thread.send(f"`{user.name}` (`{user.id}`) locked {channel.mention}. Reason: {reason}")

async def unlock_channel(channel: discord.TextChannel|discord.ForumChannel, user: discord.Member, reason: str):
    allow_deny = await get_channel_permissions(channel.id)
    allow = discord.Permissions()._from_value(allow_deny[0])
    deny = discord.Permissions()._from_value(allow_deny[1])
    overwrites = discord.PermissionOverwrite().from_pair(allow=allow, deny=deny)
    await channel.edit(overwrites={channel.guild.default_role: overwrites} ,reason=f"{user.name} ({user.id}) used /unlock. Reason: {reason}")
    if isinstance(channel, discord.TextChannel):
        embed = discord.Embed(
            title="Channel unlocked",
            description=f"> {reason}",
            colour=0x36CE36
            )
        embed.set_footer(text=f"@{user.name}", icon_url=user.avatar.url)
        await channel.send(embed=embed)
    await delete_channel_permissions(channel.id)
    epi_thread = channel.guild.get_thread(EPI_LOG_THREAD_ID)
    await epi_thread.send(f"`{user.name}` (`{user.id}`) unlocked {channel.mention}. Reason: {reason}")

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

class select_channels(ui.ChannelSelect):
    def __init__(self, action: str, reason: str, slowmode: int = None):
        super().__init__(
            channel_types=[discord.ChannelType.text, discord.ChannelType.forum],
            placeholder=f"Select channels to",
            min_values=1,
            max_values=5
        )
        self.action = action
        self.reason = reason
        self.slowmode = slowmode
    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        channels = self.values # the selected channels
        for channel in channels:
            try:
                fetched_channel = interaction.client.get_channel(channel.id) or await channel.fetch() # try to get the channel from the internal cache or fetch it if it isn't found
            except discord.HTTPException:
                await interaction.followup.send(f"Couldn't fetch {channel.mention}", ephemeral=True)
                continue
            if fetched_channel.permissions_for(interaction.user).send_messages:                    
                match self.action:
                    case "lock":
                        if not channel.id in await get_locked_channels():
                            if fetched_channel.permissions_for(interaction.guild.default_role).view_channel:
                                await lock_channel(fetched_channel, interaction.user, self.reason)
                                await interaction.followup.send(content=f"Successfully locked {channel.mention} with reason {self.reason}", ephemeral=True)
                            else:
                                await interaction.followup.send(content=f"You are only able to lock channels that the everyone role can view!", ephemeral=True)
                        else:
                            await interaction.followup.send(content=f"{channel.mention} is already locked! Use /unlock to unlock it.", ephemeral=True)
                    case "unlock":
                        if channel.id in await get_locked_channels():
                            await unlock_channel(fetched_channel, interaction.user, self.reason)
                            await interaction.followup.send(f"Successfully unlocked {channel.mention} with reason {self.reason}", ephemeral=True)
                        else:
                            await interaction.followup.send(f"Couldn't unlock {channel.mention} as it isn't currently locked.", ephemeral=True)
                    case "slowmode":
                        await fetched_channel.edit(slowmode_delay=self.slowmode, reason=f"/slowmode used by {interaction.user.name} ({interaction.user.id}). Reason: {self.reason}")
                        if self.slowmode > 0:
                            await interaction.followup.send(f"Successfully set slowmode in {channel.mention} to {self.slowmode} seconds with reason {self.reason}", ephemeral=True)
                        elif self.slowmode == 0:
                            await interaction.followup.send(f"Successfully disabled slowmode in {channel.mention}")
                        epi_thread = interaction.guild.get_thread(EPI_LOG_THREAD_ID)
                        await epi_thread.send(content=f"`{interaction.user.name}` (`{interaction.user.id}`) set slowmode of `{self.slowmode}` seconds in {channel.mention}")
            else:
                await interaction.followup.send(f"You must be able to send messages in {channel.mention} to {self.action} it!", ephemeral=True)

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
    async def epi_disable(self, interaction: discord.Interaction):
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
                    if message.channel:
                        await message.channel.edit(archived=False)
                        await message.edit(view=None)
                        await message.reply(
                            content="Hey, this issue is fixed now!\n-# Thank you for your patience."
                        )
                    else:
                        continue
                general = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                main_message = await general.send(content="Hey, this issue is now fixed!\n-# Thank you for your patience.")
                if epi_users:
                    mentions: list[discord.Member|discord.User] = []
                    for user in epi_users:
                        if len(", ".join(mentions)) + len(user.mention) + 2 < 2000: # + 2 is for the space and comma (,) next to each mention
                            mentions.append(user.mention)
                        else:
                            await main_message.reply(content=", ".join(mentions))
                            mentions = [] # reset both for another pinging message
                    if mentions:
                        await main_message.reply(content=", ".join(mentions))
                    mentioned = True
                else:
                    mentioned = False
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
                member.add_roles(users_role, reason="Add join roles when EPI is enabled.") """

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

    @app_commands.command(name="lock", description="Lock the given channels. Should only be used in emergencies.")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(reason="The reason for locking the channels.")
    async def lock(self, interaction: discord.Interaction, reason: str):
        await interaction.response.defer(ephemeral=True)
        if len(reason) < 200:
            view = ui.View()
            view.add_item(select_channels("lock", reason))
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
            view.add_item(select_channels("unlock", reason))
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
                    view.add_item(select_channels("slowmode", reason, time))
                    await interaction.followup.send(content="Select the channels where the given slowmode should be applied below.\n-# Minimum of 1, maximum of 5.", view=view)
                else:
                    await interaction.followup.send(content=f"The highest slowmode possible is 21600 and you provided `{time}`.")
            else:
                await interaction.followup.send("Achievement unlocked: How did we get here?", ephemeral=True)
        else:
            await interaction.followup.send(content="The `reason` parameter must be less than 200 characters!", ephemeral=True)
                
        # does anyone even read these comments? Ping me with the funniest/weirdest emoji you have (from any server you're in) if you see this...

    @app_commands.command(name="page", description="Alert the developer of any downtime or critical issues")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(service="The affected service(s) - Sapphire- bot/dashboard | appeal.gg | All" ,message="The message to send", priority="The severity, 1 = lowest, 4 = critical (highest)", cb_affected="Whether custom branding is affected or not (for Sapphire outages)")
    async def page(self, interaction: discord.Interaction, service: str, message: str, priority: int, cb_affected: bool):
        await interaction.response.defer()
        if 1 <= priority <= 4:
            followup = await interaction.followup.send("Sending...", wait=True)
            severity_emojis = {
                1: "green_circle",  # Low
                2: "yellow_circle",  # Medium
                3: "orange_circle",  # High
                4: "red_circle"   # Critical
            }
            async with aiohttp.ClientSession(trust_env=True) as cs:
                #jump_url = f"https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{interaction_response.message_id}"
                tags = [severity_emojis.get(priority, "question")]
                if cb_affected:
                    tags.append("moneybag")
                data = {
                    "topic": NTFY_TOPIC_NAME,
                    "message": message,
                    "title": f"{service} | Sent by @{interaction.user.name}",
                    "tags": tags,
                    "click": followup.jump_url,
                    "icon": interaction.user.avatar.url,
                    "actions": [
                        {
                            "action": "http",
                            "label": "On it",
                            "url": f"https://discord.com/api/v10/webhooks/{interaction.followup.id}/{interaction.followup.token}",
                            "clear": True
                        },
                        {
                            "action": "http",
                            "label": "Later (>1 hour)",
                            "url": f"https://discord.com/api/v10/webhooks/{interaction.followup.id}/{interaction.followup.token}",
                            "clear": True
                        }
                    ] 
                }
                try:
                    async with cs.post("https://ntfy.sh/", data=json.dumps(data)) as req:
                        if req.status == 200:
                            await self.send_epi_log(f"`{interaction.user.name}` (`{interaction.user.id}`) used /page. Service: {service} ,Message: `{message}`, Priority: {priority}, Custom Branding Affected: {cb_affected}.")
                            await followup.edit(content=f"Notification sent successfully.\n-# Message: {message} | Priority: {priority}")
                        else:
                            response = await req.text()
                            await followup.edit(f"An error occured while trying to send the notification...\nStatus: {req.status}, Response: {response}")
                except Exception as e:
                    await followup.edit(content=f"An error occured while trying to send the notification... {e}")
                    raise e
        else:
            await interaction.followup.send(content=f"Priority argument must be between 1 and 4.")

    @page.autocomplete("service")
    async def page_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name="Sapphire - bot", value="Sapphire - bot"),
            app_commands.Choice(name="Sapphire - dashboard", value="Sapphire - dashboard"),
            app_commands.Choice(name="Appeal.gg", value="Appeal.gg"),
            app_commands.Choice(name="All", value="All")
            ]

async def setup(client):
    await client.add_cog(epi(client=client))