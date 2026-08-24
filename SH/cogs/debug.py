from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import functions
from discord import ui, CheckboxGroupOption
from discord.utils import snowflake_time, format_dt
from datetime import datetime, UTC

from os import getenv
from dotenv import load_dotenv
load_dotenv()

from typing import TYPE_CHECKING, Literal
if TYPE_CHECKING:
    from main import SHBot


EXPERTS_ROLE_ID = int(getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(getenv("MODERATORS_ROLE_ID"))
ALERTS_THREAD_ID = int(getenv('ALERTS_THREAD_ID'))
DEVELOPERS_ROLE_ID = int(getenv("DEVELOPERS_ROLE_ID"))

NEED_DEV_REVIEW_TAG_ID = int(getenv("NEED_DEV_REVIEW_TAG_ID"))
SOLVED_TAG_ID = int(getenv("SOLVED_TAG_ID"))


class DebugPostView(ui.LayoutView):
    def __init__(self, post: app_commands.AppCommandThread, *, is_pending: bool, pending_post_timestamp: int = 0, owner_id: int) -> None:
        super().__init__(timeout=None)
        container = ui.Container(ui.TextDisplay(f"## [{post.name[0:25]}]({post.jump_url})"))
        container.add_item(ui.Separator())

        middle_content = ""
        if is_pending:
            middle_content += "\n- In `pending_posts`: ✅"
            middle_content += f"\n- Time inserted into db: <t:{pending_post_timestamp}:R>"
        else:
            middle_content += "\n- In `pending_posts`: ❌"
        if post.last_message_id:
            middle_content += f"\n- Last Msg ID: `{post.last_message_id}` ({format_dt(snowflake_time(post.last_message_id), 'R')})"
        middle_content += f"\n- Owner: <@{owner_id}> (`{owner_id}`)"
        container.add_item(ui.TextDisplay(middle_content))

        container.add_item(ui.Separator())

        applied_tags = post._applied_tags
        ndr = '✅' if NEED_DEV_REVIEW_TAG_ID in applied_tags else '❌'
        solved = '✅' if SOLVED_TAG_ID in applied_tags  else '❌'
        if post.archived:
            archived = f"✅ ({format_dt(post.archive_timestamp, 'R')})"
        else:
            archived = '❌'
        locked = '✅' if post.locked else '❌'

        bottom_content = f"- NDR: {ndr}\n- Solved: {solved}\n- Archived: {archived}\n- Locked: {locked}"
        container.add_item(ui.TextDisplay(bottom_content))
    
        self.add_item(container)

class EvalSqlModal(ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Eval Sql")
        tables_and_queries = ("Table Name: Possible query names:",
                              "- reminder_waiting: (`post_id`, `timestamp`)",
                              "- locked_channels_permissions: (`channel_id`, `allow`, `deny`)",
                              "- tags: (`name`, `content`, `creator_id`, `created_ts`, `uses`)")
        self.add_item(ui.TextDisplay('\n'.join(tables_and_queries)))

        self.sql_cmd = ui.Label(text="SQL Command", component=ui.TextInput(style=discord.TextStyle.long,
                                                                          required=True))
        self.add_item(self.sql_cmd)

    async def on_submit(self, interaction: discord.Interaction[SHBot]) -> None:
        assert isinstance(self.sql_cmd.component, ui.TextInput)
        await interaction.response.defer()

        sql_cmd_input = self.sql_cmd.component.value
        sql_result = str(await functions.execute_sql(sql_cmd_input.strip()))
        await interaction.followup.send(f"```json\n{sql_result[0:1950]}```")

class GlobalCacheModal(ui.Modal):
    def __init__(self, cache_type: Literal['PENDING_POSTS', 'RTDR']):
        super().__init__(title=f"{cache_type}", custom_id="global_cache_modal")
        self.cache_type: Literal['PENDING_POSTS', 'RTDR'] = cache_type

        self.post_to_debug = ui.Label(text="Post ID", description="The ID of the post you want to debug, if applicable",
                                 component=ui.TextInput(required=False, max_length=25))
        self.owner_input = ui.Label(text="RTDR Owner ID", description="This is only needed if you want add a post to RTDR",
                                 component=ui.UserSelect(max_values=1, min_values=1, required=False))

        options = [CheckboxGroupOption(label="Check in cache", value="check"), CheckboxGroupOption(label="Add to cache", value="add"),
                   CheckboxGroupOption(label="Remove from cache", value="remove"), CheckboxGroupOption(label="Clear cache", value="clear"),
                   CheckboxGroupOption(label="View all", value="view")]
        check_box = ui.CheckboxGroup(required=True, min_values=1, max_values=1,
                                     options=options)
        self.debug_type = ui.Label(text="Debug Type", component=check_box)

        self.add_item(self.post_to_debug)
        if self.cache_type == "RTDR":
            self.add_item(self.owner_input)
        self.add_item(self.debug_type)

    async def on_submit(self, interaction: discord.Interaction[SHBot]):
        await interaction.response.defer(ephemeral=True)
        assert(isinstance(self.post_to_debug.component, ui.TextInput))
        assert(isinstance(self.owner_input.component, ui.UserSelect))
        assert(isinstance(self.debug_type.component, ui.CheckboxGroup))

        debug_type: Literal['clear', 'view', 'add', 'remove', 'check'] = self.debug_type.component.values[0] # type: ignore

        if self.cache_type == 'PENDING_POSTS':
            cache = interaction.client.pending_posts
        else:
            cache = interaction.client.rtdr_posts

        if debug_type == "clear":
            cache.clear()
            await interaction.client.send_log(ALERTS_THREAD_ID, content=f"`{self.cache_type}` cache has been cleared by {interaction.user.mention}")
            await interaction.followup.send(f"{self.cache_type} cache has been cleared!", ephemeral=True)
            return
        elif debug_type == "view":
            content = f"Posts Cached: `{len(cache)}`\n```py\n{cache}```"[0:4000]
            container = ui.Container(ui.TextDisplay(content))
            await interaction.followup.send(view=ui.LayoutView().add_item(container), ephemeral=True)
            return

        try:
            post_id: int = int(self.post_to_debug.component.value)
        except ValueError:
            await interaction.followup.send(f"Expected a thread ID, got `{self.post_to_debug.component.value}` instead.", ephemeral=True)
            return
        else:
            # validate post
            try:
                post = interaction.guild.get_thread(post_id) or await interaction.guild.fetch_channel(post_id)
                if not isinstance(post, discord.Thread):
                    await interaction.followup.send(f"{post.mention} ({post.id}) is not a thread!", ephemeral=True)
                    return
            except discord.NotFound:
                await interaction.followup.send(f"Could not fetch <#{post_id}> ({post_id}).", ephemeral=True)
                return

        if debug_type == "add":
            if self.cache_type == 'RTDR':
                if post.owner_id != interaction.client.user.id:
                    await interaction.followup.send("This post must be created by Sapphire Helper in order for it to be a RTDR post!", ephemeral=True)
                    return
                if not self.owner_input.component.values:
                    await interaction.followup.send(f"A user is needed in order to add a post to RTDR!", ephemeral=True)
                    return

                owner = self.owner_input.component.values[0]
                cache[post_id] = owner.id
                await interaction.followup.send(f"Successfully added <#{post_id}> to RTDR cache with {owner.mention} ({owner.id}) as owner.", ephemeral=True)
            else:
                cache[post_id] = int(datetime.now(UTC).timestamp())
                await interaction.followup.send(f"Successfully added <#{post_id}> to PENDING_POSTS cache.", ephemeral=True)
        elif debug_type == "remove":
            try:
                del cache[post_id]
            except KeyError:
                await interaction.followup.send(f"<#{post_id}> ({post_id}) is not in {self.cache_type} cache.", ephemeral=True)
            else:
                await interaction.followup.send(f"Successfully removed <#{post_id}> ({post_id}) from {self.cache_type} cache.", ephemeral=True)
        else:
            in_cache = "is" if post_id in cache else "is not"
            await interaction.followup.send(f"<#{post_id}> ({post_id}) {in_cache} in {self.cache_type} cache.", ephemeral=True)

class DebugCog(commands.Cog):
    def __init__(self, bot: SHBot) -> None:
        self.bot = bot

    debug_group_cmd = app_commands.Group(name="debug", description="Debug Commands")


    @debug_group_cmd.command(name="post", description="Get debug information for support posts")
    @app_commands.describe(post="The post to debug")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def debug_post(self, interaction: discord.Interaction, post: app_commands.AppCommandThread): # AppCommandThread is needed as .Thread can't resolve if the post is archived
        await interaction.response.defer()
        is_pending = post.id in self.bot.pending_posts
        if is_pending:
            pending_post_timestamp = self.bot.pending_posts[post.id]
        else:
            pending_post_timestamp = 0
        
        owner_id = await self.bot.get_post_owner_id(post)
        await interaction.followup.send(view=DebugPostView(post, is_pending=is_pending, pending_post_timestamp=pending_post_timestamp,
                                                           owner_id=owner_id),
                                                           allowed_mentions=discord.AllowedMentions.none(),
                                                           ephemeral=True)

    @debug_group_cmd.command(name="eval_sql", description="Execute an SQL command")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def debug_eval_sql(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EvalSqlModal())

    @debug_group_cmd.command(name="create_db_table", description="Creates the DB tables if not already created")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def debug_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await functions.setup_db()
        await interaction.followup.send("Success!\n", ephemeral=True)


    @debug_group_cmd.command(name="global_cache", description="Get debug info and actions regarding the global cache")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(cache_type="The cache type to debug")
    async def debug_global_cache(self, interaction: discord.Interaction, cache_type: Literal['RTDR', 'PENDING_POSTS']):
        await interaction.response.send_modal(GlobalCacheModal(cache_type))

async def setup(bot: SHBot):
    await bot.add_cog(DebugCog(bot))
