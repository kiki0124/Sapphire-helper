from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from functions import check_tag_exists, save_tag, get_tag_content, get_tag_data, add_tag_uses, delete_tag, update_tag, get_used_tags, DB_PATH
import os
from dotenv import load_dotenv
from difflib import get_close_matches
import asqlite as sql
from asyncio import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import MyClient


load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))
TAG_LOGGING_THREAD_ID = int(os.getenv("TAG_LOGGING_THREAD_ID"))

class create_tag(ui.Modal):
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

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await check_tag_exists(self.pool, self.name.component.value):
            await save_tag(self.pool, name=self.name.component.value, content=self.content.component.value, creator_id=interaction.user.id)
            tag_thread = interaction.guild.get_thread(TAG_LOGGING_THREAD_ID) or await interaction.guild.fetch_channel(TAG_LOGGING_THREAD_ID)
            if tag_thread.archived:
                await tag_thread.edit(archived=False)
            webhooks = [webhook for webhook in await tag_thread.parent.webhooks() if webhook.token]
            try:
                webhook = webhooks[0] 
            except IndexError:
                webhook = await tag_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
            await webhook.send(
                content=f"Tag `{self.name.component.value}` created by {interaction.user.mention}.\nContent: ```\n{self.content.component.value}\n```",
                username=interaction.client.user.name,
                avatar_url=interaction.client.user.avatar.url,
                thread=discord.Object(id=TAG_LOGGING_THREAD_ID),
                wait=False,
                allowed_mentions=discord.AllowedMentions.none()
            )
            await interaction.followup.send(f"Tag `{self.name.component.value}` saved successfully!\nYou can now access it with /tag use", ephemeral=True)
        else:
            await interaction.followup.send("A tag with this name already exists...\n-# Use /tag delete to delete it", ephemeral=True)

class update_tag_modal(ui.Modal):
    def __init__(self, pool: sql.Pool, tag: str):
        super().__init__(title="Update tag", custom_id="update tag modal")
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

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_content = self.label.component.value
        await update_tag(self.pool, self.tag, new_content)
        tag_thread = interaction.guild.get_thread(TAG_LOGGING_THREAD_ID) or await interaction.guild.fetch_channel(TAG_LOGGING_THREAD_ID)
        if tag_thread.archived:
            await tag_thread.edit(archived=False)
        webhooks = [webhook for webhook in await tag_thread.parent.webhooks() if webhook.token]
        try:
            webhook = webhooks[0] 
        except IndexError:
            webhook = await tag_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        await webhook.send(
            content=f"Tag `{self.tag}` editted by {interaction.user.mention}. New content: ```\n{new_content}\n```",
            username=interaction.client.user.name,
            avatar_url=interaction.client.user.avatar.url,
            thread=discord.Object(id=TAG_LOGGING_THREAD_ID),
            wait=False,
            allowed_mentions=discord.AllowedMentions.none()
        )
        await interaction.followup.send(f"Successfully updated `{self.tag}`'s content!")

