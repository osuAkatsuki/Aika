from typing import Final
from enum import IntEnum
from re import compile as re_compile

regexes = {
    'beatmap_url': re_compile(r'(?:https?://)?(?:www.)?akatsuki.pw/b/(?P<bid>\d{1,7})/?'),
    'song_name': re_compile(r'(?P<artist>.+) - (?P<sn>.+)\[(?P<diff>.+)\]')
}

class Ansi(IntEnum):
    # Default colours
    BLACK: Final[int] = 30
    RED: Final[int] = 31
    GREEN: Final[int] = 32
    YELLOW: Final[int] = 33
    BLUE: Final[int] = 34
    MAGENTA: Final[int] = 35
    CYAN: Final[int] = 36
    WHITE: Final[int] = 37

    # Light colours
    GRAY: Final[int] = 90
    LIGHT_RED: Final[int] = 91
    LIGHT_GREEN: Final[int] = 92
    LIGHT_YELLOW: Final[int] = 93
    LIGHT_BLUE: Final[int] = 94
    LIGHT_MAGENTA: Final[int] = 95
    LIGHT_CYAN: Final[int] = 96
    LIGHT_WHITE: Final[int] = 97

    RESET: Final[int] = 0

    def __repr__(self) -> str:
        return f'\x1b[{self.value}m'

class Mods(IntEnum):
    NOMOD = 0
    NOFAIL = 1 << 0
    EASY = 1 << 1
    TOUCHSCREEN = 1 << 2
    HIDDEN = 1 << 3
    HARDROCK = 1 << 4
    SUDDENDEATH = 1 << 5
    DOUBLETIME = 1 << 6
    RELAX = 1 << 7
    HALFTIME = 1 << 8
    NIGHTCORE = 1 << 9
    FLASHLIGHT = 1 << 10
    AUTOPLAY = 1 << 11
    SPUNOUT = 1 << 12
    RELAX2 = 1 << 13
    PERFECT = 1 << 14
    KEY4 = 1 << 15
    KEY5 = 1 << 16
    KEY6 = 1 << 17
    KEY7 = 1 << 18
    KEY8 = 1 << 19
    KEYMOD = 1 << 20
    FADEIN = 1 << 21
    RANDOM = 1 << 22
    LASTMOD = 1 << 23
    KEY9 = 1 << 24
    KEY10 = 1 << 25
    KEY1 = 1 << 26
    KEY3 = 1 << 27
    KEY2 = 1 << 28
    SCOREV2 = 1 << 29
