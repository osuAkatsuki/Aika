import discord
from discord.ext import commands, tasks
from math import sqrt, pow
from typing import Optional
from time import time
from random import randrange
from collections import defaultdict

import utils
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
            f'UPDATE aika_users SET xp_cooldown = UNIX_TIMESTAMP() + {time} '
            'WHERE id = %s', [userID])

    async def log_deleted_message(self, userID: int, count: int = 1) -> None:
        if not await self.user_exists(userID):
            await self.create_user(userID)

        self.bot.db.execute(
            'UPDATE aika_users SET deleted_messages = deleted_messages + %s '
            'WHERE id = %s', [count, userID])

    async def increment_xp(
        self, userID: int, multiplier: float = 1.0,
        override: bool = False) -> None:
        if not await self.user_exists(userID):
            await self.create_user(userID)

        if override or await self.can_collect_xp(userID):
            xprange = [int(i * multiplier) for i in self.bot.config.xp['range']]
            await self.add_xp(userID, randrange(*xprange))

            if not override:
                await self.update_cooldown(userID)

    async def calculate_xp(self, level: float) -> int:
        return int(pow(level, 2.0) * 50)

    async def calculate_level(self, xp: int) -> float:
        return sqrt(xp / 50)

    async def get_rank(self, xp: int) -> int:
        return res['rank'] if (res := self.bot.db.fetch(
            'SELECT (COUNT(*) + 1) rank '
            'FROM aika_users WHERE xp > %s',
            [xp]
        )) else 0

    async def user_exists(self, userID: int) -> bool:
        return self.bot.db.fetch(
            'SELECT 1 FROM aika_users WHERE id = %s',
            [userID]) is not None

    async def create_user(self, userID: int) -> None:
        self.bot.db.execute(
            'INSERT IGNORE INTO aika_users (id) VALUES (%s)',
            [userID])

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
            return await ctx.send('\n'.join([
                'Invalid syntax - only one user can be fetched at a time.',
                '**Correct syntax**: `!user (optional: @user)`'
            ]))

        e = discord.Embed(
            color = self.bot.config.embed_colour
        )

        target = mentions[0] if mentions else ctx.author

        e.set_author(
            name = f'{target.display_name} ({target.name}#{target.discriminator})',
            icon_url = target.avatar_url
        )

        e.add_field(
            name = 'ID',
            value = target.id)

        xp = await self.get_xp(target.id)
        lv = await self.calculate_level(xp)
        rank = await self.get_rank(xp)

        e.add_field(
            name = 'Activity stats',
            value = f'**[#{rank}]** Lv. {lv:.2f} ({xp:,}xp)'
        )

        ordinal = lambda n: f'{n}{"tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4]}'
        format_date = lambda d: f'{d:%A, %B {ordinal(d.day)} %Y @ %I:%M:%S %p}'

        e.add_field(
            name = 'Account creation',
            value = format_date(target.created_at),
            inline = False)
        e.add_field(
            name = 'Server joined',
            value = format_date(target.joined_at),
            inline = False)

        roles = [r.mention for r in filter(lambda r: r.position != 0, target.roles)]

        if roles:
            e.add_field(
                name = 'Roles',
                value = ', '.join(reversed(roles)),
                inline = False)

        e.set_footer(text = f'Aika v{self.bot.config.version}')
        e.set_thumbnail(url = target.avatar_url)
        await ctx.send(embed = e) # TODO: cmyui.codes/u/ profiles?

    @commands.command(aliases = ['lvreq'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def levelreq(self, ctx: commands.Context, *, level) -> None:
        if not utils.isfloat(level):
            return await ctx.send(
                'Invalid syntax.\n**Correct syntax**: `!lvreq <level>`')

        xp = await self.calculate_xp(float(level))
        current_xp = await self.get_xp(ctx.author.id)
        pc = (current_xp / (current_xp + xp)) * 100 # percent there!
        await ctx.send(
            f'**XP required: {xp:,}** ({xp - current_xp:,} to go! [{pc:.2f}%]).')

    @commands.command(aliases = ['deleterboards', 'dlb'])
    @commands.guild_only()
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def deleterboard(self, ctx: commands.Context) -> None:
        if not (res := self.bot.db.fetchall(
            'SELECT id, deleted_messages FROM aika_users '
            'WHERE deleted_messages > 0 ORDER BY deleted_messages '
            'DESC LIMIT 10')
        ): return await ctx.send('Not a single soul has ever told a lie..')

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
            'SELECT id, xp FROM aika_users '
            'WHERE xp > 0 ORDER BY xp DESC LIMIT 10')
        ): return await ctx.send(
            'No users existed - now you should! (run this command again)')

        leaderboard = Leaderboard([{
            'title': user.name if (
                user := self.bot.get_user(row['id'])
                ) else '<left guild>',
            'value': f"Lv. {sqrt(row['xp'] / 50):.2f} ({row['xp']}xp)"
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
        xp = await self.get_xp(ctx.author.id)
        lv = await self.calculate_level(xp)
        await ctx.send(f'You are currently Lv. {lv:.2f} ({xp:,}xp).')

    # Voice Chat XP
    @tasks.loop(minutes = 2.5)
    async def voice_xp(self) -> None:
        await self.bot.wait_until_ready()

        is_voice = lambda c: isinstance(c, discord.VoiceChannel) \
                         and c != c.guild.afk_channel

        for channel in filter(is_voice, self.bot.get_all_channels()):
            if len(channel.voice_states) < 2: # Channel has < 2 people
                continue

            for member, state in channel.voice_states.items():
                if state.self_deaf: # Deafened gives no xp
                    continue

                multiplier = 1.0

                if state.self_video:
                    multiplier *= 2
                if state.self_stream:
                    multiplier *= 1.5
                if state.self_mute:
                    multiplier /= 2

                await self.increment_xp(member, multiplier, override = True)

def setup(bot: commands.Bot):
    bot.add_cog(User(bot))
