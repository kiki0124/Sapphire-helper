from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from functions import check_tag_exists, save_tag, get_tag_content, get_tag_data, add_tag_uses, delete_tag, update_tag, get_most_used_tags, DB_PATH
import os
from difflib import get_close_matches
import asqlite as sql
from asyncio import Lock
from typing import TYPE_CHECKING

from dotenv import load_dotenv
load_dotenv()

if TYPE_CHECKING:
    from main import MyClient


EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))
TAG_LOGGING_THREAD_ID = int(os.getenv("TAG_LOGGING_THREAD_ID"))

class CreateTagModal(ui.Modal):
    def __init__(self, pool: sql.Pool):
        super().__init__(
            title="Create new tag",
            timeout=None
            )
        self.pool = pool

    name = ui.Label(
        text="Name:",
        component=ui.TextInput(
            max_length=20,
            placeholder="cv2"
        )
    )

    content = ui.Label(
        text="Content:",
        component=ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="Components Version 2 (aka cv2) is a relatively new discord update...",
            max_length=950
        ))

    async def on_submit(self, interaction: discord.Interaction[MyClient]):
        await interaction.response.defer(ephemeral=True)
        if not await check_tag_exists(self.pool, self.name.component.value):
            await save_tag(self.pool, name=self.name.component.value, content=self.content.component.value, creator_id=interaction.user.id)
            content = f"Tag `{self.name.component.value}` created by {interaction.user.mention}.\nContent: ```\n{self.content.component.value}\n```"
            await interaction.client.send_log(TAG_LOGGING_THREAD_ID, content=content)
            await interaction.followup.send(f"Tag `{self.name.component.value}` saved successfully!\nYou can now access it with /tag use", ephemeral=True)
        else:
            await interaction.followup.send("A tag with this name already exists...\n-# Use /tag delete to delete it", ephemeral=True)

class UpdateTagModal(ui.Modal):
    def __init__(self, pool: sql.Pool, tag: str):
        super().__init__(title="Update tag", custom_id="update_tag_modal")
        self.tag = tag
        self.pool = pool

    label = ui.Label(
        text="New content:", 
        component=ui.TextInput(
            style=discord.TextStyle.paragraph, 
            placeholder="The new content that this tag should have", 
            max_length=950
        )
    )

    async def on_submit(self, interaction: discord.Interaction[MyClient]):
        await interaction.response.defer(ephemeral=True)
        new_content = self.label.component.value
        await update_tag(self.pool, self.tag, new_content)
        content=f"Tag `{self.tag}` edited by {interaction.user.mention}. \nNew content: ```\n{new_content}\n```"
        await interaction.client.send_log(TAG_LOGGING_THREAD_ID, content=content)
        await interaction.followup.send(f"Successfully updated `{self.tag}`'s content!", ephemeral=True)


class TagConfirmRow(ui.ActionRow):
    def __init__(self, parent: Tags, tag: str, tag_content: str):
        self.__parent = parent
        self.tag = tag
        self.tag_content = tag_content
        super().__init__()

    @ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button):
        await interaction.response.defer()
        async with self.__parent.tags_lock:
            if self.tag in self.__parent.tags:
                self.__parent.tags[self.tag] += 1
            else:
                self.__parent.tags[self.tag] = 1
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass # user likely dismissed the message already

        tag_view = ui.LayoutView()
        tag_container = ui.Container()
        tag_view.add_item(tag_container)

        tag_container.add_item(ui.TextDisplay(self.tag_content))
        tag_container.add_item(ui.Separator())

        tag_container.add_item(ui.TextDisplay(f"-# Recommended by {interaction.user.mention}"))
        await interaction.channel.send(view=tag_view, allowed_mentions=discord.AllowedMentions.none())


