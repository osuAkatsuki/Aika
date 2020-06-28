# -*- coding: utf-8 -*-

from typing import Optional, Union
import discord
from discord.ext import commands, tasks
from math import sqrt
from time import time
from random import randrange

from utils import try_parse_float
from Aika import Leaderboard, ContextWrap

class User(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chatxp_cache = {}
        self.voice_xp.start()

    def cog_unload(self):
        self.voice_xp.cancel()

    async def set_xp(self, discordID: int, guildID: int, xp: int) -> None:
        self.bot.db.execute(
            'INSERT INTO aika_xp (discord_id, guild_id, xp) '
            'VALUES (%(discord)s, %(guild)s, %(xp)s) '
            'ON DUPLICATE KEY UPDATE xp = %(xp)s',
            {'discord': discordID, 'guild': guildID, 'xp': xp})

    async def add_xp(self, discordID: int, guildID: int, xp: int) -> None:
        self.bot.db.execute(
            'INSERT INTO aika_xp (discord_id, guild_id, xp) '
            'VALUES (%(discord)s, %(guild)s, %(xp)s) '
            'ON DUPLICATE KEY UPDATE xp = xp + %(xp)s',
            {'discord': discordID, 'guild': guildID, 'xp': xp})

    async def get_xp(self, discordID: int, guildID: int) -> int:
        return res['xp'] if (
            res := self.bot.db.fetch(
                'SELECT xp FROM aika_xp '
                'WHERE discord_id = %s AND guild_id = %s',
                [discordID, guildID])
            ) else 0

    # We never want our XP to be inaccurate, so we only use
    # a cache-like system for reading, and save to DB every write.

    # Also, you may notice this cooldown is global - that is intentional!
    # Aika xp is designed to be like this, it will keep the global leaderboards
    # accurate - otherwise people could spam in 5x more servers for 5x more xp :P
    async def blocked_until(self, discordID: int) -> Union[int, bool]:
        if not (ret := self.chatxp_cache.get(discordID)):
            return ret['cd'] if (ret := self.bot.db.fetch(
                'SELECT xp_cooldown AS cd FROM aika_users WHERE id = %s',
                [discordID] # return true so we don't start the user off
            )) else True # if they're new and don't have an account.
        return ret

    async def can_collect_xp(self, discordID: int) -> bool:
        return (await self.blocked_until(discordID) - time()) <= 0

    async def update_cooldown(self, discordID: int, seconds: int = 60) -> None:
        t = int(time() + seconds)
        self.chatxp_cache[discordID] = t
        self.bot.db.execute(
            'UPDATE aika_users SET xp_cooldown = %s '
            'WHERE id = %s', [t, discordID])

    async def log_deleted_message(self, discordID: int, count: int = 1) -> None:
        if not await self.user_exists(discordID):
            await self.create_user(discordID)

        self.bot.db.execute(
            'UPDATE aika_users SET deleted_messages = deleted_messages + %s '
            'WHERE id = %s', [count, discordID])

    async def increment_xp(
        self, discordID: int, guildID: int,
        multiplier: float = 1.0, override: bool = False
    ) -> None:
        if not await self.user_exists(discordID):
            await self.create_user(discordID)

        if override or await self.can_collect_xp(discordID):
            xprange = (int(i * multiplier) for i in self.bot.config.xp['range'])
            await self.add_xp(discordID, guildID, randrange(*xprange))

            if not override:
                await self.update_cooldown(discordID)

    async def calculate_xp(self, level: float) -> int:
        return int((level ** 2.0) * 50.0)

    async def calculate_level(self, xp: int) -> float:
        return sqrt(xp / 50)

    async def get_rank(self, guildID: int, xp: int) -> int:
        return res['r'] if (res := self.bot.db.fetch(
            'SELECT (COUNT(*) + 1) r FROM aika_xp '
            'WHERE guild_id = %s AND xp > %s',
            [guildID, xp]
        )) else 0

    async def user_exists(self, discordID: int) -> bool:
        return self.bot.db.fetch(
            'SELECT 1 FROM aika_users WHERE id = %s',
            [discordID]) is not None

    async def create_user(self, discordID: int) -> None:
        self.bot.db.execute(
            'INSERT IGNORE INTO aika_users (id) VALUES (%s)',
            [discordID])

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
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if not after.content or after.author.bot:
            return # Don't track xp for images & bots..

        await self.increment_xp(after.author.id, after.guild.id)

    @commands.Cog.listener()
    async def on_message_delete(self, msg: discord.Message) -> None:
        if not await self.user_exists(msg.author.id):
            await self.create_user(msg.author.id)

        await self.log_deleted_message(msg.author.id)

    @commands.command(aliases = ['profile', 'u'])
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.guild_only()
    async def user(self, ctx: ContextWrap) -> None:
        if not await self.user_exists(ctx.author.id):
            await self.create_user(ctx.author.id)

        not_aika = lambda u: u != self.bot.user

        if len(mentions := list(filter(not_aika, ctx.message.mentions))) > 1:
            return await ctx.send('\n'.join([
                'Invalid syntax - only one user can be fetched at a time.',
                '**Correct syntax**: `!user (optional: @user)`'
            ]))

        e = discord.Embed(colour = self.bot.config.embed_colour)
        target = mentions[0] if mentions else ctx.author

        e.set_author(
            name = f'{target.display_name} ({target.name}#{target.discriminator})',
            icon_url = target.avatar_url)
        e.add_field(
            name = 'ID',
            value = target.id)

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
            inline = False)
        e.add_field(
            name = 'Server joined',
            value = format_date(target.joined_at),
            inline = False)

        not_everyone = lambda r: r.position != 0
        if (roles := [r.mention for r in filter(not_everyone, target.roles)]):
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
    async def levelreq(self, ctx: ContextWrap, *, _lv) -> None:
        if not (level := try_parse_float(_lv)):
            return await ctx.send('\n'.join([
                'Invalid syntax.',
                '> Correct syntax: `!lvreq <level>`.'
            ]))

        total_xp = await self.calculate_xp(level)
        current_xp = await self.get_xp(ctx.author.id, ctx.guild.id)
        pc = (current_xp / total_xp) * 100.0 if current_xp < total_xp else 100.0
        await ctx.send('\n'.join([
            f'**Level progression to {level:.2f}.**',
            f'> `{current_xp:,}/{total_xp:,}xp ({pc:.2f}%)`'
        ]))

    @commands.command(aliases = ['deleterboards', 'dlb'])
    @commands.guild_only()
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def deleterboard(self, ctx: ContextWrap) -> None:
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

    # TODO: re-create global leaderboard for all servers

    @commands.command(aliases = ['aika', 'help'])
    async def botinfo(self, ctx: ContextWrap) -> None:
        e = discord.Embed(
            colour = self.bot.config.embed_colour,
        )

        e.set_author(
            name = f'Aika (Aika#7862)',
            url = 'https://github.com/cmyui/Aika',
            icon_url = 'https://a.akatsuki.pw/u/999')

        e.add_field(
            name = 'Introduction',
            value = \
                "I'm a Discord bot written by [cmyui](https://github.com/cmyui) "
                "both as an official bot for [Akatsuki](https://akatsuki.pw), and "
                "also just to be a solid general-purpose bot.\n\n"

                "I have some pretty cool features you might find cool too.. Especially "
                "if you're looking for Akatsuki commands, of course..\n\n"

                "[Read up on my commands](https://github.com/cmyui/Aika#commands)\n"
                "[Support development](https://akatsuki.pw/donate)\n"
                "[**Invite me to your server**](https://discord.com/api/oauth2/authorize?client_id=702310727515504710&permissions=0&scope=bot)\n"
        )
        e.set_thumbnail(url = 'https://cdn.discordapp.com/avatars/285190493703503872/b1503731c4cf2f173df883aa57ff45d7.webp?size=1024')
        e.set_footer(text = f'Aika v{self.bot.config.version}')
        await ctx.send(embed = e)

    @commands.command(aliases = ['lvtop', 'xptop', 'xplb', 'lb', 'xpleaderboard'])
    @commands.guild_only()
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def leaderboard(self, ctx: ContextWrap) -> None:
        if not (res := self.bot.db.fetchall(
            'SELECT discord_id id, xp FROM aika_xp '
            'WHERE guild_id = %s AND xp > 0 '
            'ORDER BY xp DESC LIMIT 10',
            [ctx.guild.id])
        ): return await self.leaderboard(ctx)

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
                if state.self_video: multiplier *= 2
                if state.self_stream: multiplier *= 1.5
                if state.self_mute: multiplier /= 2
                await self.increment_xp(member, channel.guild.id, multiplier, override = True)

def setup(bot: commands.Bot):
    bot.add_cog(User(bot))
