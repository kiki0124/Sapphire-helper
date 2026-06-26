from __future__ import annotations

import discord
from discord.ext import commands, tasks
from functions import add_post_to_pending, \
    remove_post_from_pending, get_pending_posts, \
    check_post_last_message_time, check_time_more_than_day,\
    get_post_creator_id, remove_post_from_rtdr, generate_random_id, in_pending_posts, bulk_add_posts_to_pending, bulk_remove_posts_from_pending
import random
from discord import ui
from datetime import datetime, UTC
import os
from dotenv import load_dotenv
from typing import TYPE_CHECKING
from discord.utils import snowflake_time, time_snowflake
if TYPE_CHECKING:
    from main import MyClient
load_dotenv()

SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
CUSTOM_BRANDING_TAG_ID = int(os.getenv("CUSTOM_BRANDING_TAG_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
UNANSWERED_TAG_ID = int(os.getenv('UNANSWERED_TAG_ID'))
APPEAL_GG_TAG_ID = int(os.getenv("APPEAL_GG_TAG_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

reminder_not_sent_posts: dict[int, int] = {} # dictionary of post ids: the amount of tries

class CloseNowRow(ui.ActionRow):
    def __init__(self):
        super().__init__()

    @ui.button(label="Issue Resolved? Close Post Now", style=discord.ButtonStyle.green, custom_id="remind-close-now")
    async def on_close_now_click(self, interaction: discord.Interaction[MyClient], _: ui.Button):
        text_display: discord.TextDisplay = ui.LayoutView.from_message(interaction.message).find_item(10) # type: ignore
        new_view = discord.ui.LayoutView().add_item(ui.Container(ui.TextDisplay(f"~~{text_display.content}~~"), ui.Separator(), ui.TextDisplay(f"-# Closed by {interaction.user}")))
        await interaction.message.edit(view=new_view)

        solved = interaction.channel.parent.get_tag(SOLVED_TAG_ID)
        appeal = interaction.channel.parent.get_tag(APPEAL_GG_TAG_ID)
        cb = interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
        tags = [solved]
        if appeal in interaction.channel.applied_tags:
            tags.append(appeal)
        if cb in interaction.channel.applied_tags:
            tags.append(cb)

        action_id = generate_random_id()

        await interaction.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=interaction.channel.mention, tags=tags, context=f"Close now button clicked")
        await interaction.channel.edit(archived=True, applied_tags=tags, reason=f"ID: {action_id}. {interaction.user.name} Clicked close now button")
        await remove_post_from_pending(interaction.channel_id)
        await remove_post_from_rtdr(interaction.channel_id)


    @ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="remind-cancel")
    async def on_cancel_click(self, interaction: discord.Interaction, _: ui.Button):
        text_display: discord.TextDisplay = ui.LayoutView.from_message(interaction.message).find_item(10) # type: ignore
        new_view = discord.ui.LayoutView().add_item(ui.Container(ui.TextDisplay(f"~~{text_display.content}~~"), ui.Separator(), ui.TextDisplay(f"-# Cancelled by {interaction.user}")))
        await interaction.response.edit_message(view=new_view)
        await remove_post_from_pending(interaction.channel_id)

    async def interaction_check(self, interaction: discord.Interaction[MyClient]) -> bool:
        is_owner = interaction.user.id == interaction.channel.owner_id or interaction.user.id == await get_post_creator_id(interaction.channel_id)
        if not (interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID) or is_owner):
            await interaction.response.send_message(content="Only Moderators, Community Experts, Developers and the post creator can use this.", ephemeral=True)
            return False
        return True


class CloseNowView(ui.LayoutView):
    def __init__(self, post_author: int = 0):
        super().__init__(timeout=None)

        greetings = ("Hi", "Hey", "Hello", "Hi there")
        textdisplay = ui.TextDisplay(f"{random.choice(greetings)} <@{post_author}>, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.",
                                          id=10)
        self.confirm_close_buttons = CloseNowRow()
        self.container = ui.Container()

        self.container.add_item(textdisplay)
        self.container.add_item(discord.ui.Separator())
        self.container.add_item(self.confirm_close_buttons)
        self.add_item(self.container)


class remind(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client
        self.check_for_pending_posts.start()
        self.close_pending_posts.start()
        self.check_exception_posts.start()

    def reminders_filter(self, thread: discord.Thread):
        """  
        Filter function for posts in reminder system, returns true if all of the following criteria are met:
        * Not locked, not archived
        * Doesn't have needs dev review & solved
        * Is in #support (parent_id==SUPPORT_CHANNEL_ID)
        """
        if thread.parent_id != SUPPORT_CHANNEL_ID:
            return False

        applied_tags = thread._applied_tags
        ndr = NEED_DEV_REVIEW_TAG_ID not in applied_tags
        solved = SOLVED_TAG_ID not in applied_tags
        archived = not thread.archived
        locked = not thread.locked
        return ndr and solved and archived and locked

    @commands.Cog.listener("on_ready")
    async def add_persistent_view(self):
        self.client.add_view(CloseNowView())

    async def cog_unload(self):
        self.check_for_pending_posts.cancel()
        self.close_pending_posts.cancel()
        self.check_exception_posts.cancel()

    @tasks.loop(hours=1)
    async def check_exception_posts(self):
        to_remove = []
        for post_id, tries in reminder_not_sent_posts.items():
            post = self.client.get_channel(post_id) or await self.client.fetch_channel(post_id)
            if tries < 24:
                try:
                    message: discord.Message | None = post.last_message or await post.fetch_message(post.last_message_id)
                except discord.NotFound:
                    tries+=1
                    reminder_not_sent_posts[post.id] = tries
                    continue
                if check_time_more_than_day(message.created_at.timestamp()):
                    if post.owner: # make sure the post owner is not None- still in server
                        greetings = ["Hi", "Hello", "Hey", "Hi there"]
                        await message.channel.send(content=f"{random.choice(greetings)} {post.owner.mention}, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.", view=CloseNow())
                        await add_post_to_pending(post_id=post.id)
                        to_remove.append(post.id)
                else:
                    to_remove.append(post.id)
            elif tries == 24: 
                try:
                    message = post.last_message or await post.fetch_message(post.last_message_id)
                except discord.HTTPException as e:
                    try:
                        alerts_thread = post.guild.get_channel_or_thread(ALERTS_THREAD_ID) or await post.guild.fetch_channel(ALERTS_THREAD_ID)
                    except discord.NotFound as e2:
                        raise ExceptionGroup('Tried to fetch message and Alerts Thread', [e, e2])
                    await alerts_thread.send(
                        content=f"Reminder message could not be sent to {post.mention}.\nError: `{e.text}` Error code: `{e.code}` Status: `{e.status}`"
                    )
                    reminder_not_sent_posts[post.id] += 1
                    continue
                if check_time_more_than_day(message.created_at.timestamp()):
                    await add_post_to_pending(post.id)
                else:
                    to_remove.append(post.id)
        for post_id in to_remove:
            reminder_not_sent_posts.pop(post_id)

    @tasks.loop(hours=1)
    async def check_for_pending_posts(self):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        if not support:
            return

        posts_to_add: list[int] = []
        pending_posts: list[int] = await get_pending_posts() # Cache the list to avoid DB calls every iteration of the loop
        for post in await support.guild.active_threads():
            now_dt = time_snowflake(datetime.now(UTC))
            more_than_day = check_time_more_than_day(snowflake_time(post.last_message_id or now_dt).timestamp()) # Check time before making any further API/DB calls
            if not more_than_day or post.id in reminder_not_sent_posts or post.id in pending_posts:
                continue
            if not self.reminders_filter(post):
                continue
            try:
                message: discord.Message | None = post.last_message or await post.fetch_message(post.last_message_id)
            except discord.NotFound: # message id could be for a message that was already deleted
                reminder_not_sent_posts[post.id] = 1
                continue
            except discord.HTTPException as e:
                try:
                    alerts = post.guild.get_channel_or_thread(ALERTS_THREAD_ID) or await post.guild.fetch_channel(ALERTS_THREAD_ID)
                except discord.NotFound as e2:
                    raise ExceptionGroup('Tried to fetch message and Alerts Thread', [e, e2])
                await alerts.send(content=f"Reminder message could not be sent to {post.mention}.\nError: `{e.text}` Error code: `{e.code}` Status: {e.status}")
                continue
            post_author_id = await get_post_creator_id(post.id) or post.owner_id
            author_not_owner = message.author.id != post_author_id
            if author_not_owner and message.author != self.client.user and post.owner:
                await message.channel.send(view=CloseNowView(post_author_id))
                posts_to_add.append(post.id)

        if not posts_to_add:
            return
        await bulk_add_posts_to_pending(posts_to_add)
            
    @commands.Cog.listener('on_message')
    async def remove_pending_posts(self, message: discord.Message):
        if message.author == self.client.user:
            return
        
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
            others_filter = not message.channel.locked and NEED_DEV_REVIEW_TAG_ID not in message.channel._applied_tags
            owner_id = await get_post_creator_id(message.channel.id) or message.channel.owner_id
            message_author = message.author.id == owner_id
            if message_author and others_filter and await in_pending_posts(message.channel.id):
                await remove_post_from_pending(message.channel.id)

    @tasks.loop(hours=1)
    async def close_pending_posts(self):
        posts_to_remove: list[int] = []
        pending_posts = await get_pending_posts()

        for post_id in pending_posts:
            try:
                post = self.client.get_channel(post_id) or await self.client.fetch_channel(post_id)
            except discord.NotFound:
                continue

            if not post: # check if the post was successfully fetched (not None)
                posts_to_remove.append(post_id)
                continue

            ndr = NEED_DEV_REVIEW_TAG_ID not in post._applied_tags
            if ndr and await check_post_last_message_time(post_id):
                applied_tags = post.applied_tags
                tags = [post.parent.get_tag(SOLVED_TAG_ID)]
                cb = post.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
                appeal = post.parent.get_tag(APPEAL_GG_TAG_ID)
                if cb in applied_tags: 
                    tags.append(cb)
                if appeal in post.applied_tags:
                    tags.append(appeal)
                action_id = generate_random_id()
                try:
                    await post.edit(archived=True, reason=f"ID: {action_id}. Post inactive for 2 days", applied_tags=tags) # make the post archived and add the tags
                except discord.HTTPException:
                    continue
                await self.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=post.mention, tags=tags, context="Close pending post")
                await remove_post_from_rtdr(post.id)
                posts_to_remove.append(post.id)

        if not posts_to_remove:
            return
        await bulk_remove_posts_from_pending(posts_to_remove)


    @check_for_pending_posts.before_loop
    async def cfpp_before_loop(self):
        await self.client.wait_until_ready() # only start the loop when the bot's cache is ready

    @close_pending_posts.before_loop
    async def cpp_before_loop(self):
        await self.client.wait_until_ready()
    
    @check_exception_posts.before_loop
    async def cep_before_loop(self):
        await self.client.wait_until_ready()


    @check_for_pending_posts.error
    async def cfpp_error(self, error: BaseException):
        await self.client.send_unhandled_error(error, task=self.check_for_pending_posts)

    @close_pending_posts.error
    async def cpp_error(self, error: BaseException):
        await self.client.send_unhandled_error(error, task=self.close_pending_posts)
    
    @check_exception_posts.error
    async def cep_error(self, error: BaseException):
        await self.client.send_unhandled_error(error, task=self.check_exception_posts)

async def setup(client: MyClient):
    await client.add_cog(remind(client))