class Tags(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client
        self.tags: dict[str, int] = {} # a mapping of the tag name to the no of uses that tag has
        self.tags_lock = Lock() # asyncio.Lock to prevent mutating 'self.tags' at the same time

    async def cog_load(self):
        self.pool = await sql.create_pool(DB_PATH)
        self.refresh_use_count.start()

    async def cog_unload(self):
        self.refresh_use_count.cancel()
        await self.pool.close()

    def get_similar_tags(self, tag_name: str) -> ui.Container:
        container = ui.Container(ui.TextDisplay("Tag not found, sorry!"))
        similar_tags = get_close_matches(tag_name, list(self.tags))
        if similar_tags:
            container.add_item(ui.Separator())
            content = f"**Similar Tags:**\n"
            for tag in similar_tags:
                content += f"- `{tag}`"
            container.add_item(ui.TextDisplay(content))
        return container

    tag_group = app_commands.Group(name="tag", description="Commands related to the tag system")

    @tag_group.command(name="create", description="Add a new tag with the given content")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def add(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateTagModal(self.pool))

    @staticmethod
    async def tag_use_dynamic_cooldown(interaction: discord.Interaction):
        if interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID):
            return None
        return app_commands.Cooldown(1, 60)

    @tag_group.command(name="use", description="Use a tag to display its content")
    @app_commands.describe(tag="The name of the tag that you want to use")
    @app_commands.checks.dynamic_cooldown(tag_use_dynamic_cooldown, key= lambda i: (i.channel.id, i.user.id))
    async def use(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)

        view = ui.LayoutView()
        content = await get_tag_content(self.pool, tag)
        if content:
            container = ui.Container()
            view.add_item(container)

            container.add_item(ui.TextDisplay(content))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay("-# Click *Confirm* to send, dismiss message to cancel"))
            container.add_item(TagConfirmRow(self, tag, content or ""))
        else:
            view.add_item(self.get_similar_tags(tag))

        await interaction.followup.send(view=view, ephemeral=True)

    @tag_group.command(name="info", description="Get info about a specific tag")
    @app_commands.describe(tag="The name of the tag")
    async def info(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)

        view = ui.LayoutView()

        tag_data = await get_tag_data(self.pool, tag)
        if tag_data:
            created_ts = tag_data["created_ts"]
            creator_id = tag_data["creator_id"]
            content = tag_data["content"]
            uses = self.tags.get(tag, tag_data["uses"])

            tag_data_textdisplay = ui.TextDisplay(f"- Name: {tag}\n- Uses: {uses}\n- Created by: <@{creator_id}>\n- Created on: <t:{created_ts}>")
            container = ui.Container()
            container.add_item(ui.TextDisplay(content))
            container.add_item(ui.Separator())
            container.add_item(tag_data_textdisplay)
        else:
            container = self.get_similar_tags(tag)
        view.add_item(container)
        await interaction.followup.send(view=view, ephemeral=True)

    @tasks.loop(minutes=15)
    async def refresh_use_count(self):
        async with self.tags_lock:
            await add_tag_uses(self.pool, self.tags)
            self.tags.clear()
            self.tags = await get_most_used_tags(self.pool)

    @tag_group.command(name="delete", description="Delete the given tag")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(tag="The name of the tag to be deleted")
    async def delete(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)

        view = ui.LayoutView()

        if await check_tag_exists(self.pool, tag):
            confirm_button = ui.Button(
                label="Confirm",
                style=discord.ButtonStyle.danger,
                custom_id="tag-delete-confirm"
            )
            async def on_confirm_click(i: discord.Interaction[MyClient]):
                await i.response.defer(ephemeral=True)
                await delete_tag(self.pool, tag)
                await i.client.send_log(TAG_LOGGING_THREAD_ID, content=f"`{tag}` tag deleted by {i.user.mention}")
                async with self.tags_lock:
                    if tag in self.tags:
                        del self.tags[tag]
                try:
                    tag_deleted_view = ui.LayoutView()
                    tag_deleted_container = ui.Container(
                        ui.TextDisplay(f"Successfully deleted tag `{tag}`!")
                    )
                    tag_deleted_view.add_item(tag_deleted_container)
                    await interaction.edit_original_response(view=tag_deleted_view)
                except discord.HTTPException: # message was most likely already dismissed by the user
                    pass
            confirm_button.callback = on_confirm_click
            container = ui.Container()
            container.add_item(ui.TextDisplay(f"Are you sure you would like to delete the `{tag}` tag?\n-# Click *Confirm* to delete, dismiss message to cancel"))
            container.add_item(ui.ActionRow(confirm_button))

            view.add_item(container)
        else:
            view.add_item(self.get_similar_tags(tag))
        await interaction.followup.send(view=view, ephemeral=True)

    @tag_group.command(name="edit", description="edit the content for an existing tag")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(tag="The name of the tag that should be edited")
    async def update(self, interaction: discord.Interaction, tag: str):
        if await check_tag_exists(self.pool, tag):
            await interaction.response.send_modal(UpdateTagModal(self.pool, tag))
        else:
            view = ui.LayoutView().add_item(self.get_similar_tags(tag))
            await interaction.response.send_message(view=view, ephemeral=True)

    @use.autocomplete("tag")
    async def tag_use_autocomplete(self, interaction: discord.Interaction, current: str):
        tag_choices_all = [app_commands.Choice(name=tag_name, value=tag_name) for tag_name in self.tags]
        return tag_choices_all[0:25]
    
    @update.autocomplete("tag")
    async def tag_update_autocomplete(self, interaction: discord.Interaction, current: str):
        tag_choices_all = [app_commands.Choice(name=tag_name, value=tag_name) for tag_name in self.tags]
        return tag_choices_all[0:25]
    
    @info.autocomplete("tag")
    async def tag_info_autocomplete(self, interaction: discord.Interaction, current: str):
        tag_choices_all = [app_commands.Choice(name=tag_name, value=tag_name) for tag_name in self.tags]
        return tag_choices_all[0:25]

    @delete.autocomplete("tag")
    async def tag_delete_autocomplete(self, interaction: discord.Interaction, current: str):
        tag_choices_all = [app_commands.Choice(name=tag_name, value=tag_name) for tag_name in self.tags]
        return tag_choices_all[0:25]
    

    @tag_group.command(name="debug", description="Get debug information for tags")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def tag_debug(self, interaction: discord.Interaction):
        view = ui.LayoutView()
        container = ui.Container(ui.TextDisplay(f"Tags Cached: {len(self.tags)}"),
                                 ui.Separator(), ui.TextDisplay(f"```json\n{self.tags}```"))
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)

async def setup(client: MyClient):
    await client.add_cog(Tags(client))