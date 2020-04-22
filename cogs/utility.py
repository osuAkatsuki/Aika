import discord
from discord.ext import commands
from time import time

from objects import glob

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def format_period(seconds: int) -> str:
        days = int(seconds / 60 / 60 / 24)
        seconds %= (60 * 60 * 24)
        hours = int(seconds / 60 / 60)
        seconds %= (60 * 60)
        minutes = int(seconds / 60)
        return f'{days}d {hours}h {minutes}m'

    @commands.command(
        name = 'uptime',
        description = 'Returns the current uptime of Aika.')
    async def uptime(self, ctx) -> None:
        await ctx.send(f'Aika has been running for {self.format_period(time() - glob.start_time)}.')

def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))
