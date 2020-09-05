# -*- coding: utf-8 -*-

from typing import Union
import discord
from discord.ext import commands, tasks
from random import randrange
from math import sqrt
import time

from utils import try_parse_float
from objects.aika import Leaderboard, ContextWrap, Aika

class User(commands.Cog):
    def __init__(self, bot: Aika):
        self.bot = bot
        self.chatxp_cache = {}
        self.voice_xp.start()

    def cog_unload(self):
        self.voice_xp.cancel()

    async def set_xp(self, discordID: int,
                     guildID: int, xp: int) -> None:
        await self.bot.db.execute(
            'INSERT INTO aika_users (discordid, guildid, xp) '
            'VALUES (%(discord)s, %(guild)s, %(xp)s) '
            'ON DUPLICATE KEY UPDATE xp = %(xp)s',
            {'discord': discordID, 'guild': guildID, 'xp': xp}
        )

    async def add_xp(self, discordID: int,
                     guildID: int, xp: int) -> None:
        await self.bot.db.execute(
            'INSERT INTO aika_users (discordid, guildid, xp) '
            'VALUES (%(discord)s, %(guild)s, %(xp)s) '
            'ON DUPLICATE KEY UPDATE xp = xp + %(xp)s',
            {'discord': discordID, 'guild': guildID, 'xp': xp}
        )

    async def get_xp(self, discordID: int,
                     guildID: int) -> int:
        res = await self.bot.db.fetch(
            'SELECT xp FROM aika_users '
            'WHERE discordid = %s AND guildid = %s',
            [discordID, guildID]
        )

        return res['xp'] if res else 0

    # We never want our XP to be inaccurate, so we only use
    # a cache-like system for reading, and save to DB every write.

    # Also, you may notice this cooldown is global - that is intentional!
    # Aika xp is designed to be like this, it will keep the global leaderboards
    # accurate - otherwise people could spam in 5x more servers for 5x more xp :P
    async def blocked_until(self, discordID: int,
                            guildID: int) -> Union[int, bool]:
        # Check if they're in the cache.
        if (discordID, guildID) in self.chatxp_cache:
            return self.chatxp_cache[(discordID, guildID)]

        # Get from the db.
        ret = await self.bot.db.fetch(
            'SELECT last_xp FROM '
            'aika_users WHERE discordid = %s '
            'AND guildid = %s',
            [discordID, guildID]
        )

        return ret['last_xp'] if ret else True

    async def can_collect_xp(self, discordID: int,
                             guildID: int) -> bool:
        return (await self.blocked_until(discordID, guildID) - time.time()) <= 0

    async def update_cooldown(self, discordID: int, guildID: int,
                              seconds: int = 60) -> None:
        # Update the cache
        t = int(time.time() + seconds)
        self.chatxp_cache[(discordID, guildID)] = t

        # Update the db.
        await self.bot.db.execute(
            'UPDATE aika_users SET last_xp = %s '
            'WHERE discordid = %s AND guildid = %s',
            [t, discordID, guildID]
        )

    async def increment_xp(self, discordID: int, guildID: int,
                           multiplier: float = 1.0, override: bool = False) -> None:
        # Create the user if they don't already exist.
        if not await self.user_exists(discordID, guildID):
            await self.create_user(discordID, guildID)

        # Make sure the user is allowed to claim xp.
        if override or await self.can_collect_xp(discordID, guildID):
            xprange = [int(i * multiplier) for i in self.bot.config.xp['range']]
            await self.add_xp(discordID, guildID, randrange(*xprange))

            if not override:
                await self.update_cooldown(discordID, guildID)

    @staticmethod
    async def calculate_xp(level: float) -> int:
        return int((level ** 2.0) * 50.0)

    @staticmethod
    async def calculate_level(xp: int) -> float:
        return sqrt(xp / 50.0)

    async def get_rank(self, guildID: int, xp: int) -> int:
        res = await self.bot.db.fetch(
            'SELECT (COUNT(*) + 1) r FROM aika_users '
            'WHERE guildid = %s AND xp > %s',
            [guildID, xp]
        )

        return res['r'] if res else 0

    async def user_exists(self, discordID: int,
                          guildID: int) -> bool:
        return await self.bot.db.fetch(
            'SELECT 1 FROM aika_users WHERE '
            'discordid = %s AND guildid = %s',
            [discordID, guildID]
        ) is not None

    async def create_user(self, discordID: int,
                          guildID: int) -> None:
        await self.bot.db.execute(
            'INSERT IGNORE INTO aika_users '
            '(discordid, guildid) VALUES (%s, %s)',
            [discordID, guildID]
        )

    # sadly the listeners are called after the main listeners meaning there isn't really a clean
    # way to increment xp before displying their xp a user types !xp, so if they can gain xp, the
    # data will always be out of date lol..

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if not message.content or message.author.bot:
            return # Don't track xp for images & bots..

        await self.increment_xp(message.author.id, message.guild.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message,
                              after: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if not after.content or after.author.bot:
            return # Don't track xp for images & bots..

        await self.increment_xp(after.author.id, after.guild.id)

    @commands.command(aliases = ['profile', 'u'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def user(self, ctx: ContextWrap) -> None:
        if not await self.user_exists(ctx.author.id, ctx.guild.id):
            await self.create_user(ctx.author.id, ctx.guild.id)

        not_aika = lambda u: u != self.bot.user

        if len(mentions := list(filter(not_aika, ctx.message.mentions))) > 1:
            return await ctx.send('\n'.join((
                'Invalid syntax - only one user can be fetched at a time.',
                '**Correct syntax**: `!user (optional: @user)`'
            )))

        e = discord.Embed(colour = self.bot.config.embed_colour)
        target = mentions[0] if mentions else ctx.author

        e.set_author(
            name = f'{target.display_name} ({target.name}#{target.discriminator})',
            icon_url = target.avatar_url
        )

        e.add_field(name = 'ID', value = target.id)

        xp = await self.get_xp(target.id, target.guild.id)
        lv = await self.calculate_level(xp)
        rank = await self.get_rank(target.guild.id, xp)
        e.add_field(
            name = 'Activity stats',
            value = f'**[#{rank}]** Lv. {lv:.2f} ({xp:,}xp)'
        )

        ordinal = lambda n: f'{n}{"tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4]}'
        format_date = lambda d: f'{d:%A, %B {ordinal(d.day)} %Y @ %I:%M:%S %p}'

        e.add_field(
            name = 'Account creation',
            value = format_date(target.created_at),
            inline = False
        )

        e.add_field(
            name = 'Server joined',
            value = format_date(target.joined_at),
            inline = False
        )

        not_everyone = lambda r: r.position != 0
        if roles := [r.mention for r in filter(not_everyone, target.roles)]:
            e.add_field(
                name = 'Roles',
                value = ' | '.join(reversed(roles)),
                inline = False
            )

        e.set_footer(text = f'Aika v{self.bot.version}')
        e.set_thumbnail(url = target.avatar_url)
        await ctx.send(embed = e) # TODO: cmyui.codes/u/ profiles?

    @commands.command(aliases = ['lvreq'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def levelreq(self, ctx: ContextWrap, *, _lv) -> None:
        if not (level := try_parse_float(_lv)):
            return await ctx.send('\n'.join((
                'Invalid syntax.',
                '> Correct syntax: `!lvreq <level>`.'
            )))

        total_xp = await self.calculate_xp(level)
        current_xp = await self.get_xp(ctx.author.id, ctx.guild.id)
        pc = (current_xp / total_xp) * 100.0 if current_xp < total_xp else 100.0
        await ctx.send('\n'.join((
            f'**Level progression to {level:.2f}.**',
            f'> `{current_xp:,}/{total_xp:,}xp ({pc:.2f}%)`'
        )))

    # TODO: re-create global leaderboard for all servers

    @commands.command(aliases = ['aika', 'help'])
    async def botinfo(self, ctx: ContextWrap) -> None:
        e = discord.Embed(colour = self.bot.config.embed_colour)

        e.set_author(
            name = f'Aika (Aika#7862)',
            url = 'https://github.com/cmyui/Aika',
            icon_url = 'https://a.akatsuki.pw/999'
        )

        e.add_field(
            name = 'Introduction',
            value = (
                "A multipurpose Discord bot written by [cmyui](https://github.com/cmyui) "
                "for [osu!Akatsuki](https://akatsuki.pw) support, moderation, activity tracking, and other general functionality.\n\n"

                "[**Server Invitation**](https://discord.com/api/oauth2/authorize?client_id=702310727515504710&permissions=0&scope=bot)\n"
                "[Source code & Documentation](https://github.com/cmyui/Aika)\n"
                "[Support Development](https://akatsuki.pw/donate)"
            )
        )

        e.set_thumbnail(url = 'https://a.akatsuki.pw/999')
        e.set_footer(text = f'Aika v{self.bot.version}')
        await ctx.send(embed = e)

    @commands.command(aliases = ['lvtop', 'xptop', 'xplb', 'lb', 'xpleaderboard'])
    @commands.guild_only()
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def leaderboard(self, ctx: ContextWrap) -> None:
        res = await self.bot.db.fetchall(
            'SELECT discordid id, xp FROM aika_users '
            'WHERE guildid = %s AND xp > 0 '
            'ORDER BY xp DESC LIMIT 10',
            [ctx.guild.id]
        )

        if not res:
            return await self.leaderboard(ctx)

        lb = Leaderboard()

        for row in res:
            name = u.name if (u := self.bot.get_user(row['id'])) else '<left guild>'
            lb.update({name: f"Lv. {sqrt(row['xp'] / 50):.2f} ({row['xp']}xp)"})

        e = discord.Embed(
            title = 'XP/Level Leaderboards',
            colour = self.bot.config.embed_colour,
            description = repr(lb)
        )

        e.set_footer(text = f'Aika v{self.bot.version}')
        await ctx.send(embed = e)

    # Voice Chat XP
    @tasks.loop(minutes = 3.5)
    async def voice_xp(self) -> None:
        await self.bot.wait_until_ready()

        is_voice = lambda c: (
            isinstance(c, discord.VoiceChannel) and
            c != c.guild.afk_channel
        )

        for channel in filter(is_voice, self.bot.get_all_channels()):
            if len(channel.voice_states) < 2: # Channel has < 2 people
                continue

            for member, state in channel.voice_states.items():
                if state.self_deaf: # Deafened gives no xp
                    continue

                multiplier = 1.0
                if state.self_video:
                    multiplier *= 1.5
                if state.self_stream:
                    multiplier *= 1.25
                if state.self_mute:
                    multiplier /= 2

                await self.increment_xp(member, channel.guild.id,
                                        multiplier, override = True)

def setup(bot: commands.Bot):
    bot.add_cog(User(bot))
