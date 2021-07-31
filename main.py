# -*- coding: utf-8 -*-

import os

import discord

from objects.aika import Aika
from utils import ensure_config_ready

__all__ = ()

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    if ensure_config_ready():
        intents = discord.Intents.default()

        # TODO: support for privileged intents

        Aika(intents=intents).run() # blocking call
