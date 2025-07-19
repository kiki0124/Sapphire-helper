import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from functions import generate_random_id, get_post_creator_id

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
        
    async def send_action_log(self, action_id: str, post_mention: str, tags: list[discord.ForumTag], context: str):
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        if alerts_thread.archived:
            await alerts_thread.edit(archived=False)
        webhooks = await alerts_thread.parent.webhooks()
        try:
            webhook = webhooks[0]
        except IndexError:
            webhook = await alerts_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        await webhook.send(
            content=f"ID: {action_id}\nPost: {post_mention}\nTags: {', '.join([tag.name for tag in tags])}\nContext: {context}",
            username=self.client.user.name,
            avatar_url=self.client.user.avatar.url,
            thread=discord.Object(id=ALERTS_THREAD_ID),
            wait=False
        )
        
    posts: dict[int, asyncio.Task] = {}

    async def add_waiting_tag(self, post: discord.Thread) -> None:
        wfr = post.parent.get_tag(WAITING_FOR_REPLY_TAG_ID)
        await asyncio.sleep(600) # wait for 10 minutes to prevent rate limits
        refreshed_post = self.client.get_channel(post.id)
        applied_tags = refreshed_post.applied_tags
        if SOLVED_TAG_ID not in refreshed_post._applied_tags and NEED_DEV_REVIEW_TAG_ID not in refreshed_post._applied_tags and not refreshed_post.archived and not refreshed_post.locked:
            action_id = generate_random_id()
            applied_tags.append(wfr)
            await post.edit(applied_tags=applied_tags, reason=f"ID: {action_id}. Waiting for reply system")
            await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=applied_tags, context="Add Waiting for reply")
            self.posts.pop(post.id)

    @commands.Cog.listener('on_message')
    async def add_remove_waiting_for_reply(self, message: discord.Message):
        channel_id = message.channel.id
        if message.author != self.client.user and isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
            support = message.channel.parent
            wfr = support.get_tag(WAITING_FOR_REPLY_TAG_ID)
            applied_tags = message.channel._applied_tags
            message_author_is_owner = message.author == message.channel.owner or message.author.id == await get_post_creator_id(message.channel.id)
            has_wfr = WAITING_FOR_REPLY_TAG_ID in applied_tags
            if message.id != message.channel.id and NEED_DEV_REVIEW_TAG_ID not in applied_tags and UNANSWERED_TAG_ID not in applied_tags and SOLVED_TAG_ID not in applied_tags:
                if not has_wfr:
                    if message_author_is_owner and channel_id not in self.posts:
                        task = asyncio.create_task(self.add_waiting_tag(post=message.channel))
                        self.posts[channel_id] = task
                    elif not message_author_is_owner and channel_id in self.posts:
                        self.posts[channel_id].cancel()
                        self.posts.pop(channel_id)
                elif not message_author_is_owner and has_wfr:
                    action_id = generate_random_id()
                    tags = message.channel.applied_tags
                    tags.remove(wfr)
                    await message.channel.edit(applied_tags=tags, reason=f"ID: {action_id}. Remove waiting for reply tag")
                    await self.send_action_log(action_id=action_id, post_mention=message.channel.mention, tags=tags, context="Remove waiting for reply tag")

async def setup(client):
    await client.add_cog(waiting_for_reply(client))