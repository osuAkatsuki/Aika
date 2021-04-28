# -*- coding: utf-8 -*-

import os

import discord

from objects.aika import Aika
from utils import ensure_config

__all__ = ()

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    if ensure_config():
        intents = discord.Intents.default()
        #intents.members = True
        Aika(intents=intents).run() # blocking call
