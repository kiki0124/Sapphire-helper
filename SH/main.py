import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from functions import main
import unittest, test_functions
from pathlib import Path
from collections import OrderedDict

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PREFIX = os.getenv("PREFIX")
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))

class MyClient(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.none()
        intents.message_content = True
        intents.guild_messages = True
        intents.guilds = True
        intents.members = True
        intents.guild_reactions = True
        super().__init__(PREFIX, help_command=None, intents=intents, strip_after_prefix=True, 
                        allowed_contexts=app_commands.AppCommandContext(guild=True),
                        allowed_installs=app_commands.AppInstallationType(guild=True),
                        member_cache_flags=discord.MemberCacheFlags.none()
                         )

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

    async def send_log(self, thread_id: int, *, content: str = "", **kwargs) -> None:
        if 'action_id' in kwargs:
            content = f"ID: {kwargs['action_id']}\nPost: {kwargs['post_mention']}\nTags: {', '.join([tag.name for tag in kwargs['tags']])}\nContext: {kwargs['context']}"
    
        if thread_id == ALERTS_THREAD_ID and self.alert_webhook_url is not None:
            webhook = discord.Webhook.from_url(self.alert_webhook_url, client=self)
            try:
                await webhook.send(
                    content=content,
                    username=self.user.name,
                    avatar_url=self.user.display_avatar.url,
                    thread=discord.Object(thread_id),
                    wait=kwargs.get('wait', False),
                    allowed_mentions=kwargs.get('allowed_mentions', discord.AllowedMentions.none())
                )
            except discord.HTTPException:
                pass
            else:
                return
        log_thread = self.get_channel(thread_id) or await self.fetch_channel(thread_id)
        webhooks = [webhook for webhook in await log_thread.parent.webhooks() if webhook.token]
        if not webhooks:
            webhook = await log_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        else:
            webhook = webhooks[0]

        if thread_id == ALERTS_THREAD_ID:
            self.alert_webhook_url = webhook.url # Assign only if the url is None. This should normally only be called once when running the bot
        await webhook.send(
            content=content,
            username=self.user.name,
            avatar_url=self.user.display_avatar.url,
            thread=discord.Object(thread_id),
            wait=kwargs.get('wait', False),
            allowed_mentions=kwargs.get('allowed_mentions', discord.AllowedMentions.none())
        )

    async def on_ready(self):
        print(f"Bot is ready. Logged in as {self.user.name}")

MyClient().run(TOKEN)