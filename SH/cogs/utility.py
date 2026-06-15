from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime
import os
from dotenv import load_dotenv
from functions import remove_post_from_rtdr, get_post_creator_id, \
                    generate_random_id, remove_post_from_pending
from typing import Union, Literal, Callable, TYPE_CHECKING
import re
if TYPE_CHECKING:
    from main import MyClient


load_dotenv()

SOLVED_TAG_ID = int(os.getenv("SOLVED_TAG_ID"))
NOT_SOLVED_TAG_ID = int(os.getenv("NOT_SOLVED_TAG_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
CUSTOM_BRANDING_TAG_ID = int(os.getenv('CUSTOM_BRANDING_TAG_ID'))
EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
NDR_CHANNEL_ID = int(os.getenv('NDR_CHANNEL_ID'))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))
QR_LOG_THREAD_ID = int(os.getenv("QR_LOG_THREAD_ID"))
APPEAL_GG_TAG_ID = int(os.getenv("APPEAL_GG_TAG_ID"))
WAITING_FOR_REPLY_TAG_ID = int(os.getenv("WAITING_FOR_REPLY_TAG_ID"))
UNANSWERED_TAG_ID = int(os.getenv("UNANSWERED_TAG_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv('DEVELOPERS_ROLE_ID'))

class NeedDevReviewButtons(ui.ActionRow):
    @ui.button(label="Show an example of the questions answered", style=discord.ButtonStyle.grey, custom_id="need-dev-review-example")
    async def on_show_example_click(self, interaction: discord.Interaction, button: ui.Button):
        show_example_view = ui.LayoutView()
        show_example_container = ui.Container(
            ui.TextDisplay("## Example message on how you could answer these questions for an imaginary issue.\n\n1. Join Roles\n2. Last join role assigned yesterday at 6:03 am UTC\
            \n3. Join Roles are not being assigned. Steps:\n  - Added role \"Users\" (701822101941649558) to Join Roles in dashboard.\n  - Worked fine for two months.\n  - Suddenly stopped.\
            \n4. Yes, in one server as well but not in another.\n5. IDs:\n  - 678279978244374528 (my main server)\n  - 181730794815881216 (does not work as well)\n  - 288847386002980875 (works there)\
            \n6. I did:\n  - Removed Join Role and set it again in the dashboard\n7. Yes, we rely on Sapphire's Join Roles very much"),
            accent_color=discord.Color.purple()
        )
        show_example_view.add_item(show_example_container)
        await interaction.response.send_message(view=show_example_view, ephemeral=True)


    @ui.button(label="How to get a server's ID?", style=discord.ButtonStyle.grey, custom_id="how-to-get-server-id")
    async def on_how_to_get_server_id_click(self, interaction: discord.Interaction, button: ui.Button):
        server_id_view = ui.LayoutView()
        server_id_container = ui.Container(accent_color=discord.Color.purple())
        server_id_view.add_item(server_id_container)

        content = "## How to find your server's ID\n1. Open [Sapphire's dashboard](https://dashboard.sapph.xyz).\n2. Select your server.\n3. Find your server ID (16-19 long number) in the URL."
        image = "https://img-temp.sapph.xyz/fef61749-efb4-46c5-4015-acc7311d7900"
        server_id_container.add_item(ui.TextDisplay(content))
        server_id_container.add_item(
            ui.MediaGallery(
                discord.MediaGalleryItem(image, description="Server id location")
            )
        )

        await interaction.response.send_message(view=server_id_view, ephemeral=True)


class NeedDevReviewView(ui.LayoutView):
    def __init__(self, *, executor_id: int = 0):
        self.executor_id = executor_id
        super().__init__(timeout=None)

        container = ui.Container(accent_color=discord.Color.purple())
        self.need_dev_review_buttons = NeedDevReviewButtons()
        self.questions = f"# Waiting for dev review\nThis post was marked as **<:sapphire_red:908755238473834536> Needs dev review** by <@{self.executor_id}>\n\n### Please answer _all_ of the following questions, regardless of whether they have already been answered somewhere in this post.\n1. Which feature(s) are connected to this issue?\n2. When did this issue start to occur?\n3. What is the issue and which steps lead to it?\n4. Can this issue be reproduced by other users/in other servers?\n5. Which server IDs are related to this issue?\n6. What did you already try to fix this issue by yourself? Did it work?\n7. Does this issue need to be fixed urgently?\n\n_ _"
        self.footer = "-# Thank you for helping Sapphire to continuously improve."
        container.add_item(ui.TextDisplay(self.questions + "\n" + self.footer))
        container.add_item(ui.Separator())
        container.add_item(self.need_dev_review_buttons)

        self.add_item(container)


class ndr_options_buttons(ui.View):
    def __init__(self, Interaction: discord.Interaction[MyClient]):
        super().__init__(timeout=None)
        self.Interaction = Interaction
    
    async def mark_post_as_ndr(self, post: discord.Thread):
        ndr = post.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
        tags = [ndr]
        cb = post.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
        appeal = post.parent.get_tag(APPEAL_GG_TAG_ID)
        if cb in post.applied_tags: 
            tags.append(cb)
        if appeal in post.applied_tags:
            tags.append(appeal)
        action_id = generate_random_id()

        await post.edit(applied_tags=tags, reason=f"ID: {action_id}. Post marked as needs-dev-review with /needs-dev-review")
        await self.Interaction.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=post.mention, tags=tags, context="/needs-dev-review command used")
        channel = post.guild.get_channel(NDR_CHANNEL_ID)
        await channel.send(f'A new post has been marked as "Needs dev review"\n> {post.mention}')
        await remove_post_from_pending(post.id)

    @ui.button(label="Only add tag", style=discord.ButtonStyle.grey, custom_id="ndr-only-add-tag")
    async def on_only_add_tag_click(self, interaction: discord.Interaction, button: ui.Button):
        await self.Interaction.delete_original_response()
        await interaction.response.defer(ephemeral=False)
        await self.mark_post_as_ndr(interaction.channel)
        await interaction.channel.send(content="Post successfully marked as *needs-dev-review*.")

    @ui.button(label="Add tag & send questions", style=discord.ButtonStyle.grey, custom_id="ndr-tag-and-questions")
    async def on_send_questions_click(self, interaction: discord.Interaction, button: ui.Button):
        await self.Interaction.delete_original_response()
        await interaction.response.defer()
        await self.mark_post_as_ndr(interaction.channel)
        await interaction.channel.send(
            view=NeedDevReviewView(executor_id=interaction.user.id),
            allowed_mentions=discord.AllowedMentions.none()
        )

class SolvedView(ui.LayoutView):
    def __init__(self, unsolve_id: int) -> None:
        super().__init__(timeout=None)
        container = ui.Container()
        title = "### Marked as Solved"

        one_hour_from_now = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
        footer= f"-# Closes {discord.utils.format_dt(one_hour_from_now, 'R')}. Use </unsolve:{unsolve_id}> to cancel."

        container.add_item(ui.TextDisplay(title))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(footer))
        self.add_item(container)


