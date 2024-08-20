import discord
from discord.ext import commands, tasks
from variables import SUPPORT_CHANNEL_ID, SOLVED_TAG_ID, NOT_SOLVED_TAG_ID, UNANSWERED_TAG_ID, NEED_DEV_REVIEW_TAG_ID, EXPERTS_ROLE_ID, MODERATORS_ROLE_ID, CUSTOM_BRANDING_TAG_ID
from functions import AddPostToPending, RemovePostFromPending, GetPendingPosts, CheckPostLastMessageTime, CheckTimeLessDay
import random
from discord import ui

class CloseNow(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Issue already solved? Close post now", custom_id="remind-close-now", style=discord.ButtonStyle.grey)
    async def on_close_now_click(self, interaction: discord.Interaction, button: ui.Button):
        experts = interaction.guild.get_role(EXPERTS_ROLE_ID)
        mods = interaction.guild.get_role(MODERATORS_ROLE_ID)
        if experts in interaction.user.roles or mods in interaction.user.roles or interaction.user == interaction.channel.owner:
            await interaction.message.edit(view=None, content=f"{interaction.message.content}\n-# Closed by {interaction.user.name}")
            tags = [interaction.channel.parent.get_tag(SOLVED_TAG_ID)]
            if interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in interaction.channel.applied_tags:
                tags.append(interaction.channel.parent.get_tag(CUSTOM_BRANDING_TAG_ID))
            await interaction.channel.edit(applied_tags=tags)
        else:
            await interaction.response.send_message(content="Only Moderators, Community Experts and the post creator can use this.", ephemeral=True)

class remind(commands.Cog):
    def __init__(self, client):
        self.client: commands.Bot = client
        self.SendReminders.start() # start the loop
        self.ClosePendingPosts.start() # start the loop

    @commands.Cog.listener()
    async def on_ready(self):
        self.client.add_view(CloseNow())

    async def cog_unload(self):
        self.SendReminders.cancel() # cancel the loop as the cog was unloaded
        self.ClosePendingPosts.cancel() # cancel the loop as the cog was unloaded

    @tasks.loop(hours=1)
    async def SendReminders(self):
        channel = self.client.get_channel(SUPPORT_CHANNEL_ID) # get the channel
        solved_tag = channel.get_tag(SOLVED_TAG_ID)
        need_dev_review_tag = channel.get_tag(NEED_DEV_REVIEW_TAG_ID)
        for post in channel.threads: # start a loop for threads in the channel threads
            if not post.locked and not post.archived: # check if the post is not locked and not archived
                if need_dev_review_tag not in post.applied_tags and solved_tag not in post.applied_tags: # Make sure the post isn't already solved, doesn't have need dev review
                    if post.id not in GetPendingPosts(): # check if the post isn't already marked as closing pending
                        try:
                            message: discord.Message|None = await post.fetch_message(post.last_message_id) # try to fetch the message
                        except discord.NotFound: # message might be none, take care of that
                            continue # Message was most likely deleted, continue to the next iteration
                        if message.author != post.owner: # checks if the last message's author is post creator
                            if CheckTimeLessDay(time=message.created_at.replace(second=0, microsecond=0, tzinfo=None)): # checks if the time of the message is more than 24 hours ago
                                if post.owner: # make sure the post owner is in the cache
                                    greetings = ["Hi", "Hello", "Hey", "Hi there"]
                                    await message.channel.send(content=f"{random.choices(greetings)[0]} {post.owner.mention}, it seems like your last message was sent more than 24 hours ago.\nIf we don't hear back from you we'll assume the issue is resolved and mark your post as solved.", view=CloseNow())
                                    AddPostToPending(post_id=post.id, time=message.created_at.replace(second=0, microsecond=0))
                                else:
                                    continue
                            else:
                                continue # Continue to the next post as the message
                        else:
                            continue # The last message was not sent by the post creator, continue to the next post
                    else:
                        continue
                else:
                    continue
            else:
                continue
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if isinstance(message.channel, discord.Thread): # Check if the message was sent in a public thread
            if message.channel.parent.id == SUPPORT_CHANNEL_ID: # Check if the parent of the public thread is #support
                if message.channel.id in GetPendingPosts(): # Check if the specific post is marked as creator not answering
                    if message.author == message.channel.owner: # check if the author of the message is the creator of the post
                        RemovePostFromPending(message.channel.id) # remove the post from creator not answering list
                    else:
                        return # ignore as the message author isn't the post creator
                else:
                    return # ignore as the post isn't in reminder pending or closing pending lists
            else:
                return # ignore as the message's parent isn't #support
        else:
            return # ignore as the message wasn't sent in a public thread

    @tasks.loop(hours=1)
    async def ClosePendingPosts(self):
        for post_id in GetPendingPosts(): # loop through all posts that have closing pending status
            post = self.client.get_channel(post_id)
            if post:
                need_dev_review_tag = post.parent.get_tag(NEED_DEV_REVIEW_TAG_ID)
                if need_dev_review_tag not in post.applied_tags:
                    if CheckPostLastMessageTime(post_id):
                        tags = [post.parent.get_tag(SOLVED_TAG_ID)]
                        if post.parent.get_tag(CUSTOM_BRANDING_TAG_ID) in post.applied_tags:
                            tags.append(CUSTOM_BRANDING_TAG_ID)
                        await post.edit(archived=True, reason=f"post inactive for 2 days", applied_tags=tags)
                        RemovePostFromPending(post.id)
                    else:
                        continue
                else:
                    RemovePostFromPending(post_id)
                    continue
            else:
                continue
    
    @SendReminders.before_loop
    async def SendRemindersBeforeLoop(self):
        await self.client.wait_until_ready()

    @ClosePendingPosts.before_loop
    async def ClosePendingPostsBeforeLoop(self):
        await self.client.wait_until_ready()

async def setup(client):
    await client.add_cog(remind(client))