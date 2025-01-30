import discord
from discord.ext import commands
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
        self.unanswered = discord.Object(UNANSWERED_TAG_ID)
        self.ndr = discord.Object(NEED_DEV_REVIEW_TAG_ID)
        self.solved = discord.Object(SOLVED_TAG_ID)
        self.waiting_for_reply = discord.Object(WAITING_FOR_REPLY_TAG_ID)

    async def get_tag_ids(self, post: discord.Thread):
        """  
        Returns a list of the ids of all tags applied in the given post
        """
        return [tag.id for tag in post.applied_tags]

    async def send_action_log(self, action_id: str, post_mention: str, tags: list[discord.Object], context: str):
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        tag_names = [support.get_tag(tag.id).name for tag in tags]
        await alerts_thread.send(
            content=f"ID: {action_id}\nPost: {post_mention}\nTags: {','.join(tag_names)}\nContext: {context}"
        )
        
    posts: dict[int, asyncio.Task] = {}

    async def add_waiting_tag(self, post_id: int) -> None:
        await asyncio.sleep(600) # wait for 10 minutes to prevent rate limits
        post = self.client.get_channel(post_id)
        applied_tags = await self.get_tag_ids(post)
        applied_tags.append(self.waiting_for_reply)
        if not self.solved.id in applied_tags and not self.ndr in post.applied_tags and not post.archived:
            action_id = generate_random_id()
            await post.edit(applied_tags=applied_tags, reason=f"ID: {action_id}. Waiting for reply system")
            await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=applied_tags, context="Add Waiting for reply")
            self.posts.pop(post_id)

    @commands.Cog.listener('on_message')
    async def add_remove_waiting_for_reply(self, message: discord.Message):
        channel_id = message.channel.id
        in_support = isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID
        if message.author != self.client.user:
            if in_support:
                applied_tags = await self.get_tag_ids(message.channel)
                start_message = message.id == message.channel.id # a thread id is always equal to the starter message id
                tags_filters =   not self.ndr.id in applied_tags and\
                                not self.unanswered.id in applied_tags and\
                                not self.solved.id in applied_tags
                message_author_is_owner = message.author == message.channel.owner
                has_wfr = self.waiting_for_reply.id in applied_tags
                if not start_message and tags_filters:
                    if not has_wfr:
                        if message_author_is_owner and channel_id not in self.posts:
                            task = asyncio.create_task(self.add_waiting_tag(post_id=message.channel.id))
                            self.posts[channel_id] = task
                        elif not message_author_is_owner and channel_id in self.posts:
                            self.posts[channel_id].cancel()
                            self.posts.pop(channel_id)
                    elif not message_author_is_owner and has_wfr:
                        applied_tags.remove(self.waiting_for_reply)
                        tags = [discord.Object(tag_id) for tag_id in applied_tags]
                        action_id = generate_random_id()
                        await message.channel.edit(applied_tags=tags, reason=f"ID: {action_id}. Remove waiting for reply tag as last message author isn't OP")
                        await self.send_action_log(action_id=action_id, post_mention=message.channel.mention, tags=applied_tags, context="Remove waiting for reply tag")

async def setup(client):
    await client.add_cog(waiting_for_reply(client))