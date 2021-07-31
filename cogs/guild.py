# -*- coding: utf-8 -*-

import time

import discord
from discord.ext import commands

import constants
from objects.aika import Aika
from objects.aika import ContextWrap

class Guild(commands.Cog):
    def __init__(self, bot: Aika) -> None:
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def setprefix(self, ctx: ContextWrap, *, prefix) -> None:
        regex = constants.regexes['cmd_prefix']

        if not regex.match(prefix):
            return await ctx.send(
                f'Invalid prefix! Must match `{regex.pattern}`.')

        # Update in SQL.
        await self.bot.db.execute(
            'UPDATE aika_guilds '
            'SET cmd_prefix = %s'
            'WHERE guildid = %s',
            [prefix, ctx.guild.id]
        )

        # Update in cache.
        self.bot.cache['guilds'][ctx.guild.id]['cmd_prefix'] = prefix

        return await ctx.send('Successfully updated prefix!')

    async def set_moderation(self, guild: discord.Guild,
                             new: bool) -> None:
        if new:
            # We are enabling moderation! Ensure all is ready.

            # Create the muted role if it doesn't already exist.
            if not discord.utils.get(guild.roles, name='muted'):
                role = await guild.create_role(
                    name='muted',
                    color=discord.Colour(0xE73C82), # pinkish
                    reason='Aika moderation enabled.'
                )

                # Set it's permissions in each text channel.
                for chan in guild.text_channels:
                    await chan.set_permissions(role, send_messages = False)

                # TODO: perhaps mute people in voice channels as well?

        else:
            # We are disabling moderation! Remove everything.

            # Remove the muted role if it exists.
            if r := discord.utils.get(guild.roles, name='muted'):
                await r.delete(reason='Aika moderation disabled.')

        # Update in SQL.
        await self.bot.db.execute(
            'UPDATE aika_guilds '
            'SET moderation = %s '
            'WHERE guildid = %s',
            [new, guild.id]
        )

        # Update in cache.
        self.bot.cache['guilds'][guild.id]['moderation'] = new

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def moderation(self, ctx: ContextWrap) -> None:
        split = ctx.message.content.split(maxsplit=1)
        if len(split) < 2 or split[1] not in ('on', 'off'):
            return await ctx.send(
                'Invalid syntax: `!moderation <on/off>`.')

        new = split[1] == 'on'

        # check if this is already the guild's setting
        if self.bot.cache['guilds'][ctx.guild.id]['moderation'] == new:
            return await ctx.send('No changes were made.')

        try:
            await self.set_moderation(ctx.guild, new)
        except discord.errors.Forbidden as e:
            await ctx.send('Failed to enable moderation (missing permissions).')
            return

        await ctx.send(f"Moderation {'Enabled' if new else 'Disabled'}.")


    ##################
    ### Moderation ###
    ##################

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self.bot.wait_until_ready()

        guild_opts = self.bot.cache['guilds'][role.guild.id]

        if guild_opts['moderation'] and role.name == 'muted':
            # they have deleted the muted role, turn moderation
            # off since we can no longer mute people safely.
            try:
                await self.set_moderation(role.guild, False)
            except discord.errors.Forbidden as e:
                # TODO: perhaps we should inform them of the
                # failure & broken moderation setting via either
                # the guild's most active chat or the owner's dm?
                return

            # TODO: we should probably inform them either way,
            # even if the moderation option was indeed changed.
            # also people can block dms, so the # general idea
            # could also work as a fallback option. any channel
            # could i suppose with a @mention.

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def removestrike(self, ctx: ContextWrap, *,
                           strike_id: int) -> None:
        res = await self.bot.db.fetch(
            'SELECT 1 FROM aika_strikes '
            'WHERE id = %s',
            [strike_id]
        )

        if not res:
            return await ctx.send('No strike found!')

        await self.bot.db.execute(
            'DELETE FROM aika_strikes '
            'WHERE id = %s',
            [strike_id]
        )

        await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def strikes(self, ctx: ContextWrap, *,
                      member: discord.Member) -> None:
        res = await self.bot.db.fetchall(
            'SELECT id, time, reason '
            'FROM aika_strikes '
            'WHERE discordid = %s '
            'AND guildid = %s',
            [member.id, ctx.guild.id]
        )

        if not res:
            return await ctx.send("young paddawan is doing well..")

        await ctx.send(embed=discord.Embed(
            title = f"{member}'s strikes",
            description = '\n'.join(
                '[{time}] {id}. {reason}'.format(**row)
                for row in res
            )
        ))

    @commands.command(aliases=['warn'])
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def strike(self, ctx: ContextWrap) -> None:
        guild_opts = self.bot.cache['guilds'][ctx.guild.id]

        if not guild_opts['moderation']:
            return await ctx.send(
                'To use moderation, please first run `!moderation on`.')

        if not (mentions := ctx.message.mentions):
            return await ctx.send(
                'Invalid syntax: `!strike <@mentions ...>`.')

        max_strikes = guild_opts['max_strikes']
        strikes = {}

        rgx = constants.regexes['mention']

        # a little cursed but i'm sure this is fine for most situations.
        _reason = ctx.message.content[len(ctx.prefix + ctx.invoked_with) + 1:]
        reason = ' '.join(rgx.sub('', _reason).strip().split())[:256]

        for u in mentions:
            # make sure we have sufficient perms.
            if u.top_role >= ctx.author.top_role:
                continue

            await self.bot.db.execute(
                'INSERT INTO aika_strikes '
                '(discordid, guildid, reason, time) '
                'VALUES (%s, %s, %s, NOW())',
                [u.id, ctx.guild.id, reason],
            )

            nstrikes = (await self.bot.db.fetch(
                'SELECT COUNT(*) FROM aika_strikes '
                'WHERE discordid = %s AND guildid = %s',
                [u.id, ctx.guild.id], _dict=False
            ))[0]

            if nstrikes >= max_strikes:
                # the user has hit the max, and will be banned.
                strikes |= {u.name: f'{nstrikes} (banned)'}

                await u.ban(
                    reason = f'Striked above limit ({nstrikes}/{max_strikes}) [{reason}].',
                    delete_message_days = 0
                )

                # XXX: remove strikes on ban?
                # will have to think some more
                # about how i want this to work.

            else:
                strikes |= {u.name: nstrikes} # no need to cast really..

        if strikes:
            await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(mute_members=True)
    async def mute(self, ctx: ContextWrap) -> None:
        if not self.bot.cache['guilds'][ctx.guild.id]['moderation']:
            return await ctx.send(
                'To use moderation, please first run `!moderation on`.')

        # Filter mentions out of the message to isolate duration.
        msg = ctx.message.content.split(maxsplit=1)
        if len(msg) < 2:
            return await ctx.send(
                'Invalid syntax: `!mute <duration> <@mentions ...>`.')

        regexes = constants.regexes

        # Isolate duration in message.
        duration_str = regexes['mention'].sub('', msg[1]).replace(' ', '')

        # Parse duration_str into duration & period.
        re = regexes['duration'].match(duration_str)

        if not re:
            return await ctx.send('Invalid duration.')

        duration = int(re['duration'])
        period = re['period']

        # Adjust the duration for the period.
        if   period == 'm':
            duration *= 60
        elif period == 'h':
            duration *= 60 * 60
        elif period == 'd':
            duration *= 60 * 60 * 24
        elif period == 'w':
            duration *= 60 * 60 * 24 * 7

        mutes = []

        muted = discord.utils.get(ctx.guild.roles, name='muted')

        if not muted:
            return await ctx.send('Could not find the muted role!')

        for member in ctx.message.mentions:
            # We don't want to mute a user who has greater
            # permissions than us, or who is already muted.
            if member.top_role >= ctx.author.top_role or muted in member.roles:
                continue

            # Apply mute with the duration specified.
            await member.add_roles(muted)
            mutes.append(member)

            # Update the mute time into sql
            # in case we restart the bot.
            await self.bot.db.execute(
                'UPDATE aika_users SET muted_until = %s '
                'WHERE discordid = %s AND guildid = %s',
                [int(time.time() + duration), member.id, ctx.guild.id]
            )

            self.bot.loop.create_task(
                self.bot.remove_role_in(member, duration, muted))

        if not mutes:
            return await ctx.send(f'No changes were made.')

        users = ', '.join([m.mention for m in mutes])
        await ctx.send(f"Mute(s) applied to {users}.")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Guild(bot))
