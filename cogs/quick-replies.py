import discord
from discord.ext import commands
from discord import app_commands

"""  
Logic before I forget:
a slash command to add a new quick reply with its name, optional emoji, category?
Logic: wait_for message where author & channel == interaction.user, interaction.channel
Possible buttons with simple actions like send message, check - on_interaction, interaction.type == discord.InteractionType.component & custom_id.startswith 'custom' load the action form the db 
"""

class quick_replies(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client




async def setup(client: commands.Bot):
    await client.add_cog(quick_replies(client))