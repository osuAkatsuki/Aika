from typing import Any, Optional
from time import time
from mysql.connector.pooling import MySQLConnectionPool
from discord.ext.commands import Bot

version = 3.00 # Aika (This bot).
start_time: float = time()

db: Optional[MySQLConnectionPool] = None
config: Optional[Any] = None
debug: bool = False
mismatch: bool = False
bot: Optional[Bot] = None
