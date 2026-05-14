import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from functions import main
import unittest, test_functions
from pathlib import Path
from collections import OrderedDict

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
        super().__init__(PREFIX, help_command=None, intents=intents, strip_after_prefix=True, member_cache_flags=discord.MemberCacheFlags.none())

        self.alert_webhook_url: str | None = None
        self.incomplete_msg_posts: set[int] = set() # list of the post ids

        # NOTE: This only tracks members in one guild, i.e the support server
        self._members: OrderedDict[int, int] = OrderedDict()
        self._max_member_cache_size: int = 100

    def add_member_to_cache(self, member: discord.Member, /) -> None:
        """
        Adds a member's id to the custom cache.
        This should be called only when a post is created in the support forum.
        Since we only need to cache members there.
        """
        if member.id in self._members:
            self._members.move_to_end(member.id)
        else:
            self._members[member.id] = member.id
            if len(self._members) > self._max_member_cache_size:
                self._members.popitem(last=False)

    def member_in_cache(self, id: int, /) -> bool:
        """
        Check if the member is in the cache.
        Recommended to use REST api to check if not.
        """
        return bool(self._members.get(id))

    async def setup_hook(self):
        unittest.main(test_functions, exit=False)
        await main() # function that creates the db tables if they don't already exist
        cog_dir = Path(__file__).parent / 'cogs'
        for filename in os.listdir(cog_dir):
            if filename.endswith('.py'):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded extension {filename[:-3]}")
            else:
                print(f"Skipped loading {filename[:-3]}")

    async def on_ready(self):
        print(f"Bot is ready. Logged in as {self.user.name}")

MyClient().run(TOKEN)