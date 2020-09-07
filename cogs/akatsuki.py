# -*- coding: utf-8 -*-

# cmyui's note:
# This code is written for the use of Akatsuki specifically, you're welcome
# to use it, butplease don't expect support or really any use out of this code;
# i'm witing it for my own use case.

import asyncio
from typing import Dict, Optional, Union
import discord
from discord.ext import commands, tasks

import time
from datetime import (datetime as dt,
                      timezone as tz)

from collections import defaultdict

from objects.aika import ContextWrap, Leaderboard, Aika
from pp.owoppai import Owoppai

from constants import Ansi, Mods, regexes
from utils import (
    akatsuki_only, gamemode_readable, seconds_readable,
    accuracy_grade, calc_accuracy_std, calc_accuracy_taiko,
    mods_readable, truncate, status_readable,
    seconds_readable_full, printc
)

FAQ = Dict[str, Union[int, str]]

class Akatsuki(commands.Cog):
    def __init__(self, bot: Aika):
        self.bot = bot
        self._faq = None

        loop = asyncio.get_event_loop()
        loop.create_task(self.load_faq())

        if self.bot.config.server_build:
            # We only want this to run when
            # we're on the Akatsuki server.
            self.manage_roles.start()

    def cog_unload(self):
        if self.bot.config.server_build:
            self.manage_roles.cancel()

    #################
    ### Listeners ###
    #################

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, msg: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if not msg.content or msg.author.bot:
            return

        if msg.guild.id != self.bot.config.akatsuki['id']:
            return

        channels = self.bot.config.akatsuki['channels']

        if msg.channel.id == channels['verify'] \
        and not await self.bot.is_owner(msg.author):
            # sooo shit should be command
            if msg.content[1:] == 'verify':
                members = discord.utils.get(msg.guild.roles, name='Members')
                await msg.author.add_roles(members)

                general_chan, faq_chan, help_chan = [
                    discord.utils.get(msg.guild.text_channels, name = m)
                    for m in ('general', 'faq', 'help')
                ]

                await general_chan.send('\n'.join((
                    f'Welcome {msg.author.mention} to Akatsuki!',
                    f'If you need help, check out {faq_chan.mention}, or ask in {help_chan.mention}.'
                )))

            await msg.delete()

        elif msg.channel.id == channels['user_report']:
            if msg.role_mentions:
                try:
                    await msg.author.send('\n'.join((
                        'Your player report has not been submitted due to role mentions.',
                        'Please reformat your message without these mentions to submit a report.',
                        f'```\n{msg.clean_content}```'
                    )))
                except discord.Forbidden:
                    printc(f'Failed to DM {msg.author}.', Ansi.LIGHT_RED)
                return await msg.delete()

            admin_reports = msg.guild.get_channel(channels['admin_report'])

            e = discord.Embed(
                colour = self.bot.config.embed_colour,
                title = 'New report recieved',
                description = f'{msg.author.mention} has submitted a player report.'
            )
            e.add_field(name = 'Report content', value = msg.clean_content)
            e.set_footer(text = f'Aika v{self.bot.version}')
            await admin_reports.send(embed = e)
            await msg.delete()


    ############
    ### osu! ###
    ############

    async def get_osu(self, discordID: int) -> Optional[int]:
        return await self.bot.db.fetch(
            'SELECT a.osu_id id, u.username name, u.privileges priv '
            'FROM aika_akatsuki a LEFT JOIN users u ON u.id = a.osu_id '
            'WHERE a.discordid = %s', [discordID]
        )

    async def get_osu_from_name(self, username: str) -> Optional[int]:
        return await self.bot.db.fetch(
            'SELECT id, username name, privileges priv '
            'FROM users WHERE username = %s',
            [username]
        )

    @commands.command(aliases=['t'])
    @commands.guild_only()
    async def top(self, ctx: ContextWrap) -> None:
        msg = ctx.message.content.split(' ')[1:]

        if (rx := '-rx' in msg):
            # relax flag specified in command
            msg.remove('-rx')

        if '-gm' in msg:
            # gamemode flag specified in command

            # get index of the -gm flag, and remove it.
            idx = msg.index('-gm')
            msg.remove('-gm')

            # ensure the gm is present and is decimal
            if len(msg) < idx or not msg[idx].isdecimal():
                return await ctx.send(
                    'Invalid syntax: `!top <-gm #> <-rx> <username/@mentions ...>`.')

            # get the gm flag, make sure it's in valid range
            gm = int(msg.pop(idx))
            if gm not in range(2):
                return await ctx.send(
                    'Invalid gamemode (only osu! & osu!taiko supported).')

        else:
            # no gamemode flag specified, default to osu!standard
            gm = 0

        if not msg:
            # no mentions or username specified, check for akatsuki link
            users = [await self.get_osu(ctx.author.id)]
        else:
            # either mention or username provided
            if mentions := ctx.message.mentions:
                users = [await self.get_osu(m.id) for m in mentions]
            else:
                # XXX: while simple, this only allows a single name..
                users = [await self.get_osu_from_name(' '.join(msg))]

        if not all(users):
            return await ctx.send('Could not find all users specified.')

        # only allow bot owner to fetch restricted users
        if not all(u['priv'] & 1 for u in users) \
        and not await self.bot.is_owner(ctx.author):
            return await ctx.send('You have insufficient privileges.')

        if len(users) > 3:
            return await ctx.send(
                'No more than 3 users may be requested at a time!')

        for user in users:
            table = 'scores_relax' if rx else 'scores'
            if not (res := await self.bot.db.fetchall(' '.join((
                'SELECT s.score, s.pp, s.accuracy acc, s.max_combo s_combo,',
                's.mods, s.300_count n300, s.100_count n100,',
                's.50_count n50, s.misses_count nmiss, s.time, s.completed,',

                'b.song_name sn, b.beatmap_id bid, b.beatmapset_id bsid, b.bpm,',
                'b.ar, b.od, b.max_combo as b_combo, b.hit_length, b.ranked',

                f'FROM {table} s',
                'LEFT JOIN beatmaps b USING(beatmap_md5)',
                'WHERE s.userid = %s AND s.play_mode = %s',
                'AND b.ranked = 2 AND s.completed = 3',
                'ORDER BY s.pp DESC LIMIT 3'
                )), [user['id'], gm]
            )): return await ctx.send('The user has no scores!')

            e = discord.Embed(colour = self.bot.config.embed_colour)

            clan = await self.bot.db.fetch(
                'SELECT c.tag FROM users u '
                'LEFT JOIN clans c ON c.id = u.clan_id '
                'WHERE u.id = %s', [user['id']]
            )

            if clan and clan['tag']:
                _name = f"[{clan['tag']}] {user['name']}"
            else:
                _name = user['name']

            plural = lambda s: f"{s}'s" if s[-1] != 's' else f"{s}'"

            e.set_author(
                name = f"{plural(_name)} top 3 {gamemode_readable(gm)} plays.",
                url = f"https://akatsuki.pw/u/{user['id']}?mode={gm}&rx={int(rx)}",
                icon_url = f"https://a.akatsuki.pw/{user['id']}"
            )

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
                row['length'] = seconds_readable(row['hit_length'])
                row['ranked'] = status_readable(row['ranked'])

                # Letter grade
                # This is done.. stragely
                # TODO: don't do strangely?
                row['grade'] = self.bot.get_emoji(
                    self.bot.config.akatsuki['grade_emojis'][
                        accuracy_grade(
                            gm, row['acc'], row['mods'],
                            row['n300'], row['n100'], row['n50'],
                            row['nmiss']) if row['completed'] != 0 else 'F'
                    ])

                # Use oppai to calculate pp if FC,
                # along with star rating with mods.
                calc = Owoppai()

                # "fc" is atleast 98% of fc combo + no misses
                is_fc = (row['s_combo'] > int(row['b_combo'] * 0.98) and
                         row['nmiss'] == 0)

                if is_fc:
                    fcAcc = row['acc']
                else:
                    fcAcc = (calc_accuracy_std(
                        n300 = row['n300'],
                        n100 = row['n100'],
                        n50 = row['n50'],
                        nmiss = 0) if gm == 0 \
                    else calc_accuracy_taiko(
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
                    if not is_fc:
                        row['fcPP'] = f"\n▸ \❌**{row['nmiss']}** ({ifFc:,.2f}pp for {fcAcc:.2f}% FC)"
                        row['comboed'] = '{s_combo:,}/{b_combo:,}x'.format(**row)
                    else:
                        row['fcPP'] = ''
                        row['comboed'] = 'FC'
                else:
                    row['pp'] = f"{row['score']:,}"
                    row['fcPP'] = ''

                # Mods string
                if row['mods']:
                    row['mods'] = f"+{mods_readable(row['mods'])}"
                else:
                    row['mods'] = 'NM'

                if (r := regexes['song_name'].match(row['sn'])):
                    row['sn'] = f"{truncate(r['sn'], 35)} [{truncate(r['diff'], 25)}]"
                else:
                    return await ctx.send('<@285190493703503872> broke regex')

                row['idx'] = idx + 1

                scores.append('\n'.join((
                    '{idx}. [{sn}](https://akatsuki.pw/b/{bid})',
                    '▸ {grade} **{acc:,.2f}% {pp} {mods}**{fcPP}',
                    '▸ {{ {n100}x100, {n50}x50 }} {comboed}',
                    '▸ \⭐{difficulty:.2f} \🎵{bpm:,} \🕰️{length} **AR**{ar:.2f} **OD**{od:.2f}'
                )).format(**row))

            e.add_field(
                name = '** **', # empty title
                value = '\n'.join(scores)
            )

            e.set_footer(text = f'Aika v{self.bot.version}')
            e.set_thumbnail(url = f"https://a.akatsuki.pw/{user['id']}")
            await ctx.send(embed = e)

    @commands.command(aliases=['rc', 'rs', 'r'])
    @commands.guild_only()
    async def recent(self, ctx: ContextWrap) -> None:
        msg = ctx.message.content.split(' ')[1:]

        # check command for flags

        if (rx := '-rx' in msg):
            # relax flag specified in command
            msg.remove('-rx')

        if '-gm' in msg:
            # gamemode flag specified in command

            # get index of the -gm flag, and remove it.
            idx = msg.index('-gm')
            msg.remove('-gm')

            # ensure the gm is present and is decimal
            if len(msg) < idx or not msg[idx].isdecimal():
                return await ctx.send(
                    'Invalid syntax: `!recent <-rx> <-gm #> <username/@mentions ...>`.')

            # get the gm flag, make sure it's in valid range
            gm = int(msg.pop(idx))
            if gm not in range(2):
                return await ctx.send(
                    'Invalid gamemode (only osu! & osu!taiko supported).')

        else:
            # no gamemode flag specified, default to osu!standard
            gm = 0

        if not msg:
            # no mentions or username specified, check for akatsuki link
            users = [await self.get_osu(ctx.author.id)]
        else:
            # either mention or username provided
            if mentions := ctx.message.mentions:
                users = [await self.get_osu(m.id) for m in mentions]
            else:
                # XXX: while simple, this only allows a single name..
                users = [await self.get_osu_from_name(' '.join(msg))]

        if not all(users):
            return await ctx.send('Could not find all users specified.')

        # only allow bot owner to fetch restricted users
        if not all(u['priv'] & 1 for u in users) \
        and not await self.bot.is_owner(ctx.author):
            return await ctx.send(
                "You have insufficient privileges.")

        if len(users) > 3:
            return await ctx.send(
                'No more than 3 users may be requested at a time!')

        for user in users:
            table = 'scores_relax' if rx else 'scores'
            if not (res := await self.bot.db.fetch(' '.join((
                # Get all information we need for the embed.
                'SELECT s.score, s.pp, s.accuracy acc, s.max_combo s_combo,',
                's.mods, s.300_count n300, s.100_count n100,',
                's.50_count n50, s.misses_count nmiss, s.time, s.completed,',

                'b.song_name sn, b.beatmap_id bid, b.beatmapset_id bsid, b.bpm,',
                'b.ar, b.od, b.max_combo as b_combo, b.hit_length, b.ranked',

                f'FROM {table} s',
                'LEFT JOIN beatmaps b USING(beatmap_md5)',
                'WHERE b.ranked = 2 AND s.userid = %s',
                'AND s.play_mode = %s',
                'ORDER BY s.time DESC LIMIT 1')),
                [user['id'], gm]
            )): return await ctx.send('The user has no scores!')

            e = discord.Embed(
                title = res['sn'],
                url = f"https://akatsuki.pw/b/{res['bid']}",
                colour = self.bot.config.embed_colour
            )

            clan = await self.bot.db.fetch(
                'SELECT c.tag FROM users u '
                'LEFT JOIN clans c ON c.id = u.clan_id '
                'WHERE u.id = %s', [user['id']]
            )

            if clan and clan['tag']:
                _name = f"[{clan['tag']}] {user['name']}"
            else:
                _name = user['name']

            plural = lambda s: f"{s}'s" if s[-1] != 's' else f"{s}'"

            e.set_author(
                name = f"{plural(_name)} most recent {gamemode_readable(gm)} play.",
                url = f"https://akatsuki.pw/u/{user['id']}?mode={gm}&rx={int(rx)}",
                icon_url = f"https://a.akatsuki.pw/{user['id']}"
            )

            # Letter grade
            # This is done.. stragely
            # TODO: don't do strangely?
            res['grade'] = self.bot.get_emoji(
                self.bot.config.akatsuki['grade_emojis'][
                    accuracy_grade(
                        gm, res['acc'], res['mods'],
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
            res['length'] = seconds_readable(int(res['hit_length']))
            res['ranked'] = status_readable(res['ranked'])

            # Use oppai to calculate pp if FC,
            # along with star rating with mods.
            calc = Owoppai()

            is_fc = (res['s_combo'] > int(res['b_combo'] * 0.98) and
                     res['nmiss'] == 0)

            if is_fc:
                fcAcc = res['acc']
            else:
                fcAcc = (
                    calc_accuracy_std(
                        n300 = res['n300'],
                        n100 = res['n100'],
                        n50 = res['n50'],
                        nmiss = 0
                    ) if gm == 0 else
                    calc_accuracy_taiko(
                        n300 = res['n300'],
                        n150 = res['n100'], # lol
                        nmiss = 0
                    )
                ) * 100.0

            calc.configure(
                filename = res['bid'],
                accuracy = fcAcc,
                mode = gm,
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
                res['mods'] = f"+{mods_readable(res['mods'])}"
            else:
                res['mods'] = 'NM'

            embeds = {
                'Score information': '\n'.join((
                    '▸ {grade} **{acc:.2f}% {pp}** {mods} {s_combo:,}/{b_combo:,}x{fcPP}',
                    '▸ {{ {n100}x100, {n50}x50, {nmiss}xM }}')),
                'Beatmap information': '\n'.join((
                    '**{ranked} \⭐ {difficulty:.2f} | {length} @ \🎵 {bpm}**',
                    '**AR** {ar} **OD** {od} **[__[Download](https://akatsuki.pw/d/{bsid})__]**'))
            }

            for k, v in embeds.items():
                e.add_field(
                    name = k,
                    value = v.format(**res),
                    inline = False
                )

            # format time played for the footer
            played_at = seconds_readable_full(int(time.time() - res['time']))
            e.set_footer(text = ' | '.join([
                f'Aika v{self.bot.version}',
                f'Score submitted {played_at} ago.'
            ]))

            e.set_thumbnail(url = f"https://a.akatsuki.pw/{user['id']}")
            e.set_image(url = f"https://assets.ppy.sh/beatmaps/{res['bsid']}/covers/cover.jpg")
            await ctx.send(embed = e)

    @commands.command(aliases=['linkosu'])
    @commands.guild_only()
    async def link(self, ctx: ContextWrap) -> None:
        if user := await self.get_osu(ctx.author.id):
            return await ctx.send('\n'.join((
                'Your Discord has already been linked to an osu!Akatsuki account!',
                'If you would like to remove this, please contact cmyui#0425 directly.',
                f'> **https://akatsuki.pw/u/{user["id"]}**'
            )))

        try: # Send PM first, since if we fail we need to warn user.
            await ctx.author.send('\n'.join((
                'Please paste the following command into #osu (or dm with Aika) ingame.',
                f'> `!vdiscord {((ctx.author.id << 0o14) | 0x993) >> 1}`'
            )))
        except discord.Forbidden:
            return await ctx.send('\n'.join((
                'I was unable to DM you your code!',
                'You probably have DMs from non-friends disabled on Discord..'
            )))

        # "Unlock" the account by setting the ID to 0 instead of null
        await self.bot.db.execute(
            'INSERT INTO aika_akatsuki VALUES (%s, 0) '
            'ON DUPLICATE KEY UPDATE osu_id = 0',
            [ctx.author.id]
        )

        try: # TODO safely (i.e. not trycatch)
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        # Other bit of the process is done on osu! by the user.

    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.check(akatsuki_only)
    async def next_roleupdate(self, ctx: ContextWrap) -> None:
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
            row['id']: row['privileges'] for row in await self.bot.db.fetchall(
                'SELECT a.discordid id, u.privileges FROM aika_akatsuki a '
                'LEFT JOIN users u ON u.id = a.osu_id WHERE a.osu_id'
            )
        })

        col = Ansi.LIGHT_YELLOW

        # Remove roles
        for u in filter(lambda u: premium in u.roles, akatsuki.members):
            if not res[u.id] & (1 << 23):
                printc(f"Removing {u}'s premium.", col)
                await u.remove_roles(premium)

        for u in filter(lambda u: supporter in u.roles, akatsuki.members):
            if not res[u.id] & (1 << 2):
                printc(f"Removing {u}'s supporter.", col)
                await u.remove_roles(supporter)

        # Add roles
        no_role = lambda u: not any(r in u.roles for r in {supporter, premium})
        for u in filter(lambda u: u.id in res and no_role(u), akatsuki.members):
            if res[u.id] & (1 << 23):
                printc(f"Adding {u}'s premium.", col)
                await u.add_roles(premium)
            elif res[u.id] & (1 << 2):
                printc(f"Adding {u}'s supporter.", col)
                await u.add_roles(supporter)


    #################
    ### Reporting ###
    #################

    @commands.command()
    @commands.guild_only()
    @commands.check(akatsuki_only)
    @commands.has_permissions(manage_messages=True)
    async def reporting_embed(self, ctx: ContextWrap) -> None:
        e = discord.Embed(
            colour = self.bot.config.embed_colour,
            title = 'Welcome to the player reporting channel!',
            description = 'A place to report users who have broken the Law:tm:'
        )

        e.add_field(name = 'Information & Rules', value = '\n'.join((
            "To keep things running smoothly, we have a couple of rules.\n",
            "1. Please do not ping any staff members here, we will get to your report; no need to rush us.",
            "2. Please only submit one report - make sure you've included all information before submitting!"
        )))

        e.add_field(name = 'Report format', value = '\n'.join((
            'Please submit all reports using the following format:```',
            '<player profile url>',
            '<reason>',
            '<additional comments>```'
        )))

        e.set_footer(text = f'Aika v{self.bot.version}')
        await ctx.send(embed = e)


    ###########
    ### FAQ ###
    ###########

    async def load_faq(self) -> None:
        res = await self.bot.db.fetchall(
            'SELECT * FROM aika_faq '
            'ORDER BY id ASC'
        )

        if not res:
            raise Exception('FAQ cog enabled, but FAQ empty in database!')

        self._faq = {r['topic']: {'title': r['title'],
                                  'content': r['content']}
                     for r in res}

    async def add_faq(self, topic: str, title: str, content: str) -> None:
        if topic in self._faq:
            return

        printc(f'Adding new FAQ topic - {topic}.', Ansi.YELLOW)
        await self.bot.db.execute(
            'INSERT INTO aika_faq '
            '(id, topic, title, content) '
            'VALUES (NULL, %s, %s, %s)',
            [topic, title, content]
        )

        self._faq[topic] = {
            'title': title,
            'content': content
        }

    async def rm_faq(self, topic: str) -> None:
        if topic not in self._faq:
            return

        printc(f'Removing FAQ topic - {topic}.', Ansi.YELLOW)
        await self.bot.db.execute(
            'DELETE FROM aika_faq '
            'WHERE topic = %s',
            [topic]
        )

        del self._faq[topic]

    @commands.command()
    @commands.guild_only()
    @commands.check(akatsuki_only)
    async def faq(self, ctx: ContextWrap) -> None:
        split = ctx.message.content.split()
        topic = None

        if len(split) != 2 or len(split[1]) > 32 or split[1] not in self._faq:
            # either the size of the message is incorrect, or the topic
            # was not found in self._faq, return our available faq list.
            topics = {k: v['title'] for k, v in self._faq.items()}

            await ctx.send(embed=discord.Embed(
                title = ('Topic not found. ' if topic else '') + 'Available FAQ',
                description = (
                    'Use `!faq <topic>` with a topic below for more info.\n'
                    f'{Leaderboard(topics)!r}'
                )
            ))

        else:
            # They have requested a valid topic, send it back.
            faq = self._faq[split[1]]

            await ctx.send(embed=discord.Embed(
                title = faq['title'],
                description = faq['content']
            ))

    @commands.command(aliases=['newfaq'], hidden=True)
    @commands.guild_only()
    @commands.check(akatsuki_only)
    @commands.has_guild_permissions(ban_members = True) # somewhat arbitrary..
    async def addfaq(self, ctx: ContextWrap, *, new_faq) -> None:
        # format: topic|title|content
        if len(split := new_faq.split('|', maxsplit=3)) != 3:
            return await ctx.send('\n'.join((
                'Invalid syntax: `!addfaq <topic> | <title> | <content>`.'
            )))

        topic, title, content = [s.strip() for s in split]

        # topic cannot be an int or it will break id/topic search
        if topic.isdecimal():
            return await ctx.send(
                'Topic name cannot be a number (it may include them, but not be limited to just numbers).')

        # subtract the max amount of characters into
        # a var so we can send back the length overshot.
        if (e := len(topic) - 32) > 0:
            return await ctx.send(
                f'Your topic is {e} characters too long.')

        if (e := len(title) - 127) > 0:
            return await ctx.send(
                f'Your title is {e} characters too long.')

        if (e := len(content) - 1024) > 0:
            return await ctx.send(
                f'Your content is {e} characters too long.')

        await self.add_faq(*split)
        await ctx.send('New FAQ topic added!')

def setup(bot: commands.Bot):
    bot.add_cog(Akatsuki(bot))
