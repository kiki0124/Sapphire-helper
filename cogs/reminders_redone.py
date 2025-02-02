import discord
from discord.ext import commands
from functions import save_post_as_pending, remove_post_from_pending, get_pending_posts, get_post_creator_id, get_rtdr_posts, generate_random_id
import datetime, os, asyncio, random
from dotenv import load_dotenv
from discord import ui

load_dotenv()

NEEDS_DEV_REVIEW_TAG_ID = int(os.getenv("NEED_DEV_REVIEW_TAG_ID"))
SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
CB_TAG_ID = int(os.getenv("CUSTOM_BRANDING_TAG_ID"))
MODERATORS_ROLE_ID = int(os.getenv('MODERATORS_ROLE_ID'))
EXPERTS_ROLE_ID = int(os.getenv('EXPERTS_ROLE_ID'))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))
close_posts_tasks: dict[discord.Thread, asyncio.Task] = {} # for the 24 hours after the reminder was sent task
send_reminder_tasks: dict[discord.Thread, asyncio.Task] = {} # waiting for 24 hours and sending the reminder tasks

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
            if interaction.channel.parent.get_tag(CB_TAG_ID) in interaction.channel.applied_tags:
                tags.append(interaction.channel.parent.get_tag(CB_TAG_ID))
            action_id = generate_random_id()
            await interaction.channel.edit(applied_tags=tags, archived=True, reason=f"ID: {action_id}. {interaction.user.name} Clicked close now button")
            alerts_thread = interaction.guild.get_channel_or_thread(ALERTS_THREAD_ID)
            await alerts_thread.send(content=f"ID: {action_id}\nPost: {interaction.channel.mention}\nTags: {','.join([tag.name for tag in tags])}\nContext: Close now button clicked")
            await remove_post_from_pending(interaction.channel.id)
            if interaction.channel.id in close_posts_tasks:
                close_posts_tasks.pop(interaction.channel.id)
        else:
            await interaction.response.send_message(content="Only Moderators, Community Experts and the post creator can use this.", ephemeral=True)

class reminders_redone(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client

    async def wait_and_send_reminder(self, post: discord.Thread):
        await asyncio.sleep(24*60*60) # 1 day as asyncio.sleep takes time in seconds
        owner_id = await get_post_creator_id(post.id) or post.owner_id
        greetings = ["Hello", "Hey", "Hi", "Hi there",]
        await post.send(
            content=f"{random.choices(greetings)[0]} <@{owner_id}>, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved."
        )
        timestamp = int((datetime.datetime.now() + datetime.timedelta(hours=24)).timestamp()) # timestamp of when the post should be marked as solved if no message from op is received
        await save_post_as_pending(post_id=post.id, timestamp=timestamp)
        task = asyncio.create_task(self.close_post_after_delay(post))
        close_posts_tasks[post] = task

    async def close_post_after_delay(self, post: discord.Thread):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        ndr = support.get_tag(NEEDS_DEV_REVIEW_TAG_ID)
        await asyncio.sleep(24*60*60) # 24 hours * 60 minutes an hour * 60 seconds a minute as asyncio.sleep takes the time in seconds
        if ndr not in post.applied_tags and not post.locked:
            solved = support.get_tag(SOLVED_TAG_ID)
            cb = support.get_tag(CB_TAG_ID)
            tags = [solved]
            if cb in post.applied_tags:
                tags.append(cb)
            await post.edit(archived=True, applied_tags=tags, reason="Close pending post")

    @commands.Cog.listener('on_message')
    async def reminder_messages_listener(self, message: discord.Message):
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
            ndr = message.channel.parent.get_tag(NEEDS_DEV_REVIEW_TAG_ID)
            solved = message.channel.parent.get_tag(SOLVED_TAG_ID)
            if ndr not in message.channel.applied_tags and solved not in message.channel.applied_tags and not message.channel.locked and message.author != self.client.user:
                owner_is_author = message.author == message.channel.owner
                if message.channel.id in await get_rtdr_posts():
                    owner_is_author = message.author.id == await get_post_creator_id(message.channel.id)
                
                if owner_is_author:
                    if message.channel.id in await get_pending_posts():
                        await remove_post_from_pending(message.channel.id)
                        try:
                            close_posts_tasks[message.channel.id].cancel()
                            close_posts_tasks.pop(message.channel.id)
                        except KeyError|IndexError:
                            pass
                    elif message.channel.id in send_reminder_tasks:
                        try:
                            send_reminder_tasks[message.channel].cancel()
                            send_reminder_tasks.pop(message.channel)
                        except KeyError|IndexError:
                            pass
                else:
                    if message.channel.id not in await get_pending_posts() and message.channel.id not in send_reminder_tasks:
                        task = asyncio.create_task(self.wait_and_send_reminder(message.channel))
                        send_reminder_tasks[message.channel] = task

async def setup(client):
    await client.add_cog(reminders_redone(client))