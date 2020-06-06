import discord
from discord.ext import commands, tasks
from math import log, pow
from typing import Optional
from time import time
from random import randrange

from Aika import Leaderboard
class User(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_xp.start()

    def cog_unload(self):
        self.voice_xp.stop()

    async def set_xp(self, userID: int, xp: int) -> None:
        self.bot.db.execute(
            'UPDATE aika_users SET xp = xp + %s WHERE id = %s',
            [xp, userID])

    async def add_xp(self, userID: int, xp: int) -> None:
        self.bot.db.execute(
            'UPDATE aika_users SET xp = xp + %s WHERE id = %s',
            [xp, userID])

    async def get_xp(self, userID: int) -> int:
        return res['xp'] if (
            res := self.bot.db.fetch(
                'SELECT xp FROM aika_users WHERE id = %s',
                [userID])
            ) else 0

    async def blocked_until(self, userID: int) -> bool:
        return res['cd'] if (
            res := self.bot.db.fetch(
                'SELECT xp_cooldown AS cd FROM aika_users WHERE id = %s',
                [userID]) # return true so we start the user off
            ) else True   # if they're new and don't have an acc

    async def can_collect_xp(self, userID) -> bool:
        return (await self.blocked_until(userID) - time()) <= 0

    async def update_cooldown(self, userID: int, time: int = 60) -> None:
        self.bot.db.execute(
            f'UPDATE aika_users SET xp_cooldown = UNIX_TIMESTAMP() + {time} WHERE id = %s',
            [userID])

    async def log_deleted_message(self, userID: int, count: int = 1) -> None:
        if not await self.user_exists(userID):
            await self.create_user(userID)

        self.bot.db.execute(
            'UPDATE aika_users SET deleted_messages = deleted_messages + %s WHERE id = %s',
            [count, userID]
        )

    async def increment_xp(self, userID: int, override = False) -> None:
        if not await self.user_exists(userID):
            await self.create_user(userID)

        if override or await self.can_collect_xp(userID):
            await self.add_xp(userID, randrange(**self.bot.config.xp['range']))

            if not override:
                await self.update_cooldown(userID)

    async def get_level(self, userID: int) -> float: # level is not stored in db, but constructed every time..
        return log(xp) / log(1.5) if (
            xp := await self.get_xp(userID)
        ) else 0.0

    async def user_exists(self, userID: int) -> bool:
        return bool(self.bot.db.fetch(
            'SELECT 1 FROM aika_users WHERE id = %s',
            [userID]))

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

    @commands.Cog.listener()
    async def on_message_delete(self, msg: discord.Message) -> None:
        if not await self.user_exists(msg.author.id):
            await self.create_user(msg.author.id)

        await self.log_deleted_message(msg.author.id)

    @commands.command(aliases = ['profile', 'u'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def user(self, ctx: commands.Context) -> None:
        if not await self.user_exists(ctx.author.id):
            await self.create_user(ctx.author.id)

        not_aika = lambda u: u != self.bot.user

        if len(mentions := list(filter(not_aika, ctx.message.mentions))) > 1:
            return await ctx.send(
                'Invalid syntax - only one user can be fetched at a time.\n' \
                '**Correct syntax**: `!user (optional: @user)`')

        e = discord.Embed(title = 'User stats',
                          color = self.bot.config.embed_colour)

        target = mentions[0] if mentions else ctx.author

        level = round(await self.get_level(target.id), 2)
        xp = round(await self.get_xp(target.id), 2)
        created_date = target.created_at.strftime('%b %d %Y\n%H:%M:%S')

        e.set_author(name = target.name, icon_url = target.avatar_url)
        e.add_field(name = 'Experience', value = f'```Lv: {level}\nXP: {xp}```')
        e.add_field(name = 'Account creation', value = created_date)
        e.add_field(name = 'Highest Role', value = target.top_role)
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

    @commands.command(aliases = ['deleterboards', 'dlb'])
    @commands.guild_only()
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def deleterboard(self, ctx: commands.Context) -> None:
        if not (res := self.bot.db.fetchall(
            'SELECT id, deleted_messages FROM aika_users ' \
            'WHERE deleted_messages > 0 ORDER BY deleted_messages DESC LIMIT 10')):
            return await ctx.send('Not a single soul has ever told a lie..')

        leaderboard = Leaderboard([{
            'title': user.name if (
                user := self.bot.get_user(row['id'])
                ) else '<left guild>',
            'value': row['deleted_messages']
        } for row in res])

        e = discord.Embed(
            colour = self.bot.config.embed_colour,
            title = 'Deleted message leaderboards.',
            description = repr(leaderboard))

        e.set_footer(text = f'Aika v{self.bot.config.version}')
        await ctx.send(embed = e)

    @commands.command(aliases = ['lvtop', 'xptop', 'xplb', 'lb', 'xpleaderboard'])
    @commands.guild_only()
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def leaderboard(self, ctx: commands.Context) -> None:
        if not (res := self.bot.db.fetchall(
            'SELECT id, xp FROM aika_users ' \
            'WHERE xp > 0 ORDER BY xp DESC LIMIT 10')):
            return await ctx.send(
                'No users existed - now you should! (run this command again)')

        leaderboard = Leaderboard([{
            'title': user.name if (
                user := self.bot.get_user(row['id'])
                ) else '<left guild>',
            'value': f"Lv. {log(row['xp']) / log(1.5):.2f} ({row['xp']}xp)"
        } for row in res])

        e = discord.Embed(
            title = 'XP/Level Leaderboards',
            colour = self.bot.config.embed_colour,
            description = repr(leaderboard))

        e.set_footer(text = f'Aika v{self.bot.config.version}')
        await ctx.send(embed = e)

    @commands.command(aliases = ['lv', 'getlv', 'checklv'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def level(self, ctx: commands.Context) -> None:
        await ctx.send(
            f'You are currently lv{await self.get_level(ctx.author.id):.2f} ' \
            f'({await self.get_xp(ctx.author.id):.2f} xp).')

    # Voice Chat XP
    @tasks.loop(minutes = 2.5)
    async def voice_xp(self) -> None:
        await self.bot.wait_until_ready()

        is_voice = lambda c: isinstance(c, discord.VoiceChannel)

        for channel in filter(is_voice, self.bot.get_all_channels()):
            for member in channel.members:
                if await self.can_collect_xp(member.id):
                    await self.increment_xp(member.id, override = True)

def setup(bot: commands.Bot):
    bot.add_cog(User(bot))
