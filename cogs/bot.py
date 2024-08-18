import discord
from discord.ext import commands
from variables import EXPERTS_ROLE_ID, MODERATORS_ROLE_ID

class bot(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client

    @commands.command()
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID) # check if the user executing the command has experts role or moderators role
    async def sync(self, ctx: commands.Context):
        try:
            synced = await self.client.tree.sync() # sync commands
        except discord.app_commands.CommandSyncFailure as error:
            await ctx.reply(content=f"Command Sync Failure.\n`{error.text}`", mention_author=False)
            return
        await ctx.reply(content=f"Successfully synced {len(synced)} slash command(s)", mention_author=False)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.errors.CommandNotFound): # Check if the specific error is CommandNotFound
            return # Ignore the error
        elif isinstance(error, commands.errors.NoPrivateMessage): # Check if the specific error is NoPrivateMessage- triggered when a command is used in DMs instead of normal server channel
            embed = discord.Embed(
                title="Command disabled in this channel",
                description="> This command cannot be executed in DM channels. You may only use guild channels.",
                colour=0xce3636
            )
            await ctx.reply(embed=embed, mention_author=False)
        elif isinstance(error, commands.errors.MissingAnyRole):
            embed = discord.Embed(
                title="No permissions",
                description=f"> You are not allowed to execute this command.",
                colour=0xCE3636
            )
            await ctx.reply(embed=embed, mention_author=False)

async def setup(client: commands.Bot):
    await client.add_cog(bot(client))