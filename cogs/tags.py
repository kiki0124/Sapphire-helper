import discord
from discord.ext import commands
from discord import app_commands, ui
from functions import check_tag_exists, save_tag, get_tag_content, get_tag_data
import os
from dotenv import load_dotenv

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
            await interaction.response.send_message("A tag with this name already exists...", ephemeral=True)

class quick_replies(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.used_tags: dict[str, int] = {

        } # str(tag) name: int(amount of uses)

    tag_group = app_commands.Group(name="tag", description="Commands related to the tag system")

    @tag_group.command(name="create", description="Add a new tag with the given content")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def add(self, interaction: discord.Interaction):
        await interaction.response.send_modal(create_tag())

    @tag_group.command(name="use", description="Use a tag to display its content")
    @app_commands.describe(tag="The name of the tag that you want to use")
    @app_commands.checks.cooldown(1, 60, key=lambda i: (i.channel.id, i.user.id))
    async def use(self, interaction: discord.Interaction, tag: str):
        if await check_tag_exists(tag):
            """ if tag in self.used_tags.keys():
                self.used_tags[tag] +=1
            else:
                self.used_tags[tag] = 1 """
            await interaction.response.send_message(f"{await get_tag_content(tag)}\n-# Recommended by @{interaction.user.name}", allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.response.send_message("Tag not found, try again later...", ephemeral=True)

    @tag_group.command(name="info", description="Get info about a specific tag")
    async def info(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)
        tag_data = await get_tag_data(tag)
        if tag_data:
            created_ts = tag_data["created_ts"]
            creator_id = tag_data["creator_id"]
            content = tag_data["content"]
            await interaction.followup.send(f"Name: `{tag}`\nCreated by: <@{creator_id}>\nCreated on: <t:{created_ts}:f>\nContent: ```\n{content}\n```", ephemeral=True)
        else:
            await interaction.followup.send(f"There's no tag with the name `{tag}`, try again later...")

    """ @use.autocomplete("tag")
    async def tag_autocomplete(self, interaction: discord.Interaction, current: str):
        if self.used_tags:
            return sorted(self.used_tags.keys(), key=self.used_tags.values(), max=24)
        else:
            return current """

async def setup(client: commands.Bot):
    await client.add_cog(quick_replies(client))