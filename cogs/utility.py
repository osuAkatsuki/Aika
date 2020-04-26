import discord
from discord.ext import commands
from time import time

from objects import glob

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def format_period(seconds: int) -> str:
        days = int(seconds / 60 / 60 / 24)
        seconds %= (60 * 60 * 24)
        hours = int(seconds / 60 / 60)
        seconds %= (60 * 60)
        minutes = int(seconds / 60)
        return f'{days}d {hours}h {minutes}m {int(seconds % 60)}s'

    @commands.command(description = 'Returns the current uptime of Aika.')
    async def uptime(self, ctx: commands.Context) -> None:
        await ctx.send(f"I've been running for **{await self.format_period(time() - glob.start_time)}**.")

    @commands.is_owner()
    @commands.command(description = "Aika's power button.")
    async def shutdown(self, ctx: commands.Context) -> None:
        await ctx.send('Night night..')

        await glob.bot.close()
        glob.shutdown = True

    @commands.is_owner()
    @commands.command(description = "Lockdown commands for only the bot's owner.")
    async def lockdown(self, ctx: commands.Context) -> None:
        if len(split := ctx.message.content.split()) != 2 and (split := split[1].lower()) in ('on' 'off'):
            await ctx.send('Invalid syntax!\n> Correct syntax: `!lockdown <on/off>`.')
            return

        if split == 'on':
            await glob.bot.add_check(commands.is_owner)
            await ctx.send('Initiated.')
        else:
            await glob.bot.remove_check(commands.is_owner)
            await ctx.send('Uninitiated.')

def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))
