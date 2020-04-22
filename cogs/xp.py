import discord
from discord.ext import commands
from math import log
from typing import Union
from time import time
from random import randrange

from objects import glob

class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def _set_xp(userID: int, xp: Union[int, float]) -> None:
        glob.db.execute(
            'INSERT INTO aika_xp (user, xp, last_claimed) VALUES (%s, 0, 0)' \
            'ON DUPLICATE KEY UPDATE xp = %s', [userID, xp]
        )

    @staticmethod
    async def _get_xp(userID: int) -> float:
        res = glob.db.fetch('SELECT xp FROM aika_xp WHERE user = %s', [userID])
        return res['xp'] if res and res['xp'] else 0.0

    @staticmethod # checks if the user has waited for the ratelimit
    async def _valid_claim(userID: int) -> bool:
        res = glob.db.fetch('SELECT UNIX_TIMESTAMP() - last_claimed AS t FROM aika_xp WHERE user = %s', [userID])
        return res['t'] > 60 if res and res['t'] else True # return true so we start the user off if they're new and don't have a row

    async def increment_xp(self, userID: int) -> None:
        if await self._valid_claim(userID):
            glob.db.execute( # Insert user if they don't already exist.
                'INSERT INTO aika_xp (user, xp, last_claimed) VALUES (%s, 0, UNIX_TIMESTAMP())' \
                'ON DUPLICATE KEY UPDATE xp = xp + %s, last_claimed = UNIX_TIMESTAMP()',
                [userID, randrange(2, 7)]
            )

    # TODO: level system? probably something logarithmic in relation to xp

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await glob.bot.wait_until_ready()

        if message.author.bot: return # Don't track levels for bots..
        await self.increment_xp(message.author.id)

    @commands.command(
        name = 'xp',
        description = 'Checks your XP.',
        aliases = ('getxp',' checkxp'))
    async def get_xp(self, ctx) -> None:
        await ctx.send(f'**XP**: {await self._get_xp(ctx.author.id):d}')

    @commands.command(
        name = 'lvreq',
        description = 'Checks the XP required for a specified level.',
        aliases = ['levelreq'])
    async def get_level_requirement(self, ctx) -> None:
        # TODO: check ctx
        a = ctx.message.content.split()
        await ctx.send(f'**XP Required**: {1.23 ^ int(ctx.message.content.split()[1]):.2f}') # 6553.4

def setup(bot: commands.Bot):
    bot.add_cog(XP(bot))
