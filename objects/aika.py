# -*- coding: utf-8 -*-

import asyncio
from collections import defaultdict
from typing import Union, Optional
from cmyui import AsyncSQLPool, Version
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
    __slots__ = ('data',)

    def __init__(self) -> None:
        self.data = {}

    def update(self, d) -> None:
        self.data.update(d)

    def __repr__(self) -> str:
        # Maximum lenth of an ID as a string.
        # Only needs to work for 1-2, so optimized.
        idx_maxlen = 2 if len(self.data) > 9 else 1

        # Maximum length of a key
        key_maxlen = min(14, max(len(k) for k in self.data.keys()))

        return '```markdown\n{}```'.format(
            '\n'.join('{idx:0>{idx_maxlen}}. {key:^{key_maxlen}} - {value}'.format(
                idx = idx + 1, key = asciify(truncate(d[0], 12)), value = d[1],
                key_maxlen = key_maxlen, idx_maxlen = idx_maxlen
            ) for idx, d in enumerate(self.data.items()))
        )

# Light wrapper around commands.Context to allow for one of Aika's
# special features: the ability to edit previous messages to edit
# Aika's response (and specifically for Aika to be able to edit
# their previous) response rather than just creating a new one.
# With: ctx.send(...) // Without: self.bot.send(ctx, ...)
class ContextWrap(commands.Context):
    __slots__ = ('message', 'bot')

    async def send(self, *args, **kwargs) -> Optional[discord.Message]:
        # Allows for the syntax `ctx.send('content')`
        if len(args) == 1 and isinstance(args[0], str):
            kwargs['content'] = args[0]

        # Clear previous msg params.
        kwargs['embed'] = kwargs.pop('embed', None)
        kwargs['content'] = kwargs.pop('content', None)

        cached = self.bot.resp_cache[self.message.id]

        if cached and (time.time() - cached['timeout']) <= 0:
            # We have cache and it's not expired.
            msg = cached['resp']
            await msg.edit(**kwargs)
        else: # We either have no cached val, or it's expired.
            msg = await super().send(**kwargs)

            self.bot.resp_cache[self.message.id] = {
                'resp': msg,
                'timeout': int(time.time()) + 300 # 5 min
            }

        return msg

class Aika(commands.Bot):
    __slots__ = ('db', 'resp_cache')

    def __init__(self) -> None:
        super().__init__(commands.when_mentioned_or(self.config.prefix),
                         owner_id = self.config.discord_owner,
                         help_command = None)
        self.db: Optional[AsyncSQLPool] = None
        self.resp_cache = defaultdict(lambda: None)
        self.version = Version(1, 0, 0)

    #########
    # MySQL #
    #########

    async def connect_db(self) -> None:
        try:
            self.db = AsyncSQLPool()
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

        if self.config.server_build or msg.author.id == self.owner_id:
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

        if self.config.server_build or after.author.id == self.owner_id:
            await self.process_commands(after)

    async def on_message_delete(self, msg: discord.Message) -> None:
        # Whenever a message is deleted, check if it was in
        # our cache, and delete it (so they don't accumulate).
        cached = self.resp_cache[msg.id]

        if cached:
            try:
                await cached['resp'].delete()
            except discord.NotFound: # No 403 since it's our own message.
                pass # Response has already been deleted.

            del self.resp_cache[msg.id]

    async def on_member_ban(self, guild: discord.Guild,
                            user: Union[discord.Member, discord.User]) -> None:
        printc(f'{user} was banned from {guild}.', Ansi.GREEN)

    async def on_ready(self) -> None:
        # TODO: maybe use datetime module rather than this w/ formatting?
        if not hasattr(self, 'uptime'):
            self.uptime = time.time()

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
        if message.author.bot: return

        ctx = await self.get_context(message, cls = ContextWrap)
        await self.invoke(ctx)

    #########
    # Utils #
    #########

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

        async with aiohttp.ClientSession() as s:
            online = orjson.loads(html)['result'] if (
                html := await self.fetch(
                    s, 'http://144.217.254.156:5001/api/v1/onlineUsers')
            ) else 0

        await self.change_presence(
            activity = discord.Game(f'Akat: {online}, Servers: {len(self.guilds)}'),
            status = discord.Status.online)

    def run(self, *args, **kwargs) -> None:
        async def runner():
            await self.connect_db()

            for e in self.config.initial_extensions:
                try:
                    self.load_extension(f'cogs.{e}')
                except Exception as e:
                    print(f'Failed to load extension {e}.')
                    traceback.print_exc()

            try:
                await self.start(self.config.discord_token, *args, **kwargs)
            except:
                await self.close()

        loop = asyncio.get_event_loop()
        loop.create_task(runner())

        try:
            self.bg_loop.start()
            loop.run_forever()
        finally:
            self.bg_loop.cancel()

    @staticmethod
    async def fetch(session, url):
        async with session.get(url) as resp:
            return await resp.text() if resp.status == 200 else None

    @property
    def config(self):
        return __import__('config')
