from typing import Any, Optional
from time import time
from mysql.connector.pooling import MySQLConnectionPool

version = 3.00 # Aika (This bot).
start_time: float = time()

db: Optional[MySQLConnectionPool] = None
config: Optional[Any] = None
debug: bool = False
mismatch: bool = False
