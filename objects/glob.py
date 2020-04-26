from typing import Any, Optional, Tuple
from time import time
from mysql.connector.pooling import MySQLConnectionPool
from re import compile as re_compile, IGNORECASE
from discord.ext.commands import Bot

version = 3.00 # Aika (This bot).
start_time: float = time()

db: Optional[MySQLConnectionPool] = None
config: Optional[Any] = None
debug: bool = False
mismatch: bool = False
bot: Optional[Bot] = None
loop = None
shutdown = False # used for async loop

# unused for now
# beatmap_regexes: Tuple[Any] = (
#     re_compile(r'^(?:https?://)?(?:www\.)?(?:akatsuki|gatari|ripple|osu\.ppy).(?:pw|moe|sh)/b/(?P<beatmap_id>\d{1,7})(?:/|\?mode=[0-3])?$', IGNORECASE),
#     re_compile(r'^(?:https?://)?(?:www\.)?(?:akatsuki|gatari|ripple|osu\.ppy).(?:pw|moe|sh)/(?:s|d)/(?P<beatmapset_id>\d{1,7})(?:/|\?mode=[0-3])?$', IGNORECASE),
#     re_compile(r'^(?:https?://)?(?:www\.)?(?:akatsuki|gatari|ripple|osu\.ppy).(?:pw|moe|sh)/beatmapset/(?P<beatmapset_id>\d{1,7})/discussion/(?P<beatmap_id>\d{0,7})/?$', IGNORECASE)
# )
