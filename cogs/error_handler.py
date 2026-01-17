from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from functions import format_list
from dotenv import load_dotenv
from traceback import print_exception
import os

load_dotenv()
ALERTS_THREAD_ID = int(os.getenv("ALERTS_THREAD_ID"))
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from main import MyClient

class ErrorHandler(commands.Cog):
	def __init__(self, client: MyClient):
		self.client = client
	

	def cog_load(self):
		self.client.tree.on_error = self.on_tree_error


	async def send_unhandled_error(self, error: commands.CommandError|app_commands.AppCommandError, interaction: discord.Interaction | None = None) -> None:
		"""Alert kiki about an unhandled command error"""
		alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
		content = f"<@1105414178937774150>\nUnhandled error: `{error}`"

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
			await alerts_thread.send(content, allowed_mentions=discord.AllowedMentions(users=[discord.Object(1105414178937774150)])) #1105414178937774150 is Kiki's user ID
		else:
			await alerts_thread.send(content=content)


	@commands.Cog.listener()
	async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
		"""
		Handles text command errors

		Errors are handled based on the hierarchy in [the dpy docs](https://discordpy.readthedocs.io/en/stable/ext/commands/api.html#exception-hierarchy)
		"""
		if isinstance(e, commands.CommandNotFound):
			return
		elif isinstance(e, commands.CheckFailure):
			await self.handle_text_command_check_failure(ctx, e)
		elif isinstance(e, commands.CommandOnCooldown):
			error_message = f"This command is on cooldown for another **{e.retry_after:.2f} seconds**!"
			await ctx.reply(content=error_message, mention_author=False)
		else:
			await self.send_unhandled_error(error=e) # send error to #sapphire-helper-alerts thread under sapphire-experts channel
			raise e


	async def on_tree_error(self, interaction: discord.Interaction, e: app_commands.AppCommandError):
		"""
		Handles application command errors

		Errors are handled based on the hierarchy in [the dpy docs](https://discordpy.readthedocs.io/en/stable/interactions/api.html#exception-hierarchy)
		"""
		if isinstance(e, app_commands.CheckFailure):
			await self.handle_app_command_check_failure(interaction, e)
		else:
			await self.send_unhandled_error(e, interaction)
			print_exception(e)


	@staticmethod
	async def handle_text_command_check_failure(ctx: commands.Context, e: commands.CheckFailure):
		"""
		Handles errors raised by a user not passing the command check decorators for text commands
		"""
		if isinstance(e, commands.NoPrivateMessage):
			error_message = "You may not use this command in DMs!"
		elif isinstance(e, commands.MissingRole):
			error_message = f"Only <@&{e.missing_role}> can use this command!"
		elif isinstance(e, commands.MissingAnyRole):
			missing_roles = [f"<@&{role_id}>" for role_id in e.missing_roles]
			error_message = f"Only {format_list(missing_roles)} can use this command!"

		await ctx.reply(content=error_message, mention_author=False, allowed_mentions=discord.AllowedMentions.none())


	@staticmethod
	async def handle_app_command_check_failure(interaction: discord.Interaction, e: app_commands.CheckFailure) -> None:
		"""
		Handles errors raised by a user not meeting the command check decorators for application commands
		"""
		if isinstance(e, app_commands.NoPrivateMessage):
			error_message = "You may not use this command in DMs!"
		elif isinstance(e, app_commands.MissingRole):
			error_message = f"Only <@&{e.missing_role}> can use this command!"
		elif isinstance(e, app_commands.MissingAnyRole):
			missing_roles = [f"<@&{role_id}>" for role_id in e.missing_roles]
			error_message = f"Only {format_list(missing_roles)} can use this command!"
		elif isinstance(e, app_commands.MissingPermissions):
			missing_perms = "`, `".join(e.missing_permissions)
			error_message = f"Only users with these permissions can use this command: `{missing_perms}`!"
		elif isinstance(e, app_commands.BotMissingPermissions):
			missing_bot_perms = "`, `".join(e.missing_permissions)
			error_message = f"I need the following permissions to be able to execute this command: `{missing_bot_perms}`!"
		elif isinstance(e, app_commands.CommandOnCooldown):
			error_message = f"This command is on cooldown for another **{e.retry_after:.2f} seconds**!"
		else:
			error_message = f"Only <@&{DEVELOPERS_ROLE_ID}>, <@&{MODERATORS_ROLE_ID}> and <@&{EXPERTS_ROLE_ID}> can use this command in <#{SUPPORT_CHANNEL_ID}>"
		
		await interaction.response.send_message(error_message, ephemeral=True)

async def setup(client: MyClient):
	await client.add_cog(ErrorHandler(client))