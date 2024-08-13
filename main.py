import discord
from discord.ext import commands
import os
from variables import BOT_TOKEN, PREFIXES

client = commands.Bot(command_prefix=PREFIXES ,intents=discord.Intents.all(), help_command=None, strip_after_prefix=True)

@client.event
async def on_ready():
    print(f"Bot is ready. Logged in as {client.user.name}")

@client.event
async def setup_hook():
    for filename in os.listdir('./cogs'): # List all files in cogs folder
        if filename.endswith('.py'): # Check if file is a Python file
            await client.load_extension(f"cogs.{filename[:-3]}") # Load the file as an extension/cog
            print(f"Loaded cog {filename[:-3]}")
        else:
            print(f"Skipped loading {filename[:-3]}")

client.run(BOT_TOKEN)