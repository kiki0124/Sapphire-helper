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
    
    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def test(self, ctx: commands.Context):
        await ctx.reply("FIle recognised")

    async def send_debug_message(self, text: str) -> None:
        print(text)
        thread = self.client.get_channel(ALERTS_THREAD_ID)
        await thread.send(
            content=text
        )

    async def get_messages_to_move(self, reference_message: discord.Message) -> list[discord.Message]:
        """  
        Get a list[Message] for all messages that should be used in the new post
        """
        await self.send_debug_message("Get messages to move triggered")
        messages_to_move: list[discord.Message] = [reference_message]
        async for msg in reference_message.channel.history(limit=None, after=reference_message.created_at):
            await self.send_debug_message(f"get messages to move, iteration message: {msg.jump_url}")
            if msg.author == reference_message.author:
                await self.send_debug_message("Get messages to move, is author")
                messages_to_move.append(msg)
            else:
                await self.send_debug_message("Get messages to move- not author, broke loop")
                break
        await self.send_debug_message("Get messages to move- finished")
        return messages_to_move

    async def get_files(self, messages: list[discord.Message]) -> list[discord.File]:
        """  
        Returns list[File] for all attachments (files) that should be used in the new post 
        """
        await self.send_debug_message("get files triggered")
        files = []
        for msg in messages:
            await self.send_debug_message(f"get files, iteration msg: {msg.jump_url}")
            for attachment in msg.attachments:
                await self.send_debug_message(f"get files, iteration attachment filename: {attachment.filename}")
                files.append(await attachment.to_file())
        await self.send_debug_message("get files, finisehd")
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
        await self.send_debug_message("get content triggered")
        content = 'No message content found'
        messages_content: list[discord.Message] = []
        for message in messages:
            await self.send_debug_message(f"get content, iteration: {message.jump_url}")
            if message.content:
                await self.send_debug_message(f"message has content")
                messages_content.append(message.content)
        if messages_content:
            content = '\n'.join(messages_content)
        await self.send_debug_message(f"get content finished.\nContent: `{content}`")
        return content

    async def handle_request(self, reference_message: discord.Message, user: discord.Member, message: discord.Message|None = None) -> discord.Thread:
        await self.send_debug_message("handle request triggered")
        messages_to_move: list[discord.Message] = await self.get_messages_to_move(reference_message)
        files = await self.get_files(messages=messages_to_move)
        content = await self.get_content(messages_to_move)
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        title = f"Support for {reference_message.author.name}"
        await self.send_debug_message(f"initial title: `{title}`")
        if message and message.content.removeprefix(self.client.user.mention): # make sure the message has a content beyond @sapphire helper
            title = message.content.removeprefix(self.client.user.mention) 
        await self.send_debug_message(f"Finalized title: `{title}`")
        post = await support.create_thread(
            name=title,
            files=files,
            content=f"**Original message:**\n```\n{content}```\n\n{reference_message.author.mention} please provide any additional information here so we can give you the best help.\n-# Created by {user.name}"
        )
        await self.send_debug_message(f"Post created- {post[0].mention}")
        await add_post_to_rtdr(post_id=post[0].id, user_id=reference_message.author.id)
        await self.send_debug_message(f"Post added to db, `{post[0].id} = {reference_message.author.id}`")
        return post[0]

    @commands.Cog.listener('on_message')
    async def redirect_to_support(self, message: discord.Message):
        if not message.author.bot:
            await self.send_debug_message("on message triggered, not bot")
            if message.channel.id == GENERAL_CHANNEL_ID and message.reference and message.content.startswith(self.client.user.mention):
                await self.send_debug_message("is in genreal, has reference, starts with client user mention")
                experts = message.guild.get_role(EXPERTS_ROLE_ID)
                moderators = message.guild.get_role(MODERATORS_ROLE_ID)
                if experts in message.author.roles or moderators in message.author.roles:
                    await self.send_debug_message("message author has experts or mods")
                    replied_message = await message.channel.fetch_message(message.reference.message_id)
                    if not replied_message.author == message.author:
                        await self.send_debug_message("replied message author is not message author")
                        post = await self.handle_request(reference_message=replied_message, user=message.author, message=message)
                        await self.send_debug_message("after handle request")
                        await message.reply(content=f"Post created at {post.mention}", mention_author=False, delete_after=5)
                        await self.send_debug_message("replied with post created message")
                else:
                    return
        
    @commands.Cog.listener('on_reaction_add')
    async def reaction_redirect_to_support(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        await self.send_debug_message("on reaction add triggered")
        if reaction.message.channel.id == GENERAL_CHANNEL_ID:
            await self.send_debug_message("reaction channel is general")
            reactions = ["❓", "❔"] # allowed reactions, all other reactions will be ignored in this context
            if reaction.message.author != user and reaction.emoji in reactions:
                await self.send_debug_message("")
                experts = reaction.message.guild.get_role(EXPERTS_ROLE_ID)
                mods = reaction.message.guild.get_role(MODERATORS_ROLE_ID)
                if experts in user.roles or mods in user.roles:
                    await self.handle_request(reaction.message, user=user)
                    await reaction.remove(user)

async def setup(client):
    await client.add_cog(readthedamnrules(client))