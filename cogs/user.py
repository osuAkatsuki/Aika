import discord
from discord.ext import commands
from math import log, pow
from typing import Union
from time import time
from random import randrange

from objects import glob

class User(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def _set_xp(userID: int, xp: int) -> None:
        glob.db.execute(
            'INSERT INTO aika_users (id) VALUES (%s)' \
            'ON DUPLICATE KEY UPDATE xp = %s,' \
            'xp_cooldown = UNIX_TIMESTAMP()', [userID, xp]
        )

    @staticmethod
    def _get_xp(userID: int) -> int:
        res = glob.db.fetch('SELECT xp FROM aika_users WHERE id = %s', [userID])
        return res['xp'] if res and res['xp'] else 0.0

    @staticmethod # checks if the user has waited for the ratelimit
    def _blocked_until(userID: int) -> bool:
        res = glob.db.fetch('SELECT xp_cooldown AS xp_cd FROM aika_users WHERE id = %s', [userID])
        return res['xp_cd'] if res and res['xp_cd'] else True # return true so we start the user off
                                                              # if they're new and don't have an acc

    def increment_xp(self, userID: int) -> None:
        if (self._blocked_until(userID) - time()) <= 0:
            glob.db.execute( # Insert user if they don't already exist.
                'INSERT INTO aika_users (id) VALUES (%s)' \
                'ON DUPLICATE KEY UPDATE xp = xp + %s,' \
                'xp_cooldown = UNIX_TIMESTAMP() + %s',
                [
                    userID,
                    randrange(glob.config['xp']['min_gain'],
                              glob.config['xp']['max_gain']),
                    glob.config['xp']['ratelimit']
                ]
            )

    # TODO: level system? probably something logarithmic in relation to xp

    def _get_level(self, userID: int) -> float: # level is not stored in db, but constructed every time..
        xp: int = self._get_xp(userID)
        return log(xp) / log(1.5) if xp else 0.0

    # sadly the listeners are called after the main listeners meaning there isn't really a clean
    # way to increment xp before displying their xp a user types !xp, so if they can gain xp, the
    # data will always be out of date lol..

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if not message.content or message.author.bot:
            return # Don't track xp for images & bots..

        self.increment_xp(message.author.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if not after.content or after.author.bot:
            return # Don't track xp for images & bots..

        self.increment_xp(after.author.id)

    @commands.cooldown(
        glob.config['cooldowns']['default_user_count'],
        glob.config['cooldowns']['default_user_per'],
        commands.BucketType.user)
    @commands.command(
        description = 'Display your profile.',
        aliases     = ['profile'])
    async def user(self, ctx: commands.Context) -> None:
        embed = discord.Embed(title = 'User stats')
        embed.set_author(name = ctx.author.name, icon_url = ctx.author.avatar_url)
        embed.add_field(name = 'Level', value = round(self._get_level(ctx.author.id), 2))
        embed.add_field(name = 'Experience', value = round(self._get_xp(ctx.author.id), 2))
        embed.add_field(name = 'Account creation', value = ctx.author.created_at)
        embed.set_footer(text = f'Aika v{glob.version}')
        await ctx.send(embed = embed) # TODO: cmyui.codes/u/ profiles?

    @commands.cooldown(
        glob.config['cooldowns']['default_user_count'],
        glob.config['cooldowns']['default_user_per'],
        commands.BucketType.user)
    @commands.command(
        description = 'Checks the XP required for a specified level.',
        aliases     = ['lvreq'])
    async def levelreq(self, ctx: commands.Context) -> None:
        # TODO: check ctx
        await ctx.send(f'**XP Required**: {pow(1.5, int(ctx.message.content.split(maxsplit=1)[1])):.2f}')
    # TODO: !user help for all cmds

    @commands.cooldown(
        glob.config['cooldowns']['default_user_count'],
        glob.config['cooldowns']['default_user_per'],
        commands.BucketType.user)
    @commands.command(
        description = 'Checks your level & experience.',
        aliases     = ['getlv', 'checklv'])
    async def level(self, ctx: commands.Context) -> None:
        await ctx.send(f'You are currently lv{self._get_level(ctx.author.id):.2f} ({self._get_xp(ctx.author.id):.2f} xp).')

def setup(bot: commands.Bot):
    bot.add_cog(User(bot))
