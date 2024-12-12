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

class readthedamnrules(commands.Cog):
    def __init__(self, client) -> None:
        self.client: commands.Bot = client
    
    async def handle_request(self, reference_message: discord.Message, user: discord.Member, message: discord.Message|None = None) -> discord.Thread:
        #replied_message = await message.channel.fetch_message(message.reference.message_id) # get a full Message object from the replied message id
        messages_to_move: list[discord.Message] = [reference_message] # declare a list of the messages to move to the new post
        async for msg in reference_message.channel.history(limit=None, after=reference_message.created_at):
            if msg.author == reference_message.author:
                messages_to_move.append(msg) # add the message to the list of messages to move as its author is the author of the reply message
            else:
                break # break the loop as the message author is any other user
        files = [] # declare a list of initial attachments to add to the post's starter message
        for msg in messages_to_move: # start a for loop for all of the messages in messages_to_move list
            for attachment in msg.attachments: files.append(await attachment.to_file())
        content = ''.join(m.content+"\n" for m in messages_to_move)
        support = self.client.get_channel(SUPPORT_CHANNEL_ID)
        if message: 
            title = message.content.removeprefix(message.guild.me.mention) or f"Support for {reference_message.author.name}"
        else:
            title = f"Support for {reference_message.author.name}"
        post_data = await support.create_thread(
            name=title,
            files=files,
            content=f"**Original message:**\n```\n{content}```\n\n{reference_message.author.mention} please provide any additional information here so we can give you the best help.\n-# Created by {user.name}"
        )
        await add_post_to_rtdr(post_id=post_data[0].id, user_id=reference_message.author.id)
        return post_data[0]

    @commands.Cog.listener('on_message')
    async def redirect_to_support(self, message: discord.Message):
        if not message.author.bot:
            if message.channel.id == GENERAL_CHANNEL_ID and message.reference and message.guild.me in message.mentions:
                experts = message.guild.get_role(EXPERTS_ROLE_ID)
                moderators = message.guild.get_role(MODERATORS_ROLE_ID)
                if experts in message.author.roles or moderators in message.author.roles:
                    replied_message = await message.channel.fetch_message(message.reference.message_id)
                    if not replied_message.author == message.author:
                        message_reference = await message.channel.fetch_message(message.reference.message_id)
                        post = await self.handle_request(reference_message=message_reference, user=message.author, message=message)
                        await message.reply(content=f"Post created at {post.mention}", mention_author=False, delete_after=5)
                else:
                    return
        
    @commands.Cog.listener('on_reaction_add')
    async def reaction_redirect_to_support(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        if reaction.message.channel.id == GENERAL_CHANNEL_ID:
            reactions = ["❓", "❔"]
            if reaction.message.author != user and (reaction.emoji in reactions):
                experts = reaction.message.guild.get_role(EXPERTS_ROLE_ID)
                mods = reaction.message.guild.get_role(MODERATORS_ROLE_ID)
                if experts in user.roles or mods in user.roles:
                    await self.handle_request(reaction.message, user=user)
                    await reaction.remove(user)

async def setup(client):
    await client.add_cog(readthedamnrules(client))
    