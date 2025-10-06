import discord
from discord.ext import commands
from discord import ui

class btn(ui.ActionRow):
    def __init__(self, view):
        self._view = view
        super().__init__()

    @ui.button(label="Red button", style=discord.ButtonStyle.danger)
    async def on_red_click(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("red clicked!")

class con(ui.LayoutView):
    def __init__(self):
        super().__init__()
        self.buttons = btn(self)
        self.text = ui.TextDisplay("blah blah blah")
        self.thumbnail = ui.Thumbnail(media="https://sapph.xyz/assets/branding/logo.png")
        self.section = ui.Section(self.buttons, self.text, accessory=self.thumbnail)
        container = ui.Container(self.section, self.buttons, accent_color=discord.Colour.purple())
        self.add_item(container)

class test(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @commands.command()
    async def test(self, ctx: commands.Context):
        await ctx.reply(view=con())

async def setup(client: commands.Bot):
    await client.add_cog(test(client))