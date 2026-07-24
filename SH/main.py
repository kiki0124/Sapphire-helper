import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from dotenv import load_dotenv
from functions import setup_db
import unittest, test_functions
from pathlib import Path
import time
from aiocache import cached

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
                        allowed_installs=app_commands.AppInstallationType(guild=True)
                         )

        self.alert_webhook_url: str | None = None
        self.incomplete_msg_posts: set[int] = set() # list of the post ids
        self.uptime = time.time() # used in cogs/bot,py

    async def setup_hook(self):
        unittest.main(test_functions, exit=False)
        await setup_db() # function that creates the db tables if they don't already exist
        cog_dir = Path(__file__).parent / 'cogs'
        for filename in os.listdir(cog_dir):
            if filename.endswith('.py'):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded extension {filename[:-3]}")
            else:
                print(f"Skipped loading {filename[:-3]}")

    async def send_log(self, thread_id: int, *, content: str = "", **kwargs) -> discord.WebhookMessage | None:
        if 'action_id' in kwargs:
            content = f"ID: {kwargs['action_id']}\nPost: {kwargs['post_mention']}\nTags: {', '.join([tag.name for tag in kwargs['tags']])}\nContext: {kwargs['context']}"
    
        if thread_id == ALERTS_THREAD_ID and self.alert_webhook_url is not None:
            webhook = discord.Webhook.from_url(self.alert_webhook_url, client=self)
            try:
                return await webhook.send(
                    content=content,
                    username=self.user.name,
                    avatar_url=self.user.display_avatar.url,
                    thread=discord.Object(thread_id),
                    wait=kwargs.get('wait', False),
                    allowed_mentions=kwargs.get('allowed_mentions', discord.AllowedMentions.none())
                )
            except discord.HTTPException:
                pass
        log_thread = self.get_channel(thread_id) or await self.fetch_channel(thread_id)
        webhooks = [webhook for webhook in await log_thread.parent.webhooks() if webhook.token]
        if not webhooks:
            webhook = await log_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        else:
            webhook = webhooks[0]

        if thread_id == ALERTS_THREAD_ID:
            self.alert_webhook_url = webhook.url # Assign only if the url is None.
        return await webhook.send(
            content=content,
            username=self.user.name,
            avatar_url=self.user.display_avatar.url,
            thread=discord.Object(thread_id),
            wait=kwargs.get('wait', False),
            allowed_mentions=kwargs.get('allowed_mentions', discord.AllowedMentions.none())
        )

    # This is defined here so that tasks.loop errors can use this
    async def send_unhandled_error(self, error: BaseException, *, interaction: discord.Interaction | None = None, task: tasks.Loop | None = None) -> None:
        # 1105414178937774150 - Kiki, 802167689011134474 - Sacul
        content = f"<@1105414178937774150> <@802167689011134474>\nUnhandled error: `{error}`"

        if interaction:
            interaction_created_at = interaction.created_at.timestamp()
            interaction_data = interaction.data or {}
            content += f"\n### Interaction Error:\n>>> Interaction created at <t:{round(interaction_created_at)}:T> (<t:{round(interaction_created_at)}:R>)\
                \nUser: {interaction.user.mention} | Channel: {interaction.channel.mention} | Type: {interaction.type.name}"
            if interaction.command and interaction.command.parent is None:
                command_id = interaction_data.get('id', 0)
                options_dict  = interaction_data.get("options", [])
                command_mention = f"</{interaction.command.qualified_name}:{command_id}>"
                content += f"\nCommand: {command_mention}, inputted values:"

                options_formatted = " \n".join([f"- {option.get('name', 'Unknown')}: {option.get('value', 'Unknown')}" for option in options_dict])
                content += f"\n```{options_formatted}```"
            else:
                content += f"\n```json\n{interaction.data}```"
        elif task:
            content += f"\n### Tasks.Loop Error:\n>>> - {task._name}\n- Current iterations: `{task.current_loop}`"
        await self.send_log(ALERTS_THREAD_ID, content=content, 
                            allowed_mentions=discord.AllowedMentions(users=[discord.Object(1105414178937774150), discord.Object(802167689011134474)]))

    @cached()
    async def get_unsolve_id(self) -> int:
        """  
        Get the id of /unsolve command.
        This fetches the command from discord and caches the result
        """
        unsolve_id = 1281211280618950708
        for command in await self.tree.fetch_commands():
            if command.name == "unsolve": 
                unsolve_id=command.id
                break
        return unsolve_id

    @cached()
    async def get_solved_id(self):
        solved_id = 1274997472162349079
        for command in await self.tree.fetch_commands():
            if command.name == "solved": 
                solved_id=command.id
                break
        return solved_id

    async def on_ready(self):
        print(f"Bot is ready. Logged in as {self.user.name}")

MyClient().run(TOKEN)