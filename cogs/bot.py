import discord
from discord.ext import commands
from variables import EXPERTS_ROLE_ID, MODERATORS_ROLE_ID
import datetime
from discord import app_commands

class bot(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client

    def cog_load(self):
        tree = self.client.tree
        self._old_tree_error = tree.on_error
        tree.on_error = self.tree_on_error
    
    def cog_unload(self):
        tree = self.client.tree
        tree.on_error = self._old_tree_error

    @commands.command(name="ping")
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def ping(self, ctx: commands.Context):
        now = datetime.datetime.now() # create a datetime object from before sending the message
        message = await ctx.reply(content=f"Pong!\nClient latency: {str(self.client.latency)[:4]}s")
        latency = datetime.datetime.now() - now # create a new timedelta object that is worth the time before sening the message - now = the latency/delay
        await message.edit(content=f"{message.content}\nDiscord latency: {str(latency.total_seconds())[:4]}s") # edit the original message to include the latency

    @commands.command(name="restart")
    @commands.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def restart(self, ctx: commands.Context):
        extensions = self.client.extensions # declare a list of the extensions
        await ctx.reply(content=f"Reloading `{len(extensions)}` extensions")
        for extension in extensions: # initiate a loop for all of the extensions
            await self.client.reload_extension(extension) # reload each one

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
        elif isinstance(error, commands.errors.MissingAnyRole): # check if the error is MissingAnyRole
            embed = discord.Embed(
                title="No permissions",
                description=f"> You are not allowed to execute this command.",
                colour=0xCE3636
            )
            await ctx.reply(embed=embed, mention_author=False)
        elif isinstance(error, commands.errors.CommandOnCooldown): # Check if the error is CommandOnCooldown
            embed = discord.Embed(
                description="This command is currently on cooldown!",
                colour=discord.Colour.red()
            )
            await ctx.reply(embed=embed, mention_author=False)
        else: 
            raise error # raise the error if it isn't handled properly above

    async def tree_on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingAnyRole): # check if the error is MissingAnyRole
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(content=f"Only Moderators and Community Experts can use this command!", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure): # Check if the error is CheckFailure (failure of a custom check- checks if user is mod/expert/op)
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(content=f"Only Moderators, Community Experts and the OP can use this command!", ephemeral=True)
        elif isinstance(error, app_commands.NoPrivateMessage): # Check if the command was used in DMs
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(content="You may not use this command in DMs!", ephemeral=True)
        else:
            raise error # Raise the error if it wasn't handled properly above

async def setup(client: commands.Bot):
    await client.add_cog(bot(client))