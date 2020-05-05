import discord
from discord.ext import commands
from math import log, pow
from typing import Union, Optional
from time import time
from random import randrange

class User(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def set_xp(self, userID: int, xp: int) -> None:
        if not await self.user_exists(userID):
            await self.create_user(userID)

        self.bot.db.execute('UPDATE aika_users SET xp = xp + %s WHERE id = %s', [xp, userID])

    async def get_xp(self, userID: int) -> int:
        res = self.bot.db.fetch('SELECT xp FROM aika_users WHERE id = %s', [userID])
        return res['xp'] if res and res['xp'] else 0

    async def blocked_until(self, userID: int) -> bool:
        res = self.bot.db.fetch('SELECT xp_cooldown AS xp_cd FROM aika_users WHERE id = %s', [userID])
        return res['xp_cd'] if res and res['xp_cd'] else True # return true so we start the user off
                                                              # if they're new and don't have an acc

    async def increment_xp(self, userID: int) -> None:
        if not await self.user_exists(userID):
            await self.create_user(userID)

        if (await self.blocked_until(userID) - time()) <= 0:
            self.bot.db.execute(
                'UPDATE aika_users SET xp = xp + %s, xp_cooldown = UNIX_TIMESTAMP() + 60 WHERE id = %s',
                [randrange(**self.bot.config.xp['range']), userID]
            )

    async def get_level(self, userID: int) -> float: # level is not stored in db, but constructed every time..
        xp = await self.get_xp(userID)
        return log(xp) / log(1.5) if xp else 0.0

    async def user_exists(self, userID: int) -> bool:
        return bool(self.bot.db.fetch('SELECT 1 FROM aika_users WHERE id = %s', [userID]))

    async def create_user(self, userID: int) -> None:
        self.bot.db.execute('INSERT IGNORE INTO aika_users (id) VALUES (%s)', [userID])

    # sadly the listeners are called after the main listeners meaning there isn't really a clean
    # way to increment xp before displying their xp a user types !xp, so if they can gain xp, the
    # data will always be out of date lol..

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if not message.content or message.author.bot:
            return # Don't track xp for images & bots..

        await self.increment_xp(message.author.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if not after.content or after.author.bot:
            return # Don't track xp for images & bots..

        await self.increment_xp(after.author.id)

    @commands.command(aliases = ['profile'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def user(self, ctx: commands.Context) -> None:
        if not await self.user_exists(ctx.author.id):
            await self.create_user(ctx.author.id)

        if len(ctx.message.mentions) > 1:
            return await ctx.send(
                'Invalid syntax - only one user can be fetched at a time.\n' \
                '**Correct syntax**: `!user (optional: @user)`')

        e = discord.Embed(title = 'User stats', color = self.bot.config.embed_color)

        target = ctx.message.mentions[0] if ctx.message.mentions else ctx.author

        level = round(await self.get_level(target.id), 2)
        xp = round(await self.get_xp(target.id), 2)
        created_date = target.created_at.strftime('%c')

        e.set_author(name = target.name, icon_url = target.avatar_url)
        e.add_field(name = 'Level', value = level)
        e.add_field(name = 'Experience', value = xp)
        e.add_field(name = 'Account creation', value = created_date)
        e.set_footer(text = f'Aika v{self.bot.config.version}')
        await ctx.send(embed = e) # TODO: cmyui.codes/u/ profiles?

    @commands.command(aliases = ['lvreq'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def levelreq(self, ctx: commands.Context, *, level) -> None:
        if not level.isdigit():
            return await ctx.send(
                'Invalid syntax.\n**Correct syntax**: `!lvreq <level>`')

        await ctx.send(f'**XP Required**: {pow(1.5, int(level)):.2f}')

    @commands.command(aliases = ['lvtop', 'xptop', 'xplb', 'lb', 'xpleaderboard'])
    @commands.guild_only()
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def leaderboard(self, ctx: commands.Context) -> None:
        if not (res := self.bot.db.fetchall('SELECT id, xp FROM aika_users WHERE xp > 0 ORDER BY xp DESC LIMIT 5')):
            return await ctx.send(
                'No users existed - now you should! (run this command again)')

        e = discord.Embed(
            title = 'XP/Level Leaderboards',
            color = self.bot.config.embed_color)

        for i in res:
            user: Optional[discord.User] = self.bot.get_user(i['id'])
            e.add_field(
                name = user.name if user else f'Unknown (ID: {i["id"]})',
                value = f'Lv. **{log(i["xp"]) / log(1.5):.2f}** ({i["xp"]}xp)'
            )

        average = sum(i['xp'] for i in res) / len(res)
        e.add_field(
            name = 'Top-5 Average',
            value = f'Lv. **{log(average) / log(1.5):.2f}** ({average:.2f} xp)'
        )

        e.set_footer(text = f'Aika v{self.bot.config.version}')
        await ctx.send(embed = e)

    @commands.command(aliases = ['lv', 'getlv', 'checklv'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def level(self, ctx: commands.Context) -> None:
        await ctx.send(
            f'You are currently lv{await self.get_level(ctx.author.id):.2f} ' \
            f'({await self.get_xp(ctx.author.id):.2f} xp).')

def setup(bot: commands.Bot):
    bot.add_cog(User(bot))
