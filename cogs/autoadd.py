import discord
from discord.ext import commands, tasks
import re
import random
import os
from dotenv import load_dotenv

load_dotenv()

SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
NOT_SOLVED_TAG_ID = int(os.getenv("NOT_SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
UNANSWERED_TAG_ID = int(os.getenv('UNANSWERED_TAG_ID'))
CUSTOM_BRANDING_TAG_ID = int(os.getenv('CUSTOM_BRANDING_TAG_ID'))

sent_post_ids = [] # A list of posts where the bot sent a suggestion message to use /solved

class autoadd(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client
        self.CloseAbandonedPosts.start() # Start the loop

    async def cog_unload(self):
        self.CloseAbandonedPosts.cancel() # Cancel the loop as the cog was unloaded

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.parent_id == SUPPORT_CHANNEL_ID: # Check if the message was sent in #support
            tags = [thread.parent.get_tag(UNANSWERED_TAG_ID)]
            if thread.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in thread.applied_tags:
                tags.append(thread.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
            await thread.edit(applied_tags=tags, reason="Auto-add unanswered tag to a new post") # Add unanswered solved tag to post
            if (thread.starter_message.content and len(thread.starter_message.content) < 15) or (not thread.starter_message.content and thread.starter_message.attachments[0]): # Check if the amount of characters in the starting message is smaller than 15 
                    greets = ["Hi", "Hey", "Hello", "Hi there"]
                    await thread.starter_message.reply(content=f"{random.choices(greets)[0]}, please answer these questions if you haven't already, so we can help you faster.\n* What exactly is your question or the problem you're experiencing?\n* What have you already tried?\n* What are you trying to do / what is your overall goal?\n* If possible, please include a screenshot or screen recording of your setup.", mention_author=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.author == self.client.user: # Check if the message author is Sapphire Helper
            if isinstance(message.channel, discord.Thread):
                if message.channel.parent_id == SUPPORT_CHANNEL_ID: # Check if the message channel parent is the support channel
                    if message.channel.id not in sent_post_ids:
                        if message.author == message.channel.owner: # Checks if the message author is the post creator
                            need_dev_review_tag = message.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
                            solved_tag = message.channel.parent.get_tag(SOLVED_TAG_ID)
                            if solved_tag not in message.channel.applied_tags and need_dev_review_tag not in message.channel.applied_tags: # make sure the post is not already solved and doesn't have the need-dev-review tag
                                if not message == message.channel.starter_message:
                                    pattern = r"solved|thanks?|works?|fixe?d|thx|tysm|\bty\b"
                                    negative_pattern = r"(doe?s?n.?t|isn.?t|not?\b|but\b|before|won.?t|didn.?t)"
                                    if not re.search(negative_pattern, message.content, re.IGNORECASE):
                                        if re.search(pattern, message.content, re.IGNORECASE):
                                            await message.reply(content="-# <:tree_corner:1272886415558049893>Command suggestion: </solved:1274997472162349079>")
                                            sent_post_ids.append(message.channel.id)
                                        else:
                                            return # Ignore the message as it doesn't match the regex
                                    else:
                                        return # Ignore as the message matches the negative regex
                                else:
                                    return # ignore the message as its the first message of the thread
                            else:
                                return # Ignore the message as the post is already solved or has the need-dev-review tag
                    if message.channel.parent.get_tag(UNANSWERED_TAG_ID) in message.channel.applied_tags and not message.author == message.channel.owner:
                        tags = [message.channel.parent.get_tag(NOT_SOLVED_TAG_ID)]
                        if message.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in message.channel.applied_tags:
                            tags.append(message.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
                        await message.channel.edit(applied_tags=tags, reason="Auto-remove unanswered tag and replace with not solved tag")
                    else:
                        return # Ignore the message as a message was already sent in this channel before
                else:
                    return # Ignore the message as it was not sent in #support
            else:
                return # Ignroe the message as its channel type isn't a ForumChannel
        else:
            return # Ignore the message as it was sent by Sapphire helper

    @tasks.loop(hours=1)
    async def CloseAbandonedPosts(self):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        need_dev_review = support.get_tag(NEED_DEV_REVIEW_TAG_ID)
        for post in support.threads:
            if not post.locked and not post.archived:
                if need_dev_review not in post.applied_tags:
                    if not post.owner:
                        tags = [post.parent.get_tag(SOLVED_TAG_ID)]
                        if post.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in post.applied_tags:
                            tags.append(post.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
                        await post.edit(archived=True, reason="User left server, auto close post", applied_tags=tags)
                    else:
                        continue
                else:
                    continue
            else:
                continue

    @CloseAbandonedPosts.before_loop
    async def CloseAbandonedPostsBeforeLoop(self):
        await self.client.wait_until_ready() # wait for the bot to be ready and then start the loop

async def setup(client):
    await client.add_cog(autoadd(client))
