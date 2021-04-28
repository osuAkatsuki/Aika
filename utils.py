# -*- coding: utf-8 -*-

# This is basically a disaster file of all the utilities i always
# end up dragging around with me.. and some even more wild ones

from os import path
from shutil import copyfile
from typing import Optional

from cmyui import Ansi
from cmyui import log
from requests import get as req_get

from config import akatsuki
from constants import Mods

def mods_readable(m: int) -> str:
    if not m: return ''

    r: list[str] = []
    if m & Mods.NOFAIL:       r.append('NF')
    if m & Mods.EASY:         r.append('EZ')
    if m & Mods.TOUCHSCREEN:  r.append('TD')
    if m & Mods.HIDDEN:       r.append('HD')
    if m & Mods.HARDROCK:     r.append('HR')
    if m & Mods.NIGHTCORE:    r.append('NC')
    elif m & Mods.DOUBLETIME: r.append('DT')
    if m & Mods.RELAX:        r.append('RX')
    if m & Mods.HALFTIME:     r.append('HT')
    if m & Mods.FLASHLIGHT:   r.append('FL')
    if m & Mods.SPUNOUT:      r.append('SO')
    if m & Mods.SCOREV2:      r.append('V2')
    return ''.join(r)

def seconds_readable(seconds: int) -> str:
    r: list[str] = []

    days, seconds = divmod(seconds, 60 * 60 * 24)
    if days: r.append(f'{days:02d}')

    hours, seconds = divmod(seconds, 60 * 60)
    if hours: r.append(f'{hours:02d}')

    minutes, seconds = divmod(seconds, 60)
    r.append(f'{minutes:02d}')

    return ':'.join(r + [f'{seconds % 60:02d}'])

def seconds_readable_full(seconds: int) -> str:
    r: list[str] = []

    days, seconds = divmod(seconds, 60 * 60 * 24)
    if days: r.append(f'{days} days')

    hours, seconds = divmod(seconds, 60 * 60)
    if hours: r.append(f'{hours} hours')

    minutes, seconds = divmod(seconds, 60)
    if minutes: r.append(f'{minutes} minutes')

    return ', '.join(r + [f'{seconds} seconds'])

def gamemode_db(m: int) -> str:
    return [
        'std',   # 0
        'taiko', # 1
        'ctb',   # 2
        'mania'  # 3
    ][m]

def gamemode_readable(m: int) -> str:
    return [
        'osu!',      # 0
        'osu!taiko', # 1
        'osu!catch', # 2
        'osu!mania'  # 3
    ][m]

def status_readable(s: int) -> str:
    return {
        5: 'Loved',
        3: 'Approved',
        2: 'Ranked',
        0: 'Unranked'
    }[s]

def calc_accuracy_std(
    n300: int, n100: int,
    n50: int, nmiss: int) -> float:
    if not (total := sum((n300, n100, n50, nmiss))):
        return 0.00

    return sum((
        n50 * 50.0,
        n100 * 100.0,
        n300 * 300.0
    )) / (total * 300)

def calc_accuracy_taiko(
    n300: int, n150: int,
    nmiss: int) -> float:
    if not (total := sum((n300, n150, nmiss))):
        return 0.00

    return sum((
        n150 * 150.0,
        n300 * 300.0
    )) / (total * 300.0)

def accuracy_grade(
    mode: int, acc: float, mods: int,
    count_300: Optional[int] = None, count_100: Optional[int] = None,
    count_50: Optional[int] = None, count_miss: Optional[int] = None) -> str:
    total = sum([count_300, count_100, count_50, count_miss])
    hdfl = mods & (Mods.HIDDEN | Mods.FLASHLIGHT)
    ss = lambda: 'XH' if hdfl else 'X'
    s = lambda: 'SH' if hdfl else 'S'

    if mode == 0: # osu!
        if acc == 100.00:
            return ss()
        elif count_300 / total > 0.90 \
         and count_50 / total < 0.1 \
         and count_miss == 0:
            return s()
        elif (count_300 / total > 0.80 and count_miss == 0) \
          or (count_300 / total > 0.90):
            return 'A'
        elif (count_300 / total > 0.70 and count_miss == 0) \
          or (count_300 / total > 0.80):
            return 'B'
        elif count_300 / total > 0.60:
            return 'C'
        else:
            return 'D'
    elif mode == 1: # osu!taiko
        return 'A' # TODO: taiko
    elif mode == 2: # osu!catch
        if acc == 100.0:
            return ss()
        elif 98.01 <= acc <= 99.99:
            return s()
        elif 94.01 <= acc <= 98.00:
            return 'A'
        elif 90.01 <= acc <= 94.00:
            return 'B'
        elif 85.01 <= acc <= 90.00:
            return 'C'
        else:
            return 'D'
    elif mode == 3: # osu!mania
        if acc == 100.00:
            return ss()
        elif acc > 95.00:
            return s()
        elif acc > 90.00:
            return 'A'
        elif acc > 80.00:
            return 'B'
        elif acc > 70.00:
            return 'C'
        else:
            return 'D'

def isfloat(s: str) -> bool: # obviously not made for safety
    return s.replace('-', '', 1).replace('.', '', 1).isdigit()

def try_parse_float(s: str) -> Optional[float]:
    return float(s) if isfloat(s) else None

def asciify(s: str) -> str:
    return s.encode('ascii', 'ignore').decode('ascii')

def truncate(s: str, max_len: int) -> str:
    return f'{s[:max_len - 2]}..' if len(s) > max_len else s

def akatsuki_only(ctx) -> bool:
    return ctx.guild.id == akatsuki['id']

def ensure_config() -> bool:
    if path.exists('config.py'):
        return True

    if not path.exists('config.sample.py'):
        if not (r := req_get('http://tiny.cc/l7wzpz')):
            log('Failed to fetch default config.', Ansi.LRED)
            return False

        with open('config.sample.py', 'w+') as f:
            f.write(r.text)

    copyfile('config.sample.py', 'config.py')

    log('A default config has been generated.', Ansi.CYAN)
    return False
