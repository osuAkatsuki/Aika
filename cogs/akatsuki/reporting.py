import discord
from discord.ext import commands

from Aika import Ansi

class Reporting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, msg: discord.Message) -> None:
        if msg.channel.id != self.bot.config.akatsuki['channels']['user_report'] or msg.author.bot:
            return

        if msg.role_mentions:
            try:
                await msg.author.send('\n'.join([
                    'Your player report has not been submitted due to role mentions.',
                    'Please reformat your message without these mentions to submit a report.',
                    f'```\n{msg.clean_content}```'
                ]))
            except discord.Forbidden:
                print(f'{Ansi.LIGHT_RED!r}Failed to DM {msg.author}.{Ansi.RESET!r}')
            return await msg.delete()

        admin_reports = msg.guild.get_channel(
            self.bot.config.akatsuki['channels']['admin_report'])

        e = discord.Embed(
            colour = self.bot.config.embed_colour,
            title = 'New report recieved',
            description = f'{msg.author.mention} has submitted a player report.'
        )
        e.add_field(name = 'Report content', value = msg.clean_content)
        e.set_footer(text = f'Aika v{self.bot.config.version}')
        await admin_reports.send(embed = e)
        await msg.delete()

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_messages = True)
    async def reporting_embed(self, ctx: commands.Context) -> None:
        e = discord.Embed(
            colour = self.bot.config.embed_colour,
            title = 'Welcome to the player reporting channel!',
            description = 'A place to report users who have broken the Law:tm:'
        )

        e.add_field(name = 'Information & Rules', value = '\n'.join([
            "To keep things running smoothly, we have a couple of rules.\n",
            "1. Please do not ping any staff members here, we will get to your report; no need to rush us.",
            "2. Please only submit one report - make sure you've included all information before submitting!"
        ]))

        e.add_field(name = 'Report format', value = '\n'.join([
            'Please submit all reports using the following format:```',
            '<player profile url>',
            '<reason>',
            '<additional comments>```'
        ]))

        e.set_footer(text = f'Aika v{self.bot.config.version}')
        await self.bot.send(ctx, embed = e)

def setup(bot: commands.Bot):
    bot.add_cog(Reporting(bot))
