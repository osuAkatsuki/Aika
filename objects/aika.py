# -*- coding: utf-8 -*-

from typing import Union, List, Dict, Optional
from cmyui import MySQLPool
import discord
import aiohttp
from discord.ext import commands, tasks
from json import loads
from datetime import datetime as dt, timezone as tz
import traceback
from time import time

from constants import Ansi
from mysql.connector import errorcode, Error as SQLError
from utils import printc, asciify

__all__ = (
    'Listing',
    'Leaderboard',
    'ContextWrap',
    'Aika'
)

Listing = Dict[str, Union[int, float, str]]
class Leaderboard:
    __slots__ = ('listings',)

    def __init__(self, listings: List[Listing]) -> None:
        self.listings = [{
            'title': asciify(truncate(i['title'], 12)),
            'value': i['value']
        } for i in listings]

    def __repr__(self) -> str:
        len_id = len(str(len(self.listings))) + 1
        len_title = min(14, max(len(i['title']) for i in self.listings))

        return '```md\n{lb}```'.format(
            lb = '\n'.join(
                '{id:0>{s_id}} {title:^{s_title}} - {value}'.format(
                    id = f'{idx + 1}.', s_id = len_id, s_title = len_title,
                    **i # <-- the real params
                ) for idx, i in enumerate(self.listings))
        )

# Light wrapper around commands.Context to allow for one of Aika's
# special features: the ability to edit previous messages to edit
# Aika's response (and specifically for Aika to be able to edit
# their previous) response rather than just creating a new one.
# With: ctx.send(...) // Without: self.bot.send(ctx, ...)
class ContextWrap(commands.Context):
    __slots__ = ('message', 'bot')

    async def send(self, *args, **kwargs) -> Optional[discord.Message]:
        # Check for a hit in our cache.
        is_cached = lambda m: m['msg'] == self.message
        hit = discord.utils.find(is_cached, self.bot.resp_cache)

        if hit and (expired := (int(time()) - hit['expire']) > 0):
            # We have a hit, but it's expired.
            # Remove it from the cache, and use a new msg.
            self.bot.resp_cache.remove(hit)
            hit = False

        if len(args) == 1 and isinstance(args[0], str):
            # Allows for the sytax: ctx.send('content')
            kwargs['content'] = args[0]

        # Clear previous msg params.
        kwargs['embed'] = kwargs.pop('embed', None)
        kwargs['content'] = kwargs.pop('content', None)

        if hit: # cache hit - edit.
            await (m := hit['resp']).edit(**kwargs)
        else: # cache miss (or expired) - send.
            m = await super().send(**kwargs)
            self.bot.resp_cache.append({
                'msg': self.message, # their msg
                'resp': m, # our msg
                'expire': int(time()) + (5 * 60)
            })

        # Return our response message object.
        return m

class Aika(commands.Bot):
    __slots__ = ('db', 'resp_cache')

    def __init__(self) -> None:
        super().__init__(commands.when_mentioned_or(self.config.prefix),
                         owner_id = self.config.discord_owner,
                         help_command = None)
        self.connect_db()
        self.resp_cache = []

        for e in self.config.initial_extensions:
            try:
                self.load_extension(f'cogs.{e}')
            except Exception as e:
                print(f'Failed to load extension {e}.')
                traceback.print_exc()

    #########
    # MySQL #
    #########

    def connect_db(self) -> None:
        if hasattr(self, 'db'):
            return

        try:
            self.db = MySQLPool(**self.config.mysql, pool_size = 4)
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

        filtered = msg.guild.id == self.config.akatsuki['id'] \
               and await self.filter_content(msg.content.lower())

        colour = Ansi.LIGHT_MAGENTA if msg.author.bot \
            else Ansi.LIGHT_RED if filtered \
            else Ansi.LIGHT_CYAN

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

        filtered = after.guild.id == self.config.akatsuki['id'] \
               and await self.filter_content(after.content.lower())

        colour = Ansi.LIGHT_RED if filtered else Ansi.LIGHT_YELLOW
        await self.print_console(after, colour)

        if filtered:
            return await after.delete()

        if self.config.server_build or after.author.id == self.owner_id:
            await self.process_commands(after)

    async def on_message_delete(self, msg: discord.Message) -> None:
        # Whenever a message is deleted, check if it was in
        # our cache, and delete it (so they don't accumulate).
        is_cached = lambda m: m['msg'] == msg

        if (hit := discord.utils.find(is_cached, self.resp_cache)):
            try:
                await hit['resp'].delete()
            except discord.NotFound: # No 403 - it's 100% our own message
                pass # response has already been deleted
            self.resp_cache.remove(hit)

    async def on_member_ban(self, guild: discord.Guild,
                            user: Union[discord.Member, discord.User]) -> None:
        printc(f'{user} was banned from {guild}.', Ansi.GREEN)

    async def on_ready(self) -> None:
        # TODO: maybe use datetime module rather than this w/ formatting?
        if not hasattr(self, 'uptime'):
            self.uptime = time()

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

        return any(f in msg for f in self.config.substring_filters) \
            or any(s in self.config.filters for s in msg.split())

    async def print_console(self, msg: discord.Message, col: Ansi) -> None:
        print('{c!r}[{time:%H:%M:%S} {guild} #{chan}]{gray!r} {author}{reset!r}: {msg}'.format(
            c = col, time = dt.now(tz = tz.utc), guild = msg.channel.guild,
            chan = msg.channel, gray = Ansi.GRAY, author = msg.author,
            reset = Ansi.RESET, msg = msg.clean_content.replace('\u001b', '')
        ))

    @tasks.loop(seconds = 15)
    async def bg_loop(self) -> None:
        await self.wait_until_ready()

        async with aiohttp.ClientSession() as s:
            online = loads(html)['result'] if (
                html := await self.fetch(
                    s, 'http://144.217.254.156:5001/api/v1/onlineUsers')
            ) else 0

        await self.change_presence(
            activity = discord.Game(f'Akat: {online}, Servers: {len(self.guilds)}'),
            status = discord.Status.online)

    def run(self) -> None:
        try:
            self.bg_loop.start()
            super().run(self.config.discord_token, reconnect=True)
        finally:
            self.bg_loop.cancel()

    @staticmethod
    async def fetch(session, url):
        async with session.get(url) as resp:
            return await resp.text() if resp.status == 200 else None

    @property
    def config(self):
        return __import__('config')
