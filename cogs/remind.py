from __future__ import annotations

import discord
from discord.ext import commands, tasks
from functions import add_post_to_pending, \
    remove_post_from_pending, get_pending_posts, \
    check_post_last_message_time, check_time_more_than_day,\
    get_post_creator_id, remove_post_from_rtdr, generate_random_id, in_pending_posts
import random
from discord import ui
from datetime import datetime, timezone
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

class CloseNow(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @ui.button(label="Issue already solved? Close post now", custom_id="remind-close-now", style=discord.ButtonStyle.grey)
    async def on_close_now_click(self, interaction: discord.Interaction, button: ui.Button):
        is_owner = interaction.user.id == interaction.channel.owner_id or interaction.user.id == await get_post_creator_id(interaction.channel_id)
        if interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID) or is_owner:
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
            try:
                alerts_thread = interaction.guild.get_channel_or_thread(ALERTS_THREAD_ID) or await interaction.guild.fetch_channel(ALERTS_THREAD_ID)
            except discord.NotFound as e:
                raise e
            if alerts_thread.archived:
                await alerts_thread.edit(archived=False)
            await alerts_thread.send(content=f"ID: {action_id}\nPost: {interaction.channel.mention}\nTags: {','.join([tag.name for tag in tags])}\nContext: Close now button clicked")
            await remove_post_from_pending(interaction.channel_id)
            await remove_post_from_rtdr(interaction.channel_id)
        else:
            await interaction.response.send_message(content="Only Moderators, Community Experts and the post creator can use this.", ephemeral=True)

