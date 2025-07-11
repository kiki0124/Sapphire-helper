import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime
import os
from dotenv import load_dotenv
from functions import remove_post_from_rtdr, get_post_creator_id, \
                    generate_random_id, remove_post_from_pending
from aiocache import cached
from typing import Union, Literal
import re

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
        alerts_thread = post.guild.get_channel_or_thread(ALERTS_THREAD_ID)
        await post.edit(applied_tags=tags, reason=f"ID: {action_id}.Post marked as needs-dev-review with /needs-dev-review")
        if alerts_thread.archived:
            await alerts_thread.edit(archived=False)
        await alerts_thread.send(content=f"ID: {action_id}\nPost: {post.mention}\nTags: {','.join([tag.name for tag in tags])}\nContext: /needs-dev-review command used")
        channel = post.guild.get_channel(NDR_CHANNEL_ID)
        await channel.send(f'A new post has been marked as "Needs dev review"\n> {post.mention}')
        await remove_post_from_pending(post.id)

    @ui.button(label="Only add tag", style=discord.ButtonStyle.grey, custom_id="ndr-only-add-tag")
    async def on_only_add_tag_click(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=False)
        await self.mark_post_as_ndr(interaction.channel)
        await interaction.channel.send(content="Post successfully marked as *needs-dev-review*.")
        await self.Interaction.delete_original_response()

    @ui.button(label="Add tag & send questions", style=discord.ButtonStyle.grey, custom_id="ndr-tag-and-questions")
    async def on_send_questions_click(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.mark_post_as_ndr(interaction.channel)
        embed = discord.Embed(
                    description=f"# Waiting for dev review\nThis post was marked as **<:sapphire_red:908755238473834536> Needs dev review** by {interaction.user.mention}\n\n### Please answer _all_ of the following questions, regardless of whether they have already been answered somewhere in this post.\n1. Which feature(s) are connected to this issue?\n2. When did this issue start to occur?\n3. What is the issue and which steps lead to it?\n4. Can this issue be reproduced by other users/in other servers?\n5. Which server IDs are related to this issue?\n6. What did you already try to fix this issue by yourself? Did it work?\n7. Does this issue need to be fixed urgently?\n\n_ _",
                    colour=0x2b2d31
                )
        embed.set_footer(text="Thank you for helping Sapphire to continuously improve.")
        await interaction.channel.send(embed=embed, view=need_dev_review_buttons())
        await self.Interaction.delete_original_response()

class utility(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        
    async def send_action_log(self, action_id: str, post_mention: str, tags: list[discord.ForumTag], context: str):
        alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
        if alerts_thread.archived:
            await alerts_thread.edit(archived=False)
        webhooks = await alerts_thread.parent.webhooks()
        webhook = webhooks[0] or await alerts_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        await webhook.send(
            content=f"ID: {action_id}\nPost: {post_mention}\nTags: {', '.join([tag.name for tag in tags])}\nContext: {context}",
            username=self.client.user.name,
            avatar_url=self.client.user.avatar.url,
            thread=discord.Object(id=ALERTS_THREAD_ID),
            wait=False
        )

    @cached()
    async def get_unsolve_id(self) -> int:
        """  
        Get the id of /unsolve command.
        This fetches the command from discord and caches the result
        """
        unsolve_id = 1281211280618950708
        for command in await self.client.tree.fetch_commands():
            if command.name == "unsolve": 
                unsolve_id=command.id
                break
            else:
                continue
        return unsolve_id
    
    @cached()
    async def get_solved_id(self):
        solved_id = 1274997472162349079
        for command in await self.client.tree.fetch_commands():
                if command.name == "solved": 
                    solved_id=command.id
                    break
                else:
                    continue
        return solved_id

    close_tasks: dict[discord.Thread, asyncio.Task] = {} # posts that are waiting to be closed with their respective asyncio.Task

    async def close_post(self, post: discord.Thread) -> None:
        """  
        Used with asyncio.create_task to close the given post after an hour of delay.
        """
        await asyncio.sleep(3600) # wait for 1 hour
        await post.edit(archived=True, reason=f"Auto archive solved post after 1 hour")
        self.close_tasks.pop(post)
        await remove_post_from_rtdr(post.id)
        await remove_post_from_pending(post.id)

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
        await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=tags, context="/solved used")
        task = asyncio.create_task(self.close_post(post=post))
        self.close_tasks[post] = task
        return task

    async def unsolve_post(self, post: discord.Thread) -> None:
        """  
        Cancel marking the given post as solved, used in /unsolve command
        """
        if post in self.close_tasks: 
            self.close_tasks[post].cancel()
            del self.close_tasks[post]
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
        await self.send_action_log(action_id=action_id, post_mention=post.mention, tags=tags, context="/unsolve used")

    @staticmethod
    async def one_of_mod_expert_op(interaction: discord.Interaction):
        """  
        Checks if the interaction user is a Moderator or Community Expert or the creator of the post\n
        --Integrated with rtdr system
        """
        if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == SUPPORT_CHANNEL_ID:
            return bool(interaction.user.get_role(EXPERTS_ROLE_ID) or interaction.user.get_role(MODERATORS_ROLE_ID)) or interaction.user == interaction.channel.owner or interaction.user.id == await get_post_creator_id(interaction.channel.id)
        else:
            return False

    @commands.Cog.listener()
    async def on_ready(self):
        self.client.add_view(need_dev_review_buttons()) # add the need dev review button/view to make it persistent (work after restart)

    @app_commands.command(name="solved", description="Mark the current post as solved")
    @app_commands.check(one_of_mod_expert_op)
    @app_commands.guild_only()
    async def solved(self, interaction: discord.Interaction):
        if NEED_DEV_REVIEW_TAG_ID not in interaction.channel._applied_tags and "forwarded" not in interaction.channel.name.casefold():
            if SOLVED_TAG_ID not in interaction.channel._applied_tags:
                await self.mark_post_as_solved(interaction.channel)
                one_hour_from_now = datetime.datetime.now() + datetime.timedelta(hours=1)
                try:
                    await interaction.response.send_message(content=f"This post was marked as solved.\n-# It will be automatically closed <t:{round(one_hour_from_now.timestamp())}:R>. Use </unsolve:{await self.get_unsolve_id()}> to cancel.")
                except discord.NotFound:
                    alerts_thread = interaction.guild.get_thread(ALERTS_THREAD_ID)
                    if alerts_thread.archived:
                        await alerts_thread.edit(archived=False)
                    await alerts_thread.send(
                        f"/solved raised NotFound <@1105414178937774150>. Created at {interaction.created_at.timestamp()} <t:{round(interaction.created_at.timestamp())}:T>, now {datetime.datetime.now().timestamp()}, <t:{round(datetime.datetime.now().timestamp())}:T>\n"
                    )
                    await interaction.channel.send(content=f"This post was marked as solved.\n-# It will be automatically closed <t:{round(one_hour_from_now.timestamp())}:R>. Use </unsolve:{await self.get_unsolve_id()}> to cancel.")
            else:
                await interaction.response.send_message(content="This post is already marked as solved.", ephemeral=True)
        else:
            button = ui.Button(label="Confirm", style=discord.ButtonStyle.green, custom_id="solved-confirm")
            async def on_confirm_button_click(Interaction: discord.Interaction):
                await self.mark_post_as_solved(interaction.channel)
                one_hour_from_now = datetime.datetime.now() + datetime.timedelta(hours=1)
                await Interaction.response.defer(ephemeral=True)
                await Interaction.delete_original_response()
                await Interaction.channel.send(content=f"This post was marked as solved.\n-# It will be automatically closed <t:{round(one_hour_from_now.timestamp())}:R>. Use </unsolve:{await self.get_unsolve_id()}> to cancel.")
            button.callback = on_confirm_button_click
            view = ui.View() # construct an empty view item
            view.add_item(button)
            await interaction.response.send_message(content="This post has the **needs-dev-review tag**, are you sure you would like to mark it as solved?", view=view, ephemeral=True)
            
    @app_commands.command(name="remove", description="Remove the given member from the current post")
    @app_commands.guild_only()
    @app_commands.describe(user="What user do you want to remove?")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def remove(self, interaction: discord.Interaction, user: discord.Member):
        if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == SUPPORT_CHANNEL_ID:
            await interaction.channel.remove_user(user)
            await interaction.response.send_message(content=f"Successfully removed {user.mention} from this post.", ephemeral=True)
            alerts_thread = self.client.get_channel(ALERTS_THREAD_ID)
            if alerts_thread.archived:
                await alerts_thread.edit(archived=False)
            await alerts_thread.send(f"{interaction.user.mention} removed {user.mention} from {interaction.channel.mention}).", allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.response.send_message(content=f"This command is only usable in a post in <#{SUPPORT_CHANNEL_ID}>")

    @app_commands.command(name="unsolve", description="Cancel the post from being closed")
    @app_commands.check(one_of_mod_expert_op)
    @app_commands.guild_only()
    async def unsolved(self, interaction: discord.Interaction):
        if interaction.channel in self.close_tasks or SOLVED_TAG_ID in interaction.channel._applied_tags:
            await self.unsolve_post(interaction.channel)
            await interaction.response.send_message(content=f"Post successfully unsolved!\nPlease send a message here explaining what you still need help with.\n-# If the post is solved you may use </solved:{await self.get_solved_id()}> to mark it as solved.")
        else:
            await interaction.response.send_message(content="This post isn't currently marked as solved...\nTry again later", ephemeral=True)

    @app_commands.command(name="needs-dev-review", description="This post needs to be reviewed by the developer")
    @app_commands.guild_only()
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, MODERATORS_ROLE_ID)
    async def need_dev_review(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == SUPPORT_CHANNEL_ID:
            if NEED_DEV_REVIEW_TAG_ID not in interaction.channel._applied_tags:
                await interaction.response.send_message(ephemeral=True, view=ndr_options_buttons(interaction), content="Select one of the options below or dismiss message to cancel.")
            else:
                await interaction.response.send_message(content="This post already has needs-dev-review tag.", ephemeral=True)
        else:
            await interaction.response.send_message(f"This command is only usable in a post in <#{SUPPORT_CHANNEL_ID}>", ephemeral=True)

    async def send_qr_log(self, message: discord.Message, user: discord.Member):
        qr_logs_thread = self.client.get_channel(QR_LOG_THREAD_ID)
        webhooks = await qr_logs_thread.parent.webhooks()
        webhook = webhooks[0] or await qr_logs_thread.parent.create_webhook(name="Created by Sapphire Helper", reason="Create a webhook for action logs, EPI logs and so on. It will be reused in the future if it wont be deleted.")
        if qr_logs_thread.archived:
            await qr_logs_thread.edit(archived=False)
        await webhook.send(
            content=f"Message deleted by {user.mention} in {message.channel.mention}\nMessage id: `{message.id}`",
            username=self.client.user.name,
            avatar_url=self.client.user.avatar.url,
            thread=discord.Object(id=QR_LOG_THREAD_ID),
            allowed_mentions=discord.AllowedMentions.none()
        )

    @commands.Cog.listener('on_reaction_add')
    async def delete_accidental_qr(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        in_support = isinstance(reaction.message.channel, discord.Thread) \
            and reaction.message.channel.parent_id == SUPPORT_CHANNEL_ID
        from_sapphire = reaction.message.author.id == 678344927997853742 # Sapphire's user id
        reaction_allowed = reaction.emoji in ["🗑️", "❌"]
        if in_support and from_sapphire and reaction_allowed:
            if user.get_role(EXPERTS_ROLE_ID):
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
                    regex = f'(Recommended|Sent) by @{user.name}'
                    footer_text = reaction.message.embeds[len(reaction.message.embeds)-1].footer.text
                    if re.match(regex, footer_text, re.IGNORECASE):
                        await reaction.message.delete()
                        await self.send_qr_log(message=reaction.message, user=user)
                        return
            if reaction.message.reference and reaction.message.reference.cached_message:
                if user == reaction.message.reference.cached_message.author:
                    await reaction.message.delete()
                    await self.send_qr_log(reaction.message, user)
                    return

    @app_commands.command(name="atbl", description="Mark the current post as 'Added to bug list'")
    @app_commands.describe(priority="The priority of this issue")
    @app_commands.checks.has_any_role(MODERATORS_ROLE_ID, EXPERTS_ROLE_ID)
    async def atbl(self, interaction: discord.Interaction, priority: Literal["Very Low", "Low", "Medium", "High", "Special Issue"]):
        if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == SUPPORT_CHANNEL_ID:
            priority_texts = {
                "very low": "We'll get to this eventually.",
                "low": "We'll take care of this when we have time and if there are no higher-priority bugs.",
                "medium": "We'll probably get to this in about 1-2 weeks, unless something more urgent comes up.",
                "high": "We'll fix this as soon as we can.",
                "special issue": "User specific issue"
            }
            embed = discord.Embed(
                title="",
                description="### The development team has added this bug to their tracking list.",
                colour=0xe88802
            )
            embed.add_field(name="Priority", value=priority, inline=False)
            if priority.casefold() != "special issue":
                embed.add_field(name="When is this issue expected to be resolved?", value=priority_texts.get(priority.casefold()), inline=False)
            await interaction.response.send_message(embed=embed)
            ndr = interaction.channel.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
            cb = interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID)
            appeal = interaction.channel.parent.get_tag(APPEAL_GG_TAG_ID)
            tags = [ndr]
            if cb in interaction.channel.applied_tags:
                tags.append(cb)
            if appeal in interaction.channel.applied_tags:
                tags.append(appeal)
            await interaction.channel.edit(name=f"[ATBL] {interaction.channel.name}", reason=f"@{interaction.user.name} used /atbl", applied_tags=tags)
        else:
            await interaction.response.send_message(content=f"This command can only be used in <#{SUPPORT_CHANNEL_ID}>!", ephemeral=True)

    @commands.hybrid_command(name="incomplete-post", description="Request more information from the post creator")
    @commands.guild_only()
    async def incomplete_post(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        if isinstance(ctx.channel, discord.Thread) and ctx.channel.parent_id == SUPPORT_CHANNEL_ID:
            user_id = await get_post_creator_id(ctx.channel.id) or ctx.channel.owner_id
            content = None
            if ctx.author.get_role(EXPERTS_ROLE_ID) or ctx.author.get_role(MODERATORS_ROLE_ID):
                content = f"<@{user_id}>"
            embed = discord.Embed(
                title="Incomplete support post",
                description="Hey, it seems like your support post is incomplete. Please make sure to provide the following information:\n\n> `-` What feature do you need help with?\n> `-` What exactly is the issue / what are you trying to do?\n> `-` What did you already try?\n> `-` Include screenshots if possible'",
                colour=0xFFA800
            )
            embed.set_footer(text=f"Recommended by @{ctx.author.name}", icon_url=ctx.author.avatar.url)
            if not ctx.interaction:
                await ctx.message.delete()
            elif ctx.interaction:
                await ctx.interaction.delete_original_response()
            await ctx.channel.send(content=content, embed=embed)
        else:
            await ctx.reply(content=f"This command can only be used in <#{SUPPORT_CHANNEL_ID}>!", ephemeral=True)

async def setup(client):
    await client.add_cog(utility(client))