class quick_replies(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client
        self.used_tags: dict[str, int] = {} # saved and sent to DB every 15 minutes
        self.recommended_tags: list[str] = [] # max 25 with highest uses from DB extracted every 15 minutes
        self.used_tags_lock = Lock()

    async def send_tag_log(self, content: str):
        tag_thread = self.client.get_channel(TAG_LOGGING_THREAD_ID) or await self.client.fetch_channel(TAG_LOGGING_THREAD_ID)
        if tag_thread.archived:
            await tag_thread.edit(archived=False)
        webhooks = [webhook for webhook in await tag_thread.parent.webhooks() if webhook.token]
        try:
            webhook = webhooks[0] 
        except IndexError:
            webhook = await tag_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        await webhook.send(
            content=content,
            username=self.client.user.name,
            avatar_url=self.client.user.avatar.url,
            thread=discord.Object(id=TAG_LOGGING_THREAD_ID),
            wait=False,
            allowed_mentions=discord.AllowedMentions.none()
        )

    async def cog_load(self):
        self.pool = await sql.create_pool(DB_PATH)
        self.refresh_use_count.start()

    async def cog_unload(self):
        self.refresh_use_count.cancel()
        await self.pool.close()

    tag_group = app_commands.Group(name="tag", description="Commands related to the tag system")

    @tag_group.command(name="create", description="Add a new tag with the given content")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def add(self, interaction: discord.Interaction):
        await interaction.response.send_modal(create_tag(self.pool))

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
        if await check_tag_exists(self.pool, tag):
            content = await get_tag_content(self.pool, tag)
            confirm = ui.Button(
                label="Confirm",
                custom_id="tag-send-confirm",
                style=discord.ButtonStyle.danger
            )
            async def confirm_click(i: discord.Interaction):
                await i.response.defer(ephemeral=True)
                async with self.used_tags_lock:
                    if tag in self.used_tags.keys():
                        self.used_tags[tag] +=1
                    else:
                        self.used_tags[tag] = 1
                try:
                    await i.delete_original_response()
                except discord.HTTPException:
                    pass # message was most likely already dismissed by the user
                await interaction.channel.send(f"{content}\n-# Recommended by {i.user.mention}", allowed_mentions=discord.AllowedMentions.none())
            view = ui.View()
            confirm.callback = confirm_click
            view.add_item(confirm)
            await interaction.followup.send(
                f"Are you sure you would like to send this tag?\n{content}\n-# Click *Confirm* to confirm, dismiss message to cancel",
                view=view
            )
        else:
            content = "Tag not found."
            suggestions = get_close_matches(tag, [str(reco_tag) for reco_tag in self.recommended_tags])
            if suggestions:
                content += f" Similar tags:\n"
                content += "\n".join(suggestions)
            await interaction.followup.send(content, ephemeral=True)

    @tag_group.command(name="info", description="Get info about a specific tag")
    @app_commands.describe(tag="The name of the tag")
    async def info(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)
        tag_data = await get_tag_data(self.pool, tag)
        if tag_data:
            created_ts = tag_data["created_ts"]
            creator_id = tag_data["creator_id"]
            content = tag_data["content"]
            uses = tag_data["uses"]
            await interaction.followup.send(f"Name: `{tag}`\nCreated by: <@{creator_id}>\nCreated on: <t:{created_ts}:f>\nUses: `{uses}`\nContent: ```\n{content}\n```", ephemeral=True)
        else:
            content = f"There's no tag with the name `{tag}`."
            suggestions = get_close_matches(tag, [str(reco_tag) for reco_tag in self.recommended_tags])
            if suggestions:
                content += f" Similar tags:\n"
                content += '\n'.join(suggestions)
            await interaction.followup.send(content, ephemeral=True)

    @tasks.loop(minutes=1)
    async def refresh_use_count(self):
        async with self.used_tags_lock:
            await add_tag_uses(self.pool, self.used_tags.items())
            self.used_tags.clear()
            self.recommended_tags = await get_used_tags(self.pool)

    @use.autocomplete("tag")
    async def tag_autocomplete(self, interaction: discord.Interaction, current: str):
        if self.recommended_tags:
            return [app_commands.Choice(name=str(tag), value=str(tag)) for tag in self.recommended_tags[0:25]]
        else:
            return []

    @tag_group.command(name="delete", description="Delete the given tag")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(tag="The name of the tag to be deleted")
    async def delete(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)
        if await check_tag_exists(self.pool, tag):
            confirm = ui.Button(
                label="Confirm",
                style=discord.ButtonStyle.danger,
                custom_id="tag-delete-confirm"
            )
            async def on_confirm_click(i: discord.Interaction):
                await i.response.defer(ephemeral=True)
                await delete_tag(self.pool, tag)
                await self.send_tag_log(f"Tag `{tag}` deleted by {i.user.mention}")
                async with self.used_tags_lock:
                    if tag in self.recommended_tags:
                        self.recommended_tags.remove(tag)
                    if tag in self.used_tags:
                        del self.used_tags[tag]
                try:
                    await interaction.delete_original_response()
                except discord.HTTPException: # message was most likely already dismissed by the user
                    pass
                await i.followup.send(f"Successfully deleted tag `{tag}`!", ephemeral=True)
            confirm.callback = on_confirm_click
            view = ui.View()
            view.add_item(confirm)
            await interaction.followup.send(f"Are you sure you would like to delete the tag `{tag}`?\n-# Click *Confirm* to confirm, dismiss message to cancel", view=view)
        else:
            content = f"Couldn't delete tag `{tag}` because it doesn't exist or has already been deleted."
            suggestions = get_close_matches(tag, [str(reco_tag) for reco_tag in self.recommended_tags])
            if suggestions:
                content += f" Similar tags:\n"
                content += '\n'.join(suggestions)
            await interaction.followup.send(content, ephemeral=True)

    @tag_group.command(name="edit", description="edit the content for an existing tag")
    @app_commands.describe(tag="The name of the tag that should be editted")
    async def update(self, interaction: discord.Interaction, tag: str):
        if await check_tag_exists(self.pool, tag):
            await interaction.response.send_modal(update_tag_modal(self.pool, tag))
        else:
            content = f"Couldn't edit tag `{tag}` because it doesn't exist."
            suggestions = get_close_matches(tag, [str(reco_tag) for reco_tag in self.recommended_tags])
            if suggestions:
                content += f" Similar tags:\n"
                content += '\n'.join(suggestions)
            await interaction.response.send_message(content, ephemeral=True)

async def setup(client: MyClient):
    await client.add_cog(quick_replies(client))
