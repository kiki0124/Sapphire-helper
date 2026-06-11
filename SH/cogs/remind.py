from __future__ import annotations

import discord
from discord.ext import commands, tasks
from functions import remove_post_from_pending, get_pending_posts, \
    check_post_last_message_time, check_time_more_than,\
    get_post_creator_id, remove_post_from_rtdr, generate_random_id, in_pending_posts, bulk_add_posts_to_pending, bulk_remove_posts_from_pending
import random
from discord import ui
from datetime import datetime, timedelta, UTC
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

class CloseNow(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @ui.button(label="Issue already solved? Close post now", custom_id="remind-close-now", style=discord.ButtonStyle.grey)
    async def on_close_now_click(self, interaction: discord.Interaction, button: ui.Button):
        is_owner = interaction.user.id == interaction.channel.owner_id or interaction.user.id == await get_post_creator_id(interaction.channel_id)
        if not (interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID) or is_owner):
            await interaction.response.send_message(content="Only Moderators, Community Experts and the post creator can use this.", ephemeral=True)
            return
        await interaction.message.edit(view=None, content=f"{interaction.message.content}\n-# Closed by {interaction.user.name}")
        tags = [interaction.channel.parent.get_tag(SOLVED_TAG_ID)]
        cb = interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
        appeal = interaction.channel.parent.get_tag(APPEAL_GG_TAG_ID)
        if cb in interaction.channel.applied_tags:
            tags.append(cb)
        if appeal in interaction.channel.applied_tags:
            tags.append(appeal)
        action_id = generate_random_id()
        await interaction.channel.edit(applied_tags=tags, reason=f"ID: {action_id}. {interaction.user.name} Clicked close now button", archived=True)

        alerts_thread = interaction.guild.get_channel_or_thread(ALERTS_THREAD_ID) or await interaction.guild.fetch_channel(ALERTS_THREAD_ID)
        await alerts_thread.send(content=f"ID: {action_id}\nPost: {interaction.channel.mention}\nTags: {','.join([tag.name for tag in tags])}\nContext: Close now button clicked")
        await remove_post_from_pending(interaction.channel_id)
        if interaction.channel.owner_id == interaction.client.user.id:
            await remove_post_from_rtdr(interaction.channel_id)

class remind(commands.Cog):
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
        self.client.add_view(CloseNow())

    async def cog_load(self):
        self.reminders_loop.start()

    async def cog_unload(self):
        self.reminders_loop.cancel()


    @tasks.loop(minutes=1)
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
        print(f"Posts: {len(posts)}")
        if posts:
            await self.close_abandoned_posts(posts, support_channel)
            await self.check_for_pending_posts(posts)
        print(f"Posts after: {len(posts)}")


    async def close_abandoned_posts(self, posts: list[discord.Thread], support_channel: discord.ForumChannel):
        for i in range(len(posts) - 1, -1, -1):
            post = posts[i]
            if post.parent_id != SUPPORT_CHANNEL_ID or post.locked or NEED_DEV_REVIEW_TAG_ID in post._applied_tags:
                continue

            owner_id = post.owner_id if post.owner_id != self.client.user.id else await get_post_creator_id(post.id)
            if owner_id:
                try:
                    member_or_member_id = self.client.get_member_id(owner_id) or await post.guild.fetch_member(owner_id)
                    if isinstance(member_or_member_id, discord.Member):
                        self.client.add_member_to_cache(member_or_member_id)
                except discord.NotFound:
                    pass
                else:
                    # owner still in server, we skip
                    continue

            tags = [support_channel.get_tag(SOLVED_TAG_ID)]
            cb = support_channel.get_tag(CUSTOM_BRANDING_TAG_ID)
            appeal = support_channel.get_tag(APPEAL_GG_TAG_ID)
            if CUSTOM_BRANDING_TAG_ID in post._applied_tags: 
                tags.append(cb)
            if APPEAL_GG_TAG_ID in post._applied_tags:
                tags.append(appeal)
            action_id = generate_random_id()
            await post.send("This post was automatically marked as **Solved** because the post creator left the server.")
            await post.edit(archived=True, reason=f"ID: {action_id}. User left server, auto close post", applied_tags=tags)
            await self.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=post.mention, tags=tags, context="Post creator left the server")
            del posts[i] # remove from the post so that check_for_pending_posts won't need to check for it

        
    async def check_for_pending_posts(self, posts: list[discord.Thread]):
        posts_to_add: list[int] = []
        pending_posts: list[int] = await get_pending_posts() # Cache the list to avoid DB calls every iteration of the loop
        for post in posts:
            now_dt = time_snowflake(datetime.now(UTC))
            more_than_day = check_time_more_than(snowflake_time(post.last_message_id or now_dt).timestamp(), timedelta(seconds=30)) # Check time before making any further API/DB calls
            if not more_than_day or post.id in pending_posts:
                continue
            if not self.reminders_filter(post):
                continue

            try:
                last_message: discord.Message | None = post.last_message or await post.fetch_message(post.last_message_id)
            except discord.NotFound:
                # if we can't fetch the message and it's been 7 days
                # doesn't matter whether the last message is from the owner or from other users
                # we will just send this reminder
                if not check_time_more_than(snowflake_time(post.last_message_id or now_dt).timestamp(), timedelta(seconds=60)):
                    continue
                time_ago = "2 days"
                post_author_id = await get_post_creator_id(post.id) or post.owner_id
            else:
                time_ago = "24 hours"
                post_author_id = await get_post_creator_id(post.id) or post.owner_id
                if last_message.author.id == post_author_id or last_message.author == self.client.user:
                    continue
            greetings = ["Hi", "Hello", "Hey", "Hi there"]
            await post.send(content=f"{random.choice(greetings)} <@{post_author_id}>, it seems like your last message was sent more than {time_ago} ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.", view=CloseNow())
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
        pending_posts = await get_pending_posts()

        for post_id in pending_posts:
            try:
                post = self.client.get_channel(post_id) or await self.client.fetch_channel(post_id)
            except discord.NotFound:
                await remove_post_from_rtdr(post.id)
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
                if post.owner_id == self.client.user.id:
                    await remove_post_from_rtdr(post.id)
                posts_to_remove.append(post.id)

        if not posts_to_remove:
            return
        await bulk_remove_posts_from_pending(posts_to_remove)


    @reminders_loop.before_loop
    async def reminders_loop_before(self):
        await self.client.wait_until_ready() # only start the loop when the bot's cache is ready

async def setup(client: MyClient):
    await client.add_cog(remind(client))