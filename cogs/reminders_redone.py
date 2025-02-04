import discord
from discord.ext import commands, tasks
from functions import save_post_as_pending, remove_post_from_pending, get_pending_posts, get_post_creator_id, get_rtdr_posts, generate_random_id, get_waiting_posts, add_post_to_waiting, remove_post_from_waiting
import datetime, os, asyncio, random
from dotenv import load_dotenv
from discord import ui
from typing import Union

load_dotenv()

NEEDS_DEV_REVIEW_TAG_ID = int(os.getenv("NEED_DEV_REVIEW_TAG_ID"))
SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
CB_TAG_ID = int(os.getenv("CUSTOM_BRANDING_TAG_ID"))
MODERATORS_ROLE_ID = int(os.getenv('MODERATORS_ROLE_ID'))
EXPERTS_ROLE_ID = int(os.getenv('EXPERTS_ROLE_ID'))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))
close_posts_tasks: dict[int, asyncio.Task] = {} # for the 24 hours after the reminder was sent task
send_reminder_tasks: dict[int, asyncio.Task] = {} # waiting for 24 hours and sending the reminder tasks

class close_now(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @ui.button(label="Issue already solved? Close post now", custom_id="remind-close-now", style=discord.ButtonStyle.grey)
    async def on_close_now_click(self, interaction: discord.Interaction, button: ui.Button):
        experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
        mods = interaction.guild.get_role(MODERATORS_ROLE_ID)
        if experts in interaction.user.roles or mods in interaction.user.roles or interaction.user == interaction.channel.owner:
            await interaction.message.edit(view=None, content=f"{interaction.message.content}\n-# Closed by {interaction.user.name}")
            tags = [interaction.channel.parent.get_tag(SOLVED_TAG_ID)]
            if interaction.channel.parent.get_tag(CB_TAG_ID) in interaction.channel.applied_tags:
                tags.append(interaction.channel.parent.get_tag(CB_TAG_ID))
            action_id = generate_random_id()
            await interaction.channel.edit(applied_tags=tags, archived=True, reason=f"ID: {action_id}. {interaction.user.name} Clicked close now button")
            alerts_thread = interaction.guild.get_channel_or_thread(ALERTS_THREAD_ID)
            await alerts_thread.send(content=f"ID: {action_id}\nPost: {interaction.channel.mention}\nTags: {','.join([tag.name for tag in tags])}\nContext: Close now button clicked")
            await remove_post_from_pending(interaction.channel.id)
            if interaction.channel.id in close_posts_tasks:
                close_posts_tasks.pop(interaction.channel.id)
            alerts_thread = interaction.guild.get_thread(ALERTS_THREAD_ID)
            await alerts_thread.send(content=f"ID: {action_id}\nPost: {interaction.channel.mention}\nTags: {', '.join([tag.name for tag in tags])}\nContext: Close now button clicked")
        else:
            await interaction.response.send_message(content="Only Moderators, Community Experts and the post creator can use this.", ephemeral=True)

class reminders_redone(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client

    async def send_action_log(self, action_id: str, post_mention: str, tags: list[discord.ForumTag], context: str):
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        await alerts_thread.send(content=f"ID: {action_id}\nPost: {post_mention}\nTags: {', '.join([tag.name for tag in tags])}\nContext: {context}")

    @tasks.loop(count=1, seconds=1)
    async def check_db_pending_posts(self):
        """  
        If Sapphire Helper was restarted some posts that were waiting to be 
        """
        for post_id, timestamp in await get_waiting_posts():
            post = self.client.get_channel(post_id)
            if post:
                solved = post.parent.get_tag(SOLVED_TAG_ID)
                ndr = post.parent.get_tag(NEEDS_DEV_REVIEW_TAG_ID)
                if solved not in post.applied_tags and ndr not in post.applied_tags and not post.archived and not post.locked:
                    time = datetime.datetime.fromtimestamp(timestamp)
                    delay = time - datetime.datetime.now()
                    task = asyncio.create_task(self.wait_and_send_reminder(post, time, delay))
                    send_reminder_tasks[post_id] = task
                    await add_post_to_waiting(post_id, timestamp)
                else:
                    await remove_post_from_waiting(post_id)

    async def wait_and_send_reminder(self, post: discord.Thread, time: datetime.datetime = datetime.datetime.now(), delay: int = 24*60*60, remove_reaction_from: discord.Message = None):
        print("wait and send reminders triggered")
        owner_id = await get_post_creator_id(post.id) or post.owner_id
        print(f"owner id: {owner_id}")
        greetings = ["Hello", "Hey", "Hi", "Hi there",]
        #await asyncio.sleep(delay) # 1 day as asyncio.sleep takes time in seconds
        await asyncio.sleep(20) #! Remove this before pushing to main
        #! Xge or anyone else that sees this comment, if you see this it means that I forgot to remove it = change the delay to what it should be, please ping me to remind me to remove it.
        print("waited time")
        refreshed_post = self.client.get_channel(post.id) # "refresh" it, for example if tags were changed during thee asyncio.sleep time
        ndr = post.parent.get_tag(NEEDS_DEV_REVIEW_TAG_ID)
        solved = post.parent.get_tag(SOLVED_TAG_ID)
        if ndr not in refreshed_post.applied_tags and solved not in refreshed_post.applied_tags and not refreshed_post.locked:
            await post.send(
                content=f"{random.choices(greetings)[0]} <@{owner_id}>, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.",
                view=close_now()
            )
            print("message sent")
            timestamp = int((time + datetime.timedelta(hours=24)).timestamp()) # timestamp of when the post should be marked as solved if no message from op is received
            await save_post_as_pending(post_id=post.id, timestamp=timestamp)
            print("post saved as pending")
            task = asyncio.create_task(self.close_post_after_delay(refreshed_post))
            print("task created with close post after delay")
            close_posts_tasks[post.id] = task
            await save_post_as_pending(post.id, timestamp)
            print("task cached")
            send_reminder_tasks.pop(post.id)
            print("removed from cache")
            await remove_post_from_waiting(post.id)
            print("removed from waiting")
            if remove_reaction_from:
                await remove_reaction_from.clear_reactions()


    async def close_post_after_delay(self, post_id: int):
        print("close after delay called")
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        ndr = support.get_tag(NEEDS_DEV_REVIEW_TAG_ID)
        solved = support.get_tag(SOLVED_TAG_ID)
        #await asyncio.sleep(24*60*60) # 24 hours * 60 minutes an hour * 60 seconds a minute as asyncio.sleep takes the time in seconds
        await asyncio.sleep(20) #! remove this line before pushing to main.
        #! Xge (or anyone else that sees this) if this is in main please immediately ping me or just delete this line and remove the comment from the line above this one
        print("time waited")
        post = self.client.get_channel(post_id)
        if ndr not in post.applied_tags and not post.locked and solved not in post.applied_tags and not post.archived:
            print("not ndr, not locked")
            cb = support.get_tag(CB_TAG_ID)
            tags = [solved]
            if cb in post.applied_tags:
                tags.append(cb)
            action_id = generate_random_id()
            await post.edit(archived=True, applied_tags=tags, reason=f"ID: {action_id} .Close pending post")
            print("post edited")
            await self.send_action_log(action_id, post.mention, tags, "Close pending post")
            close_posts_tasks.pop(post_id)
            print("removed from cache")
            await remove_post_from_pending(post.id)
            print("removed from db")
        else:
            print("close after delay- else")
            await remove_post_from_pending(post_id)
            close_posts_tasks.pop(post_id)


    @commands.Cog.listener('on_message')
    async def reminder_messages_listener(self, message: discord.Message):
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID and message.author != self.client.user:
            print("message in #support")
            ndr = message.channel.parent.get_tag(NEEDS_DEV_REVIEW_TAG_ID)
            solved = message.channel.parent.get_tag(SOLVED_TAG_ID)
            if ndr not in message.channel.applied_tags and solved not in message.channel.applied_tags and not message.channel.locked:
                print("not ndr, not solved, not locked")
                owner_is_author = message.author == message.channel.owner
                if message.channel.id in await get_rtdr_posts():
                    owner_is_author = message.author.id == await get_post_creator_id(message.channel.id)
                if owner_is_author:
                    print("owner is author.")
                    if message.channel.id in await get_pending_posts():
                        print("in get pending posts")
                        await remove_post_from_pending(message.channel.id)
                        print("removed from pending")
                        try:
                            close_posts_tasks[message.channel.id].cancel()
                            close_posts_tasks.pop(message.channel.id)
                        except KeyError or IndexError:
                            print("key or index error")
                            pass
                    elif message.channel.id in send_reminder_tasks:
                        print("in send reminder tasks")
                        try:
                            send_reminder_tasks[message.channel.id].cancel()
                            send_reminder_tasks.pop(message.channel.id)
                        except KeyError or IndexError:
                            print("elif key or index error")
                else:
                    print("else = not author is owner")
                    if message.channel.id not in await get_pending_posts() and message.channel.id not in close_posts_tasks and message.channel.id not in send_reminder_tasks:
                        print("channel not in pending posts")
                        task = asyncio.create_task(self.wait_and_send_reminder(message.channel))
                        print("task created")
                        send_reminder_tasks[message.channel.id] = task
                        await add_post_to_waiting(message.channel.id)
                        print("added to cache")

    @commands.Cog.listener("on_reaction_add")
    async def manually_add_to_pending(self, reaction: discord.Reaction, user: Union[discord.User, discord.Member]):
        if isinstance(reaction.message.channel, discord.Thread) and reaction.message.channel.parent_id == SUPPORT_CHANNEL_ID:
            post_owner_id = await get_post_creator_id(reaction.message.channel.id) or reaction.message.channel.owner_id
            if reaction.message.author.id == post_owner_id and reaction.message.channel.id not in close_posts_tasks and reaction.message.channel.id not in send_reminder_tasks:
                experts = reaction.message.channel.guild.get_role(EXPERTS_ROLE_ID)
                mods = reaction.message.channel.guild.get_role(MODERATORS_ROLE_ID   )
                allowed_reactions = ["⏰", "⏳"]
                if reaction.emoji in allowed_reactions and experts in user.roles or mods in user.roles:
                    await self.wait_and_send_reminder(post=reaction.message.channel, time=reaction.message.created_at)

async def setup(client):
    await client.add_cog(reminders_redone(client))