class remind(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client
        self.check_for_pending_posts.start()
        self.close_pending_posts.start()
        self.check_exception_posts.start()

    async def reminders_filter(self, thread: discord.Thread):
        """  
        Filter function for posts in reminder system, returns true if all of the following criteria are met:
        * Not locked, not archived
        * Doesn't have needs dev review & solved
        * Is in #support (parent_id==SUPPORT_CHANNEL_ID)
        """
        if thread.parent_id == SUPPORT_CHANNEL_ID:
            applied_tags = thread._applied_tags
            ndr = NEED_DEV_REVIEW_TAG_ID not in applied_tags
            solved = SOLVED_TAG_ID not in applied_tags
            archived = not thread.archived
            locked = not thread.locked
            return ndr and solved and archived and locked
        else:
            return False
        
    async def send_action_log(self, action_id: str, post_mention: str, tags: list[discord.ForumTag], context: str):
        if self.client.alert_webhook_url is not None:
            webhook = discord.Webhook.from_url(self.client.alert_webhook_url, client=self.client)
            try:
                await webhook.send(
                    content=f"ID: {action_id}\nPost: {post_mention}\nTags: {', '.join([tag.name for tag in tags])}\nContext: {context}",
                    username=self.client.user.name,
                    avatar_url=self.client.user.display_avatar.url,
                    thread=discord.Object(id=ALERTS_THREAD_ID),
                    wait=False
                )
                return
            except Exception:
                pass #pass so that it can try the other methods below
        try:
            alerts_thread = self.client.get_channel(ALERTS_THREAD_ID) or await self.client.fetch_channel(ALERTS_THREAD_ID)
        except discord.NotFound as e:
            raise e
        if alerts_thread.archived:
            await alerts_thread.edit(archived=False)
        webhooks = [webhook for webhook in await alerts_thread.parent.webhooks() if webhook.token]
        try:
            webhook = webhooks[0]
        except IndexError:
            webhook = await alerts_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        await webhook.send(
            content=f"ID: {action_id}\nPost: {post_mention}\nTags: {', '.join([tag.name for tag in tags])}\nContext: {context}",
            username=self.client.user.name,
            avatar_url=self.client.user.display_avatar.url,
            thread=discord.Object(id=ALERTS_THREAD_ID),
            wait=False
        )
        self.client.alert_webhook_url = webhook.url #Assign only if the url is None. This should normally only be called once when running the bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.client.add_view(CloseNow())

    async def cog_unload(self):
        self.check_for_pending_posts.cancel()
        self.close_pending_posts.cancel()
        self.check_exception_posts.cancel()

    @tasks.loop(hours=1)
    async def check_exception_posts(self):
        to_remove = []
        for post_id, tries in reminder_not_sent_posts.items():
            post = self.client.get_channel(post_id)
            if tries < 24:
                try:
                    message: discord.Message|None = post.last_message or await post.fetch_message(post.last_message_id)
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
                        continue
                else:
                    to_remove.append(post.id)
                    continue
            elif tries == 24: 
                try:
                    message = post.last_message or await post.fetch_message(post.last_message_id)
                except discord.HTTPException as e:
                    try:
                        alerts_thread = post.guild.get_channel_or_thread(ALERTS_THREAD_ID) or await post.guild.fetch_channel(ALERTS_THREAD_ID)
                    except discord.NotFound as e2:
                        raise ExceptionGroup('Tried to fetch message and Alerts Thread', [e, e2])
                    if alerts_thread.archived:
                        await alerts_thread.edit(archived=False)
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
        if support:
            pending_posts: list[int] = await get_pending_posts() # Cache the list to avoid DB calls every iteration of the loop
            for post in await support.guild.active_threads():
                now_dt = time_snowflake(datetime.now(timezone.utc))
                more_than_day = check_time_more_than_day(snowflake_time(post.last_message_id or now_dt).timestamp()) # Check time before making any further API/DB calls
                if not more_than_day:
                    continue
                if await self.reminders_filter(post): # reminders_filter includes all criteria for a post (tags, state, parent channel...)
                    if post.id not in reminder_not_sent_posts and post.id not in pending_posts:
                        try:
                            message: discord.Message|None = post.last_message or await post.fetch_message(post.last_message_id)
                        except discord.NotFound: # message id could be for a message that was already deleted
                            reminder_not_sent_posts[post.id] = 1
                            continue
                        except discord.HTTPException as e:
                            try:
                                alerts = post.guild.get_channel_or_thread(ALERTS_THREAD_ID) or await post.guild.fetch_channel(ALERTS_THREAD_ID)
                            except discord.NotFound as e2:
                                raise ExceptionGroup('Tried to fetch message and Alerts Thread', [e, e2])
                            if alerts.archived:
                                await alerts.edit(archived=False)
                            await alerts.send(content=f"Reminder message could not be sent to {post.mention}.\nError: `{e.text}` Error code: `{e.code}` Status: {e.status}")
                            continue
                        post_author_id = await get_post_creator_id(post.id) or post.owner_id
                        author_not_owner = message.author.id != post_author_id
                        if author_not_owner and message.author != self.client.user:
                            if post.owner: # make sure post owner isn't None- still in server
                                greetings = ["Hi", "Hello", "Hey", "Hi there"]
                                await message.channel.send(content=f"{random.choice(greetings)} <@{post_author_id}>, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.", view=CloseNow())
                                await add_post_to_pending(post_id=post.id)
            
    @commands.Cog.listener('on_message')
    async def remove_pending_posts(self, message: discord.Message):
        if message.author != self.client.user:
            if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
                others_filter = not message.channel.locked and NEED_DEV_REVIEW_TAG_ID not in message.channel._applied_tags
                owner_id = await get_post_creator_id(message.channel.id) or message.channel.owner_id
                message_author = message.author.id == owner_id
                in_pending_post = await in_pending_posts(message.channel.id)
                if message_author and in_pending_post and others_filter:
                    await remove_post_from_pending(message.channel.id)

    @tasks.loop(hours=1)
    async def close_pending_posts(self):
        for post_id in await get_pending_posts():
            post = self.client.get_channel(post_id)
            if post: # check if the post was successfully fetched (not None)
                ndr = NEED_DEV_REVIEW_TAG_ID not in post._applied_tags
                more_than_24_hours = await check_post_last_message_time(post_id)
                if ndr and more_than_24_hours:
                    applied_tags = post.applied_tags
                    tags = [post.parent.get_tag(SOLVED_TAG_ID)]
                    cb = post.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
                    appeal = post.parent.get_tag(APPEAL_GG_TAG_ID)
                    if cb in applied_tags: 
                        tags.append(cb)
                    if appeal in post.applied_tags:
                        tags.append(appeal)
                    action_id = generate_random_id()
                    await post.edit(archived=True, reason=f"ID: {action_id}. Post inactive for 2 days", applied_tags=tags) # make the post archived and add the tags
                    await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=tags, context="Close pending post")
                    await remove_post_from_pending(post.id)
                    await remove_post_from_rtdr(post.id)
            else:
                await remove_post_from_pending(post_id)


    @check_for_pending_posts.before_loop
    async def cfpp_before_loop(self):
        await self.client.wait_until_ready() # only start the loop when the bot's cache is ready

    @close_pending_posts.before_loop
    async def cpp_before_loop(self):
        await self.client.wait_until_ready()
    
    @check_exception_posts.before_loop
    async def cep_before_loop(self):
        await self.client.wait_until_ready()

async def setup(client):
    await client.add_cog(remind(client))