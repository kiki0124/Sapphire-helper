import discord
from discord.ext import commands, tasks
import re
import random
import os
from dotenv import load_dotenv
from functions import get_post_creator_id, get_rtdr_posts, generate_random_id, remove_post_from_rtdr
from aiocache import cached
from discord import ui

load_dotenv()

SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
NOT_SOLVED_TAG_ID = int(os.getenv("NOT_SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
UNANSWERED_TAG_ID = int(os.getenv('UNANSWERED_TAG_ID'))
CUSTOM_BRANDING_TAG_ID = int(os.getenv('CUSTOM_BRANDING_TAG_ID'))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))
EXPERTS_ROLE_ID = int(os.getenv('EXPERTS_ROLE_ID'))
MODERATORS_ROLE_ID = int(os.getenv('MODERATORS_ROLE_ID'))
WAITING_FOR_REPLY_TAG_ID = int(os.getenv("WAITING_FOR_REPLY_TAG_ID"))
APPEAL_GG_TAG_ID = int(os.getenv("APPEAL_GG_TAG_ID"))

class confirm_close(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Mark as solved", style=discord.ButtonStyle.green, custom_id="auto-close-confirm")
    async def on_confirm_click(self, interaction: discord.Interaction, button: ui.Button):
        experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
        mods = interaction.guild.get_role(MODERATORS_ROLE_ID)
        is_owner = interaction.user == interaction.channel.owner or interaction.user.id == await get_post_creator_id(interaction.channel_id)
        if experts in interaction.user.roles or mods in interaction.user.roles or is_owner:
            await interaction.message.edit(view=None, content=f"{interaction.message.content}\n-# {interaction.user.name} clicked the confirm button", allowed_mentions=discord.AllowedMentions.none())
            solved = interaction.channel.parent.get_tag(SOLVED_TAG_ID)
            appeal = interaction.channel.parent.get_tag(APPEAL_GG_TAG_ID)
            cb = interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
            tags = [solved]
            if appeal in interaction.channel.applied_tags:
                tags.append(appeal)
            if cb in interaction.channel.applied_tags:
                tags.append(cb)
            action_id = generate_random_id()
            alerts_thread = interaction.guild.get_thread(ALERTS_THREAD_ID)
            await alerts_thread.send(content=f"ID: {action_id}\nPost: {interaction.channel.mention}\nTags: {', '.join([tag.name for tag in tags])}\nContext: Post starter message delete and confirm button clicked- mark post as solved")
            if alerts_thread.archived:
                await alerts_thread.edit(archived=False)
            await interaction.channel.edit(archived=True, applied_tags=tags, reason=f"ID: {action_id}. Auto close as starter message was deleted and confirm button was clicked.")
            await remove_post_from_rtdr(interaction.channel_id)
        else:
            await interaction.response.send_message(content=f"Only {experts.mention}, {mods.mention} and the post creator can use this!", ephemeral=True)

    @ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="auto-close-cancel")
    async def on_cancel_click(self, interaction: discord.Interaction, button: ui.Button):
        experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
        mods = interaction.guild.get_role(MODERATORS_ROLE_ID)
        is_owner = interaction.user == interaction.channel.owner or interaction.user.id == await get_post_creator_id(interaction.channel_id)
        if experts in interaction.user.roles or mods in interaction.user.roles or is_owner:
            await interaction.message.edit(content=f"~~{interaction.message.content}~~\n-# {interaction.user.name} has clicked the *cancel* button.", view=None, allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.response.send_message(content=f"Only {experts.mention}, {mods.mention} and the post creator can use this!", ephemeral=True)

class autoadd(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.close_abandoned_posts.start()
        
    @commands.Cog.listener('on_ready')
    async def add_persistent_view(self):
        self.client.add_view(confirm_close())

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
        if alerts_thread.archived:
            await alerts_thread.edit(archived=False)
        await alerts_thread.send(content=f"ID: {action_id}\nPost: {post_mention}\nTags: {', '.join([tag.name for tag in tags])}\nContext: {context}")
    
    sent_post_ids = [] # A list of posts where the bot sent a suggestion message to use /solved

    @commands.Cog.listener('on_message')
    async def message(self, message: discord.Message):
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUPPORT_CHANNEL_ID:
            if message.id == message.channel.id:
                await self.on_thread_create(message.channel)
            if message.channel.id not in self.sent_post_ids:
                await self.send_suggestion_message(message)
            if message.id != message.channel.id:
                await self.replace_unanswered_tag(message)

    async def on_thread_create(self, thread: discord.Thread):
        tags = thread.applied_tags
        tags.append(thread.parent.get_tag(UNANSWERED_TAG_ID))
        action_id = generate_random_id()
        await thread.edit(applied_tags=tags, reason=f"ID: {action_id}. Auto-add unanswered tag to a new post.")
        await self.send_action_log(action_id=action_id, post_mention=thread.mention, tags=tags, context="Auto add unanswered tag")
        start_msg = thread.starter_message
        if start_msg.content and (len(start_msg.content) < 15 or start_msg.content.casefold() == thread.name.casefold()) or not start_msg.content:
            greets = ["Hi", "Hey", "Hello", "Hi there"]
            await thread.starter_message.reply(content=f"{random.choices(greets)[0]}, please answer these questions if you haven't already, so we can help you faster.\n* What exactly is your question or the problem you're experiencing?\n* What have you already tried?\n* What are you trying to do / what is your overall goal?\n* If possible, please include a screenshot or screen recording of your setup.", mention_author=True)

    async def send_suggestion_message(self, message: discord.Message):
        if message.author != self.client.user and (message.author == message.channel.owner) or (message.author.id == await get_post_creator_id(message.channel.id)):
            ndr = message.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
            solved = message.channel.parent.get_tag(SOLVED_TAG_ID)
            applied_tags = message.channel.applied_tags
            if solved not in applied_tags and ndr not in applied_tags: 
                if not message.id == message.channel.id:
                    pattern = r"solved|thanks?|works?|fixe?d|thx|tysm|\bty\b"
                    negative_pattern = r"doe?s?n.?t|isn.?t|not?\b|but\b|before|won.?t|didn.?t|\?|can.?t"
                    if not re.search(negative_pattern, message.content, re.IGNORECASE):
                        if re.search(pattern, message.content, re.IGNORECASE):
                            await message.reply(content=f"-# <:tree_corner:1272886415558049893>Command suggestion: </solved:{await self.get_solved_id()}>")
                            self.sent_post_ids.append(message.channel.id)

    async def replace_unanswered_tag(self, message: discord.Message):
        applied_tags = message.channel.applied_tags
        unanswered = message.channel.parent.get_tag(UNANSWERED_TAG_ID)
        if unanswered in applied_tags and message.author != self.client.user:
            author_not_owner = message.author != message.channel.owner
            if message.channel.id in await get_rtdr_posts():
                author_not_owner = message.author.id != await get_post_creator_id(message.channel.id)
            if author_not_owner:
                tags = [message.channel.parent.get_tag(NOT_SOLVED_TAG_ID)]
                cb = message.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
                appeal = message.channel.parent.get_tag(APPEAL_GG_TAG_ID)
                if cb in applied_tags: 
                    tags.append(cb)
                if appeal in applied_tags:
                    tags.append(appeal)
                action_id = generate_random_id()
                await message.channel.edit(applied_tags=tags, reason=f"ID: {action_id}. Auto-remove unanswered tag and replace with not solved tag")
                await self.send_action_log(action_id=action_id, post_mention=message.channel.mention, tags=tags, context="Replace unanswered tag with not solved")

    @tasks.loop(hours=1)
    async def close_abandoned_posts(self):
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        if support:
            for post in await support.guild.active_threads():
                if post.parent_id == SUPPORT_CHANNEL_ID:
                    if not post.locked:
                        applied_tags = post.applied_tags
                        ndr = support.get_tag(NEED_DEV_REVIEW_TAG_ID)
                        if ndr not in applied_tags:
                            owner = post.owner
                            if post.id in await get_rtdr_posts():
                                owner = post.guild.get_member(await get_post_creator_id(post.id))
                            if not owner: # post owner/creator will be None if they left the server
                                tags = [support.get_tag(SOLVED_TAG_ID)]
                                cb = support.get_tag(CUSTOM_BRANDING_TAG_ID)
                                appeal = support.get_tag(APPEAL_GG_TAG_ID)
                                if cb in applied_tags: 
                                    tags.append(cb)
                                if appeal in applied_tags:
                                    tags.append(appeal)
                                action_id = generate_random_id()
                                await post.edit(archived=True, reason=f"ID: {action_id}. User left server, auto close post", applied_tags=tags)
                                await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=tags, context="Post creator left the server")

    @commands.Cog.listener('on_raw_message_delete')
    async def suggest_closing_post(self, payload: discord.RawMessageDeleteEvent):
        message_channel = self.client.get_channel(payload.channel_id)
        is_in_support = isinstance(message_channel, discord.Thread) \
                    and message_channel.parent_id == SUPPORT_CHANNEL_ID
        is_starter_message = payload.message_id == payload.channel_id
        if is_in_support and is_starter_message:
            ndr = message_channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
            solved = message_channel.parent.get_tag(SOLVED_TAG_ID)
            tag_filters = ndr not in message_channel.applied_tags and solved not in message_channel.applied_tags
            other_filters = not message_channel.locked and not message_channel.archived
            if tag_filters and other_filters:
                greetings = ["Hi", "Hey", "Hello", "Hi there"]
                owner_id = await get_post_creator_id(payload.channel_id) or message_channel.owner_id
                await message_channel.send(
                    content=f"{random.choices(greetings)[0]} <@{owner_id}>, it seems like this post's starter message was deleted. Please select one of the buttons below to choose whether to mark this post as solved if you no longer need help or keep it open if you still require help.",
                    view=confirm_close()
                )
                
    @close_abandoned_posts.before_loop
    async def wait_until_ready(self):
        await self.client.wait_until_ready()

async def setup(client):
    await client.add_cog(autoadd(client))