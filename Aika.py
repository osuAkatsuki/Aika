# -*- coding: utf-8 -*-

import discord, asyncio
from discord.ext import commands
from os import path, SEEK_END
from json import loads, dump
from datetime import datetime
from random import randint

from db import dbConnector
from mysql.connector import errorcode, Error as SQLError

from objects import glob


""" DB, config, etc. """

with open(f'{path.dirname(path.realpath(__file__))}/config.json', 'r+') as f:
    if f.seek(0, SEEK_END) and f.tell(): f.seek(0)
    else: raise Exception('\x1b[31mConfig file is empty!\x1b[0m')

    glob.config = loads(f.read())
    glob.mismatch = glob.config['version'] < glob.version

    if glob.mismatch: # Update the config file's version #.
        print(f'\x1b[92mAika has been updated (v{glob.config["version"]} -> v{glob.version}).\x1b[0m')
        glob.config['version'] = glob.version
        f.seek(0)
        dump(glob.config, f, sort_keys=True, indent=4)
        f.truncate()
    elif glob.config['version'] > glob.version:
        raise Exception('\x1b[31mConfig is from a newer version of Aika?\x1b[0m')

# Attempt to connect to SQL
try: glob.db = dbConnector.SQLPool(
    pool_size = 4, config = {
        'user': glob.config['mysql']['user'],
        'password': glob.config['mysql']['passwd'],
        'host': glob.config['mysql']['host'],
        'database': glob.config['mysql']['database']
    }
)
except SQLError as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        raise Exception('\x1b[31mSQLError: Something is wrong with your username or password.\x1b[0m')
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        raise Exception('\x1b[31mSQLError: Database does not exist.\x1b[0m')
    else: raise Exception(err)
else: print('\x1b[32mSuccessfully connected to SQL.\x1b[0m')

glob.bot = commands.Bot(
    command_prefix = commands.when_mentioned_or(glob.config['command_prefix']),
    owner_id = glob.config['discord_owner_userid'],
    case_insensitive = True, help_command = None, self_bot = False
)
for i in glob.config['cogs']: glob.bot.load_extension(f'cogs.{i}')

def filter_message(msg: str) -> bool:
    return any(f in msg for f in glob.config['substring_filters']) \
        or any(s in glob.config['filters'] for s in msg.split())

""" Event handlers. """

@glob.bot.event
async def on_message(message: discord.Message) -> None:
    await glob.bot.wait_until_ready()

    filtered: bool = glob.config['filters'] and filter_message(message.content.lower())
    print(f'\x1b[{91 if filtered else 96}m[{datetime.now():%H:%M%p} #{message.channel}]\x1b[38;5;244m {message.author}\x1b[0m: {message.clean_content}')

    if filtered:
        await message.delete()
        return

    # TODO:
    # - parse message to see if it is a:
    #   > report, rank request, etc.

    await glob.bot.process_commands(message)

@glob.bot.event
async def on_message_edit(before: discord.Message, after: discord.Message) -> None:
    await glob.bot.wait_until_ready()

    filtered: bool = glob.config['filters'] and filter_message(after.content.lower())
    print(f'\x1b[{91 if filtered else 93}m[{datetime.now():%H:%M%p} #{after.channel}]\x1b[38;5;244m {after.author}\x1b[0m: {after.clean_content}')

    if filtered:
        await after.delete()
        return

    # TODO: same things as on_message()

    await glob.bot.process_commands(after)


@glob.bot.event
async def on_ready() -> None:
    print(f'\x1b[32mSuccessfully logged in as {glob.bot.user.name}\x1b[0m')

    if glob.config['server_build'] and glob.mismatch:
        await glob.bot.get_channel(glob.config['channels']['general']).send(
            embed = discord.Embed(
                title = f'Aika has been updated to v{glob.version:.2f}. (Previous: v{glob.mismatch:.2f})',
                description = \
                    "Ready for commands B)",#\n\n",
                    #"Aika is cmyui's [open source](https://github.com/cmyui/Aika-v3) discord bot.\n\n"
                    #"[cmyui](https://cmyui.codes/)\n"
                    #"[Support cmyui](https://cmyui.codes/support/)",
                color = randint(0, 0xffffff)))

glob.bot.run(
    glob.config['discord_token'],
    bot = True, reconnect = True
)
