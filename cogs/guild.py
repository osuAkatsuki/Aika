# -*- coding: utf-8 -*-

import discord
from discord.ext import commands, tasks
import time

from objects.aika import Aika, ContextWrap, Leaderboard
import constants

class Guild(commands.Cog):
    def __init__(self, bot: Aika):
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
        self.bot.guild_cache[ctx.guild.id]['cmd_prefix'] = prefix

        return await ctx.send('Successfully updated prefix!')

    async def set_moderation(self, guild: discord.Guild,
                             new: bool) -> None:
        if new:
            # We are enabling moderation! Ensure all is ready.

            # Create the muted role if it doesn't already exist.
            if not discord.utils.get(guild.roles, name='muted'):
                role = await guild.create_role(
                    name = 'muted',
                    color = discord.Colour(0xE73C82), # pinkish
                    reason = 'Aika moderation enabled.'
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
            'UPDATE aika_guilds SET moderation = %s '
            'WHERE guildid = %s',
            [new, guild.id]
        )

        # Update in cache.
        self.bot.guild_cache[guild.id]['moderation'] = new

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def moderation(self, ctx: ContextWrap) -> None:
        split = ctx.message.content.split(maxsplit=1)
        if len(split) < 2 or split[1] not in ('on', 'off'):
            return await ctx.send(
                'Invalid syntax: `!moderation <on/off>`.')

        new = split[1] == 'on'
        new_str = 'Enabled' if new else 'Disabled'

        # check if this is already the guild's setting
        if self.bot.guild_cache[ctx.guild.id]['moderation'] == new:
            return 'No changes were made.'

        await self.set_moderation(ctx.guild, new)
        return await ctx.send(f'Moderation {new_str}.')


    ##################
    ### Moderation ###
    ##################

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self.bot.wait_until_ready()

        guild_opts = self.bot.guild_cache[role.guild.id]

        if guild_opts['moderation'] and role.name == 'muted':
            # they have deleted the muted role, turn moderation
            # off since we can no longer mute people safely.
            await self.set_moderation(role.guild, False)

            # TODO: get the general channel of the guild somehow?
            # i want to send a warning to the person who removed
            # the role that we've disabled moderation, and that
            # they can re-enable it if it was a mistake.. :/
            # doing by dm can work but some people will block them

    @commands.command(aliases=['warn'])
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def strike(self, ctx: ContextWrap) -> None:
        guild_opts = self.bot.guild_cache[ctx.guild.id]

        if not guild_opts['moderation']:
            return await ctx.send(
                'To use moderation, please first run `!moderation on`.')

        if not (mentions := ctx.message.mentions):
            return await ctx.send(
                'Invalid syntax: `!strike <@mentions ...>`.')

        max_strikes = guild_opts['max_strikes']
        strikes = {}

        for u in mentions:
            # Make sure we have sufficient perms.
            if u.top_role >= ctx.author.top_role:
                continue

            res = await self.bot.db.fetch(
                'SELECT strikes FROM aika_users '
                'WHERE discordid = %s AND guildid = %s',
                [u.id, ctx.guild.id], _dict=False
            )

            if res:
                # We have this user in the db.
                if (nstrikes := res[0] + 1) >= max_strikes:
                    await u.ban(
                        reason = 'Reached strike limit.',
                        delete_message_days = 0
                    )

                await self.bot.db.execute(
                    'UPDATE aika_users SET strikes = strikes + 1 '
                    'WHERE discordid = %s AND guildid = %s',
                    [u.id, ctx.guild.id]
                )

            else:
                # This is the user's first interaction.
                # This will probably never really happen?
                # Why would you get striked without having
                # claimed xp..? Either way.. here it is.
                await self.bot.db.execute(
                    'INSERT INTO aika_users '
                    '(discordid, guildid, strikes) '
                    'VALUES (%s, %s, 1)'
                )

                nstrikes = 1

            if nstrikes >= max_strikes:
                strikes.update({u.name: f'{nstrikes} (banned)'})
            else:
                strikes.update({u.name: nstrikes}) # no need to cast really..

        if not strikes:
            return await ctx.send('No changes were made.')

        # Construct a response containing the user's new statuses.
        e = discord.Embed(
            colour = self.bot.config.embed_colour,
            title = 'Strikes applied successfully',
            description = ('The results can be seen below.\n'
                          f'{Leaderboard(strikes)!r}')
        )

        e.set_footer(text = (
            f'Reaching {max_strikes} strikes will result in a ban!\n'
            f'Aika v{self.bot.version}'
        ))
        await ctx.send(embed=e)

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(mute_members=True)
    async def mute(self, ctx: ContextWrap) -> None:
        if not self.bot.guild_cache[ctx.guild.id]['moderation']:
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
        if   period == 'm': duration *= 60
        elif period == 'h': duration *= 60 * 60
        elif period == 'd': duration *= 60 * 60 * 24
        elif period == 'w': duration *= 60 * 60 * 24 * 7

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


def setup(bot: commands.Bot):
    bot.add_cog(Guild(bot))
