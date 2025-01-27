import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
from functions import add_post_to_rtdr
from typing import Union

load_dotenv()
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
EXPERTS_ROLE_ID = int(os.getenv('EXPERTS_ROLE_ID'))
MODERATORS_ROLE_ID = int(os.getenv('MODERATORS_ROLE_ID'))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))

class readthedamnrules(commands.Cog):
    def __init__(self, client) -> None:
        self.client: commands.Bot = client

    async def get_messages_to_move(self, reference_message: discord.Message) -> list[discord.Message]:
        """  
        Get a list[Message] for all messages that should be used in the new post
        """
        messages_to_move: list[discord.Message] = [reference_message]
        async for msg in reference_message.channel.history(limit=None, after=reference_message.created_at):
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
                messages_content.append(message.content)
        if messages_content:
            content = '\n'.join(messages_content)
        return content

    async def handle_request(self, reference_message: discord.Message, user: discord.Member, message: discord.Message|None = None) -> discord.Thread:
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
            content=f"**Original message:**\n```\n{content}```\n\n{reference_message.author.mention} please provide any additional information here so we can give you the best help.\n-# Created by {user.name}"
        )
        new_message_content = post[0].starter_message.content.removesuffix(user.name).join(user.mention)
        await post[0].starter_message.edit()
        await add_post_to_rtdr(post_id=post[0].id, user_id=reference_message.author.id)
        return post[0]

    @commands.Cog.listener('on_message')
    async def redirect_to_support(self, message: discord.Message):
        if not message.author.bot:
            if message.channel.id == GENERAL_CHANNEL_ID and message.reference and message.content.startswith(self.client.user.mention):
                experts = message.guild.get_role(EXPERTS_ROLE_ID)
                moderators = message.guild.get_role(MODERATORS_ROLE_ID)
                if experts in message.author.roles or moderators in message.author.roles:
                    replied_message = await message.channel.fetch_message(message.reference.message_id)
                    if not replied_message.author == message.author:
                        post = await self.handle_request(reference_message=replied_message, user=message.author, message=message)
                        await message.reply(content=f"Post created at {post.mention}", mention_author=False, delete_after=5)
                        await message.delete(delay=5) # delete the trigger message when the reply message with the post was sent

    @commands.Cog.listener('on_reaction_add')
    async def reaction_redirect_to_support(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        if reaction.message.channel.id == GENERAL_CHANNEL_ID:
            reactions = ["❓", "❔"] # allowed reactions, all other reactions will be ignored in this context
            if reaction.message.author != user and reaction.emoji in reactions:
                experts = reaction.message.guild.get_role(EXPERTS_ROLE_ID)
                mods = reaction.message.guild.get_role(MODERATORS_ROLE_ID)
                if experts in user.roles or mods in user.roles:
                    await self.handle_request(reaction.message, user=user)
                    await reaction.remove(user)

async def setup(client):
    await client.add_cog(readthedamnrules(client))