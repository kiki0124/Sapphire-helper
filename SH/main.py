import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from functions import main
import unittest, test_functions

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PREFIX = os.getenv("PREFIX")

class MyClient(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.none()
        intents.message_content = True
        intents.guild_messages = True
        intents.guilds = True
        intents.members = True
        intents.guild_reactions = True
        super().__init__(PREFIX, help_command=None, intents=intents, strip_after_prefix=True)

        self.alert_webhook_url: str | None = None

    async def setup_hook(self):
        unittest.main(test_functions, exit=False)
        await main() # function that creates the db tables if they don't already exist
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded extension {filename[:-3]}")
            else:
                print(f"Skipped loading {filename[:-3]}")

    async def on_ready(self):
        print(f"Bot is ready. Logged in as {self.user.name}")

MyClient().run(TOKEN)