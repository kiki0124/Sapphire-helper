from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import functions
from discord import ui
from discord.utils import snowflake_time, format_dt

from os import getenv
from dotenv import load_dotenv
load_dotenv()

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import MyClient


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
                              "- pending_posts: (`post_id`, `timestamp`)",
                              "- readthedamnrules: (`post_id`, `user_id`)",
                              "- reminder_waiting: (`post_id`, `timestamp`)",
                              "- locked_channels_permissions: (`channel_id`, `allow`, `deny`)",
                              "- tags: (`name`, `content`, `creator_id`, `created_ts`, `uses`)",
                              "- epi_config: (`started_iso`, `message`, `message_id`, `sticky`, `sticky_message_id`)",
                              "- epi_users: (`user_id`)",
                              "- epi_messages: (`thread_id`, `message_id`)",)
        self.add_item(ui.TextDisplay('\n'.join(tables_and_queries)))

        self.sql_cmd = ui.Label(text="SQL Command", component=ui.TextInput(style=discord.TextStyle.long,
                                                                          required=True))
        self.add_item(self.sql_cmd)

    async def on_submit(self, interaction: discord.Interaction[MyClient]) -> None:
        assert isinstance(self.sql_cmd.component, ui.TextInput)
        await interaction.response.defer()

        sql_cmd_input = self.sql_cmd.component.value
        sql_result = str(await functions.execute_sql(sql_cmd_input.strip()))
        await interaction.followup.send(f"```json\n{sql_result[0:1950]}```")


class DebugCog(commands.Cog):
    def __init__(self, bot: MyClient) -> None:
        self.bot = bot

    debug_group_cmd = app_commands.Group(name="debug", description="Debug Commands")


    @debug_group_cmd.command(name="post", description="Get debug information for support posts")
    @app_commands.describe(post="The post to debug")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def debug_post(self, interaction: discord.Interaction, post: app_commands.AppCommandThread): # AppCommandThread is needed as .Thread can't resolve if the post is archived
        await interaction.response.defer()
        is_pending = await functions.in_pending_posts(post.id)
        if is_pending:
            pending_post_timestamp = await functions.get_post_timestamp(post.id) or 0
        else:
            pending_post_timestamp = 0
        
        owner_id = await functions.get_post_creator_id(post.id) or post.owner_id
        await interaction.followup.send(view=DebugPostView(post, is_pending=is_pending, pending_post_timestamp=pending_post_timestamp,
                                                           owner_id=owner_id),
                                                           allowed_mentions=discord.AllowedMentions.none())

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

async def setup(client: MyClient):
    await client.add_cog(DebugCog(client))
