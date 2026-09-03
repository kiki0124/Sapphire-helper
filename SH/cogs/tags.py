from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands, ui
from functions import check_tag_exists, save_tag, get_tag_content, get_tag_data, increment_tag_uses, delete_tag, update_tag_content, \
    get_most_used_tags, format_recommended_by, update_tag_name
import os
from difflib import get_close_matches
import asyncio
from typing import TYPE_CHECKING

from dotenv import load_dotenv
load_dotenv()

if TYPE_CHECKING:
    from main import SHBot


EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))
TAG_LOGGING_THREAD_ID = int(os.getenv("TAG_LOGGING_THREAD_ID"))


class CreateTagModal(ui.Modal):
    def __init__(self, tag_cog: Tags):
        super().__init__(
            title="Create new tag",
            timeout=None
            )
        self.tag_cog = tag_cog

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

    async def on_submit(self, interaction: discord.Interaction[SHBot]):
        await interaction.response.defer(ephemeral=True)
        tag_name: str = self.name.component.value
        if not await check_tag_exists(tag_name):
            await save_tag(name=tag_name, content=self.content.component.value, creator_id=interaction.user.id)
            content = f"Tag `{tag_name}` created by {interaction.user.mention}.\nContent: ```\n{self.content.component.value}\n```"
            await interaction.client.send_log(TAG_LOGGING_THREAD_ID, content=content)
            await interaction.followup.send(f"Tag `{tag_name}` saved successfully!\nYou can now access it with `/tag use`", ephemeral=True)

            await self.tag_cog.update_cached_tags()
        else:
            await interaction.followup.send("A tag with this name already exists...\n-# Use `/tag delete` to delete it", ephemeral=True)

class UpdateTagModal(ui.Modal):
    def __init__(self, cog: Tags, tag_name: str, tag_content: str):
        super().__init__(title="Update tag", custom_id="update_tag_modal")
        self.cog = cog
        self.tag_name: str = tag_name
        self.tag_content = tag_content

        self.add_item(ui.TextDisplay(f"Original content for `{self.tag_name}`:```{tag_content}```"))

        self.new_name_label = ui.Label(
            text="New name (Optional):", 
            component=ui.TextInput(
                style=discord.TextStyle.short, 
                placeholder="The new name of the tag", 
                max_length=25,
                required=False
            )
        )

        self.new_content_label = ui.Label(
            text="New content (Optional):", 
            component=ui.TextInput(
                style=discord.TextStyle.paragraph, 
                placeholder="The new content that this tag should have", 
                max_length=950,
                required=False
            )
        )

        self.add_item(self.new_name_label)
        self.add_item(self.new_content_label)

    async def on_submit(self, interaction: discord.Interaction[SHBot]):
        await interaction.response.defer(ephemeral=True)
        new_content: str = self.new_content_label.component.value # type: ignore
        new_name: str = self.new_name_label.component.value # type: ignore

        if not new_content and not new_name:
            await interaction.followup.send("One of `name` or `content` must be edited!", ephemeral=True)
            return

        content: str = f"`{self.tag_name}` tag updated by {interaction.user.mention}\n\n"
        if new_name:
            new_tag_content = await get_tag_content(new_name)
            if new_tag_content is not None and new_tag_content != self.tag_content:
                await interaction.followup.send(f"`{new_name}` already exists!", ephemeral=True)
                return
            await update_tag_name(self.tag_name, new_name)
            content += f"New name: `{new_name}`\n"
            await self.cog.update_cached_tags()

        if new_content:
            tag_name = new_name or self.tag_name # use the updated name if set
            await update_tag_content(tag_name, new_content)
            content += f"New content: ```{new_content}```"


        await interaction.client.send_log(TAG_LOGGING_THREAD_ID, content=content)
        await interaction.followup.send(f"Tag updated successfully!", ephemeral=True)


class TagConfirmRow(ui.ActionRow):
    def __init__(self, tag_cog: Tags, tag: str, tag_content: str):
        self.tag_cog = tag_cog
        self.tag = tag
        self.tag_content = tag_content
        super().__init__()

    @ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, _: ui.Button):
        await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass # user likely dismissed the message already

        tag_view = ui.LayoutView()
        tag_container = ui.Container()
        tag_view.add_item(tag_container)

        tag_container.add_item(ui.TextDisplay(self.tag_content))
        tag_container.add_item(ui.Separator())
        tag_container.add_item(ui.TextDisplay(format_recommended_by(interaction.user)))

        await increment_tag_uses(self.tag)

        # only update the cached tags if the tag isn't already cached
        if self.tag not in self.tag_cog.cached_tags:
            await self.tag_cog.update_cached_tags()
        await interaction.channel.send(view=tag_view, allowed_mentions=discord.AllowedMentions.none())


