from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import MyClient
    from collections import OrderedDict

SUPPORT_SERVER_ID = 678279978244374528

EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))


class MemberCacheActionRow(discord.ui.ActionRow):
    @discord.ui.button(label="View Cache")
    async def view_users_callback(self, interaction: discord.Interaction, button: discord.ui.Button[MemberCacheView]):
        await interaction.response.defer(ephemeral=True)
        if not any(role in interaction.user._roles for role in (EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)):
            await interaction.followup.send(f"Only a expert/mod/dev can access this info!", ephemeral=True)
            return

        members_formatted = f"{str(list((reversed(button.view.members))))[0: 3900]}" # 3900 is just an arbitrary number
        content = (f"From newest to oldest:\n"
                   "```py\n"
                   f"{members_formatted}```"
                   )
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.TextDisplay(content))
        await interaction.followup.send(view=view, ephemeral=True)


class MemberCacheView(discord.ui.LayoutView):
    def __init__(self, members: OrderedDict[int, int], max_size: int):
        super().__init__(timeout=None)
        self.members = members

        container = discord.ui.Container()
        self.add_item(container)

        num_members = len(members)
        total_size = sys.getsizeof(members)
        content = (f"- No. of members: `{num_members}`",
                   f"- Max size: `{max_size}`",
                   f"- Total Size: `{total_size}` bytes")
        
        container.add_item(discord.ui.TextDisplay(f"### Member Cache Stats"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay('\n'.join(content)))
        container.add_item(discord.ui.Separator())
        container.add_item(MemberCacheActionRow())


class MemberCache(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client

    cache_group = app_commands.Group(name="member_cache", description="Group command for member-cached related commands")

    @commands.Cog.listener('on_raw_member_remove')
    async def remove_from_cache(self, payload: discord.RawMemberRemoveEvent):
        if payload.guild_id != SUPPORT_SERVER_ID:
            return
        self.client._members.pop(payload.user.id, None)

    @cache_group.command(name="stats", description="Get info/stats on the current member cache")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def clear_cache(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=MemberCacheView(self.client._members, self.client._max_member_cache_size))

    @cache_group.command(name="clear", description="Clear the custom member cache")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def clear_cache(self, interaction: discord.Interaction):
        num_members = len(self.client._members)
        total_size = sys.getsizeof(self.client._members)
        self.client._members.clear()

        await interaction.response.send_message(f"Cleared cache of `{num_members}` members (`{total_size}` bytes)")

    @cache_group.command(name="set_maxsize", description="Sets the max number of members in the cache.")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(size="The new max number of members allowed in the cache")
    async def set_size(self, interaction: discord.Interaction, size: app_commands.Range[int, 1, 1000]):
        old_num, old_size = len(self.client._members), sys.getsizeof(self.client._members)
        old_max_size = self.client._max_member_cache_size

        if size < old_num:
            to_pop = old_num - size
            for _ in range(to_pop):
                # Pop from oldest member inserted into cache, keeping the newest
                self.client._members.popitem(last=False)

        new_num, new_size = len(self.client._members), sys.getsizeof(self.client._members)
        self.client._max_member_cache_size = size

        response = (f"Diff:",
                        f"- No. of members in cache: `{old_num}` -> `{new_num}`",
                        f"- Total Size: `{old_size}` -> `{new_size}` (bytes)",
                        f"- Max Size: `{old_max_size} -> `{size}`")

        await interaction.response.send_message('\n'.join(response))


async def setup(client: MyClient):
    await client.add_cog(MemberCache(client))