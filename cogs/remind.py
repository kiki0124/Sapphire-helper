import discord
from discord.ext import commands, tasks
from functions import AddPostToPending, RemovePostFromPending, GetPendingPosts, CheckPostLastMessageTime, CheckTimeMoreThanDay
import random
from discord import ui
import datetime
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
CUSTOM_BRANDING_TAG_ID = int(os.getenv("CUSTOM_BRANDING_TAG_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
WAITING_FOR_REPLY_TAG_ID = int(os.getenv("WAITING_FOR_REPLY_TAG_ID"))
NOT_SOLVED_TAG_ID = int(os.getenv("NOT_SOLVED_TAG_ID"))
UNANSWERED_TAG_ID = int(os.getenv('UNANSWERED_TAG_ID'))

reminder_not_sent_posts: dict[int, int] = {} # declare a dictionary of post ids: the amount of tries
waiting_for_reply_posts: dict[int, asyncio.Task] = {} # declare a dictionary of post ids: the task for each post, used to know when to add the wiating for reply tag to posts


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
            await interaction.channel.edit(applied_tags=tags, archived=True, reason=f"{interaction.user.name} Clicked close now button")
            RemovePostFromPending(interaction.channel.id)
        else:
            await interaction.response.send_message(content="Only Moderators, Community Experts and the post creator can use this.", ephemeral=True)

class remind(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client
        self.SendReminders.start() # start the loop
        self.ClosePendingPosts.start() # start the loop
        self.CheckExceptionPosts.start()

    @commands.Cog.listener()
    async def on_ready(self):
        self.client.add_view(CloseNow())

    async def cog_unload(self):
        self.SendReminders.cancel() # cancel the loop as the cog was unloaded
        self.ClosePendingPosts.cancel() # cancel the loop as the cog was unloaded
        self.CheckExceptionPosts.cancel()

    async def AddWaitingForOpTag(post: discord.Thread):
        await asyncio.sleep(600)
        tags = [post.parent.get_tag(NOT_SOLVED_TAG_ID), post.parent.get_tag(WAITING_FOR_REPLY_TAG_ID)]
        if post.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in post.applied_tags:
            tags.append(post.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
        await post.edit(applied_tags=tags)
        waiting_for_reply_posts.pop(post.id)

    @tasks.loop(hours=1)
    async def CheckExceptionPosts(self):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        to_remove = []
        for post_id, tries in reminder_not_sent_posts.items():
            post = support.guild.get_thread(post_id)
            if tries < 24:
                try:
                    message: discord.Message|None = await post.fetch_message(post.last_message_id)
                except discord.NotFound:
                    tries+=1
                    reminder_not_sent_posts[post.id] = tries
                    continue
                if CheckTimeMoreThanDay(message.created_at.replace(tzinfo=None)):
                    if post.owner:
                        greetings = ["Hi", "Hello", "Hey", "Hi there"]
                        await message.channel.send(content=f"{random.choices(greetings)[0]} {post.owner.mention}, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.", view=CloseNow())
                        AddPostToPending(post_id=post.id, time=message.created_at.replace(second=0, microsecond=0))
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
                    experts_channel = post.guild.get_thread(ALERTS_THREAD_ID) # get the sapphire-experts channel
                    await experts_channel.send( # send a message to the channel with the content below this comment
                        content=f"Reminder message could not be sent to {post.mention}.\nError: `{e.text}` Error code: `{e.code}` Status: `{e.status}`"
                    )
                    continue
                if CheckTimeMoreThanDay(message.created_at.replace(tzinfo=None)):
                    AddPostToPending(post.id, datetime.datetime.now(tz=None))
                    continue
                else:
                    to_remove.append(post.id)
                    continue
        for post_id in to_remove:
            reminder_not_sent_posts.pop(post_id)

    @tasks.loop(hours=1)
    async def SendReminders(self):
        channel = self.client.get_channel(SUPPORT_CHANNEL_ID) # get the channel
        solved_tag = channel.get_tag(SOLVED_TAG_ID)
        need_dev_review_tag = channel.get_tag(NEED_DEV_REVIEW_TAG_ID)
        for post in channel.threads: # start a loop for threads in the channel threads
            if not post.locked and not post.archived: # check if the post is not locked and not archived
                if need_dev_review_tag not in post.applied_tags and solved_tag not in post.applied_tags: # Make sure the post isn't already solved, doesn't have need dev review
                    if post.id not in GetPendingPosts() and post.id not in reminder_not_sent_posts: # check if the post isn't already marked as closing pending
                        try:
                            message: discord.Message|None = await post.fetch_message(post.last_message_id) # try to fetch the message
                        except discord.NotFound: # create an exception for cases where the message couldn't be fetched
                            reminder_not_sent_posts[post.id] = 1
                            continue # Continue to the next iteration of the loop
                        except discord.HTTPException as e:
                            alerts = post.guild.get_thread(1290009354589962371)
                            await alerts.send(content=f"Reminder message could not be sent to {post.mention}.\nError: `{e.text}` Error code: `{e.code}` Status: {e.status}")
                            continue
                        if message.author != post.owner: # checks if the last message's author is post creator
                            if CheckTimeMoreThanDay(time=message.created_at.replace(microsecond=0, tzinfo=None)): # checks if the time of the message is more than 24 hours ago
                                if post.owner: # make sure the post owner is in the cache
                                    greetings = ["Hi", "Hello", "Hey", "Hi there"]
                                    await message.channel.send(content=f"{random.choices(greetings)[0]} {post.owner.mention}, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.", view=CloseNow())
                                    AddPostToPending(post_id=post.id, time=message.created_at.replace(second=0, microsecond=0))
    
    async def PendingPostsListener(self, message: discord.Message):
        if message.channel.id in GetPendingPosts():
            if message.author == message.channel.owner:
                RemovePostFromPending(message.channel.id) # Remove the message from pending list as the 
                
    async def AddRemoveWaitingTag(self, message: discord.Message):
        if not message.channel.parent.get_tag(UNANSWERED_TAG_ID) in message.channel.applied_tags:
            waiting_for_reply = message.channel.parent.get_tag(WAITING_FOR_REPLY_TAG_ID)
            if waiting_for_reply in message.channel.applied_tags and message.author != message.channel.owner: # check if the post has waiting for reply tag and the author of the message is op
                tags = [message.channel.parent.get_tag(NOT_SOLVED_TAG_ID)]
                cb = message.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
                if cb in message.channel.applied_tags:
                    tags.append(cb) # add cb tag to the tags list
                await message.channel.edit(applied_tags=tags) # edit the channel to remove waiting for reply tag
            if waiting_for_reply not in message.channel.applied_tags and message.author == message.channel.owner: # check if the post doesn't have waiting for reply tag and the message author isn't op
                task = asyncio.create_task(self.AddWaitingForOpTag(message.channel)) # create a new task with the AddWaitingForOpTag coroutine
                waiting_for_reply_posts[message.channel.id] = task # add the task with the channel to the dict
            if waiting_for_reply not in message.channel.applied_tags and message.author != message.channel.owner and message.channel.id in waiting_for_reply_posts.keys():
                waiting_for_reply_posts.pop(message.channel.id) # remove the channel from the list
            else:
                return # any other scenario, ignore the message
        else:
            return # Ignore as the message channel has unanswered tag
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if isinstance(message.channel, discord.Thread): # check if the message was sent in a thread
            if message.channel.parent_id == SUPPORT_CHANNEL_ID: # check if the thread's parent is #support
                need_dev_review = message.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
                if not message.channel.locked and not need_dev_review in message.channel.applied_tags: # check if the post doesn't have ndr and isn't locked
                    await self.AddRemoveWaitingTag(message) # call the AddRmoveWaitingTag coroutine to add/remove the waiting for op tag based on the need
                    await self.PendingPostsListener(message) # call the PendingPostsListener coroutien that is related to the reminder system

    @tasks.loop(hours=1)
    async def ClosePendingPosts(self):
        for post_id in GetPendingPosts(): # loop through all posts that have closing pending status
            post = self.client.get_channel(post_id)
            if post: # check if the post was successfully fetched (not None)
                need_dev_review_tag = post.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
                if need_dev_review_tag not in post.applied_tags:
                    if CheckPostLastMessageTime(post_id): # check if the last message was sent more than 48 hours ago (24 hours after the reminder message)
                        tags = [post.parent.get_tag(SOLVED_TAG_ID)]
                        if post.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in post.applied_tags:
                            tags.append(CUSTOM_BRANDING_TAG_ID)
                        await post.edit(archived=True, reason="post inactive for 2 days", applied_tags=tags) # make the post archived and add the tags
                        RemovePostFromPending(post.id) # remove post from pending as it was closed
                    else:
                        continue # the last message is not yet 48 hours ago, continue to the next post
                else:
                    RemovePostFromPending(post_id) # remove the post from pending list as it has ndr tag
                    continue # continue to the next post
            else:
                continue # The post couldn't be fetched, most likely deleted or not in the cache for some reason

    @SendReminders.before_loop
    async def SendRemindersBeforeLoop(self):
        await self.client.wait_until_ready() # only start the loop when the bot is ready (online)

    @ClosePendingPosts.before_loop
    async def ClosePendingPostsBeforeLoop(self):
        await self.client.wait_until_ready()

    @CheckExceptionPosts.before_loop
    async def ExceptionPostsBeforeLoop(self):
        await self.client.wait_until_ready()

async def setup(client):
    await client.add_cog(remind(client))