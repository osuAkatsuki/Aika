# -*- coding: utf-8 -*-

from typing import Dict, List, Optional, Union
import discord
from discord.ext import commands, tasks

from datetime import datetime as dt, timezone as tz
from time import time
from re import (
    compile as re_compile,
    match as re_match
)

from collections import defaultdict

from Aika import Ansi
from oppai.owoppai import Owoppai

import utils
from utils import Mods

class osu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.map_regex = re_compile( # Very very primitive regex..
            r'^(?P<artist>.+) - (?P<sn>.+)\[(?P<diff>.+)\]$')
        if self.bot.config.server_build:
            # We only want this to run when
            # we're on the Akatsuki server.
            self.manage_roles.start()

    def cog_unload(self):
        if self.bot.config.server_build:
            self.manage_roles.cancel()

    async def get_osu(self, discordID: int) -> Optional[int]:
        return res if (res := self.bot.db.fetch(
            'SELECT au.osu_id id, u.username name FROM aika_users au '
            'LEFT JOIN users u ON u.id = au.osu_id WHERE au.id = %s',
            [discordID]
        )) and res['id'] else None

    async def get_osu_from_name(self, username: str) -> Optional[int]:
        return res if (res := self.bot.db.fetch(
            'SELECT id, username name FROM users '
            'WHERE username = %s', # yes i know lol
            [username]
        )) and res['id'] else None

    @commands.command()
    @commands.guild_only()
    async def top(self, ctx: commands.Context) -> None:
        msg = ctx.message.content.split(' ')[1:] # Remove command from content
        if (rx := '-rx' in msg): # Check for and remove -rx from command
            msg.remove('-rx')

        if '-gm' in msg: # -gm <int>
            if len(msg) < (index := msg.index('-gm')) + 1 \
            or not msg[index + 1].isdecimal():
                return await ctx.send(
                    'Invalid syntax!\n> Correct syntax: `!top <-rx, -gm 2> <username/@mention>`.')

            msg.remove('-gm')
            if (gm := int(msg.pop(index))) not in range(2):
                return await ctx.send('Invalid gamemode (only osu! & osu!taiko supported).')
        else: # no -gm flag present
            gm = 0

        if not msg: # Nothing specified, check for account link
            if not all(users := [await self.get_osu(ctx.author.id)]):
                return await ctx.send(
                    'You must first link your Akatsuki account with **!linkosu**!')
        else: # They sent the user, either by mention or akatsuki username.
            if ctx.message.mentions:
                if not all(users := [await self.get_osu(i.id) for i in ctx.message.mentions]):
                    return await ctx.send(
                        "At least one of those people don't have their Akatsuki accoutnt linked!")
            else: # Akatsuki username
                # They can only specify one name here due to limitations with spaces.
                # (not going to enforce underscores only).
                if not all(users := [await self.get_osu_from_name(' '.join(msg))]):
                    ret = ["We couldn't find a user by that username on Akatsuki."]
                    if len(msg) > 1: ret.append( # Incase they're trying to..
                        'Please note that while using an Akatsuki username '
                        'as a paramter, only one user can be specified at a time.'
                    )
                    return await ctx.send('\n'.join(ret))

        if len(users) > 3:
            return await ctx.send(
                'No more than 3 users may be requested at a time!')

        for user in users:
            table = 'scores_relax' if rx else 'scores'
            if not (res := self.bot.db.fetchall(' '.join([
                'SELECT s.score, s.pp, s.accuracy acc, s.max_combo s_combo,',
                's.mods, s.300_count n300, s.100_count n100,',
                's.50_count n50, s.misses_count nmiss, s.time, s.completed,',

                'b.song_name sn, b.beatmap_id bid, b.beatmapset_id bsid, b.bpm,',
                'b.ar, b.od, b.max_combo as b_combo, b.hit_length, b.ranked',

                f'FROM {table} s',
                'LEFT JOIN beatmaps b USING(beatmap_md5)',
                'WHERE s.userid = %s AND s.play_mode = %s',
                'AND s.completed = 3',
                'ORDER BY s.pp DESC LIMIT 3'
                ]), [user['id'], gm]
            )): return await ctx.send('The user has no scores!')

            e = discord.Embed(colour = self.bot.config.embed_colour)

            clan = self.bot.db.fetch(
                'SELECT c.tag FROM users u '
                'LEFT JOIN clans c ON c.id = u.clan_id '
                'WHERE u.id = %s', [user['id']]
            )

            if clan and clan['tag']:
                _name = f"[{clan['tag']}] {user['name']}"
            else:
                _name = user['name']

            plural = lambda s: f"{s}'" if s[-1] == 's' else f"{s}'s"

            e.set_author(
                name = f"{plural(_name)} top 3 {utils.gamemode_readable(gm)} plays.",
                url = f"https://akatsuki.pw/u/{user['id']}?mode={gm}&rx={int(rx)}",
                icon_url = f"https://a.akatsuki.pw/{user['id']}")

            # Store the score embed strings as a list initially since we
            # actually want to print the whole embed in a single block.
            # We'll eventually join them all by newlines into the
            scores = []
            for idx, row in enumerate(res):
                # Iterate through scores, adding them to `scores`.
                if row['mods'] & (Mods.DOUBLETIME | Mods.NIGHTCORE):
                    row['hit_length'] = int(row['hit_length'] / 1.5)
                    row['bpm'] = int(row['bpm'] * 1.5)
                elif row['mods'] & Mods.HALFTIME:
                    row['hit_length'] = int(row['hit_length'] * 1.5)
                    row['bpm'] = int(row['bpm'] / 1.5)

                # Length and ranked status as formatted strings
                row['length'] = utils.seconds_readable(row['hit_length'])
                row['ranked'] = utils.status_readable(row['ranked'])

                # Letter grade
                # This is done.. stragely
                # TODO: don't do strangely?
                row['grade'] = self.bot.get_emoji(
                    self.bot.config.akatsuki['grade_emojis'][
                        utils.accuracy_grade(
                            gm, row['acc'], row['mods'],
                            row['n300'], row['n100'], row['n50'],
                            row['nmiss']) if row['completed'] != 0 else 'F'
                    ])

                # Use oppai to calculate pp if FC,
                # along with star rating with mods.
                calc = Owoppai()
                is_fc = row['s_combo'] == row['b_combo']

                if is_fc:
                    fcAcc = row['acc']
                else:
                    fcAcc = (utils.calc_accuracy_std(
                        n300 = row['n300'],
                        n100 = row['n100'],
                        n50 = row['n50'],
                        nmiss = 0) if gm == 0 \
                    else utils.calc_accuracy_taiko(
                        n300 = row['n300'],
                        n150 = row['n100'], # lol
                        nmiss = 0)) * 100.0

                calc.configure(
                    filename = row['bid'],
                    accuracy = fcAcc,
                    mode = gm,
                    mods = row['mods'],
                )

                ifFc, row['difficulty'] = calc.calculate_pp()

                if row['pp']:
                    row['pp'] = f"{row['pp']:,.2f}pp"

                    # If the user didn't fc, we need to print out
                    # the amount it would have been for an fc
                    # (with acc corrected for misses).
                    row['fcPP'] = f'\n▸ {ifFc:,.2f}pp for {fcAcc:.2f}% FC' if not is_fc else ''
                else:
                    row['pp'] = f"{row['score']:,}"
                    row['fcPP'] = ''

                # Mods string
                if row['mods']:
                    row['mods'] = f"+{utils.mods_readable(row['mods'])}"
                else:
                    row['mods'] = 'NM'

                if (r := re_match(self.map_regex, row['sn'])):
                    row['sn'] = f"{utils.truncate(r['sn'], 35)} [{utils.truncate(r['diff'], 25)}]"
                else:
                    return await ctx.send('<@285190493703503872> broke regex')

                row['idx'] = idx + 1

                scores.append('\n'.join([
                    '{idx}. [{sn}](https://akatsuki.pw/b/{bid})',
                    '▸ {grade} **{acc:,.2f}% {pp}** {mods}{fcPP}',
                    '▸ {{{n100}x100, {n50}x50, {nmiss}xM}} {s_combo:,}/{b_combo:,}x',
                    '▸ \⭐{difficulty:.2f} \🎵{bpm:,} \🕰️{length} AR{ar} OD{od}'
                ]).format(**row))

            e.add_field(
                name = '** **', # empty title
                value = '\n'.join(scores)
            )

            e.set_footer(text = f'Aika v{self.bot.config.version}')
            e.set_thumbnail(url = f"https://a.akatsuki.pw/{user['id']}")
            await ctx.send(embed = e)

    @commands.command()
    @commands.guild_only()
    async def recent(self, ctx: commands.Context) -> None:
        msg = ctx.message.content.split(' ')[1:] # Remove command from content
        if (rx := '-rx' in msg): # Check for and remove -rx from command
            msg.remove('-rx')

        if not msg: # Nothing specified, check for account link
            if not all(users := [await self.get_osu(ctx.author.id)]):
                return await ctx.send(
                    'You must first link your Akatsuki account with **!linkosu**!')
        else: # They sent the user, either by mention or akatsuki username.
            if ctx.message.mentions:
                if not all(users := [await self.get_osu(i.id) for i in ctx.message.mentions]):
                    return await ctx.send(
                        "At least one of those people don't have their Akatsuki accoutnt linked!")
            else: # Akatsuki username
                # They can only specify one name here due to limitations with spaces.
                # (not going to enforce underscores only).
                if not all(users := [await self.get_osu_from_name(' '.join(msg))]):
                    ret = ["We couldn't find a user by that username on Akatsuki."]
                    if len(msg) > 1: ret.append( # Incase they're trying to..
                        'Please note that while using an Akatsuki username '
                        'as a paramter, only one user can be specified at a time.'
                    )
                    return await ctx.send('\n'.join(ret))

        if len(users) > 3:
            return await ctx.send(
                'No more than 3 users may be requested at a time!')

        for user in users:
            table = 'scores_relax' if rx else 'scores'
            if not (res := self.bot.db.fetch(' '.join([
                # Get all information we need for the embed.
                'SELECT s.score, s.pp, s.accuracy acc, s.max_combo s_combo,',
                's.mods, s.300_count n300, s.100_count n100,',
                's.50_count n50, s.misses_count nmiss, s.time, s.completed,',
                's.play_mode mode,',

                'b.song_name sn, b.beatmap_id bid, b.beatmapset_id bsid, b.bpm,',
                'b.ar, b.od, b.max_combo as b_combo, b.hit_length, b.ranked',

                f'FROM {table} s',
                'LEFT JOIN beatmaps b USING(beatmap_md5)',
                'WHERE s.userid = %s',
                'ORDER BY s.time DESC LIMIT 1']),
                [user['id']]
            )): return await ctx.send('The user has no scores!')

            e = discord.Embed(
                title = res['sn'],
                url = f"https://akatsuki.pw/b/{res['bid']}",
                colour = self.bot.config.embed_colour)

            clan = self.bot.db.fetch(
                'SELECT c.tag FROM users u '
                'LEFT JOIN clans c ON c.id = u.clan_id '
                'WHERE u.id = %s', [user['id']]
            )

            if clan and clan['tag']:
                _name = f"[{clan['tag']}] {user['name']}"
            else:
                _name = user['name']

            e.set_author(
                name = _name,
                url = f"https://akatsuki.pw/u/{user['id']}?mode={res['mode']}&rx={int(rx)}",
                icon_url = f"https://a.akatsuki.pw/{user['id']}")

            # Letter grade
            # This is done.. stragely
            # TODO: don't do strangely?
            res['grade'] = self.bot.get_emoji(
                self.bot.config.akatsuki['grade_emojis'][
                    utils.accuracy_grade(
                        res['mode'], res['acc'], res['mods'],
                        res['n300'], res['n100'], res['n50'],
                        res['nmiss']) if res['completed'] != 0 else 'F'
                ])

            if res['mods'] & (Mods.DOUBLETIME | Mods.NIGHTCORE):
                res['hit_length'] = int(res['hit_length'] / 1.5)
                res['bpm'] = int(res['bpm'] * 1.5)
            elif res['mods'] & Mods.HALFTIME:
                res['hit_length'] = int(res['hit_length'] * 1.5)
                res['bpm'] = int(res['bpm'] / 1.5)

            # Length and ranked status as formatted strings
            res['length'] = utils.seconds_readable(int(res['hit_length']))
            res['ranked'] = utils.status_readable(res['ranked'])

            # Use oppai to calculate pp if FC,
            # along with star rating with mods.
            calc = Owoppai()
            is_fc = res['s_combo'] == res['b_combo']

            if is_fc:
                fcAcc = res['acc']
            else:
                fcAcc = (utils.calc_accuracy_std(
                    n300 = res['n300'],
                    n100 = res['n100'],
                    n50 = res['n50'],
                    nmiss = 0) if res['mode'] == 0 \
                else utils.calc_accuracy_taiko(
                    n300 = res['n300'],
                    n150 = res['n100'], # lol
                    nmiss = 0)) * 100.0

            calc.configure(
                filename = res['bid'],
                accuracy = fcAcc,
                mode = res['mode'],
                mods = res['mods'],
            )

            ifFc, res['difficulty'] = calc.calculate_pp()

            if res['pp']:
                res['pp'] = f"{res['pp']:,.2f}pp"

                # If the user didn't fc, we need to print out
                # the amount it would have been for an fc
                # (with acc corrected for misses).
                res['fcPP'] = f'\n▸ {ifFc:,.2f}pp for {fcAcc:.2f}% FC' if not is_fc else ''
            else:
                res['pp'] = f"{res['score']:,}"
                res['fcPP'] = ''

            # Mods string
            if res['mods']:
                res['mods'] = f"+{utils.mods_readable(res['mods'])}"
            else:
                res['mods'] = 'NM'

            embeds = {
                'Score information': '\n'.join([
                    '▸ {grade} **{acc:.2f}% {pp}** {mods} {s_combo:,}/{b_combo:,}x{fcPP}',
                    '▸ {{ {n100}x100, {n50}x50, {nmiss}xM }}']),
                'Beatmap information': '\n'.join([
                    '**{ranked} \⭐ {difficulty:.2f} | {length} @ \🎵 {bpm}**',
                    '**AR** {ar} **OD** {od} **[__[Download](https://akatsuki.pw/d/{bsid})__]**'])
            }

            for k, v in embeds.items():
                e.add_field(
                    name = k,
                    value = v.format(**res),
                    inline = False
                )

            # format time played for the footer
            played_at = utils.seconds_readable_full(int(time() - res['time']))
            e.set_footer(text = ' | '.join([
                f'Aika v{self.bot.config.version}',
                f'Score submitted {played_at} ago.'
            ]))

            e.set_thumbnail(url = f"https://a.akatsuki.pw/{user['id']}")
            e.set_image(url = f"https://assets.ppy.sh/beatmaps/{res['bsid']}/covers/cover.jpg")
            await ctx.send(embed = e)

    @commands.command()
    @commands.guild_only()
    async def linkosu(self, ctx: commands.Context) -> None:
        if not (user := await self.get_osu(ctx.author.id)):
            try: # Send PM first, since if we fail we need to warn user.
                await ctx.author.send('\n'.join([
                    'Please paste the following command into #osu (or dm with Aika) ingame.',
                    f'> `!vdiscord {((ctx.author.id << 0o14) | 0x993) >> 1}`'
                ]))
            except discord.Forbidden:
                return await ctx.send('\n'.join([
                    'I was unable to DM you your code!',
                    'You probably have DMs from non-friends disabled on Discord..'
                ]))

            # "Unlock" the account by setting the ID to 0 instead of null
            self.bot.db.execute(
                'UPDATE aika_users SET osu_id = 0 WHERE id = %s',
                [ctx.author.id])

            await ctx.message.delete()
        else:
            await ctx.send('\n'.join([
                'Your Discord has already been linked to an osu!Akatsuki account!',
                'If you would like to remove this, please contact cmyui#0425 directly.',
                f'> **https://akatsuki.pw/u/{user["id"]}**'
            ]))

    @commands.command(hidden = True)
    @commands.guild_only()
    async def next_roleupdate(self, ctx: commands.Context) -> None:
        if not (next_iteration := self.manage_roles.next_iteration):
            return await ctx.send('Role updates are currently disabled.')

        t = int((next_iteration - dt.now(tz.utc)).total_seconds())
        await ctx.send(f'Next iteration in {t // 60}:{t % 60:02d}.')

    @tasks.loop(minutes = 15)
    async def manage_roles(self) -> None:
        await self.bot.wait_until_ready()

        akatsuki = discord.utils.get(
            self.bot.guilds, id = self.bot.config.akatsuki['id'])

        premium = discord.utils.get(akatsuki.roles, name = 'Premium')
        supporter = discord.utils.get(akatsuki.roles, name = 'Supporter')

        res = defaultdict(lambda: 0, {
            row['id']: row['privileges'] for row in self.bot.db.fetchall(
                'SELECT aika_users.id, users.privileges FROM aika_users '
                'LEFT JOIN users ON users.id = aika_users.osu_id '
                'WHERE aika_users.osu_id'
            )
        })

        col = Ansi.LIGHT_YELLOW

        # Remove roles
        for u in filter(lambda u: premium in u.roles, akatsuki.members):
            if not res[u.id] & (1 << 23):
                print(f"{col!r}Removing {u}'s premium.{Ansi.RESET!r}")
                await u.remove_roles(premium)

        for u in filter(lambda u: supporter in u.roles, akatsuki.members):
            if not res[u.id] & (1 << 2):
                print(f"{col!r}Removing {u}'s supporter.{Ansi.RESET!r}")
                await u.remove_roles(supporter)

        # Add roles
        no_role = lambda u: not any(r in u.roles for r in {supporter, premium})
        for u in filter(lambda u: u.id in res and no_role(u), akatsuki.members):
            if res[u.id] & (1 << 23):
                print(f"{col!r}Adding {u}'s premium.{Ansi.RESET!r}")
                await u.add_roles(premium)
            elif res[u.id] & (1 << 2):
                print(f"{col!r}Adding {u}'s supporter.{Ansi.RESET!r}")
                await u.add_roles(supporter)

def setup(bot: commands.Bot):
    bot.add_cog(osu(bot))
