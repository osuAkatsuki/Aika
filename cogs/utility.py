# -*- coding: utf-8 -*-

from typing import List, Dict
import discord
from discord.ext import commands
from time import time

from Aika import ContextWrap

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def format_period(seconds: int) -> str:
        r: List[str] = []

        if (days := int(seconds / 60 / 60 / 24)):
            r.append(f'{days}d')
        seconds %= (60 * 60 * 24)

        if (hours := int(seconds / 60 / 60)):
            r.append(f'{hours}h')
        seconds %= (60 * 60)

        if (minutes := int(seconds / 60)):
            r.append(f'{minutes}m')
        seconds %= 60

        r.append(f'{seconds:.2f}s')
        return ' '.join(r)

    @commands.command()
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def uptime(self, ctx: ContextWrap) -> None:
        uptime = await self.format_period(time() - self.bot.uptime)
        await ctx.send(f"I've been running for **{uptime}**.")

    @commands.command(hidden = True)
    @commands.is_owner()
    async def shutdown(self, ctx: ContextWrap) -> None:
        await ctx.send('Night night..')
        await self.bot.close()

    # TODO: prune_user() or combine logic for a specific user wipe into prune()

    @commands.command(hidden = True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages = True)
    async def prune(self, ctx: ContextWrap, *, count) -> None:
        if not count.isdecimal() or (count := int(count)) > 1000:
            return await ctx.send('\n'.join([
                'Invalid syntax.',
                '**Correct syntax**: `!prune <count (max 1000)>`.'
            ]))

        await ctx.message.delete()
        await ctx.channel.purge(limit = count)

def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))
