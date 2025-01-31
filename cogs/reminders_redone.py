import discord
from discord.ext import commands
from functions import save_post_as_pending, _remove_post_from_pending
import datetime, os, asyncio
from dotenv import load_dotenv

load_dotenv()

NEEDS_DEV_REVIEW_TAG_ID = int(os.getenv("NEED_DEV_REVIEW_TAG_ID"))
SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
CB_TAG_ID = int(os.getenv("CUSTOM_BRANDING_TAG_ID"))

class reminders_redone(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client

    async def close_post_after_delay(self, post: discord.Thread):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        ndr = support.get_tag(NEEDS_DEV_REVIEW_TAG_ID)
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
            raise NotImplemented # to be continued

async def setup(client):
    await client.add_cog(reminders_redone(client))