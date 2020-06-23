from typing import Dict, List, Optional, Union
import discord
from discord.ext import commands, tasks

from datetime import datetime as dt, timezone as tz
from time import time

from collections import defaultdict

from Aika import Ansi
import utils

class osu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.config.server_build:
            # We only want this to run when
            # we're on the Akatsuki server.
            self.manage_roles.start()

    def cog_unload(self):
        if self.bot.config.server_build:
            self.manage_roles.cancel()

    async def get_osuID(self, discordID: int) -> Optional[int]:
        return res['osu_id'] if (res := self.bot.db.fetch(
            'SELECT osu_id FROM aika_users WHERE id = %s',
            [discordID]
        )) else None

    async def get_osuID_from_name(self, username: str) -> Optional[int]:
        return res['id'] if (res := self.bot.db.fetch(
            'SELECT id FROM users WHERE username = %s',
            [username]
        )) else None

    @commands.command()
    @commands.guild_only()
    async def recent(self, ctx: commands.Context) -> None:
        msg = ctx.message.content.split(' ')[1:] # Remove command from content
        if (rx := '-rx' in msg): # Check for and remove -rx from command
            msg.remove('-rx')

        if not msg: # Nothing specified, check for account link
            if not all(users := [await self.get_osuID(ctx.author.id)]):
                return await ctx.send(
                    'You must first link your Akatsuki account with **!linkosu**!')
        else: # They sent the user, either by mention or akatsuki username.
            if ctx.message.mentions:
                if not all(users := [await self.get_osuID(i.id) for i in ctx.message.mentions]):
                    return await ctx.send(
                        "At least one of those people don't have their Akatsuki accoutnt linked!")
            else: # Akatsuki username
                # They can only specify one name here due to limitations with spaces.
                # (not going to enforce underscores only).
                if not all(users := [await self.get_osuID_from_name(' '.join(msg))]):
                    return await ctx.send(
                        "We couldn't find a user by that username on Akatsuki.")

        if len(users) > 3:
            return await ctx.send(
                'No more than 3 users may be requested at a time!')

        for user in users:
            table = 'scores_relax' if rx else 'scores'
            if not (res := self.bot.db.fetch(
                # Get all information we need for the embed.
                'SELECT s.score, s.pp, s.accuracy acc, s.max_combo s_combo, '
                's.full_combo, s.mods, s.300_count, s.100_count, s.50_count, '
                's.misses_count, s.time, s.play_mode, s.completed, '

                'b.song_name sn, b.beatmap_id bid, b.beatmapset_id bsid, '
                'b.ar, b.od, b.max_combo as b_combo, b.hit_length, b.ranked, '
                'b.bpm, b.playcount, b.passcount, '

                # Laziness
                'b.difficulty_std, b.difficulty_taiko, '
                'b.difficulty_ctb, b.difficulty_mania, '

                'u.username, c.tag '

                f'FROM {table} s '
                'LEFT JOIN beatmaps b USING(beatmap_md5) '
                'LEFT JOIN users u ON u.id = s.userid '
                'LEFT JOIN clans c ON c.id = u.clan_id '
                'WHERE s.userid = %s '
                'ORDER BY s.time DESC LIMIT 1',
                [user])
            ): return await ctx.send('The user has no scores!.')

            e = discord.Embed(
                color = self.bot.config.embed_colour)

            name = res['username']
            if res['tag']: # add clan
                name = f"{res['tag']} {name}"

            e.set_author(
                name = name,
                icon_url = f"https://a.akatsuki.pw/{user}")

            # Letter grade
            # This is done.. stragely
            # TODO: don't do strangely?
            res['grade'] = self.bot.get_emoji(
                self.bot.config.akatsuki['grade_emojis'][
                    utils.accuracy_grade(
                        res['play_mode'], res['acc'], res['mods'],
                        res['300_count'], res['100_count'], res['50_count'],
                        res['misses_count']) if res['completed'] != 0 else 'F'
                ])

            # Mods string
            if res['mods']:
                res['mods'] = f"+{utils.mods_readable(res['mods'])}"
            else:
                res['mods'] = 'NM'

            # Difficulty for specific gamemode
            res['difficulty'] = res[f"difficulty_{utils.gamemode_db(res['play_mode'])}"]

            # Length and ranked status as formatted strings
            res['length'] = utils.seconds_readable(res['hit_length'])
            res['ranked'] = utils.status_readable(res['ranked'])

            res['points'] = f"{res['pp']:,.2f}pp" if res['pp'] else f"{res['score']:,}"

            embeds = {
                'Score information': '\n'.join([
                    '**{points} ({acc:.2f}% {s_combo}/{b_combo}x) {mods}**',
                    '{grade} {{ {300_count}x300, {100_count}x100, {50_count}x50, {misses_count}xM }}']),
                'Beatmap information': '\n'.join([
                    '**__[{sn}](https://akatsuki.pw/b/{bid})__ (__[Download](https://akatsuki.pw/d/{bsid})__)**',
                    '**{ranked} \⭐ {difficulty:.2f} | {length} @ \🎵 {bpm}**',
                    '**AR** {ar} **OD** {od}'])
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

            e.set_thumbnail(url = f"https://a.akatsuki.pw/{user}")
            e.set_image(url = f"https://assets.ppy.sh/beatmaps/{res['bsid']}/covers/cover.jpg")
            await ctx.send(embed = e)

    @commands.command()
    @commands.guild_only()
    async def linkosu(self, ctx: commands.Context) -> None:
        res = self.bot.db.fetch(
            'SELECT osu_id FROM aika_users WHERE id = %s',
            [ctx.author.id]
        )

        if not (res and res['osu_id']):
            try: # Send PM first, since if we fail we need to warn user.
                await ctx.author.send('\n'.join([
                    'Please paste the following command into #osu (or dm with Aika) ingame.',
                    f'> `!vdiscord {ctx.author.id << 2}`'
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
                f'> **https://akatsuki.pw/u/{res["osu_id"]}**'
            ]))

    @commands.command(hidden = True)
    @commands.guild_only()
    async def next_roleupdate(self, ctx: commands.Context) -> None:
        t = (self.manage_roles.next_iteration - dt.now(tz.utc)).total_seconds()
        minutes = int(t // 60)
        seconds = int(t % 60)
        await ctx.send(
            f'Next iteration in {minutes}:{seconds:02d}.')

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
