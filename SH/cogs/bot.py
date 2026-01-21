from __future__ import annotations

import discord
from discord.ext import commands
import datetime
from discord import app_commands, ui
import os
from dotenv import load_dotenv
import functions
import psutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import MyClient

load_dotenv()

EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

class bot(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client

    @commands.command(name="ping")
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def ping(self, ctx: commands.Context):
        now = datetime.datetime.now()
        message = await ctx.reply(content=f"Pong!\nClient latency: {str(self.client.latency)[:4]}s", mention_author=False)
        latency = datetime.datetime.now() - now
        await message.edit(content=f"{message.content}\nDiscord latency: {str(latency.total_seconds())[:4]}s")

    @commands.command(name="restart")
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def restart(self, ctx: commands.Context):
        cogs_dir = Path(__file__).parent
        extensions = os.listdir(cogs_dir)
        for filename in extensions:
            if filename.endswith(".py"):
                await self.client.reload_extension(f"cogs.{filename[:-3]}")

        await ctx.reply(content=f"Reloaded {len(extensions)} extension(s)", mention_author=False)

    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def sync(self, ctx: commands.Context):
        try:
            synced = await self.client.tree.sync()
        except discord.app_commands.CommandSyncFailure as error:
            await ctx.reply(content=f"Command Sync Failure.\n`{error.text}`", mention_author=False)
            return
        await ctx.reply(content=f"Successfully synced {len(synced)} slash command(s)", mention_author=False)

    @app_commands.command(name="debug", description="Debug for various systems")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(debug = "Options: last message id | in db | timestamp | more than 24 hours | eval sql ... | check post", post = "The post to debug")
    async def debug(self, interaction: discord.Interaction, debug: str, post: discord.Thread = None):
        if debug in ("last_message_id", "in_db", "timestamp", "more_than_24_hours", "check_post") and post is None:
            await interaction.response.send_message(f"To use the `{debug}` debug, a post must be provided.", ephemeral=True)
        elif debug == "last_message_id":
            await interaction.response.send_message(content=post.last_message_id)
        elif debug == "in_db":
            await interaction.response.send_message(content=post.id in await functions.get_pending_posts())
        elif debug == "timestamp":
            await interaction.response.send_message(content=await functions.get_post_timestamp(post.id) or 'Unknown')
        elif debug == "more_than_24_hours":
            await interaction.response.send_message(content=await functions.check_post_last_message_time(post.id))
        elif debug.startswith("eval sql"):
            command = debug.removeprefix('eval sql ').strip("<>")
            await interaction.response.send_message(content=f"Executed SQL. Results: ```json\n{await functions.execute_sql(command)}```")
        elif debug == "check_post":
            applied_tags = post._applied_tags
            ndr = int(os.getenv("NEED_DEV_REVIEW_TAG_ID")) not in applied_tags
            solved = int(os.getenv("SOLVED_TAG_ID")) not in applied_tags
            archived = not post.archived
            locked = not post.locked
            is_pending = post.id not in await functions.get_pending_posts()
            try:
                last_message = post.last_message or await post.fetch_message(post.last_message_id)
            except discord.NotFound:
                last_message = None
            message_time = False
            author_is_owner = False
            owner_id = await functions.get_post_creator_id(post.id) or post.owner_id
            if last_message:
                author_is_owner = last_message.author.id != owner_id
                message_time = functions.check_time_more_than_day(last_message.created_at.timestamp())
            await interaction.response.send_message(f"NDR: {ndr} | solved: {solved} | archived: {archived} | locked: {locked} | message time: {message_time} | author is owner: {author_is_owner} | pending: {is_pending} | **total: {ndr and solved and archived and locked and author_is_owner and message_time and is_pending}**")
        else:
            await interaction.response.send_message(content="Debug not found...", ephemeral=True)

    @debug.autocomplete('debug')
    async def debug_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name='last message id', value='last_message_id'),
            app_commands.Choice(name='in db', value= 'in_db'),
            app_commands.Choice(name='timestamp', value='timestamp'),
            app_commands.Choice(name='more than 24 hours', value='more_than_24_hours'),
            app_commands.Choice(name='eval sql <command>', value='eval sql'),
            app_commands.Choice(name='check post', value='check_post')
        ]

    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def stats(self, ctx: commands.Context):
        view = ui.LayoutView()
        container = ui.Container(accent_colour=0xA06BE6)

        title = ui.TextDisplay("## [Sapphire helper | Version 6.0](https://github.com/kiki0124/sapphire-helper)")

        info_text = (f"**CPU Count:** {os.cpu_count()}\n"
                     f"**CPU Load:** {psutil.cpu_percent()}%\n"
                     f"**Available memory:** {str(round(psutil.virtual_memory()[0]/1000000000))}GB\n"
                     f"**Memory Usage:** {psutil.virtual_memory()[2]}%\n"
                     f"-# discord.py version {discord.__version__}")
        
        container.add_item(title)
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay(info_text))
        view.add_item(container)
        await ctx.reply(view=view, mention_author=False)

async def setup(client: MyClient):
    await client.add_cog(bot(client))