class Tags(commands.Cog):
    def __init__(self, bot: SHBot):
        self.bot = bot
        self.cached_tags: list[str] = [] # tags cached to use for autocomplete and suggesting similar tags
        self.tags_lock = asyncio.Lock() # Lock to prevent mutating 'cached_tags' at the same time

    def get_similar_tags(self, tag_name: str) -> ui.Container:
        container = ui.Container(ui.TextDisplay("Tag not found, sorry!"))
        similar_tags = get_close_matches(tag_name, self.cached_tags)
        if similar_tags:
            container.add_item(ui.Separator())
            content = f"**Similar Tags:**"
            for tag in similar_tags:
                content += f"\n- `{tag}`"
            container.add_item(ui.TextDisplay(content))
        return container
    
    async def cog_load(self):
        """Cache the tags"""
        self.cached_tags = await get_most_used_tags()
    
    async def update_cached_tags(self):
        """The actual implementation to update the cached tags"""
        async with self.tags_lock:
            self.cached_tags.clear()
            self.cached_tags.extend(await get_most_used_tags())

    tag_group = app_commands.Group(name="tag", description="Commands related to the tag system")

    @tag_group.command(name="create", description="Add a new tag with the given content")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def add(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateTagModal(self))

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
        content = await get_tag_content(tag)
        if content:
            container = ui.Container()
            view.add_item(container)

            container.add_item(ui.TextDisplay(content))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay("-# Click *Confirm* to send, dismiss message to cancel"))
            container.add_item(TagConfirmRow(self, tag, content))
        else:
            view.add_item(self.get_similar_tags(tag))

        await interaction.followup.send(view=view, ephemeral=True)

    @tag_group.command(name="info", description="Get info about a specific tag")
    @app_commands.describe(tag="The name of the tag")
    async def info(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)

        view = ui.LayoutView()

        tag_data = await get_tag_data(tag)
        if tag_data:
            created_ts = tag_data["created_ts"]
            creator_id = tag_data["creator_id"]
            content = tag_data["content"]
            uses = tag_data["uses"]

            tag_data_textdisplay = ui.TextDisplay(f"- Name: {tag}\n- Uses: {uses}\n- Created by: <@{creator_id}>\n- Created on: <t:{created_ts}>")
            container = ui.Container()
            container.add_item(ui.TextDisplay(content))
            container.add_item(ui.Separator())
            container.add_item(tag_data_textdisplay)
        else:
            container = self.get_similar_tags(tag)
        view.add_item(container)
        await interaction.followup.send(view=view, ephemeral=True)

    @tag_group.command(name="delete", description="Delete the given tag")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(tag="The name of the tag to be deleted")
    async def delete(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)

        view = ui.LayoutView()

        tag_obj = await get_tag_data(tag)
        if tag_obj is not None:
            confirm_button = ui.Button(
                label="Confirm",
                style=discord.ButtonStyle.danger,
                custom_id="tag-delete-confirm"
            )
            async def on_confirm_click(i: discord.Interaction[SHBot]):
                await i.response.defer(ephemeral=True)
                await delete_tag(tag)
                try:
                    tag_deleted_view = ui.LayoutView()
                    tag_deleted_container = ui.Container(
                        ui.TextDisplay(f"Successfully deleted tag `{tag}`!")
                    )
                    tag_deleted_view.add_item(tag_deleted_container)
                    await interaction.edit_original_response(view=tag_deleted_view)
                except discord.HTTPException: # message was most likely already dismissed by the user
                    pass
                await i.client.send_log(TAG_LOGGING_THREAD_ID, content=f"`{tag}` tag deleted by {i.user.mention}")

                try:
                    async with self.tags_lock:
                        self.cached_tags.remove(tag)
                except ValueError:
                    pass
                else:
                    # Only update the cached tags if the tag was cached
                    await self.update_cached_tags()

            confirm_button.callback = on_confirm_click # type: ignore
            container = ui.Container()
            content = f"### Are you sure you would like to delete the `{tag}` tag?\nClick *Confirm* to delete, dismiss message to cancel."
            if tag_obj['creator_id'] != interaction.user.id:
                content += f"\n-# - Note: You do not own this tag, <@{tag_obj['creator_id']}> does!"
            container.add_item(ui.TextDisplay(content))
            container.add_item(ui.ActionRow(confirm_button))

            view.add_item(container)
        else:
            view.add_item(self.get_similar_tags(tag))
        await interaction.followup.send(view=view, ephemeral=True)

    @tag_group.command(name="edit", description="edit the content for an existing tag")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(tag="The name of the tag that should be edited")
    async def update(self, interaction: discord.Interaction, tag: str):
        tag_data = await get_tag_data(tag)
        if tag_data is None:
            view = ui.LayoutView().add_item(self.get_similar_tags(tag))
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        
        await interaction.response.send_modal(UpdateTagModal(self, tag_data['name'], tag_data['content']))

    @use.autocomplete("tag")
    async def tag_use_autocomplete(self, interaction: discord.Interaction, current: str):
        tag_choices_all = [app_commands.Choice(name=tag_name, value=tag_name) for tag_name in self.cached_tags]
        return tag_choices_all[0:25]
    
    @update.autocomplete("tag")
    async def tag_update_autocomplete(self, interaction: discord.Interaction, current: str):
        tag_choices_all = [app_commands.Choice(name=tag_name, value=tag_name) for tag_name in self.cached_tags]
        return tag_choices_all[0:25]
    
    @info.autocomplete("tag")
    async def tag_info_autocomplete(self, interaction: discord.Interaction, current: str):
        tag_choices_all = [app_commands.Choice(name=tag_name, value=tag_name) for tag_name in self.cached_tags]
        return tag_choices_all[0:25]

    @delete.autocomplete("tag")
    async def tag_delete_autocomplete(self, interaction: discord.Interaction, current: str):
        tag_choices_all = [app_commands.Choice(name=tag_name, value=tag_name) for tag_name in self.cached_tags]
        return tag_choices_all[0:25]
    

    @tag_group.command(name="debug", description="Get debug information for cached tags")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def tag_debug(self, interaction: discord.Interaction):
        view = ui.LayoutView()
        
        description = f"Tags Cached: {len(self.cached_tags)}"
        container = ui.Container(ui.TextDisplay(description),
                                 ui.Separator(), ui.TextDisplay(f"```json\n{self.cached_tags}```"))
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)

async def setup(bot: SHBot):
    await bot.add_cog(Tags(bot))