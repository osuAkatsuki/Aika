# -*- coding: utf-8 -*-

import asyncio
from collections import defaultdict
from typing import Union, Optional, Dict, Any
import cmyui
import discord
import aiohttp
from math import sqrt
from discord.ext import commands, tasks
from datetime import (datetime as dt,
                      timezone as tz)
import traceback
import time
import orjson

from constants import Ansi
from mysql.connector import errorcode, Error as SQLError
from utils import printc, asciify, truncate

__all__ = (
    'Leaderboard',
    'ContextWrap',
    'Aika'
)

class Leaderboard:
    """A simple class to create simple readable key: value pair
    leaderboards which can be pretty-printed for output in Discord.
    """
    __slots__ = ('data', 'max_keylen')

    def __init__(self, data = {}, max_keylen: int = 0) -> None:
        self.data = data
        self.max_keylen = max_keylen

    def update(self, d) -> None:
        self.data.update(d)

    def __repr__(self) -> str:
        # Maximum lenth of an ID as a string.
        # Only needs to work for 1-2, so optimized.
        idx_maxlen = 2 if len(self.data) > 9 else 1

        # Maximum length of a key.
        if self.max_keylen:
            # Make sure the length does not exceed `self.max_keylen` chars
            keylen = min(self.max_keylen, max(len(k) for k in self.data))
        else:
            # Keys can be of any length.
            keylen = max(len(k) for k in self.data)

        # Generate the lines of our leaderboard.
        lines = []

        for idx, (k, v) in enumerate(self.data.items()):
            # Truncate key if max length is specified.
            if keylen:
                k = truncate(k, keylen)

            lines.append(
                '{i:0>{ilen}}. {k:^{klen}} - {v}'.format(
                i = idx + 1, k = asciify(k), v = v,
                ilen = idx_maxlen, klen = keylen
            ))

        # Put the leaderboard all together,
        # and display it with markdown syntax.
        return '```md\n{}```'.format('\n'.join(lines))

# Light wrapper around commands.Context to allow for one of Aika's
# special features: the ability to edit previous messages to edit
# Aika's response (and specifically for Aika to be able to edit
# their previous) response rather than just creating a new one.
# With: ctx.send(...) // Without: self.bot.send(ctx, ...)
class ContextWrap(commands.Context):
    async def send(self, *args, **kwargs) -> Optional[discord.Message]:
        # Allows for the syntax `ctx.send('content')`
        if len(args) == 1 and isinstance(args[0], str):
            kwargs['content'] = args[0]

        # Clear previous msg params.
        kwargs['embed'] = kwargs.pop('embed', None)
        kwargs['content'] = kwargs.pop('content', None)

        cached = self.bot.cache['responses'][self.message.id]

        if cached and (time.time() - cached['timeout']) <= 0:
            # We have cache and it's not expired.
            msg = cached['resp']
            await msg.edit(**kwargs)
        else: # We either have no cached val, or it's expired.
            msg = await super().send(**kwargs)

            self.bot.cache['responses'][self.message.id] = {
                'resp': msg,
                'timeout': int(time.time()) + 300 # 5 min
            }

        return msg

