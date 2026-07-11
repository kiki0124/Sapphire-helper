from __future__ import annotations

import discord
from discord.ext import commands, tasks
from functions import remove_post_from_pending, get_pending_posts, \
    get_pending_posts_and_timestamps, check_time_more_than,\
    get_post_creator_id, remove_post_from_rtdr, generate_random_id, \
    in_pending_posts, bulk_add_posts_to_pending, bulk_remove_posts_from_pending
import random
from discord import ui
from datetime import timedelta
import os
from dotenv import load_dotenv
from typing import TYPE_CHECKING
from discord.utils import snowflake_time

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


class CloseNowRow(ui.ActionRow):
    def __init__(self):
        super().__init__()
        self.is_owner: bool = False

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
    async def on_cancel_click(self, interaction: discord.Interaction[MyClient], _: ui.Button):
        text_display: discord.TextDisplay = ui.LayoutView.from_message(interaction.message).find_item(10) # type: ignore
        footer = f"-# Cancelled by {interaction.user}"
        if SOLVED_TAG_ID in interaction.channel._applied_tags:
            footer += f" | Use </unsolve:{await interaction.client.get_unsolve_id()}> to unsolve"
        new_view = discord.ui.LayoutView().add_item(ui.Container(ui.TextDisplay(f"~~{text_display.content}~~"), ui.Separator(), ui.TextDisplay(footer)))
        await interaction.response.edit_message(view=new_view)
        await remove_post_from_pending(interaction.channel_id)

        if self.is_owner:
            description = "Please send a message here explaining what you still need help with."
            footer = f"-# When the issue is resolved, you may use </solved:{await interaction.client.get_solved_id()}> to mark it as solved."
            view = ui.LayoutView().add_item(ui.Container(ui.TextDisplay(description), ui.Separator(), ui.TextDisplay(footer)))
            await interaction.message.reply(view=view)

    async def interaction_check(self, interaction: discord.Interaction[MyClient]) -> bool:
        self.is_owner = interaction.user.id == interaction.channel.owner_id or interaction.user.id == await get_post_creator_id(interaction.channel_id)
        if not (interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID) or self.is_owner):
            await interaction.response.send_message(content="Only Moderators, Community Experts, Developers and the post creator can use this.", ephemeral=True)
            return False
        return True


class CloseNowView(ui.LayoutView):
    def __init__(self, post_author: int = 0, *, time_ago: str = "..."):
        super().__init__(timeout=None)

        greetings = ("Hi", "Hey", "Hello", "Hi there")
        textdisplay = ui.TextDisplay(
            f"{random.choice(greetings)} <@{post_author}>, it seems like your last message was sent more than {time_ago} ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.",
                                    id=10)
        self.confirm_close_buttons = CloseNowRow()
        self.container = ui.Container()

        self.container.add_item(textdisplay)
        self.container.add_item(discord.ui.Separator())
        self.container.add_item(self.confirm_close_buttons)
        self.add_item(self.container)


