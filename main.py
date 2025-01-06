import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from functions import main

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PREFIX = os.getenv("PREFIX")

client = commands.Bot(command_prefix=PREFIX ,intents=discord.Intents.all(), help_command=None, strip_after_prefix=True)

@client.event
async def on_ready():
    print(f"Bot is ready. Logged in as {client.user.name}")

@client.event
async def setup_hook():
    await main() # function that creates the db table if they don't already exist
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await client.load_extension(f"cogs.{filename[:-3]}")
            print(f"Loaded extension {filename[:-3]}")
        else:
            print(f"Skipped loading {filename[:-3]}")

client.run(TOKEN)