class SolvedRowWithNDR(ui.ActionRow):
    def __init__(self, mark_post_as_solved: Callable) -> None:
        super().__init__()
        self.mark_post_as_solved = mark_post_as_solved
    
    @ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="solved-confirm")
    async def on_confirm_button_click(self, interaction: discord.Interaction[MyClient], button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.delete_original_response()
        await interaction.channel.send(view=SolvedView(await interaction.client.get_unsolve_id()))
        await self.mark_post_as_solved(interaction.channel)


# This is sent when the post has a NDR tag
class SolvedViewWithNDR(ui.LayoutView):
    def __init__(self, mark_post_as_solved: Callable) -> None:
        super().__init__(timeout=None)
        container = ui.Container()
        container.add_item(ui.TextDisplay("This post has the **needs-dev-review tag**, are you sure you would like to mark it as solved?"))
        container.add_item(ui.Separator())
        container.add_item(SolvedRowWithNDR(mark_post_as_solved))
        self.add_item(container)


class utility(commands.Cog):
    def __init__(self, client: MyClient):
        self.client = client

    close_tasks: dict[int, asyncio.Task] = {} # posts that are waiting to be closed with their respective asyncio.Task

    async def close_post(self, post: discord.Thread, close_delay: float = 3600) -> None:
        """  
        Used with asyncio.create_task to close the given post after the given delay in seconds.
        """
        await asyncio.sleep(close_delay) # wait for close_delay hours
        await post.edit(
            archived=True,
            reason=f"Auto archive {'solved' if close_delay == 3600 else 'unrelated'} post after {close_delay} seconds"
        )
        self.close_tasks.pop(post.id)
        await remove_post_from_rtdr(post.id)
        await remove_post_from_pending(post.id)
        if post.id in self.client.incomplete_msg_posts:
            self.client.incomplete_msg_posts.remove(post.id)

    async def mark_post_as_solved(self, post: discord.Thread) -> None:
        """  
        Mark the given post as solved- adds tags and create task with delay to archive it.
        Returns the task
        """
        solved = post.parent.get_tag(SOLVED_TAG_ID)
        cb = post.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
        appeal = post.parent.get_tag(APPEAL_GG_TAG_ID)
        tags = [solved]
        if cb in post.applied_tags: 
            tags.append(cb)
        if appeal in post.applied_tags:
            tags.append(appeal)
        action_id = generate_random_id()
        await post.edit(applied_tags=tags, reason=f"ID: {action_id}. Post marked as solved with /solved")
        await self.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=post.mention, tags=tags, context="/solved used")
        task = asyncio.create_task(self.close_post(post=post))
        self.close_tasks[post.id] = task

    async def lock_unrelated_post(self, post: discord.Thread) -> None:
        """
        Lock the given post, override the tags to the solved tag and create a task with a delay to archive it
        """
        solved = [post.parent.get_tag(SOLVED_TAG_ID)]
        action_id = generate_random_id()
        await post.edit(locked=True, applied_tags=solved, reason=f'ID: {action_id}. Post locked as it was not sapphire related')
        await self.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=post.mention, tags=solved, context="/unrelated used")
        asyncio.create_task(self.close_post(post=post, close_delay=600))

    async def unsolve_post(self, post: discord.Thread) -> None:
        """  
        Cancel marking the given post as solved, used in /unsolve command
        """
        if post.id in self.close_tasks: 
            self.close_tasks[post.id].cancel()
            del self.close_tasks[post.id]
        not_solved = post.parent.get_tag(NOT_SOLVED_TAG_ID)
        cb = post.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
        appeal = post.parent.get_tag(APPEAL_GG_TAG_ID)
        tags = [not_solved]
        if cb in post.applied_tags: 
            tags.append(cb)
        if appeal in post.applied_tags:
            tags.append(appeal)
        action_id = generate_random_id()
        await post.edit(applied_tags=tags, reason=f"ID: {action_id}. Post unsolved with /unsolve")
        await self.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=post.mention, tags=tags, context="/unsolve used")

    @staticmethod
    async def one_of_mod_expert_op(interaction: discord.Interaction):
        """  
        Checks if the interaction user is a Moderator or Community Expert or the creator of the post\n
        --Integrated with rtdr system
        """
        if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == SUPPORT_CHANNEL_ID:
            owner_id = await get_post_creator_id(interaction.channel_id) or interaction.channel.owner_id
            return bool(interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID)) or interaction.user.id == owner_id
        else:
            return False

    @staticmethod
    async def is_mod_or_expert_or_dev(interaction: discord.Interaction):
        """  
        Checks if the interaction user is a Moderator or Community Expert
        """
        return bool(interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID))

    @commands.Cog.listener("on_ready")
    async def add_persistent_view(self):
        self.client.add_view(NeedDevReviewView())

    @app_commands.command(name="solved", description="Mark the current post as solved")
    @app_commands.check(one_of_mod_expert_op)
    @app_commands.guild_only()
    async def solved(self, interaction: discord.Interaction):
        if NEED_DEV_REVIEW_TAG_ID not in interaction.channel._applied_tags and "forwarded" not in interaction.channel.name.casefold():
            if SOLVED_TAG_ID in interaction.channel._applied_tags:
                await interaction.response.send_message(content="This post is already marked as solved.", ephemeral=True)
                return
            await interaction.response.send_message(view=SolvedView(await self.client.get_unsolve_id()))
            await self.mark_post_as_solved(interaction.channel)
        else:
            await interaction.response.send_message(view=SolvedViewWithNDR(self.mark_post_as_solved), ephemeral=True)
            
    @app_commands.command(name="remove", description="Remove the given member from the current post")
    @app_commands.guild_only()
    @app_commands.describe(user="What user do you want to remove?", reason="The reason for removing the user")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def remove(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided."):
        if not isinstance(interaction.channel, discord.Thread) or interaction.channel.parent_id != SUPPORT_CHANNEL_ID:
            await interaction.response.send_message(content=f"This command is only usable in a post in <#{SUPPORT_CHANNEL_ID}>", ephemeral=True)
            return
        is_owner = user.id == interaction.channel.owner_id or user.id == await get_post_creator_id(interaction.channel_id)
        if is_owner:
            await interaction.response.send_message(f"{user.mention} is the owner of this post. Therefore they cannot be removed.", ephemeral=True)
            return
        await interaction.channel.remove_user(user)
        await interaction.response.send_message(content=f"Successfully removed {user.mention} from this post.", ephemeral=True)

        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID) or await self.client.fetch_channel(ALERTS_THREAD_ID)
        await alerts_thread.send(f"{interaction.user.mention} removed {user.mention} from {interaction.channel.mention}.\nReason: {reason}", allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="unsolve", description="Cancel the post from being closed")
    @app_commands.check(one_of_mod_expert_op)
    @app_commands.guild_only()
    async def unsolved(self, interaction: discord.Interaction):
        if interaction.channel in self.close_tasks or SOLVED_TAG_ID in interaction.channel._applied_tags:
            if interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID):
                await interaction.response.send_message("Post successfully unsolved!")
                return
            title = "### Post Successfully Unsolved"
            description = "Please send a message here explaining what you still need help with"
            footer = f"-# If the issue is resolved, you may use </solved:{await self.client.get_solved_id()}> to mark it as solved."
            view = ui.LayoutView().add_item(ui.Container(ui.TextDisplay(title), ui.Separator(visible=False), ui.TextDisplay(description), ui.Separator(), ui.TextDisplay(footer)))
            await interaction.response.send_message(view=view)
            await self.unsolve_post(interaction.channel)
        else:
            await interaction.response.send_message(content="This post isn't currently marked as solved...\nTry again later", ephemeral=True)

    @app_commands.command(name="needs-dev-review", description="This post needs to be reviewed by the developer")
    @app_commands.guild_only()
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def need_dev_review(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == SUPPORT_CHANNEL_ID:
            if NEED_DEV_REVIEW_TAG_ID not in interaction.channel._applied_tags:
                await interaction.response.send_message(ephemeral=True, view=ndr_options_buttons(interaction), content="Select one of the options below or dismiss message to cancel.")
            else:
                await interaction.response.send_message(content="This post already has needs-dev-review tag.", ephemeral=True)
        else:
            await interaction.response.send_message(f"This command is only usable in a post in <#{SUPPORT_CHANNEL_ID}>", ephemeral=True)

    async def send_qr_log(self, message: discord.Message, user: discord.Member):
        await self.client.send_log(QR_LOG_THREAD_ID, content=f"Message deleted by {user.mention} in {message.channel.mention}\nMessage id: `{message.id}`")

    def get_user_id_from_avatar(self, avatar_url: str) -> int | None:
        """Gets the user_id from a users avatar"""

        guild_member_avatar_regex = r"^https?:\/\/cdn\.discord(?:app)?\.com\/guilds\/\d+\/users\/\d+\/avatars\/"
        user_avatar_regex = r"^https?:\/\/cdn\.discord(?:app)?\.com\/avatars\/\d+\/"
        if re.match(user_avatar_regex, avatar_url, re.IGNORECASE):
            user_id = int(avatar_url.split("/")[4]) #https://cdn.discordapp.com/avatars/user_id/user_avatar.png -> ['https:', '', 'cdn.discordapp.com', 'avatars', 'user_id', 'user_avatar.png']
        elif re.match(guild_member_avatar_regex, avatar_url, re.IGNORECASE):
            user_id = int(avatar_url.split("/")[6]) #https://cdn.discordapp.com/guilds/guild_id/users/user_id/avatars/member_avatar.png -> ['https:', '', 'cdn.discordapp.com', 'guilds', 'guild_id', 'users', 'user_id', 'avatars', 'member_avatar.png']
        else:
            user_id = None
        return user_id

    @commands.Cog.listener('on_reaction_add')
    async def delete_accidental_qr(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        in_support = isinstance(reaction.message.channel, discord.Thread) \
            and reaction.message.channel.parent_id == SUPPORT_CHANNEL_ID
        from_sapphire_or_helper = reaction.message.author.id == 678344927997853742 or \
                                reaction.message.author.id == self.client.user.id
        reaction_allowed = reaction.emoji in ("🗑️", "❌")
        if not in_support or not from_sapphire_or_helper or not reaction_allowed:
            return
    
        if user.get_role(EXPERTS_ROLE_ID) or user.get_role(MODERATORS_ROLE_ID) or user.get_role(DEVELOPERS_ROLE_ID):
            await reaction.message.delete()
            await self.send_qr_log(reaction.message, user)
            return
        if reaction.message.interaction_metadata:
            if reaction.message.interaction_metadata.user == user:
                await reaction.message.delete()
                await self.send_qr_log(message=reaction.message, user=user)
                return
        elif reaction.message.embeds:
            if reaction.message.embeds[len(reaction.message.embeds)-1].footer:
                footer = reaction.message.embeds[len(reaction.message.embeds)-1].footer

                regex = f'(Recommended|Sent) by @{user.name}'
                if footer.text and re.match(regex, footer.text, re.IGNORECASE):
                    await reaction.message.delete()
                    await self.send_qr_log(message=reaction.message, user=user)
                    return

                if footer.icon_url:
                    user_id = self.get_user_id_from_avatar(footer.icon_url)
                    if user_id is not None and user_id == user.id:
                        await reaction.message.delete()
                        await self.send_qr_log(message=reaction.message, user=user)
                        return
        elif reaction.message.flags.components_v2:
            patterns =  (f'-# Recommended by {user.mention}', f"-# Sent by {user.mention}")
            view = ui.LayoutView.from_message(reaction.message)
            for child in view.walk_children():
                if isinstance(child, ui.TextDisplay) and any(child.content.endswith(pattern) for pattern in patterns):
                    await reaction.message.delete()
                    await self.send_qr_log(reaction.message, user)
                    return

        if reaction.message.reference and reaction.message.reference.cached_message:
            if user == reaction.message.reference.cached_message.author:
                await reaction.message.delete()
                await self.send_qr_log(reaction.message, user)
                return
        if reaction.message.content and reaction.message.content.endswith(f"Recommended by {user.mention}"):
            await reaction.message.delete()
            await self.send_qr_log(reaction.message, user)
            return    

    @app_commands.command(name="atbl", description="Mark the current post as 'Added to bug list'")
    @app_commands.describe(priority="The priority of this issue")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID)
    async def atbl(self, interaction: discord.Interaction, priority: Literal["Very Low", "Low", "Medium", "High", "Special Issue"]):
        if not isinstance(interaction.channel, discord.Thread) or interaction.channel.parent_id != SUPPORT_CHANNEL_ID:
            await interaction.response.send_message(content=f"This command can only be used in <#{SUPPORT_CHANNEL_ID}>!", ephemeral=True)
            return
        priority_texts = {
            "very low": "We'll get to this eventually.",
            "low": "We'll take care of this when we have time and if there are no higher-priority bugs.",
            "medium": "We'll probably get to this in about 1-2 weeks, unless something more urgent comes up.",
            "high": "We'll fix this as soon as we can.",
            "special issue": "User specific issue"
        }
        view = ui.LayoutView()
        text = f"### The development team has added this bug to their tracking list\n**Priority**\n{priority}"
        if priority.casefold() != "special issue":
            text += f"\n**When is this issue expected to be resolved?**\n{priority_texts.get(priority.casefold())}"
        container = ui.Container(
            ui.TextDisplay(text),
            accent_colour=0xE88802
        )
        view.add_item(container)
        await interaction.response.send_message(view=view)

        ndr = interaction.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
        cb = interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
        appeal = interaction.channel.parent.get_tag(APPEAL_GG_TAG_ID)
        tags = [ndr]
        if cb in interaction.channel.applied_tags:
            tags.append(cb)
        if appeal in interaction.channel.applied_tags:
            tags.append(appeal)
        await interaction.channel.edit(name=f"[ATBL] {interaction.channel.name}", reason=f"@{interaction.user.name} used /atbl", applied_tags=tags)

    @commands.hybrid_command(name="incomplete-post", description="Request more information from the post creator")
    @commands.guild_only()
    async def incomplete_post(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        if not isinstance(ctx.channel, discord.Thread) or ctx.channel.parent_id != SUPPORT_CHANNEL_ID:
            await ctx.reply(content=f"This command can only be used in <#{SUPPORT_CHANNEL_ID}>!", ephemeral=True)
            return
    
        if SOLVED_TAG_ID in ctx.channel._applied_tags or NEED_DEV_REVIEW_TAG_ID in ctx.channel._applied_tags:
            await ctx.reply("You cannot use this command as this post has the *Solved* or *Needs dev review* tag.", ephemeral=True, delete_after=3)
            return
        
        if ctx.channel.id in self.client.incomplete_msg_posts:
            await ctx.reply("You cannot use this command as an automatic message was already sent.", ephemeral=True, delete_after=5)
            return
        user_id = await get_post_creator_id(ctx.channel.id) or ctx.channel.owner_id
        text_prefix = "## Incomplete support post\nHey"
        if ctx.author.get_role(EXPERTS_ROLE_ID) or ctx.author.get_role(MODERATORS_ROLE_ID) or ctx.author.get_role(DEVELOPERS_ROLE_ID):
            text_prefix = f"## Incomplete support post\nHey <@{user_id}>"
        view = ui.LayoutView()
        container = ui.Container(
            ui.TextDisplay(f"{text_prefix}, it seems like your support post is incomplete. Please make sure to provide the following information:\n\n> `-` What feature do you need help with?\n> `-` What exactly is the issue / what are you trying to do?\n> `-` What did you already try?\n> `-` Include screenshots if possible\n-# Recommended by {ctx.author.mention}"),
            accent_colour=0xFFA800
        )
        view.add_item(container)

        if not ctx.interaction:
            await ctx.message.delete()
        elif ctx.interaction:
            await ctx.interaction.delete_original_response()
        if WAITING_FOR_REPLY_TAG_ID in ctx.channel._applied_tags or UNANSWERED_TAG_ID in ctx.channel._applied_tags:
            tags = [ctx.channel.parent.get_tag(NOT_SOLVED_TAG_ID)]
            if CUSTOM_BRANDING_TAG_ID in ctx.channel._applied_tags:
                tags.append(ctx.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
            if APPEAL_GG_TAG_ID in ctx.channel._applied_tags:
                tags.append(ctx.channel.parent.get_tag(APPEAL_GG_TAG_ID))
            action_id = generate_random_id()
            await ctx.channel.edit(applied_tags=tags, reason=f"ID: {action_id}. @{ctx.author.name} used /incomplete-post")
            await self.client.send_log(ALERTS_THREAD_ID, action_id=action_id, post_mention=ctx.channel.mention, tag=tags, context="/incomplete-post used")
        await ctx.channel.send(
            view=view,
            allowed_mentions=discord.AllowedMentions(users=[discord.Object(user_id)])
        )
    @staticmethod
    async def non_expert_mod_cooldown(interaction: discord.Interaction):
        """
        Returns a cooldown of 1 use per 5 minutes if the command author is not expert or mod
        """
        if interaction.user.get_role(MODERATORS_ROLE_ID) or interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(DEVELOPERS_ROLE_ID):
            return None

        return commands.Cooldown(1,  5.0 * 60.0)


    @app_commands.command(
            name='unrelated',
            description='Inform the post creator that their question/issue is not Sapphire/appeal.gg related.'
    )
    @app_commands.guild_only()
    @app_commands.checks.dynamic_cooldown(non_expert_mod_cooldown)
    async def wrong_server(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.Thread) or interaction.channel.parent_id != SUPPORT_CHANNEL_ID:
            await interaction.response.send_message(f"This command can only be used in <#{SUPPORT_CHANNEL_ID}>", ephemeral=True)
            return
        
        await interaction.response.defer()
        user_id = 0
        view = ui.LayoutView()
        container = ui.Container(accent_colour=0xFFA800)
        view.add_item(container)

        text_prefix = "Hey"
        if await self.is_mod_or_expert_or_dev(interaction=interaction):
            user_id = await get_post_creator_id(interaction.channel_id) or interaction.channel.owner_id
            text_prefix = f"Hey <@{user_id}>"
            await self.lock_unrelated_post(interaction.channel)

        title = "## Unrelated question/issue"
        description = f"{text_prefix}, your question/issue **is not related** to Sapphire or appeal.gg. Please search for the proper server/resource to get an answer to your question.\nWe cannot help you any further with your query."
        footer = f"-# Recommended by {interaction.user.mention}"

        container.add_item(
            ui.TextDisplay(f"{title}\n{description}\n{footer}")
        )

        await interaction.channel.send(
            view=view,
            allowed_mentions=discord.AllowedMentions(users=[discord.Object(user_id)])
        )
        await interaction.delete_original_response()
            

async def setup(client: MyClient):
    await client.add_cog(utility(client))
