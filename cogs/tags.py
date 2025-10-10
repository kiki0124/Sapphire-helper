import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from functions import check_tag_exists, save_tag, get_tag_content, get_tag_data, add_tag_uses, delete_tag, update_tag, get_used_tags
import os
from dotenv import load_dotenv
from difflib import get_close_matches

load_dotenv()
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))

class create_tag(ui.Modal):
    def __init__(self):
        super().__init__(
            title="Create new tag",
            timeout=None
            )

    name = ui.TextInput(
        label="Name", 
        placeholder="cv2", 
        max_length=20
        )
    
    content = ui.TextInput(
        label="Content",
        style=discord.TextStyle.paragraph,
        placeholder="Components Version 2 (aka cv2) is a relatively new discord update...",
        max_length=1_000
        )

    async def on_submit(self, interaction: discord.Interaction):
        if not await check_tag_exists(self.name.value):
            await save_tag(name=self.name.value, content=self.content.value, creator_id=interaction.user.id)
            await interaction.response.send_message(f"Tag `{self.name.value}` saved successfully!\nYou can now access it with /tag use", ephemeral=True)
        else:
            await interaction.response.send_message("A tag with this name already exists...\n-# Use /tag delete to delete it", ephemeral=True)

class update_tag_modal(ui.Modal):
    def __init__(self, tag: str):
        super().__init__(title="Update tag", custom_id="update tag modal")
        self.tag = tag

    label = ui.Label(text="New content:", component=ui.TextInput(style=discord.TextStyle.paragraph, placeholder="The new content that this tag should have"))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_content = self.label.component.value
        await update_tag(self.tag, new_content)
        await interaction.followup.send(f"Successfully updated `{self.tag}`'s content!")

class quick_replies(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.used_tags: dict[str, int] = {} # saved and sent to DB every 15 minutes
        self.recommended_tags: list[str] = [] # max 25 with highest uses from DB extracted every 15 minutes
        self.refresh_use_count.start()

    tag_group = app_commands.Group(name="tag", description="Commands related to the tag system")

    @tag_group.command(name="create", description="Add a new tag with the given content")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def add(self, interaction: discord.Interaction):
        await interaction.response.send_modal(create_tag())

    @tag_group.command(name="use", description="Use a tag to display its content")
    @app_commands.describe(tag="The name of the tag that you want to use")
    @app_commands.checks.cooldown(1, 60, key=lambda i: (i.channel.id, i.user.id))
    async def use(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)
        if await check_tag_exists(tag):
            content = await get_tag_content(tag)
            confirm = ui.Button(
                label="Confirm",
                custom_id="tag-send-confirm",
                style=discord.ButtonStyle.danger
            )
            async def confirm_click(i: discord.Interaction):
                if tag in self.used_tags.keys():
                    self.used_tags[tag] +=1
                else:
                    self.used_tags[tag] = 1
                await interaction.channel.send(f"{content}\n-# Recommended by @{i.user.name}", allowed_mentions=discord.AllowedMentions.none())
            view = ui.View()
            confirm.callback = confirm_click
            view.add_item(confirm)
            await interaction.followup.send(
                f"Are you sure you would like to send this tag?\n```\n{content}\n```\n-# Click *Confirm* to confirm, dismiss message to cancel",
                view=view
            )
        else:
            content = "Tag not found, try again later..."
            suggestions = get_close_matches(tag, [str(reco_tag) for reco_tag in self.recommended_tags])
            if suggestions:
                content += f"Similar tags:\n {'\n'.join(suggestions)}"
            await interaction.followup.send(content, ephemeral=True)

    @tag_group.command(name="info", description="Get info about a specific tag")
    @app_commands.describe(tag="The name of the tag")
    async def info(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)
        tag_data = await get_tag_data(tag)
        if tag_data:
            created_ts = tag_data["created_ts"]
            creator_id = tag_data["creator_id"]
            content = tag_data["content"]
            uses = tag_data["uses"]
            await interaction.followup.send(f"Name: `{tag}`\nCreated by: <@{creator_id}>\nCreated on: <t:{created_ts}:f>\nUses: `{uses}`\nContent: ```\n{content}\n```", ephemeral=True)
        else:
            content = f"There's no tag with the name `{tag}`, try again later..."
            suggestions = get_close_matches(tag, [str(reco_tag) for reco_tag in self.recommended_tags])
            if suggestions:
                content += f"Similar tags: {'\n'.join(suggestions)}"
            await interaction.followup.send(content, ephemeral=True)

    @tasks.loop(minutes=1)
    async def refresh_use_count(self):
        await add_tag_uses(self.used_tags.items())
        self.used_tags.clear()
        self.recommended_tags = await get_used_tags()

    @use.autocomplete("tag")
    async def tag_autocomplete(self, interaction: discord.Interaction, current: str):
        if self.recommended_tags:
            return [app_commands.Choice(name=str(tag), value=str(tag)) for tag in self.recommended_tags]
        else:
            return []

    @tag_group.command(name="delete", description="Delete the given tag")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    @app_commands.describe(tag="The name of the tag to be deleted")
    async def delete(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)
        if await check_tag_exists(tag):
            confirm = ui.Button(
                label="Confirm",
                style=discord.ButtonStyle.danger,
                custom_id="tag-delete-confirm"
            )
            async def on_confirm_click(i: discord.Interaction):
                await delete_tag(tag)
                await i.followup.send(f"Successfully deleted tag `{tag}`!", ephemeral=True)
            confirm.callback = on_confirm_click
            view = ui.View()
            view.add_item(confirm)
            await interaction.followup.send(f"Are you sure you would like to delete the tag `{tag}`?\n-# Click *Confirm* to confirm, dismiss message to cancel", view=view)
        else:
            content = f"Couldn't delete tag `{tag}` because it doesn't exist or has already been deleted..."
            suggestions = get_close_matches(tag, [str(reco_tag) for reco_tag in self.recommended_tags])
            if suggestions:
                content += f"Similar tags:\n{'\n'.join(suggestions)}"
            await interaction.followup.send(content, ephemeral=True)

    @tag_group.command(name="update", description="Update the content for an existing tag")
    @app_commands.describe(tag="The name of the tag that should be updated")
    async def update(self, interaction: discord.Interaction, tag: str):
        if await check_tag_exists(tag):
            await interaction.response.send_modal(update_tag_modal(tag))
        else:
            content = f"Couldn't update tag `{tag}` because it doesn't exist..", ephemeral=True
            suggestions = get_close_matches(tag, [str(reco_tag) for reco_tag in self.recommended_tags])
            if suggestions:
                content += f"Similar tags:\n{'\n'.join(suggestions)}"
            await interaction.response.send_message(content, ephemeral=True)

async def setup(client: commands.Bot):
    await client.add_cog(quick_replies(client))