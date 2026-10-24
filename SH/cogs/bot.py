from __future__ import annotations

import discord
from discord.ext import commands
from time import perf_counter
from discord import ui
import os
from dotenv import load_dotenv
import psutil
from pathlib import Path
import time
from sys import version_info as py_version
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from main import SHBot
    from epi import EPI

load_dotenv()

EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

class Bot(commands.Cog):
    def __init__(self, bot: SHBot):
        self.bot = bot
        self.last_restarted = time.time()

        self.process = psutil.Process()

    @staticmethod
    def get_cooldown_key(ctx: commands.Context):
        if ctx.author.get_role(EXPERTS_ROLE_ID) or ctx.author.get_role(MODERATORS_ROLE_ID) or ctx.author.get_role(DEVELOPERS_ROLE_ID):
            return None
        return commands.Cooldown(1, 15)

    @commands.command(name="ping")
    @commands.guild_only()
    @commands.dynamic_cooldown(get_cooldown_key, type=commands.BucketType.member)
    async def ping(self, ctx: commands.Context):
        start = perf_counter()
        message = await ctx.reply(content=f"Pong!\nClient latency: {str(self.bot.latency)[:4]}s", mention_author=False)
        latency = perf_counter() - start
        await message.edit(content=f"{message.content}\nDiscord latency: {latency:.2f}s")

    @commands.command(name="restart")
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def restart(self, ctx: commands.Context):
        cog: EPI = self.bot.get_cog("EPI") # type: ignore
        if cog.epi_data:
            await ctx.send("EPI is currently enabled, please disable it first before restarting!", delete_after=10)
            return
        cogs_dir = Path(__file__).parent
        extensions = os.listdir(cogs_dir)
        for filename in extensions:
            if filename.endswith(".py"):
                await self.bot.reload_extension(f"cogs.{filename[:-3]}")

        await ctx.reply(content=f"Reloaded {len(extensions)} extension(s)", mention_author=False)

    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def sync(self, ctx: commands.Context):
        try:
            synced = await self.bot.tree.sync()
        except discord.app_commands.CommandSyncFailure as error:
            await ctx.reply(content=f"Command Sync Failure.\n`{error.text}`", mention_author=False)
            return
        await ctx.reply(content=f"Successfully synced {len(synced)} slash command(s)", mention_author=False)


    @staticmethod
    def convert_bytes(bytes: int, to: Literal['MB', 'GB'] = 'GB') -> float:
        if to == 'GB':
            return bytes / (1024 ** 3)

        return bytes / (1024 ** 2)

    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def stats(self, ctx: commands.Context):
        view = ui.LayoutView()
        container = ui.Container(accent_colour=0xA06BE6)

        title = ui.TextDisplay("## [Sapphire Helper | Version 6.3](https://github.com/kiki0124/sapphire-helper)")

        cpu_text = (f"- **CPU Count:** {os.cpu_count()}",
                     f"- **CPU Load:** {psutil.cpu_percent()}%")

        virtual_mem = psutil.virtual_memory()
        ram_total = virtual_mem.total
        sh_ram_usage = self.process.memory_info().rss
        sh_ram_usage_percent = (sh_ram_usage / ram_total) * 100
        mem_text = (f"- **Total Ram:** {self.convert_bytes(ram_total):.0f}GB",
                    f"- **Total Ram Usage:** {self.convert_bytes(virtual_mem.used):.0f}GB ({virtual_mem.percent}%)",
                    f"- **SH Ram Usage:** {self.convert_bytes(sh_ram_usage):.1f}GB ({sh_ram_usage_percent:.1f}%)")


        python_version_fmt = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
        other_info_text = (
                     f"- **Uptime (since)**: <t:{int(self.bot.uptime)}:R>",
                     f"- **Last Restarted**: <t:{int(self.last_restarted)}:R>\n",
                     f"-# discord.py {discord.__version__}  •  python {python_version_fmt}")
        
        container.add_item(title)
        container.add_item(ui.Separator())

        container.add_item(ui.TextDisplay('\n'.join(cpu_text)))
        container.add_item(ui.TextDisplay('\n'.join(mem_text)))
        container.add_item(ui.TextDisplay('\n'.join(other_info_text)))

        view.add_item(container)
        await ctx.reply(view=view, mention_author=False)

async def setup(bot: SHBot):
    await bot.add_cog(Bot(bot))
