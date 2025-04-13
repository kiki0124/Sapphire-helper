import discord
from discord.ext import commands
import datetime
from discord import app_commands
import os
from dotenv import load_dotenv
from traceback import print_exception
import functions

load_dotenv()

EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))

class bot(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client

    def cog_load(self):
        self.client.tree.on_error = self.tree_on_error
    
    async def send_unhandled_error(self, error: commands.CommandError|app_commands.AppCommandError, interaction: discord.Interaction = None) -> None:
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        content=f"Unhandled error: `{error}`\n<@1105414178937774150>"
        await alerts_thread.send(content=content)
        if interaction:
            await alerts_thread.send(content=f"Interaction created at `{interaction.created_at.timestamp()}` <t:{round(interaction.created_at.timestamp())}:f>. Now `{datetime.datetime.now().timestamp()}` <t:{round(datetime.datetime.now().timestamp())}:f>")

    @commands.command(name="ping")
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def ping(self, ctx: commands.Context):
        now = datetime.datetime.now()
        message = await ctx.reply(content=f"Pong! v3.1\nClient latency: {str(self.client.latency)[:4]}s")
        latency = datetime.datetime.now() - now
        await message.edit(content=f"{message.content}\nDiscord latency: {str(latency.total_seconds())[:4]}s")

    @commands.command(name="restart")
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def restart(self, ctx: commands.Context):
        extensions = os.listdir("./cogs")
        await ctx.reply(content=f"Reloading {len(extensions)} extension(s)", mention_author=False)
        for filename in extensions:
            if filename.endswith(".py"):
                await self.client.reload_extension(f"cogs.{filename[:-3]}")
            else:
                continue

    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def sync(self, ctx: commands.Context):
        try:
            synced = await self.client.tree.sync()
        except discord.app_commands.CommandSyncFailure as error:
            await ctx.reply(content=f"Command Sync Failure.\n`{error.text}`", mention_author=False)
            return
        await ctx.reply(content=f"Successfully synced {len(synced)} slash command(s)", mention_author=False)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.reply(content="This command cannot be executed in DM channels.", mention_author=False)
        elif isinstance(error, commands.errors.MissingAnyRole):
            await ctx.reply(content="Insufficient permissions- you are not allowed to execute this command.", mention_author=False)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(content="Command currently on cooldown, try again later...", mention_author=False)
        else:
            await self.send_unhandled_error(error=error) # send error to #sapphire-helper-alerts thread under sapphire-experts channel
            raise error

    async def tree_on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingAnyRole):
            await interaction.response.send_message(content=f"Only <@&{MODERATORS_ROLE_ID}> and <@&{EXPERTS_ROLE_ID}> can use this command!", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure): # raised when a user tries to use a command that only mods/experts/op can use, eg /solved
            await interaction.response.send_message(content=f"Only <@&{MODERATORS_ROLE_ID}>, <@&{EXPERTS_ROLE_ID}> and the OP can use this command and only in #support!", ephemeral=True)
        elif isinstance(error, app_commands.NoPrivateMessage):
            await interaction.response.send_message(content="You may not use this command in DMs!", ephemeral=True)
        else:
            await self.send_unhandled_error(error=error, interaction=interaction)
            print_exception(error)

    @app_commands.command(name="debug", description="Debug for various systems")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def debug(self, interaction: discord.Interaction, debug: str, post: discord.Thread = None):
        if debug == "last message id":
            await interaction.response.send_message(content=post.last_message_id)
        elif debug == "in db":
            await interaction.response.send_message(content=post.id in await functions.get_pending_posts())
        elif debug == "timestamp":
            await interaction.response.send_message(content=await functions.get_post_timestamp(post.id))
        elif debug == "more than 24 hours":
            await interaction.response.send_message(content=await functions.check_post_last_message_time(post.id))
        elif debug.startswith("eval sql"):
            command = debug.removeprefix('eval sql ')
            await interaction.response.send_message(content=f"Executed SQL. Results: `{await functions.execute_sql(command)}`")
        else:
            await interaction.response.send_message(content="Debug not found...", ephemeral=True)

async def setup(client: commands.Bot):
    await client.add_cog(bot(client))