class Reminders(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client

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

    async def cog_load(self):
        self.reminders_loop.start()

    async def cog_unload(self):
        self.reminders_loop.cancel()

    @tasks.loop(hours=1)
    async def reminders_loop(self):
        """
        This task consists of 3 'loops':
        - close_abandoned_posts
        - check_for_pending_posts
        - close_pending_posts
        """
        await self.close_pending_posts()
        support_channel = self.client.get_channel(SUPPORT_CHANNEL_ID)
        if not support_channel:
            return

        posts = await support_channel.guild.active_threads()
        if posts:
            await self.close_abandoned_posts(posts)
            await self.check_for_pending_posts(posts)

    async def close_abandoned_posts(self, posts: list[discord.Thread]):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        if not support:
            return

        for i in range(len(posts) - 1, -1, -1): # we need to do this so that we don't modify the rest of the list when we remove a post
            post = posts[i]
            if post.parent_id != SUPPORT_CHANNEL_ID or post.locked or NEED_DEV_REVIEW_TAG_ID in post._applied_tags:
                continue
            
            if SOLVED_TAG_ID in post._applied_tags: # /solved could've been used as the post doesn't get archived immediately
                del posts[i]
                continue

            owner = post.guild.get_member(await get_post_creator_id(post.id)) or post.owner
            if owner is not None: # post owner/creator will be None if they left the server
                continue

            tags = [support.get_tag(SOLVED_TAG_ID)]
            cb = support.get_tag(CUSTOM_BRANDING_TAG_ID)
            appeal = support.get_tag(APPEAL_GG_TAG_ID)
            if CUSTOM_BRANDING_TAG_ID in post._applied_tags: 
                tags.append(cb)
            if APPEAL_GG_TAG_ID in post._applied_tags:
                tags.append(appeal)
            action_id = generate_random_id()
            await post.send("This post was automatically marked as **Solved** because the post creator left the server.")
            await post.edit(archived=True, reason=f"ID: {action_id}. Post creator left the server, auto close post", applied_tags=tags)
            await self.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=post.mention, tags=tags, context="Post creator left the server")
            del posts[i] # remove from the post so that check_for_pending_posts won't need to check for it


    async def check_for_pending_posts(self, posts: list[discord.Thread]):
        posts_to_add: list[int] = []
        pending_posts: list[int] = await get_pending_posts() # Cache the list to avoid DB calls every iteration of the loop
        for post in posts:
            if not post.last_message_id: # no message was ever sent?? This should realistically never happen for threads
                continue

            last_msg_timestamp = snowflake_time(post.last_message_id).timestamp()
            more_than_day = check_time_more_than(last_msg_timestamp,
                                                timedelta(days=1)) # Check time before making any further API/DB calls
            if not more_than_day or post.id in pending_posts:
                continue
            if not self.reminders_filter(post):
                continue

            post_author_id = await get_post_creator_id(post.id) or post.owner_id
            
            # If the last message > 3d, we send the reminder regardless of other requirements
            if check_time_more_than(last_msg_timestamp, timedelta(days=3)):
                await post.send(view=CloseNowView(post_author_id, time_ago="3 days"))
                posts_to_add.append(post.id)
                continue

            # from here on, we already know last_message is (> 1d ago) but (< 3d ago)
            try:
                last_message: discord.Message = post.last_message or await post.fetch_message(post.last_message_id)
            except discord.NotFound:
                continue
            else:
                # skip if the last message is the message author themselves
                if last_message.author.id == post_author_id:
                    continue

            await post.send(view=CloseNowView(post_author_id, time_ago="24 hours"))
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


    async def close_pending_posts(self):
        posts_to_remove: list[int] = []
        pending_posts = await get_pending_posts_and_timestamps()

        for post_id, timestamp in pending_posts:
            # only close posts that have been pending for > 1 day
            if not check_time_more_than(timestamp, timedelta(days=1)):
                continue

            try:
                post = self.client.get_channel(post_id) or await self.client.fetch_channel(post_id)
            except discord.NotFound:
                await remove_post_from_rtdr(post.id)
                posts_to_remove.append(post_id)
                continue

            if NEED_DEV_REVIEW_TAG_ID not in post._applied_tags:
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
                    await post.edit(archived=True, 
                                    reason=f"ID: {action_id}. Post inactive for too long.", 
                                    applied_tags=tags) # type: ignore
                except discord.HTTPException:
                    continue
                await self.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=post.mention, tags=tags, 
                                           context=f"Close pending post")
                await remove_post_from_rtdr(post.id)
                posts_to_remove.append(post.id)

        if not posts_to_remove:
            return
        await bulk_remove_posts_from_pending(posts_to_remove)


    @reminders_loop.before_loop
    async def reminders_loop_before_loop(self):
        await self.client.wait_until_ready() # only start the loop when the bot's cache is ready

    @reminders_loop.error
    async def reminders_loop_error(self, error: BaseException):
        await self.client.send_unhandled_error(error, task=self.reminders_loop)


async def setup(client: MyClient):
    await client.add_cog(Reminders(client))