# -*- coding: utf-8 -*-

from typing import Optional
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
    else: raise Exception('\x1b[31mconfig.json is empty!\x1b[0m')

    glob.config = loads(f.read())
    glob.mismatch = glob.config['version'] < glob.version

    if glob.mismatch: # Update the config file's version #.
        print(f'\x1b[92mAika has been updated (v{glob.config["version"]} -> v{glob.version}).\x1b[0m')
        glob.config['version'] = glob.version
        f.seek(0)
        dump(glob.config, f, sort_keys = True, indent = 4)
        f.truncate()
    elif glob.config['version'] > glob.version:
        raise Exception('\x1b[31mconfig.json is from a newer version of Aika?\x1b[0m')

# Attempt to connect to SQL
try: glob.db = dbConnector.SQLPool(config = {
    'user':     glob.config['mysql']['user'],
    'password': glob.config['mysql']['passwd'],
    'host':     glob.config['mysql']['host'],
    'database': glob.config['mysql']['database']
},  pool_size = 4)
except SQLError as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        raise Exception('\x1b[31mSQLError: Something is wrong with your username or password\x1b[0m')
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        raise Exception('\x1b[31mSQLError: Database does not exist\x1b[0m')
    else: raise Exception(err)
else: print('\x1b[32mSuccessfully connected to SQL\x1b[0m')

glob.bot = commands.Bot(
    command_prefix = commands.when_mentioned_or(glob.config['command_prefix']),
    owner_id = glob.config['discord_owner_userid'], help_command = None)
for i in glob.config['cogs']: glob.bot.load_extension(f'cogs.{i}')

def filter_message(msg: str) -> bool:
    return any(f in msg for f in glob.config['substring_filters']) \
        or any(s in glob.config['filters'] for s in msg.split())


""" Event handlers. """

@glob.bot.event
async def on_message(message: discord.Message) -> None:
    await glob.bot.wait_until_ready()
    if not message.content: return

    filtered: bool = glob.config['filters'] and filter_message(message.content.lower())
    print( # `{filtered?red:bot?magenga:cyan}[20:44:19 #channel] {dark_gray}cmyui#2147{reset}: message`
        f'\x1b[{91 if filtered else (95 if message.author.bot else 96)}m',
        f'[{datetime.now():%H:%M:%S} #{message.channel}]',
        f'\x1b[38;5;244m {message.author}',
        f'\x1b[0m: {message.clean_content}',
        sep = '')

    if filtered:
        await message.delete()
        return

    await glob.bot.process_commands(message)

@glob.bot.event
async def on_message_edit(before: discord.Message, after: discord.Message) -> None:
    await glob.bot.wait_until_ready()
    if not after.content: return

    filtered: bool = glob.config['filters'] and filter_message(after.content.lower())
    print( # `{filtered?red:yellow}[20:44:19 #channel] {dark_gray}cmyui#2147{reset}: message`
        f'\x1b[{91 if filtered else 93}m',
        f'[{datetime.now():%H:%M:%S} #{after.channel}]',
        f'\x1b[38;5;244m {after.author}',
        f'\x1b[0m: {after.clean_content}',
        sep = '')

    if filtered:
        await after.delete()
        return

    await glob.bot.process_commands(after)

@glob.bot.event
async def on_ready() -> None:
    print(f'\x1b[32mSuccessfully logged in as {glob.bot.user.name}\x1b[0m')

    if glob.config['server_build'] and glob.mismatch:
        await glob.bot.get_channel(glob.config['channels']['general']).send(embed = discord.Embed(
            title = f'Aika has been updated to v{glob.version:.2f}. (Previous: v{glob.mismatch:.2f})',
            description = 'Ready for commands B)', color = randint(0, 0xffffff)) # TODO: pick a constant color?
        )

@glob.bot.event
async def on_command_error(ctx: commands.Context, error: discord.ext.commands.errors.CommandError) -> None:
    if isinstance(error, discord.ext.commands.CommandOnCooldown):
        await ctx.send(f'{ctx.author.mention} that command is still on cooldown for another **{error.retry_after:.2f}** seconds.')
    elif isinstance(error, discord.ext.commands.CommandNotFound):
        await ctx.send(f"{ctx.author.mention} I couldn't find a command by that name..")
    elif isinstance(error, discord.ext.commands.NotOwner):
        pass
    elif isinstance(error, discord.ext.commands.CommandInvokeError):
        embed = discord.Embed(
            title = 'Exception traceback',
            description = 'Error encountered while invoking command.'
        )
        embed.set_footer(text = f'Aika v{glob.version}')
        embed.add_field(name = 'Type', value = type(error.original))
        for idx, arg in enumerate(error.original.args):
            embed.add_field(name = f'arg{idx}', value = arg)

        await ctx.send(embed = embed)
    else:
        print(f'\x1b[31mUnhandled error of type {type(error)}\x1b[0m')
        pass

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