class Aika(commands.Bot):
    __slots__ = ('db', 'http', 'cache', 'version')

    def __init__(self) -> None:
        super().__init__(
            owner_id = self.config.discord_owner,
            command_prefix = self.when_mentioned_or_prefix(),
            help_command = None
        )

        self.db: Optional[cmyui.AsyncSQLPool] = None
        self.http_sess: Optional[aiohttp.ClientSession] = None

        # Various types of cache
        # for different applications.
        self.cache = {
            # whenever aika replies to a command, cache
            # {msgid: {'timeout': sent+5min, 'msg': resp}}
            'responses': defaultdict(lambda: None),
            # keep all data from aika_guilds cached from startup
            'guilds': {}, # {guildid: {guild_info ...}, ...}
            # keep all chatxp wait times in cache.
            'chatxp': {} # {(discordid, guildid): timeout, ...}
        }

        self.version = cmyui.Version(1, 1, 4)

    def when_mentioned_or_prefix(self):
        def inner(bot, msg):
            prefix = self.cache['guilds'][msg.guild.id]['cmd_prefix']
            return commands.when_mentioned_or(prefix)(bot, msg)

        return inner

    #########
    # MySQL #
    #########

    async def connect_db(self) -> None:
        try:
            self.db = cmyui.AsyncSQLPool()
            await self.db.connect(**self.config.mysql)
        except SQLError as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                raise Exception('SQLError: Incorrect username/password.')
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                raise Exception('SQLError: Database does not exist')
            else:
                raise Exception(err)
        else:
            print('Successfully connected to SQL')

    ##########
    # Events #
    ##########

    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.wait_until_ready()

        # Insert into database.
        await self.db.execute(
            'INSERT INTO aika_servers '
            '(guildid) VALUES (%s)',
            [guild.id]
        )

        res = await self.db.fetch(
            'SELECT * FROM aika_guilds '
            'WHERE guildid = %s',
            [guild.id]
        )

        # Add to cache.
        self.cache['guilds'][guild.id] = {
            k: res[k] for k in set(res) - {'guildid'}
        }

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.wait_until_ready()

        # Delete from database.
        # TODO: maybe don't..? needs more consideration
        await self.db.execute(
            'DELETE FROM aika_servers '
            'WHERE guildid = %s',
            [guild.id]
        )

        # Remove from cache.
        del self.cache['guilds'][guild.id]

    async def on_message(self, msg: discord.Message) -> None:
        await self.wait_until_ready()
        if not msg.content or msg.author.bot:
            return

        filtered = (msg.guild.id == self.config.akatsuki['id'] and
                    await self.filter_content(msg.content.lower()))

        colour = (Ansi.LIGHT_MAGENTA if msg.author.bot else
                  Ansi.LIGHT_RED if filtered else
                  Ansi.LIGHT_CYAN)

        await self.print_console(msg, colour)

        if filtered:
            return await msg.delete()

        if self.config.server_build \
        or await self.is_owner(msg.author):
            await self.process_commands(msg)

    async def on_message_edit(self, before: discord.Message,
                              after: discord.Message) -> None:
        await self.wait_until_ready()

        if not after.content or after.author.bot \
        or before.content == after.content:
            return

        filtered = (after.guild.id == self.config.akatsuki['id'] and
                    await self.filter_content(after.content.lower()))

        colour = Ansi.LIGHT_RED if filtered else Ansi.LIGHT_YELLOW
        await self.print_console(after, colour)

        if filtered:
            return await after.delete()

        if self.config.server_build \
        or await self.is_owner(after.author):
            await self.process_commands(after)

    async def on_message_delete(self, msg: discord.Message) -> None:
        # Whenever a message is deleted, check if it was in
        # our cache, and delete it (so they don't accumulate).
        cached = self.cache['responses'][msg.id]

        if cached:
            try:
                await cached['resp'].delete()
            except discord.NotFound: # No 403 since it's our own message.
                pass # Response has already been deleted.

            del self.cache['responses'][msg.id]

    async def on_member_ban(self, guild: discord.Guild,
                            user: Union[discord.Member, discord.User]) -> None:
        printc(f'{user} was banned from {guild}.', Ansi.GREEN)

    async def on_ready(self) -> None:
        # TODO: maybe use datetime module rather than this w/ formatting?
        if not hasattr(self, 'uptime'):
            self.uptime = time.time()

        """ load all pending mutes from sql into tasks """

        res = await self.db.fetchall(
            'SELECT discordid, guildid, muted_until '
            'FROM aika_users WHERE muted_until != 0'
        )

        async def reset_mute(discordid: int, guildid: int) -> None:
            await self.db.execute(
                'UPDATE aika_users SET muted_until = 0 '
                'WHERE discordid = %s and guildid = %s',
                [discordid, guildid]
            )

        for row in res:
            # get the guild
            if not (g := self.get_guild(row['guildid'])):
                await reset_mute(row['discordid'], row['guildid'])
                continue

            # get the member
            if not (m := g.get_member(row['discordid'])):
                await reset_mute(row['discordid'], row['guildid'])
                continue

            # get the muted role
            if not (r := discord.utils.get(g.roles, name='muted')):
                await reset_mute(row['discordid'], row['guildid'])
                continue

            duration = max(0, time.time() - row['muted_until'])

            # Enqueue the task to remove their mute when complete.
            self.loop.create_task(self.remove_role_in(m, duration, r))

        print('{col}Ready{reset}: {user} ({userid})'.format(
              col = repr(Ansi.GREEN), reset = repr(Ansi.RESET),
              user = self.user, userid = self.user.id))

    async def on_error(self, event, args, **kwargs) -> None:
        if event != 'on_message':
            print(f'{Ansi.LIGHT_RED!r}ERR{Ansi.RESET!r}: {event}')

    async def on_command_error(self, ctx: ContextWrap,
                               error: commands.errors.CommandError) -> None:
        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (commands.CommandNotFound,
                   commands.UserInputError,
                   commands.NotOwner)

        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(f'{ctx.command} is currently disabled.')

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(f'{ctx.command} can only be used in guilds.')
            except:
                pass

        elif isinstance(error, commands.CommandOnCooldown):
            return await ctx.send('{u} that commands is still on cooldown ({t:.1f}s)'.format(
                u = ctx.author.mention, t = error.retry_after))

        elif isinstance(error, commands.BotMissingPermissions):
            return await ctx.send('I have insufficient guild permissions to perform that command.')

        elif isinstance(error, commands.MissingPermissions):
            return await ctx.send('You have insufficient guild permissions to perform that command.')

        elif isinstance(error, commands.CheckFailure):
            return # Someone tried using an akatsuki-limited command outside.

        print(f'Ignoring exception in command {ctx.command}')
        traceback.print_exception(type(error), error, error.__traceback__)

    ########
    # Misc #
    ########

    async def process_commands(self, message):
        if message.author.bot:
            return

        ctx = await self.get_context(message, cls = ContextWrap)
        await self.invoke(ctx)

    #########
    # Utils #
    #########

    @staticmethod
    async def add_role_in(member: discord.Member,
                          duration: int, *roles) -> None:
        await asyncio.sleep(duration)
        await member.add_roles(*roles)

    @staticmethod
    async def remove_role_in(member: discord.Member,
                             duration: int, *roles) -> None:
        await asyncio.sleep(duration)
        await member.remove_roles(*roles)

    async def filter_content(self, msg: str) -> bool:
        if not (self.config.filters or self.config.substring_filters):
            return False # filters disabled

        return (any(f in msg for f in self.config.substring_filters) or
                any(s in self.config.filters for s in msg.split()))

    async def print_console(self, msg: discord.Message, col: Ansi) -> None:
        if not (res := await self.db.fetch(
            'SELECT xp FROM aika_users '
            'WHERE discordid = %s AND guildid = %s',
            [msg.author.id, msg.guild.id]
        )): res = {'xp': 0} # user's first time talking.

        author_fmt = f"{msg.author} (Lv. {sqrt(res['xp'] / 50):.2f})"
        print('{c!r}[{time:%H:%M:%S} {guild} #{chan}]{gray!r} {author}{reset!r}: {msg}'.format(
            c = col, time = dt.now(tz = tz.utc), guild = msg.channel.guild,
            chan = msg.channel, gray = Ansi.GRAY, author = author_fmt,
            reset = Ansi.RESET, msg = msg.clean_content.replace('\u001b', '')
        ))

    @tasks.loop(seconds = 30)
    async def bg_loop(self) -> None:
        await self.wait_until_ready()

        akat_url = 'http://144.217.254.156:5001/api/v1/onlineUsers'
        async with self.http_sess.get(akat_url) as r:
            if r.status == 200:
                online = (await r.json(content_type=None))['result']
            else:
                online = 0

        await self.change_presence(
            activity = discord.Game(f'Akat: {online}, Servers: {len(self.guilds)}'),
            status = discord.Status.online)

    def run(self, *args, **kwargs) -> None:
        async def runner():
            # get our db connection & http client
            await self.connect_db()

            self.http_sess = aiohttp.ClientSession(
                json_serialize = orjson.dumps # use for speed
            )

            # load guild settings into cache
            res = await self.db.fetchall('SELECT * FROM aika_guilds')

            self.cache['guilds'] = {
                row['guildid']: {k: row[k] for k in set(row) - {'guildid'}}
                for row in res
            }

            try: # load all of Aika's enabled cogs.
                [self.load_extension(f'cogs.{e}')
                 for e in self.config.initial_extensions]
            except Exception as e:
                print(f'Failed to load extension {e}.')
                traceback.print_exc()

            try:
                await self.start(self.config.discord_token,
                                 *args, **kwargs)
            except:
                # close http session
                await self.http_sess.close()

                # close db conn pool.
                self.db.pool.close()
                await self.db.pool.wait_closed()

                # close any discordpy
                # bot related stuff.
                await self.close()

        loop = asyncio.get_event_loop()
        loop.create_task(runner())

        try:
            self.bg_loop.start()
            loop.run_forever()
        finally:
            self.bg_loop.cancel()

    @property
    def config(self):
        return __import__('config')
