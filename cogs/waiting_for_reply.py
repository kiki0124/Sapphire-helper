import discord
from discord.ext import commands
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

    posts: dict[int, asyncio.Task] = {}

    async def add_waiting_tag(self, post: discord.Thread) -> None: # task for adding the waiting tag after 10 minutes of delay
        await asyncio.sleep(600) # wait for 600 seconds
        applied_tags = post.applied_tags
        applied_tags.append(post.parent.get_tag(WAITING_FOR_REPLY_TAG_ID))
        solved = post.parent.get_tag(SOLVED_TAG_ID)
        ndr = post.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
        if not solved in post.applied_tags and not ndr in post.applied_tags and not post.archived:
            await post.edit(applied_tags=applied_tags)
            self.posts.pop(post.id) # remove post from internal list of posts that are waiting for waiting tag to be added


    @commands.Cog.listener('on_message')
    async def add_remove_waiting_for_reply(self, message: discord.Message):
        if not message.author == self.client.user:
            if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
                if message != message.channel.starter_message: # make sure its not a new post- prevent it from replacing unanswered with wfr
                    solved = message.channel.parent.get_tag(SOLVED_TAG_ID)
                    ndr = message.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
                    unanswered = message.channel.parent.get_tag(UNANSWERED_TAG_ID)
                    if not ndr in message.channel.applied_tags and not solved in message.channel.applied_tags and not unanswered in message.channel.applied_tags:
                        waiting_tag = message.channel.parent.get_tag(WAITING_FOR_REPLY_TAG_ID)
                        if not waiting_tag in message.channel.applied_tags:
                            if message.author == message.channel.owner and not message.channel.id in self.posts:
                                task = asyncio.create_task(self.add_waiting_tag(post=message.channel))
                                self.posts[message.channel.id] = task
                            elif message.author != message.channel.owner and message.channel.id in self.posts:
                                self.posts[message.channel.id].cancel() # cancel the task
                                self.posts.pop(message.channel.id) # remove the post from the dict
                        elif message.author != message.channel.owner and waiting_tag in message.channel.applied_tags:
                            applied_tags = message.channel.applied_tags
                            applied_tags.remove(waiting_tag)
                            await message.channel.edit(applied_tags=applied_tags)

async def setup(client):
    await client.add_cog(waiting_for_reply(client))