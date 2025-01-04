import discord
from discord.ext import commands, tasks
import re
import random
import os
from dotenv import load_dotenv
from functions import get_post_creator_id, get_rtdr_posts, generate_random_id
from aiocache import cached

load_dotenv()

SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
NOT_SOLVED_TAG_ID = int(os.getenv("NOT_SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
UNANSWERED_TAG_ID = int(os.getenv('UNANSWERED_TAG_ID'))
CUSTOM_BRANDING_TAG_ID = int(os.getenv('CUSTOM_BRANDING_TAG_ID'))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))

class autoadd(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.get_tags.start()
        self.close_abandoned_posts.start()

    def cog_unload(self):
        self.close_abandoned_posts.cancel()

    @cached()
    async def get_solved_id(self):
        solved_id = 1274997472162349079
        for command in await self.client.tree.fetch_commands():
                if command.name == "solved": 
                    solved_id=command.id
                    break
                else:
                    continue
        return solved_id

    async def send_action_log(self, action_id: str, post_mention: str, tags: list[discord.ForumTag], context: str):
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        await alerts_thread.send(content=f"ID: {action_id}\nPost: {post_mention}\nTags: {','.join([tag.name for tag in tags])}\nContext: {context}")

    @tasks.loop(seconds=1, count=1)
    async def get_tags(self):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        self.unanswered = support.get_tag(UNANSWERED_TAG_ID)
        self.ndr = support.get_tag(NEED_DEV_REVIEW_TAG_ID)
        self.solved = support.get_tag(SOLVED_TAG_ID)
        self.not_solved = support.get_tag(NOT_SOLVED_TAG_ID)
        self.cb = support.get_tag(CUSTOM_BRANDING_TAG_ID)

    sent_post_ids = [] # A list of posts where the bot sent a suggestion message to use /solved

    @commands.Cog.listener('on_message')
    async def message(self, message: discord.Message):
        if not message.author == self.client.user: # Check if the message author is Sapphire Helper
            if isinstance(message.channel, discord.Thread):
                if message.channel.parent_id == SUPPORT_CHANNEL_ID:
                    if message.id == message.channel.id:
                        await self.on_thread_create(message.channel)
                    if not message.channel.id in self.sent_post_ids:
                        await self.send_suggestion_message(message)
                    if message.id != message.channel.id:
                        await self.replace_unanswered_tag(message)

    async def on_thread_create(self, thread: discord.Thread):
        tags = thread.applied_tags
        tags.append(self.unanswered)
        action_id = generate_random_id()
        await thread.edit(applied_tags=tags, reason=f"ID: {action_id}. Auto-add unanswered tag to a new post.")
        await self.send_action_log(action_id=action_id, post_mention=thread.mention, tags=tags, context="Auto add unanswered tag")
        if (thread.starter_message.content and len(thread.starter_message.content) < 15) or not thread.starter_message.content: # Check if the amount of characters in the starting message is smaller than 15 or if the starter message doesn't have content- attachment(s) only
            greets = ["Hi", "Hey", "Hello", "Hi there"]
            await thread.starter_message.reply(content=f"{random.choices(greets)[0]}, please answer these questions if you haven't already, so we can help you faster.\n* What exactly is your question or the problem you're experiencing?\n* What have you already tried?\n* What are you trying to do / what is your overall goal?\n* If possible, please include a screenshot or screen recording of your setup.", mention_author=True)

    async def send_suggestion_message(self, message: discord.Message):
        if message.author == message.channel.owner or message.author.id == await get_post_creator_id(message.channel.id): # Checks if the message author is the post creator
            if self.solved not in message.channel.applied_tags and self.ndr not in message.channel.applied_tags: 
                if not message == message.channel.starter_message:
                    pattern = r"solved|thanks?|works?|fixe?d|thx|tysm|\bty\b"
                    negative_pattern = r"doe?s?n.?t|isn.?t|not?\b|but\b|before|won.?t|didn.?t|\?"
                    if not re.search(negative_pattern, message.content, re.IGNORECASE):
                        if re.search(pattern, message.content, re.IGNORECASE):
                            await message.reply(content=f"-# <:tree_corner:1272886415558049893>Command suggestion: </solved:{await self.get_solved_id()}>")
                            self.sent_post_ids.append(message.channel.id)

    async def replace_unanswered_tag(self, message: discord.Message):
        if self.unanswered in message.channel.applied_tags:
            if (message.author != message.channel.owner) or (message.channel.id in await get_rtdr_posts() and message.author.id == await get_post_creator_id(message.channel)):
                tags = [self.not_solved]
                if self.cb in message.channel.applied_tags: tags.append(self.cb)
                action_id = generate_random_id()
                await message.channel.edit(applied_tags=tags, reason=f"ID: {action_id}. Auto-remove unanswered tag and replace with not solved tag")
                await self.send_action_log(action_id=action_id, post_mention=message.channel.mention, tags=tags, context="Replace unanswered tag with not solved")

    @tasks.loop(hours=1)
    async def close_abandoned_posts(self):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        for post in await support.guild.active_threads():
            if post.parent_id == SUPPORT_CHANNEL_ID:
                if not post.locked:
                    if self.ndr not in post.applied_tags:
                        if not post.owner:
                            tags = [self.solved]
                            if self.cb in post.applied_tags: tags.append(self.cb)
                            action_id = generate_random_id()
                            await post.edit(archived=True, reason=f"ID: {action_id}. User left server, auto close post", applied_tags=tags)
                            await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=tags, context="Post creator left the server")

    @close_abandoned_posts.before_loop
    @get_tags.before_loop
    async def wait_until_ready(self):
        await self.client.wait_until_ready()

async def setup(client):
    await client.add_cog(autoadd(client))
