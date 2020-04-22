# -*- coding: utf-8 -*-

import discord, asyncio
from discord.ext import commands
from os import path, SEEK_END
from json import loads, dump
from datetime import datetime

from db import dbConnector
from mysql.connector import errorcode, Error as SQLError

from objects import glob


""" DB, config, etc. """

with open(f'{path.dirname(path.realpath(__file__))}/config.json', 'r+') as f:
    if f.seek(0, SEEK_END) and f.tell(): f.seek(0)
    else: raise Exception('Config file is empty!')

    glob.config = loads(f.read())
    glob.mismatch = glob.config['version'] < glob.version

    if glob.mismatch:
        print(f'Aika has been updated (v{glob.config["version"]} -> v{glob.version}).')
        glob.config['version'] = glob.version
        f.seek(0)
        dump(glob.config, f, sort_keys=True, indent=4)
        f.truncate()
    elif glob.config['version'] > glob.version:
        raise Exception('Config is from a newer version of Aika?')

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
        raise Exception('SQLError: Something is wrong with your username or password.')
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        raise Exception('SQLError: Database does not exist.')
    else: raise Exception(err)
else: print('Successfully connected to SQL.')

glob.bot = commands.Bot(
    command_prefix = commands.when_mentioned_or(glob.config['command_prefix']),
    owner_id = glob.config['discord_owner_userid'],
    case_insensitive = True, help_command = None, self_bot = False
)
for i in glob.config['cogs']: glob.bot.load_extension(f'cogs.{i}')

def filter_message(msg: str) -> bool:
    return any(f in msg for f in glob.config['substring_filters']) \
        or any(s in glob.config['filters'] for s in msg.split('\n'))

""" Event handlers. """

@glob.bot.event
async def on_message(message: discord.Message) -> None:
    await glob.bot.wait_until_ready()
    print(f'[{datetime.now():%H:%M%p} #{message.channel}] {message.author}: {message.clean_content}')

    if glob.config['filters'] and filter_message(message.content.lower()):
        print('Filtered message ^')
        await message.delete()
        return

    # TODO:
    # - parse message to see if it is a:
    #   > report, rank request, etc.

    await glob.bot.process_commands(message)


@glob.bot.event
async def on_message_edit(before: discord.Message, after: discord.Message) -> None:
    await glob.bot.wait_until_ready()
    print(f'[{datetime.now():%H:%M%p} #{after.channel}] {after.author}:* {after.clean_content}')

    if glob.config['filters'] and filter_message(after.content.lower()):
        print('Filtered message ^')
        await after.delete()
        return

    # TODO: same things as on_message()

    await glob.bot.process_commands(after)


@glob.bot.event
async def on_ready() -> None:
    print(f'Successfully logged in as {glob.bot.user.name}')

    if glob.config['server_build'] and mismatch:
        await glob.bot.get_channel(glob.config['channels']['general']).send(embed = discord.Embed(
            title = f'Aika has been updated to v{glob.version:.2f}. (Previous: v{mismatch:.2f})',
            description = \
                "Ready for commands <3\n\n"
                "Aika is cmyui's [open source](https://github.com/cmyui/Aika-v3) discord bot.\n\n"
                "[cmyui](https://cmyui.codes/)\n"
                "[Support cmyui](https://cmyui.codes/support/)",
            color = 0x00ff00
        ))

glob.bot.run(glob.config['discord_token'], bot=True, reconnect=True)
