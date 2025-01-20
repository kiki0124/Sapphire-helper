import discord
from discord.ext import commands, tasks
from functions import add_post_to_pending, \
    remove_post_from_pending, get_pending_posts, \
    check_post_last_message_time, check_time_more_than_day, \
    get_post_creator_id, remove_post_from_rtdr, generate_random_id
import random
from discord import ui
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
CUSTOM_BRANDING_TAG_ID = int(os.getenv("CUSTOM_BRANDING_TAG_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
UNANSWERED_TAG_ID = int(os.getenv('UNANSWERED_TAG_ID'))

reminder_not_sent_posts: dict[int, int] = {} # dictionary of post ids: the amount of tries
class CloseNow(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @ui.button(label="Issue already solved? Close post now", custom_id="remind-close-now", style=discord.ButtonStyle.grey)
    async def on_close_now_click(self, interaction: discord.Interaction, button: ui.Button):
        experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
        mods = interaction.guild.get_role(MODERATORS_ROLE_ID)
        if experts in interaction.user.roles or mods in interaction.user.roles or interaction.user == interaction.channel.owner:
            await interaction.message.edit(view=None, content=f"{interaction.message.content}\n-# Closed by {interaction.user.name}")
            tags = [interaction.channel.parent.get_tag(SOLVED_TAG_ID)]
            if interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in interaction.channel.applied_tags:
                tags.append(interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
            action_id = generate_random_id()
            await interaction.channel.edit(applied_tags=tags, archived=True, reason=f"ID: {action_id}. {interaction.user.name} Clicked close now button")
            alerts_thread = interaction.guild.get_channel_or_thread(ALERTS_THREAD_ID)
            await alerts_thread.send(content=f"ID: {action_id}\nPost: {interaction.channel.mention}\nTags: {','.join([tag.name for tag in tags])}\nContext: Close now button clicked")
            await remove_post_from_pending(interaction.channel.id)
        else:
            await interaction.response.send_message(content="Only Moderators, Community Experts and the post creator can use this.", ephemeral=True)

class remind(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.check_for_pending_posts.start()
        self.close_pending_posts.start()
        self.check_exception_posts.start()
        self.unanswered = discord.Object(id=UNANSWERED_TAG_ID)
        self.needs_dev_review = discord.Object(id=NEED_DEV_REVIEW_TAG_ID)
        self.solved = discord.Object(id=SOLVED_TAG_ID)
        self.cb = discord.Object(CUSTOM_BRANDING_TAG_ID)


    async def reminders_filter(self, thread: discord.Thread):
        """  
        Filter function for posts in reminder system, returns true if all of the following criteria are met:
        * Not locked, not archived
        * Doesn't have needs dev review & solved
        * Is in #support (parent_id==SUPPORT_CHANNEL_ID)
        """
        ndr = not self.needs_dev_review in thread.applied_tags
        solved = not self.solved in thread.applied_tags
        archived = not thread.archived
        locked = not thread.locked
        support = thread.parent_id == SUPPORT_CHANNEL_ID
        return ndr and solved and archived and locked and support
    
    async def send_action_log(self, action_id: str, post_mention: str, tags: list[discord.Object], context: str):
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        tag_names = [support.get_tag(tag.id).name for tag in tags]
        await alerts_thread.send(content=f"ID: {action_id}\nPost: {post_mention}\nTags: {','.join(tag_names)}\nContext: {context}")

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
                    message: discord.Message|None = await post.fetch_message(post.last_message_id)
                except discord.NotFound:
                    tries+=1
                    reminder_not_sent_posts[post.id] = tries
                    continue
                if check_time_more_than_day(message.created_at.timestamp()):
                    if post.owner: # make sure the post owner is not None- still in server
                        greetings = ["Hi", "Hello", "Hey", "Hi there"]
                        await message.channel.send(content=f"{random.choices(greetings)[0]} {post.owner.mention}, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.", view=CloseNow())
                        await add_post_to_pending(post_id=post.id, timestamp=datetime.datetime.now(tz=datetime.datetime.now().astimezone().tzinfo).timestamp())
                        to_remove.append(post.id)
                        continue
                    else:
                        continue
                else:
                    to_remove.append(post.id)
                    continue
            elif tries == 24: 
                try:
                    message = await post.fetch_message(post.last_message_id)
                except discord.HTTPException as e:
                    alerts_thread = post.guild.get_channel_or_thread(ALERTS_THREAD_ID)
                    await alerts_thread.send(
                        content=f"Reminder message could not be sent to {post.mention}.\nError: `{e.text}` Error code: `{e.code}` Status: `{e.status}`"
                    )
                    reminder_not_sent_posts[post.id] += 1
                    continue
                if check_time_more_than_day(message.created_at.timestamp()):
                    await add_post_to_pending(post.id, datetime.datetime.now(tz=datetime.datetime.now().astimezone().tzinfo).timestamp())
                    continue
                else:
                    to_remove.append(post.id)
                    continue
        for post_id in to_remove:
            reminder_not_sent_posts.pop(post_id)

    @tasks.loop(hours=1)
    async def check_for_pending_posts(self):
        channel = self.client.get_channel(SUPPORT_CHANNEL_ID)
        for post in await channel.guild.active_threads():
            if await self.reminders_filter(post): # reminders_filter includes all criteria for a post (tags, state, parent channel...)
                if post.id not in await get_pending_posts() and post.id not in reminder_not_sent_posts:
                    try:
                        message: discord.Message|None = await post.fetch_message(post.last_message_id)
                    except discord.NotFound: # message id could be for a message that was already deleted
                        reminder_not_sent_posts[post.id] = 1
                        continue
                    except discord.HTTPException as e:
                        alerts = post.guild.get_channel_or_thread(ALERTS_THREAD_ID)
                        await alerts.send(content=f"Reminder message could not be sent to {post.mention}.\nError: `{e.text}` Error code: `{e.code}` Status: {e.status}")
                        continue
                    author_not_owner = message.author != post.owner
                    more_than_day = check_time_more_than_day(message.created_at.timestamp())
                    if author_not_owner and more_than_day:
                        if post.owner: # make sure post owner isn't None- still in server
                            greetings = ["Hi", "Hello", "Hey", "Hi there"]
                            post_author_id = await get_post_creator_id(post.id) or post.owner_id
                            await message.channel.send(content=f"{random.choices(greetings)[0]} <@{post_author_id}>, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.", view=CloseNow())
                            await add_post_to_pending(post_id=post.id, timestamp=datetime.datetime.now(tz=datetime.datetime.now().astimezone().tzinfo).timestamp())
            
    @commands.Cog.listener('on_message')
    async def remove_pending_posts(self, message: discord.Message):
        if message.author != self.client.user:
            if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
                others_filter = not message.channel.locked and not self.needs_dev_review in message.channel.applied_tags
                message_author = message.author == message.channel.owner or message.author.id == await get_post_creator_id(message.channel.id)
                in_pending_post = message.channel.id in await get_pending_posts()
                if message_author and in_pending_post and others_filter:
                    await remove_post_from_pending(message.channel.id)
                
    @tasks.loop(hours=1)
    async def close_pending_posts(self):
        for post_id in await get_pending_posts():
            post = self.client.get_channel(post_id)
            if post: # check if the post was successfully fetched (not None)
                ndr = self.needs_dev_review in post.applied_tags
                more_than_24_hours = await check_post_last_message_time(post_id)
                if ndr and more_than_24_hours:
                    tags = [self.solved]
                    if self.cb in post.applied_tags: tags.append(self.cb)
                    action_id = generate_random_id()
                    await post.edit(archived=True, reason=f"ID: {action_id}. Post inactive for 2 days", applied_tags=tags) # make the post archived and add the tags
                    await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=tags, context="Close pending post")
                    await remove_post_from_pending(post.id)
                    await remove_post_from_rtdr(post.id)
            else:
                    await remove_post_from_pending(post_id)
                    continue

    @check_for_pending_posts.before_loop
    @close_pending_posts.before_loop
    @check_exception_posts.before_loop
    async def loops_before_loop(self):
        await self.client.wait_until_ready() # only start the loop when the bot's cache is ready

async def setup(client):
    await client.add_cog(remind(client))
