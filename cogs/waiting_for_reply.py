import discord
from discord.ext import commands, tasks
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
WAITING_FOR_REPLY_TAG_ID = int(os.getenv('WAITING_FOR_REPLY_TAG_ID'))
UNANSWERED_TAG_ID = int(os.getenv("UNANSWERED_TAG_ID"))


class waiting_for_reply(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client
        self.get_tags.start()

    @tasks.loop(seconds=1, count=1)
    async def get_tags(self):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        self.unanswered = support.get_tag(UNANSWERED_TAG_ID)
        self.ndr = support.get_tag(NEED_DEV_REVIEW_TAG_ID)
        self.solved = support.get_tag(SOLVED_TAG_ID)
        self.waiting_for_reply = support.get_tag(WAITING_FOR_REPLY_TAG_ID)

    posts: dict[int, asyncio.Task] = {}

    async def add_waiting_tag(self, post: discord.Thread) -> None: # task for adding the waiting tag after 10 minutes of delay
        await asyncio.sleep(600) # wait for 600 seconds
        applied_tags = post.applied_tags
        applied_tags.append(self.waiting_for_reply)
        if not self.solved in post.applied_tags and not self.ndr in post.applied_tags and not post.archived:
            await post.edit(applied_tags=applied_tags, reason="Waiting for reply system")
            self.posts.pop(post.id) # remove post from internal list of posts that are waiting for waiting tag to be added

    @commands.Cog.listener('on_message')
    async def add_remove_waiting_for_reply(self, message: discord.Message):
        if not message.author == self.client.user:
            if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
                if message != message.channel.starter_message: # make sure its not a new post- prevent it from replacing unanswered with wfr
                    if not self.ndr in message.channel.applied_tags and not self.solved in message.channel.applied_tags and not self.unanswered in message.channel.applied_tags:
                        if not self.waiting_for_reply in message.channel.applied_tags:
                            if message.author == message.channel.owner and not message.channel.id in self.posts:
                                task = asyncio.create_task(self.add_waiting_tag(post=message.channel))
                                self.posts[message.channel.id] = task
                            elif message.author != message.channel.owner and message.channel.id in self.posts:
                                self.posts[message.channel.id].cancel() # cancel the task
                                self.posts.pop(message.channel.id) # remove the post from the dict
                        elif message.author != message.channel.owner and self.waiting_for_reply in message.channel.applied_tags:
                            applied_tags = message.channel.applied_tags
                            applied_tags.remove(self.waiting_for_reply)
                            await message.channel.edit(applied_tags=applied_tags, reason="Remove waiting for reply tag as last message author isn't OP")

    @get_tags.before_loop
    async def wait_until_ready(self):
        await self.client.wait_until_ready()

async def setup(client):
    await client.add_cog(waiting_for_reply(client))