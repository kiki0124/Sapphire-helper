import discord
from discord.ext import commands
from variables import NEED_DEV_REVIEW_TAG_ID, SOLVED_TAG_ID, NOT_SOLVED_TAG_ID, SUPPORT_CHANNEL_ID, UNANSWERED_TAG_ID, EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, CUSTOM_BRANDING_TAG_ID
from discord import app_commands, ui
import asyncio
import datetime

close_tasks: dict[discord.Thread, asyncio.Task] = {}

async def ClosePost(post: discord.Thread) -> None:
    await asyncio.sleep(3600)
    await post.edit(archived=True, reason="Auto archive solved post after 1 hour")
    close_tasks.pop(post)

class NeedDevReviewButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Show an example of the questions answered", style=discord.ButtonStyle.grey, custom_id="need-dev-review-example")
    async def on_show_example_click(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            content="## Example message on how you could answer these questions for an imaginary issue.\n\n1. Join Roles\n2. Last join role assigned yesterday at 6:03 am UTC\n3. Join Roles are not being assigned. Steps:\\- Added role \"Users\" (701822101941649558) to Join Roles in dashboard.\n\\- Worked fine for two months.\n\\- Suddenly stopped.\n4. Yes, in one server as well but not in another.\n5. IDs:\n\\- 678279978244374528 (my main server)\n\\- 181730794815881216 (does not work as well)\n\\- 288847386002980875 (works there)\n6. I did:\\- Removed Join Role and set it again in the dashboard\n7. Yes, we rely on Sapphire's Join Roles very much", 
            ephemeral=True
            )
    @ui.button(label="How to get a server's ID?", style=discord.ButtonStyle.grey, custom_id="how-to-get-server-id")
    async def on_how_to_get_server_id_click(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="How to find your server's ID",
            description="1. Open [Sapphire's dashboard](https://dashboard.sapph.xyz).\n2. Select your server.\n3. Find your server ID (16-19 long number) in the URL."
        )
        embed.set_image(url="https://img-temp.sapph.xyz/fef61749-efb4-46c5-4015-acc7311d7900")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class utility(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.client.add_view(NeedDevReviewButtons())

    @app_commands.command(name="list-unsolved",  description="Lists all currently unsolved posts")
    @commands.guild_only() # Allow the command to only be used in guilds
    async def list_unsolved(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        posts = '' # Define an initial empty string to add the links to
        support = interaction.guild.get_channel(SUPPORT_CHANNEL_ID) # Get #support channel
        for post in support.threads: # Loop through all threads in #support
            if not post.archived and not post.locked: # Check if the post is not archived and not locked
                not_solved_tag = support.get_tag(NOT_SOLVED_TAG_ID) # Get not solved tag
                solved_tag = support.get_tag(SOLVED_TAG_ID) # Get solved tag
                need_dev_review_tag = support.get_tag(NEED_DEV_REVIEW_TAG_ID) # Get need-dev-review tag
                unanswered_tag = support.get_tag(UNANSWERED_TAG_ID)
                if need_dev_review_tag not in post.applied_tags: # Check if the post doesn't have need dev review tag
                    if not_solved_tag in post.applied_tags or solved_tag not in post.applied_tags or unanswered_tag in post.applied_tags: # Check if the post has not solved tag or doesn't have solved or has unanswered
                        posts += f"* {post.mention}\n" # Add the current post's link to the posts list
                    else:
                        continue # Continue to the next iteration of the loop as the current post has solved tag
                else:
                    continue # Continue to the next iteration of the loop as the current post has need dev review tag
            else:
                continue # Continue to the next iteration of the loop as the current post is archived (closed) or locked
        if posts != '': # Check if posts var has any characters in it
            embed = discord.Embed(
                title="Unsolved posts:",
                description=posts,
                colour=0x2b2d31
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        elif posts == '': # Check if no posts were found
            await interaction.followup.send(content="There aren't any unsolved posts at the moment, come back later...", ephemeral=True)

    @app_commands.command(name="solved", description="Mark the current post as solved")
    @app_commands.guild_only()
    async def solved(self, interaction: discord.Interaction):
        experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
        moderators = interaction.guild.get_role(MODERATORS_ROLE_ID)
        if isinstance(interaction.channel, discord.Thread):
            if interaction.user == interaction.channel.owner or experts in interaction.user.roles or moderators in interaction.user.roles: # Check if the user is the creator of the post or has experts/moderators roles
                need_dev_review_tag = interaction.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
                solved = interaction.channel.parent.get_tag(SOLVED_TAG_ID)
                cb = interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
                if need_dev_review_tag not in interaction.channel.applied_tags:
                    if solved not in interaction.channel.applied_tags:
                        task =  asyncio.create_task(ClosePost(post=interaction.channel))
                        close_tasks[interaction.channel] = task # Add the and post to the "close_tasks" dict
                        tags = [solved]
                        if cb in interaction.channel.applied_tags:
                            tags.append(cb)
                        await interaction.channel.edit(applied_tags=tags)
                        now = datetime.datetime.now()
                        one_hour_from_now = now + datetime.timedelta(hours=1)
                        await interaction.response.send_message(content=f"This post was marked as solved.\n-# It will be automatically closed <t:{round(one_hour_from_now.timestamp())}:R>. Use </unsolved:1274997472162349078> to cancel.")
                    else:
                        await interaction.response.send_message(content="This post is already marked as solved.", ephemeral=True)
                else:
                    button = ui.Button(label="Confirm", style=discord.ButtonStyle.green, custom_id="solved-confirm")
                    async def on_confirm_button_click(Interaction: discord.Interaction):
                        task = asyncio.create_task(ClosePost(post=interaction.channel))
                        close_tasks[interaction.channel] = task # Add the task and post to the "close_tasks" dict
                        await interaction.delete_original_response()
                        now = datetime.datetime.now()
                        one_hour_from_now = now + datetime.timedelta(hours=1)
                        await Interaction.response.send_message(content=f"This post was marked as solved.\n-# It will be automatically closed <t:{round(one_hour_from_now.timestamp())}:R>. Use </unsolved:1274997472162349078> to cancel.")
                        tags = [solved]
                        if cb in Interaction.channel.applied_tags:
                            tags.append(cb)
                        await Interaction.channel.edit(applied_tags=tags)
                    button.callback = on_confirm_button_click
                    view = ui.View()
                    view.add_item(button)
                    await interaction.response.send_message(content="This post has need-dev-review tag, are you sure you would like to mark it as solved?", view=view, ephemeral=True)
            else:
                await interaction.response.send_message(content="Only Moderators, Community Experts and the post creator can use this.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="Command disabled in this channel",
                description="> This command can only be used inside of a post in <#1023653278485057596>.",
                colour=0xce3636
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unsolve", description="Cancel the post from being closed")
    @app_commands.guild_only()
    async def unsolved(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.Thread):
            if interaction.channel.parent_id == SUPPORT_CHANNEL_ID:
                experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
                mods = interaction.guild.get_role(MODERATORS_ROLE_ID)
                if experts in interaction.user.roles or mods in interaction.user.roles or interaction.user == interaction.channel.owner:
                    if interaction.channel in close_tasks:
                        close_tasks[interaction.channel].cancel()
                        close_tasks.pop(interaction.channel)
                        tags = [interaction.channel.parent.get_tag(NOT_SOLVED_TAG_ID)]
                        if interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in interaction.channel.applied_tags:
                            tags.append(interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
                        await interaction.channel.edit(applied_tags=tags)
                        await interaction.response.send_message(content="Post successfully unsolved")
                    elif interaction.channel.parent.get_tag(SOLVED_TAG_ID) in interaction.channel.applied_tags:
                        tags = [interaction.channel.parent.get_tag(NOT_SOLVED_TAG_ID)]
                        if interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in interaction.channel.applied_tags:
                            tags.append(interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
                        await interaction.channel.edit(applied_tags=tags)
                        await interaction.response.send_message(content="Post successfully unsolved")
                    else:
                        await interaction.response.send_message(content="This post isn't currently marked as solved...\nTry again later", ephemeral=True)
                else:
                    await interaction.response.send_message(content="This command can only be used by Moderators, Community Experts, and the creator of the post.", ephemeral=True)
            else:
                await interaction.response.send_message(content="This command can only be used in <#1023653278485057596>")
        else:
            await interaction.response.send_message(content=f"This command can only be used inside of a post in <#1023653278485057596>", ephemeral=True)

    @app_commands.command(name="needs-dev-review", description="This post needs to be reviewed by the developer")
    @app_commands.guild_only()
    async def need_dev_review(self, interaction: discord.Interaction):
        experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
        moderators = interaction.guild.get_role(MODERATORS_ROLE_ID)
        if isinstance(interaction.channel, discord.Thread):
            if moderators in interaction.user.roles or experts in interaction.user.roles:
                if interaction.channel.parent.id == SUPPORT_CHANNEL_ID:
                    await interaction.response.defer()
                    embed = discord.Embed(
                        description=f"# Waiting for dev review\nThis post was marked as **<:sapphire_red:908755238473834536> Needs dev review** by {interaction.user.mention}\n\n### Please answer _all_ of the following questions, regardless of whether they have already been answered somewhere in this post.\n1. Which feature(s) are connected to this issue?\n3. When did this issue start to occur?\n4. What is the issue and which steps lead to it?\n5. Can this issue be reproduced by other users/in other servers?\n6. Which server IDs are related to this issue?\n7. What did you already try to fix this issue by yourself? Did it work?\n8. Does this issue need to be fixed urgently?\n\n_ _",
                        colour=0x2b2d31
                    )
                    embed.set_footer(text="Thank you for helping Sapphire to continuously improve.")
                    await interaction.followup.send(embed=embed, view=NeedDevReviewButtons())
                    tags = [interaction.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)]
                    if interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in interaction.channel.applied_tags:
                        tags.append(interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
                    await interaction.channel.edit(applied_tags=tags)
                    channel = interaction.guild.get_channel(1145088659545141421)
                    await channel.send(f'A new post has been marked as "Needs dev review"\n> {interaction.channel.mention}')
                else:
                    await interaction.response.defer(ephemeral=True)
                    embed = discord.Embed(
                        title="Command disabled in this channel",
                        description="> This command can only be used inside of a post in <#1023653278485057596>.",
                        colour=0xce3636
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.defer(ephemeral=True)
                await interaction.followup.send(content="Only Moderators and Community Experts can use this command.", ephemeral=True)
        else:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(content="This command can only be used in #support!", ephemeral=True)
                
async def setup(client):
    await client.add_cog(utility(client))
