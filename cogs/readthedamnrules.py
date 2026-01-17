from __future__ import annotations

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
from functions import add_post_to_rtdr
from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from main import MyClient

load_dotenv()
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
EXPERTS_ROLE_ID = int(os.getenv('EXPERTS_ROLE_ID'))
MODERATORS_ROLE_ID = int(os.getenv('MODERATORS_ROLE_ID'))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

class readthedamnrules(commands.Cog):
    def __init__(self, client: MyClient) -> None:
        self.client = client

    async def get_messages_to_move(self, reference_message: discord.Message) -> list[discord.Message]:
        """  
        Get a list[Message] for all messages that should be used in the new post
        """
        messages_to_move: list[discord.Message] = [reference_message]
        async for msg in reference_message.channel.history(limit=100, after=reference_message.created_at):
            if msg.author == reference_message.author:
                messages_to_move.append(msg)
            else:
                break
        return messages_to_move

    async def get_files(self, messages: list[discord.Message]) -> list[discord.File]:
        """  
        Returns list[File] for all attachments (files) that should be used in the new post 
        """
        files = []
        for msg in messages:
            for attachment in msg.attachments:
                files.append(await attachment.to_file())
        return files

    async def get_content(self, messages: list[discord.Message]) -> str:
        """  
        Returns a string of messages that should be used in the content of the post in this format
        ```
        first message content
        second message content
        ...
        ```
        or "No message content found" if all messages don't have content (only have attachments)
        """
        content = 'No message content found'
        messages_content: list[discord.Message] = []
        for message in messages:
            if message.content:
                messages_content.append(message.clean_content)
        if messages_content:
            content = '\n'.join(messages_content)
        return content

    def get_extra_content(self, reference_msg: discord.Message) -> str:
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        if isinstance(reference_msg.channel, discord.Thread) and reference_msg.channel.parent_id == SUPPORT_CHANNEL_ID:
            return f"{reference_msg.author.mention} in the future please always create your own post instead of using other users' posts!" # asking for help in another user's support post
        elif isinstance(reference_msg.channel, discord.Thread) and reference_msg.channel.id != SUPPORT_CHANNEL_ID and reference_msg.channel.category_id == support.category_id:
            return f"{reference_msg.author.mention} the feature you suggested is already possible with Sapphire!" # requesting a feature which already exists
        else:
            return f"{reference_msg.author.mention} please provide any additional information here so we can give you the best help." # default message - if none of the special ones above are used

    async def handle_request(self, reference_message: discord.Message, user: discord.Member, message: discord.Message|None = None) -> discord.Thread:
        await reference_message.channel.typing()
        messages_to_move: list[discord.Message] = await self.get_messages_to_move(reference_message)
        files = await self.get_files(messages=messages_to_move)
        content = await self.get_content(messages_to_move)
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        title = f"Support for {reference_message.author.name}"
        if message and message.content.removeprefix(self.client.user.mention): # make sure the message has a content beyond @sapphire helper
            title = message.content.removeprefix(self.client.user.mention) 
        post = await support.create_thread(
            name=title,
            files=files,
            content=f"**Original message:**\n```\n{content}```\n\n{self.get_extra_content(reference_message)}\n-# Created by {user.mention} | In the future please always create a post in <#{SUPPORT_CHANNEL_ID}> for all Sapphire and appeal.gg related questions."
        )
        await add_post_to_rtdr(post_id=post[0].id, user_id=reference_message.author.id)
        await reference_message.channel.send(content=f'{reference_message.author.mention} asked something about Sapphire or appeal.gg. A post was opened to answer it: {post[0].mention}\n-# Please ask any Sapphire or appeal.gg related questions in <#{SUPPORT_CHANNEL_ID}>. Asking anywhere else repeatedly will result in a punishment.', delete_after=300, allowed_mentions=discord.AllowedMentions.none())
        await reference_message.channel.delete_messages(messages_to_move, reason=f"rtdr system used by {user.name}")
        return post[0]

    @commands.Cog.listener('on_message')
    async def redirect_to_support(self, message: discord.Message):
        if not message.author.bot and message.reference and message.content.startswith(self.client.user.mention) and message.guild:
            everyone = message.guild.default_role
            if message.channel.permissions_for(everyone).view_channel and message.channel.permissions_for(everyone).send_messages or message.channel.permissions_for(everyone).send_messages_in_threads:
                if message.author.get_role(EXPERTS_ROLE_ID) or message.author.get_role(MODERATORS_ROLE_ID) or message.author.get_role(DEVELOPERS_ROLE_ID):
                    replied_message = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
                    if not replied_message.author == message.author:
                        await self.handle_request(reference_message=replied_message, user=message.author, message=message)
                        await message.delete(delay=5) # delete the trigger message when the reply message with the post was sent

    @commands.Cog.listener('on_reaction_add')
    async def reaction_redirect_to_support(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        if reaction.message.guild and reaction.message.author != user and not reaction.message.author.bot:
            everyone = reaction.message.guild.default_role
            if reaction.message.channel.permissions_for(everyone).view_channel and reaction.message.channel.permissions_for(everyone).send_messages:
                reactions = ("❓", "❔") # allowed reactions, all other reactions will be ignored in this context
                if reaction.emoji in reactions:
                    if user.get_role(EXPERTS_ROLE_ID) or user.get_role(MODERATORS_ROLE_ID) or user.get_role(DEVELOPERS_ROLE_ID):
                        await self.handle_request(reaction.message, user=user)

async def setup(client: MyClient):
    await client.add_cog(readthedamnrules(client))