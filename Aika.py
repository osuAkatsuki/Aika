# -*- coding: utf-8 -*-

from typing import Optional, Union
import discord, asyncio
from discord.ext import commands, tasks
from os import path, SEEK_END
from time import time
from datetime import datetime
from random import randint
import traceback

from db import dbConnector
from mysql.connector import errorcode, Error as SQLError

import config

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

    async def on_message(self, message: discord.Message) -> None:
        await self.wait_until_ready()
        if not message.content or message.author.bot: return

        filtered = self.config.filters and filter_message(message.content.lower())
        await self.print_console(message, 91 if filtered else (95 if message.author.bot else 96))

        if filtered:
            return await message.delete()

        await self.process_commands(message)

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        await self.wait_until_ready()
        if not after.content or after.author.bot: return

        filtered: bool = self.config.filters and filter_message(after.content.lower())
        await self.print_console(after, 91 if filtered else 93)

        if filtered:
            return await after.delete()

        await self.process_commands(after)

    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]) -> None:
        print (f'\x1b[32m{user.name} was banned from {guild.name}.\x1b[0m')

    async def on_ready(self) -> None:
        # TODO: maybe use datetime module rather than this w/ formatting?
        if not hasattr(self, 'uptime'):
            self.uptime = time()

        print(f'\x1b[32mReady\x1b[0m: {self.user} ({self.user.id})')

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

    def filter_message(self, msg: str) -> bool: # TODO: aSYNC
        return any(f in msg for f in self.config['substring_filters']) \
            or any(s in self.config['filters'] for s in msg.split())

    async def print_console(self, msg: discord.Message, col: int) -> None:
        print(f'\x1b[{col}m[{datetime.now():%H:%M:%S} {msg.channel.guild.name} #{msg.channel}]',
            f'\x1b[38;5;244m {msg.author}',
            f'\x1b[0m: {msg.clean_content}',
            sep = '')

    @tasks.loop(seconds = config.bg_loop_interval)
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
            print(f'\x1b[37mSuccessfully logged out of {self.user.name}\x1b[0m')

    @property
    def config(self):
        return __import__('config')

if __name__ == '__main__':
    # TODO: config validation (& default generation?)
    bot = Aika()
    bot.run()
