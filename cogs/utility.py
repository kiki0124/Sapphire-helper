import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime
import os
from dotenv import load_dotenv
from functions import remove_post_from_rtdr, get_post_creator_id

load_dotenv()

SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
NOT_SOLVED_TAG_ID = int(os.getenv("NOT_SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
UNANSWERED_TAG_ID = int(os.getenv('UNANSWERED_TAG_ID'))
CUSTOM_BRANDING_TAG_ID = int(os.getenv('CUSTOM_BRANDING_TAG_ID'))
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
NDR_CHANNEL_ID = int(os.getenv('NDR_CHANNEL_ID'))

close_tasks: dict[discord.Thread, asyncio.Task] = {}

async def ClosePost(post: discord.Thread) -> None:
    await asyncio.sleep(3600) # wait for 3,600 seconds
    await post.edit(archived=True, reason="Auto archive solved post after 1 hour")
    close_tasks.pop(post) # remove the post from internal lists of posts waiting to be closed- list used for /unsolve
    await remove_post_from_rtdr(post.id) # remove the post from rtdr table if it was there or do nothing if it wasn't

async def mark_post_as_ndr(interaction: discord.Interaction):
    tags = interaction.channel.applied_tags
    tags.append(interaction.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID))
    await interaction.channel.edit(applied_tags=tags)
    channel = interaction.guild.get_channel(NDR_CHANNEL_ID)
    await channel.send(f'A new post has been marked as "Needs dev review"\n> {interaction.channel.mention}')

class need_dev_review_buttons(ui.View):
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

class ndr_options_buttons(ui.View):
    def __init__(self, Interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.Interaction = Interaction
    
    @ui.button(label="Only add tag", style=discord.ButtonStyle.grey, custom_id="ndr-only-add-tag")
    async def on_only_add_tag_click(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=False)
        await mark_post_as_ndr(interaction)
        await interaction.channel.send(content="Post successfully marked as *needs-dev-review*.")
        await self.Interaction.delete_original_response()

    @ui.button(label="Add tag & send questions", style=discord.ButtonStyle.grey, custom_id="ndr-tag-and-questions")
    async def on_send_questions_click(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await mark_post_as_ndr(interaction)
        embed = discord.Embed(
                    description=f"# Waiting for dev review\nThis post was marked as **<:sapphire_red:908755238473834536> Needs dev review** by {interaction.user.mention}\n\n### Please answer _all_ of the following questions, regardless of whether they have already been answered somewhere in this post.\n1. Which feature(s) are connected to this issue?\n2. When did this issue start to occur?\n3. What is the issue and which steps lead to it?\n4. Can this issue be reproduced by other users/in other servers?\n5. Which server IDs are related to this issue?\n6. What did you already try to fix this issue by yourself? Did it work?\n7. Does this issue need to be fixed urgently?\n\n_ _",
                    colour=0x2b2d31
                )
        embed.set_footer(text="Thank you for helping Sapphire to continuously improve.")
        await interaction.channel.send(embed=embed, view=need_dev_review_buttons()) # send the embed with the buttons
        await self.Interaction.delete_original_response()

class utility(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client
    
    @staticmethod
    async def ModOrExpertOrOP(interaction: discord.Interaction):
        """  
        Checks if the interaction user is a Moderator or Community Expert or the creator of the post\n
        --Integrated with rtdr system
        """
        experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
        mods = interaction.guild.get_role(MODERATORS_ROLE_ID)
        return experts in interaction.user.roles or mods in interaction.user.roles or interaction.user == interaction.channel.owner or interaction.user.id == await get_post_creator_id(interaction.channel.id)

    @commands.Cog.listener()
    async def on_ready(self):
        self.client.add_view(need_dev_review_buttons()) # add the need dev review button/view to make it persistent (work after restart)

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
        if posts: # Check if posts var has any characters in it
            embed = discord.Embed(
                title="Unsolved posts:",
                description=posts,
                colour=0x2b2d31
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        elif not posts: # Check if no posts were found
            await interaction.followup.send(content="There aren't any unsolved posts at the moment, come back later...", ephemeral=True)

    @app_commands.command(name="solved", description="Mark the current post as solved")
    @app_commands.check(ModOrExpertOrOP)
    @app_commands.guild_only() # make the command only usable in guilds- not dms
    async def solved(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.Thread):
            if interaction.channel.parent_id == SUPPORT_CHANNEL_ID:    
                need_dev_review_tag = interaction.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
                solved = interaction.channel.parent.get_tag(SOLVED_TAG_ID)
                cb = interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
                if need_dev_review_tag not in interaction.channel.applied_tags and "forwarded" not in interaction.channel.name.lower():
                    if solved not in interaction.channel.applied_tags:
                        await interaction.response.defer()
                        task =  asyncio.create_task(ClosePost(post=interaction.channel)) # create a task to close the post in 1 hour
                        close_tasks[interaction.channel] = task # Add the and post to the "close_tasks" dict
                        tags = [solved] # declare an initial list of tags to be applied to the post
                        if cb in interaction.channel.applied_tags: 
                            tags.append(cb) # add cb tag as it was in the post before the command was used
                        await interaction.channel.edit(applied_tags=tags)
                        now = datetime.datetime.now()
                        one_hour_from_now = now + datetime.timedelta(hours=1) # create a tiem object from 1 hour into the future from now, to be used as timestamp in the message
                        await interaction.followup.send(content=f"This post was marked as solved.\n-# It will be automatically closed <t:{round(one_hour_from_now.timestamp())}:R>. Use </unsolve:1281211280618950708> to cancel.")
                    else:
                        await interaction.response.defer(ephemeral=True)
                        await interaction.followup.send(content="This post is already marked as solved.", ephemeral=True)
                else: # post has ndr, send confirmation message
                    await interaction.response.defer(ephemeral=True)
                    button = ui.Button(label="Confirm", style=discord.ButtonStyle.green, custom_id="solved-confirm")
                    async def on_confirm_button_click(Interaction: discord.Interaction):
                        await Interaction.response.defer()
                        task = asyncio.create_task(ClosePost(post=interaction.channel))
                        close_tasks[interaction.channel] = task # Add the task and post to the "close_tasks" dict
                        await interaction.delete_original_response()
                        now = datetime.datetime.now()
                        one_hour_from_now = now + datetime.timedelta(hours=1)
                        await Interaction.followup.send(content=f"This post was marked as solved.\n-# It will be automatically closed <t:{round(one_hour_from_now.timestamp())}:R>. Use </unsolve:1281211280618950708> to cancel.")
                        tags = [solved]
                        if cb in Interaction.channel.applied_tags:
                            tags.append(cb)
                        await Interaction.channel.edit(applied_tags=tags)
                    button.callback = on_confirm_button_click # declare the callback for the button as the function above
                    view = ui.View()
                    view.add_item(button) # add the item to the view
                    await interaction.followup.send(content="This post has the need-dev-review tag, are you sure you would like to mark it as solved?", view=view, ephemeral=True)
            else:
                await interaction.response.defer(ephemeral=True)
                await interaction.followup.send(content=f"This command can only be used in <#{SUPPORT_CHANNEL_ID}>", ephemeral=True)
        else:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(content=f"This command can only be used in a post in <#{SUPPORT_CHANNEL_ID}>", ephemeral=True)

    @app_commands.command(name="remove", description="Remove the given member from the current post")
    @app_commands.guild_only()
    @app_commands.describe(user="What user do you want to remove?")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def remove(self, interaction: discord.Interaction, user: discord.Member):
        if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id==SUPPORT_CHANNEL_ID:
            await interaction.channel.remove_user(user)
            await interaction.response.send_message(content=f"Successfully removed {user.name} from this post.", ephemeral=True)
        else:
            await interaction.response.send_message(content=f"You can only use this command in a thread in <#{SUPPORT_CHANNEL_ID}>", ephemeral=True)

    @app_commands.command(name="unsolve", description="Cancel the post from being closed")
    @app_commands.check(ModOrExpertOrOP)
    @app_commands.guild_only()
    async def unsolved(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.Thread):
            if interaction.channel.parent_id == SUPPORT_CHANNEL_ID:
                if interaction.channel in close_tasks:
                    await interaction.response.defer()
                    close_tasks[interaction.channel].cancel()
                    close_tasks.pop(interaction.channel)
                    tags = [interaction.channel.parent.get_tag(NOT_SOLVED_TAG_ID)]
                    if interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in interaction.channel.applied_tags:
                        tags.append(interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
                    await interaction.channel.edit(applied_tags=tags, reason=f"{interaction.user.name} used /unsolve")
                    await interaction.followup.send(content="Post successfully unsolved")
                elif interaction.channel.parent.get_tag(SOLVED_TAG_ID) in interaction.channel.applied_tags:
                    await interaction.response.defer()
                    tags = [interaction.channel.parent.get_tag(NOT_SOLVED_TAG_ID)]
                    if interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in interaction.channel.applied_tags:
                        tags.append(interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
                    await interaction.channel.edit(applied_tags=tags, reason=f"{interaction.user.name} used /unsolve")
                    await interaction.followup.send(content="Post successfully unsolved")
                else:
                    await interaction.response.send_message(content="This post isn't currently marked as solved...\nTry again later", ephemeral=True)
            else:
                await interaction.response.send_message(content="This command can only be used in <#1023653278485057596>", ephemeral=True)
        else:
            await interaction.response.send_message(content=f"This command can only be used inside of a post in <#1023653278485057596>", ephemeral=True)

    @app_commands.command(name="needs-dev-review", description="This post needs to be reviewed by the developer")
    @app_commands.guild_only()
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def need_dev_review(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.Thread): # check if the interaction channel is a thread
            if interaction.channel.parent.id == SUPPORT_CHANNEL_ID: # check if the thread parent channel is #support
                ndr_tag = interaction.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
                if ndr_tag not in interaction.channel.applied_tags:
                    await interaction.response.defer(ephemeral=True)
                    """embed = discord.Embed(
                        description=f"# Waiting for dev review\nThis post was marked as **<:sapphire_red:908755238473834536> Needs dev review** by {interaction.user.mention}\n\n### Please answer _all_ of the following questions, regardless of whether they have already been answered somewhere in this post.\n1. Which feature(s) are connected to this issue?\n2. When did this issue start to occur?\n3. What is the issue and which steps lead to it?\n4. Can this issue be reproduced by other users/in other servers?\n5. Which server IDs are related to this issue?\n6. What did you already try to fix this issue by yourself? Did it work?\n7. Does this issue need to be fixed urgently?\n\n_ _",
                        colour=0x2b2d31
                    )
                    embed.set_footer(text="Thank you for helping Sapphire to continuously improve.")
                    await interaction.followup.send(embed=embed, view=need_dev_review_buttons()) # send the embed with the buttons
                    tags = [interaction.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)] 
                    if interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in interaction.channel.applied_tags:
                        tags.append(interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
                    await interaction.channel.edit(applied_tags=tags, reason=f"{interaction.user.name} used /need-dev-review") # Add need-dev-review tag
                    channel = interaction.guild.get_channel(1145088659545141421)
                    await channel.send(f'A new post has been marked as "Needs dev review"\n> {interaction.channel.mention}') # Send a message to a private mods channel so they can forward it """
                    await interaction.followup.send(ephemeral=True, view=ndr_options_buttons(interaction), content="Select one of the options below or dismiss message to cancel.")
                else:
                    await interaction.response.send_message(content="This post already has needs-dev-review tag.", ephemeral=True)
            else:
                await interaction.response.defer(ephemeral=True)
                await interaction.followup.send(content="This command can only be used in #support!", ephemeral=True)    
        else:
            await interaction.followup.send(content="This command can only be used in a thread inside of #support!", ephemeral=True)
            
async def setup(client):
    await client.add_cog(utility(client))
