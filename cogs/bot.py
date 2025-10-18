import discord
from discord.ext import commands
import datetime
from discord import app_commands
import os
from dotenv import load_dotenv
from traceback import print_exception
import functions
import psutil
from functions import humanize_duration

load_dotenv()

EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

class bot(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client

    def cog_load(self):
        self.client.tree.on_error = self.tree_on_error
    
    async def send_unhandled_error(self, error: commands.CommandError|app_commands.AppCommandError, interaction: discord.Interaction | None = None) -> None:
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        content = f"<@1105414178937774150>\nUnhandled error: `{error}`"

        if interaction:
            interaction_created_at = interaction.created_at.timestamp()
            interaction_data = interaction.data or {}
            content += f"\n### Interaction Error:\n>>> Interaction created at <t:{round(interaction_created_at)}:T> (<t:{round(interaction_created_at)}:R>)\
                \nUser: {interaction.user.mention} | Channel: {getattr(interaction.channel, "mention", f"DM channel ({interaction.channel_id})")} | Type: {interaction.type.name}"
            if interaction.command and isinstance(interaction.command, app_commands.Command) and interaction.command.parent is None:
                command_id = interaction_data.get('id', 0)
                options_dict  = interaction_data.get("options", [])
                command_mention = f"</{interaction.command.qualified_name}:{command_id}>"
                content += f"\nCommand: {command_mention}, inputted values:"

                options_formatted = " \n".join([f"- {option.get('name', 'Unknown')}: {option.get('value', 'Unknown')}" for option in options_dict]) or "There are no inputted values."
                content += f"\n```{options_formatted}```"
            else:
                content += f"\n```json\n{interaction.data}```"
            await alerts_thread.send(content, allowed_mentions=discord.AllowedMentions(users=[discord.Object(1105414178937774150)])) #1105414178937774150 is Kiki's user ID
        else:
            await alerts_thread.send(content=content)

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
        extensions = os.listdir("./cogs")
        await ctx.reply(content=f"Reloading {len(extensions)} extension(s)", mention_author=False)
        for filename in extensions:
            if filename.endswith(".py"):
                await self.client.reload_extension(f"cogs.{filename[:-3]}")
            else:
                continue

    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
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
        send_message = interaction.response.send_message if not interaction.response.is_done() else interaction.followup.send
        if isinstance(error, app_commands.MissingAnyRole):
            await send_message(content=f"Only <@&{DEVELOPERS_ROLE_ID}>, <@&{MODERATORS_ROLE_ID}> and <@&{EXPERTS_ROLE_ID}> can use this command!", ephemeral=True)
        elif isinstance(error, app_commands.NoPrivateMessage):
            await send_message(content="You may not use this command in DMs!", ephemeral=True)
        elif isinstance(error, app_commands.CommandOnCooldown):
            await send_message(f"This command is on cooldown. You can run it again **{humanize_duration(error.retry_after)}**", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure): # raised when a user tries to use a command that only mods/experts/op can use, eg /solved
            await send_message(content=f"Only <@&{DEVELOPERS_ROLE_ID}>, <@&{MODERATORS_ROLE_ID}>, <@&{EXPERTS_ROLE_ID}> and the OP can use this command and only in #support!", ephemeral=True)
        else:
            await self.send_unhandled_error(error=error, interaction=interaction)
            print_exception(error)
            await send_message("An unexpected error occurred, the developer of Sapphire Helper has been notified.", ephemeral=True)

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
        embed = discord.Embed(
            title="Sapphire Helper | Version 5.0",
            colour=discord.Colour.purple(),
            url="https://github.com/kiki0124/sapphire-helper"
        )
        embed.add_field(name="CPU Count:", value=os.cpu_count(), inline=False)
        embed.add_field(name="CPU Load:", value=f"{psutil.cpu_percent()}%", inline=False)
        embed.add_field(name="Available Memory:", value=f"{str(round(psutil.virtual_memory()[0]/1000000000))}GB", inline=False)
        embed.add_field(name="Memory Usage:", value=f"{psutil.virtual_memory()[2]}%", inline=False)
        embed.set_footer(text=f"Discord.py version {discord.__version__}")
        await ctx.reply(embed=embed, mention_author=False)

async def setup(client: commands.Bot):
    await client.add_cog(bot(client))
