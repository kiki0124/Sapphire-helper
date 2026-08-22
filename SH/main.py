from __future__ import annotations

from typing import Literal

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import os
from dotenv import load_dotenv
from functions import setup_db
import unittest, test_functions
from pathlib import Path
import time
from aiocache import cached
from datetime import datetime, UTC

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

class SHBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.none()
        intents.message_content = True
        intents.guild_messages = True
        intents.guilds = True
        intents.guild_reactions = True
        super().__init__(commands.when_mentioned, help_command=None, intents=intents, strip_after_prefix=True, 
                        allowed_contexts=app_commands.AppCommandContext(guild=True),
                        allowed_installs=app_commands.AppInstallationType(guild=True)
                         )

        self.alert_webhook_url: str | None = None
        self.incomplete_msg_posts: set[int] = set() # list of the post ids
        self.uptime = time.time() # used in cogs/bot,py

        self.rtdr_posts: dict[int, int] = {} # posts for RTDR
        self.pending_posts: dict[int, int] = {} # posts for pending

        self.extensions_cmd.binding = self
        self.tree.add_command(self.extensions_cmd, override=True)

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


    async def perform_extension_action(self, action: Literal["load", "reload", "unload"], extension: str) -> None:
        currently_loaded = self.extensions.get(extension)
        if action == "load":
            if currently_loaded is False:
                await self.load_extension(extension)
        elif action == "reload":
            await self.reload_extension(extension)
        elif action == "unload":
            if currently_loaded:
                await self.unload_extension(extension)

    @app_commands.command(name="extensions", description="Manage the bot's extensions")
    @app_commands.describe(action="The action to perform", extension="The extension file to reload (if not specified, all extensions will be reloaded)")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID, MODERATORS_ROLE_ID)
    async def extensions_cmd(self, interaction: discord.Interaction, action: Literal["load", "reload", "unload"] | None = None, extension: str | None = None):
        await interaction.response.defer(ephemeral=True)
        cog_dir = Path(__file__).parent / 'cogs'
        files = [file for file in os.listdir(cog_dir) if file.endswith('.py')]
        if action is None:

            files = sorted(files)

            loaded = {file: f"cogs.{file[:-3]}" for file in files if f"cogs.{file[:-3]}" in self.extensions}
            not_loaded = [file for file in files if f"cogs.{file[:-3]}" not in self.extensions]

            view = ui.LayoutView()

            header_container = ui.Container(ui.TextDisplay("## Extensions"), ui.Separator())
            header_container.add_item(ui.TextDisplay(f"- Loaded: **{len(loaded)}/{len(files)}**"))
            header_container.accent_color = discord.Colour.green() if not not_loaded else discord.Colour.brand_red()
            view.add_item(header_container)

            if loaded:
                loaded_container = ui.Container(ui.TextDisplay("### Loaded"), ui.Separator())
                for file, ext_name in loaded.items():
                    content = f"- ✅ `{file}`"
                    loaded_container.add_item(ui.TextDisplay(content))
                loaded_container.accent_color = discord.Colour.green()
                view.add_item(loaded_container)

            if not_loaded:
                not_loaded_container = ui.Container(ui.TextDisplay("### Not loaded"), ui.Separator())
                fmt = "\n".join(f"- ❌ `{file}`" for file in not_loaded)
                not_loaded_container.add_item(ui.TextDisplay(fmt))
                not_loaded_container.accent_color = discord.Colour.brand_red()
                view.add_item(not_loaded_container)

            await interaction.followup.send(view=view, ephemeral=True)
            return

        else:
            if extension is None:
                for file in files:
                    try:
                        await self.perform_extension_action(action, f"cogs.{file[:-3]}")
                    except commands.ExtensionError as error:
                        await interaction.followup.send(f"Failed to {action} `{file[:-3]}`: `{error}`", ephemeral=True)
                        return
                await interaction.followup.send(f"{action.capitalize()}ed all extensions!", ephemeral=True)
                return

            try:
                await self.perform_extension_action(action, f"cogs.{extension}")
            except commands.ExtensionError as error:
                await interaction.followup.send(f"Failed to {action} `{extension}`: `{error}`", ephemeral=True)
            else:
                await interaction.followup.send(f"{action.capitalize()}ed `{extension}`!", ephemeral=True)

    @extensions_cmd.autocomplete("extension")
    async def extensions_autocomplete(self, _: discord.Interaction, current: str):
        cog_dir = Path(__file__).parent / 'cogs'
        files = [file for file in os.listdir(cog_dir) if file.endswith('.py')]
        choices = [app_commands.Choice(name=file, value=file[:-3]) for file in files if current.lower() in file.lower()]
        return choices[:25]

    async def get_post_owner_id(self, post: discord.Thread | app_commands.AppCommandThread) -> int:
        """
        Helper function to get the owner ID for a support post. Returns `0` if not found.
        """
        if post.owner_id != self.user.id:
            return post.owner_id

        # Created by RTDR
        owner_id = self.rtdr_posts.get(post.id)
        if owner_id is None:
            left_paren_index = post.name.rfind("(")
            if left_paren_index == -1:
                return 0

            # Example title: Support for @username (USER_ID)
            try:
                return int(post.name[left_paren_index + 1:len(post.name) - 1])
            except (ValueError, IndexError):
                return 0
        return owner_id


    # CACHE HELPER FUNCTIONS
    def add_post_to_rtdr(self, thread_id: int, owner_id: int) -> None:
        """
        Adds a post to the `RTDR` cache.
        """
        self.rtdr_posts[thread_id] = owner_id

    def remove_post_from_rtdr(self, thread_id: int) -> None:
        """
        Removes a post from the `RTDR` cache.
        """
        self.rtdr_posts.pop(thread_id, None)


    def add_post_to_pending(self, thread_id: int) -> None:
        """
        Adds a post to the `pending_posts` cache and store the time it was inserted at.
        """
        now = int(datetime.now(UTC).timestamp())
        self.pending_posts[thread_id] = now

    def remove_post_from_pending(self, thread_id: int) -> None:
        """
        Removes a post from the `pending_posts` cache
        """
        self.pending_posts.pop(thread_id, None)


    async def on_ready(self):
        print(f"Bot is ready. Logged in as {self.user.name}")

SHBot().run(TOKEN)