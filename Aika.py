# -*- coding: utf-8 -*-

from typing import Union
import discord, asyncio
from discord.ext import commands, tasks
from os import chdir, path
from time import time
from datetime import datetime
import traceback
from shutil import copyfile
from requests import get # DONT USE IN ASYNC FUNCTIONS!

from enum import IntEnum

from db import dbConnector
from mysql.connector import errorcode, Error as SQLError

class Ansi(IntEnum):
    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37

    GRAY = 90
    LIGHT_RED = 91
    LIGHT_GREEN = 92
    LIGHT_YELLOW = 93
    LIGHT_BLUE = 94
    LIGHT_MAGENTA = 95
    LIGHT_CYAN = 96
    LIGHT_WHITE = 97

    RESET = 0

    def __str__(self):
        return f'\x1b[{self.value}m'

class Aika(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix = commands.when_mentioned_or(self.config.command_prefix),
            owner_id = self.config.discord_owner)

        self.db = None
        self.connect_db()

        self.locked = False # lock aika's commands to only bot owner

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
        try:
            self.db = dbConnector.SQLPool(
                config = self.config.mysql,
                pool_size = 4)
        except SQLError as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                raise Exception('SQLError: Something is wrong with your username or password')
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                raise Exception('SQLError: Database does not exist')
            else:
                raise Exception(err)
        else:
            print('Successfully connected to SQL')

    ##########
    # Events #
    ##########

    async def on_message(self, message: discord.Message) -> None:
        await self.wait_until_ready()
        if not message.content or message.author.bot:
            return

        filtered = self.config.filters and await self.filter_message(message.content.lower())

        if self.config.verbose_console:
            colour = Ansi.LIGHT_RED if filtered else (Ansi.LIGHT_MAGENTA if message.author.bot else Ansi.LIGHT_CYAN)
            await self.print_console(message, colour)

        if filtered:
            return await message.delete()

        await self.process_commands(message)

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        await self.wait_until_ready()
        if not after.content or after.author.bot:
            return

        filtered = self.config.filters and await self.filter_message(after.content.lower())

        if self.config.verbose_console:
            colour = Ansi.LIGHT_RED if filtered else Ansi.LIGHT_YELLOW
            await self.print_console(after, colour)

        if filtered:
            return await after.delete()

        await self.process_commands(after)

    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]) -> None:
        print (f'{Ansi.GREEN!s}{user.name} was banned from {guild.name}.{Ansi.RESET!s}')

    async def on_ready(self) -> None:
        # TODO: maybe use datetime module rather than this w/ formatting?
        if not hasattr(self, 'uptime'):
            self.uptime = time()

        print(f'{Ansi.GREEN!s}Ready{Ansi.RESET!s}: {self.user} ({self.user.id})')

    async def on_command_error(self, ctx: commands.Context, error: commands.errors.CommandError) -> None:
        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (commands.CommandNotFound, commands.UserInputError, commands.NotOwner)
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(
                f'{ctx.command} is currently disabled.')

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(
                    f'{ctx.command} can only be used in guilds.')
            except:
                pass

        elif isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(
                f'{ctx.author.mention} that command is still on cooldown for another **{error.retry_after:.2f}** seconds.')

        elif isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(
                'I have insufficient privileges in the server to perform such a command.')

        elif isinstance(error, commands.MissingPermissions):
            return await ctx.send(
                'You have insufficient privileges to perform such a command.')

        print(f'Ignoring exception in command {ctx.command}')
        traceback.print_exception(type(error), error, error.__traceback__)

    #########
    # Utils #
    #########

    async def filter_message(self, msg: str) -> bool: # TODO: aSYNC
        return any(f in msg for f in self.config['substring_filters']) \
            or any(s in self.config['filters'] for s in msg.split())

    async def print_console(self, msg: discord.Message, col: Ansi) -> None:
        print(f'{col!s}[{datetime.now():%H:%M:%S} {msg.channel.guild.name} #{msg.channel}]',
            f'{Ansi.GRAY!s} {msg.author}',
            f'{Ansi.RESET!s}: {msg.clean_content}',
            sep = '')

    @tasks.loop(seconds = 10)
    async def bg_loop(self):
        await self.wait_until_ready()

        is_420 = (now := datetime.now()).hour in (4, 16) and now.minute == 20

        await self.change_presence(
            status = discord.Status.online,
            activity = discord.Game(f'with {len(self.users)} users!{" (& the joint)" if is_420 else ""}')
        )

    def run(self) -> None:
        try:
            self.bg_loop.start()
            super().run(self.config.discord_token, reconnect=True)
        finally:
            self.bg_loop.cancel()

    async def close(self):
        await super().close()
        await self.session.close()

    @property
    def config(self):
        return __import__('config')

def main() -> None:
    chdir(path.dirname(path.realpath(__file__)))

    # Ensure config
    if not path.exists('config.py'):
        if not path.exists('config.sample.py'):
            if not (r := get('https://raw.githubusercontent.com/cmyui/Aika-3/master/config.sample.py')):
                print(f'{Ansi.LIGHT_RED!s}Failed to fetch default config.{Ansi.RESET!s}')
                return

            with open('config.sample.py', 'w+') as f:
                f.write(r.text)

        copyfile('config.sample.py', 'config.py')

        print(f'{Ansi.CYAN!s}A default config has been generated.{Ansi.RESET!s}')
        return

    # Run Aika
    aika = Aika()
    aika.run()

if __name__ == '__main__':
    main()
