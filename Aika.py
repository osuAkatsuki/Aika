# -*- coding: utf-8 -*-

from typing import Optional, Union
import discord, asyncio
from discord.ext import commands
from os import path, SEEK_END
from json import loads, dump
from datetime import datetime
from random import randint
import traceback

from db import dbConnector
from mysql.connector import errorcode, Error as SQLError

from objects import glob


""" DB, config, etc. """

with open(f'{path.dirname(path.realpath(__file__))}/config.json', 'r+') as f:
    if f.seek(0, SEEK_END) and f.tell(): f.seek(0)
    else: raise Exception('config.json is empty!')

    glob.config = loads(f.read())
    glob.mismatch = glob.config['version'] < glob.version

    if glob.mismatch: # Update the config file's version #.
        print(f'\x1b[92mAika has been updated (v{glob.config["version"]} -> v{glob.version}).\x1b[0m')
        glob.config['version'] = glob.version
        f.seek(0)
        dump(glob.config, f, sort_keys = True, indent = 4)
        f.truncate()
    elif glob.config['version'] > glob.version:
        raise Exception('config.json is from a newer version of Aika?')

# Attempt to connect to SQL
try:
    glob.db = dbConnector.SQLPool(
        config = glob.config['mysql'],
        pool_size = 4
    )
except SQLError as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        raise Exception('SQLError: Something is wrong with your username or password')
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        raise Exception('SQLError: Database does not exist')
    else: raise Exception(err)
else: print('Successfully connected to SQL')

glob.bot = commands.Bot(
    command_prefix = commands.when_mentioned_or(glob.config['command_prefix']),
    owner_id = glob.config['discord_owner_userid']
)

for i in glob.config['cogs']:
    glob.bot.load_extension(f'cogs.{i}')

def filter_message(msg: str) -> bool:
    return any(f in msg for f in glob.config['substring_filters']) \
        or any(s in glob.config['filters'] for s in msg.split())

async def print_console(msg: discord.Message, col: int) -> None:
    print(f'\x1b[{col}m[{datetime.now():%H:%M:%S} {msg.channel.guild.name} #{msg.channel}]',
          f'\x1b[38;5;244m {msg.author}',
          f'\x1b[0m: {msg.clean_content}',
          sep = '')

""" Event handlers. """

@glob.bot.event
async def on_message(message: discord.Message) -> None:
    await glob.bot.wait_until_ready()
    if not message.content or message.author.bot: return

    filtered = glob.config['filters'] and filter_message(message.content.lower())
    await print_console(message, 91 if filtered else (95 if message.author.bot else 96))

    if filtered:
        await message.delete()
        return

    await glob.bot.process_commands(message)

@glob.bot.event
async def on_message_edit(before: discord.Message, after: discord.Message) -> None:
    await glob.bot.wait_until_ready()
    if not after.content or after.author.bot: return

    filtered: bool = glob.config['filters'] and filter_message(after.content.lower())
    await print_console(after, 91 if filtered else 93)

    if filtered:
        await after.delete()
        return

    await glob.bot.process_commands(after)

@glob.bot.event
async def on_member_ban(guild, user: Union[discord.Member, discord.User]) -> None:
    print (f'\x1b[32m{user.name} was banned from {guild.name}.\x1b[0m')

@glob.bot.event
async def on_ready() -> None:
    print(f'\x1b[32mSuccessfully logged in as {glob.bot.user.name}\x1b[0m')

    if glob.config['server_build'] and glob.mismatch:
        await glob.bot.get_channel(glob.config['channels']['general']).send(embed = discord.Embed(
            title = f'Aika has been updated to v{glob.version:.2f}. (Previous: v{glob.mismatch:.2f})',
            description = 'Ready for commands B)', color = glob.config['embed_color']) # TODO: pick a constant color?
        )

@glob.bot.event
async def on_command_error(ctx: commands.Context, error: commands.errors.CommandError) -> None:
    if hasattr(ctx.command, 'on_error'):
        return

    ignored = (commands.CommandNotFound, commands.UserInputError, commands.NotOwner)
    error = getattr(error, 'original', error)

    if isinstance(error, ignored):
        return
    elif isinstance(error, commands.DisabledCommand):
        return await ctx.send(f'{ctx.command} is currently disabled.')
    elif isinstance(error, commands.NoPrivateMessage):
        try: return await ctx.author.send(f'{ctx.command} can only be used in guilds.')
        except: pass
    elif isinstance(error, commands.CommandOnCooldown):
        return await ctx.send(f'{ctx.author.mention} that command is still on cooldown for another **{error.retry_after:.2f}** seconds.')
    elif isinstance(error, commands.BotMissingPermissions):
        return await ctx.send('I have insufficient privileges in the server to perform such a command.')
    elif isinstance(error, commands.MissingPermissions):
        return await ctx.send('You have insufficient privileges to perform such a command.')
    #elif isinstance(error, commands.CommandInvokeError):
    #    e = discord.Embed(
    #        title = 'Exception traceback',
    #        description = 'Error encountered while invoking command.',
    #        color = glob.config['embed_color']
    #    )
    #    e.set_footer(text = f'Aika v{glob.version}')
    #    e.add_field(name = 'Type', value = type(error))
    #    for idx, arg in enumerate(error.args):
    #        e.add_field(name = f'arg{idx}', value = arg)
    #    await ctx.send(embed = e)

    print(f'Ignoring exception in command {ctx.command}')
    traceback.print_exception(type(error), error, error.__traceback__)

async def _background_loop():
    while not glob.bot.is_ready():
        await asyncio.sleep(2)

    while not glob.shutdown:
        try: # for omega unlucky timing moments
            await glob.bot.change_presence(
                status = discord.Status.online,
                activity = discord.Game(f'with {len(glob.bot.users)} users!')
            )
        except: return

        # Rather than waiting for the loop interval for the program
        # to close, check if we are to shutdown every 1s of the interval.
        for _ in range(min(1, glob.config['bg_loop_interval'])):
            if glob.shutdown: return
            await asyncio.sleep(1)

async def main():
    await asyncio.wait([
        glob.bot.start(glob.config['discord_token']),
        _background_loop()
    ])

    print(f'\x1b[38mSuccessfully logged out of {glob.bot.user.name}\x1b[0m')

if __name__ == '__main__':
    # TODO: config validation (& default generation?)

    glob.loop = asyncio.get_event_loop()
    glob.loop.run_until_complete(main())
    glob.loop.close()
