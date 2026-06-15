from __future__ import annotations

import discord
from discord.ext import commands
import datetime
from discord import ui
import os
from dotenv import load_dotenv
import psutil
from pathlib import Path
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import MyClient

load_dotenv()

EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

class bot(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client
        self.last_restarted = time.time()

    @staticmethod
    def get_cooldown_key(ctx: commands.Context):
        if ctx.author.get_role(EXPERTS_ROLE_ID) or ctx.author.get_role(MODERATORS_ROLE_ID) or ctx.author.get_role(DEVELOPERS_ROLE_ID):
            return None
        return commands.Cooldown(1, 15)

    @commands.command(name="ping")
    @commands.guild_only()
    @commands.dynamic_cooldown(get_cooldown_key, type=commands.BucketType.member)
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

    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def stats(self, ctx: commands.Context):
        view = ui.LayoutView()
        container = ui.Container(accent_colour=0xA06BE6)

        title = ui.TextDisplay("## [Sapphire helper | Version 6.1](https://github.com/kiki0124/sapphire-helper)")
        info_text = (f"- **CPU Count:** {os.cpu_count()}",
                     f"- **CPU Load:** {psutil.cpu_percent()}%",
                     f"- **Available memory:** {str(round(psutil.virtual_memory()[0]/1000000000))}GB",
                     f"- **Memory Usage:** {psutil.virtual_memory()[2]}%",
                     f"- **Uptime (since)**: <t:{int(self.client.uptime)}:R>",
                     f"- **Last Restarted**: <t:{int(self.last_restarted)}:R>",
                     f"-# discord.py version {discord.__version__}")
        
        container.add_item(title)
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay('\n'.join(info_text)))
        view.add_item(container)
        await ctx.reply(view=view, mention_author=False)

async def setup(client: MyClient):
    await client.add_cog(bot(client))
