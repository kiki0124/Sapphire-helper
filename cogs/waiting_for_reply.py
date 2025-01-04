import discord
from discord.ext import commands, tasks
import asyncio
import os
from dotenv import load_dotenv
from functions import generate_random_id

load_dotenv()
SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
WAITING_FOR_REPLY_TAG_ID = int(os.getenv('WAITING_FOR_REPLY_TAG_ID'))
UNANSWERED_TAG_ID = int(os.getenv("UNANSWERED_TAG_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))

class waiting_for_reply(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client
        self.get_tags.start()

    async def send_action_log(self, action_id: str, post_mention: str, tags: list[discord.ForumTag], context: str):
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        await alerts_thread.send(
            content=f"ID: {action_id}\nPost: {post_mention}\nTags: {','.join([tag.name for tag in tags])}"
        )

    @tasks.loop(seconds=1, count=1)
    async def get_tags(self):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        self.unanswered = support.get_tag(UNANSWERED_TAG_ID)
        self.ndr = support.get_tag(NEED_DEV_REVIEW_TAG_ID)
        self.solved = support.get_tag(SOLVED_TAG_ID)
        self.waiting_for_reply = support.get_tag(WAITING_FOR_REPLY_TAG_ID)

    posts: dict[int, asyncio.Task] = {}

    async def add_waiting_tag(self, post: discord.Thread) -> None:
        await asyncio.sleep(600) # wait for 10 minutes to prevent rate limits
        applied_tags = post.applied_tags
        applied_tags.append(self.waiting_for_reply)
        if not self.solved in post.applied_tags and not self.ndr in post.applied_tags and not post.archived:
            action_id = generate_random_id()
            await post.edit(applied_tags=applied_tags, reason=f"ID: {action_id}. Waiting for reply system")
            await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=applied_tags, context="Add Waiting for reply")
            self.posts.pop(post.id)

    @commands.Cog.listener('on_message')
    async def add_remove_waiting_for_reply(self, message: discord.Message):
        channel_id = message.channel.id
        if not message.author == self.client.user:
            if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
                tags = message.channel.applied_tags
                if message != message.channel.starter_message: # make sure its not a new post- prevent it from replacing unanswered with wfr
                    if not self.ndr in tags and not self.solved in tags and not self.unanswered in message.channel.applied_tags:
                        if not self.waiting_for_reply in tags:
                            if message.author == message.channel.owner and not channel_id in self.posts:
                                task = asyncio.create_task(self.add_waiting_tag(post=message.channel))
                                self.posts[channel_id] = task
                            elif message.author != message.channel.owner and channel_id in self.posts:
                                self.posts[channel_id].cancel()
                                self.posts.pop(channel_id)
                        elif message.author != message.channel.owner and self.waiting_for_reply in message.channel.applied_tags:
                            tags.remove(self.waiting_for_reply)
                            action_id = generate_random_id()
                            await message.channel.edit(applied_tags=tags, reason=f"ID: {action_id}. Remove waiting for reply tag as last message author isn't OP")
                            await self.send_action_log(action_id=action_id, post_mention=message.channel.mention, tags=tags, context="Remove waiting for reply tag")

    @get_tags.before_loop
    async def wait_until_ready(self):
        await self.client.wait_until_ready()

async def setup(client):
    await client.add_cog(waiting_for_reply(client))