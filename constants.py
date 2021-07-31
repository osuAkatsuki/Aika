# -*- coding: utf-8 -*-

import re

regexes = {
    #'beatmap_url': re.compile(r'(?:https?://)?(?:www.)?akatsuki.pw/(?:b|beatmaps)/(?P<bid>[0-9]{1,10})/?'),
    #'beatmapset_url': re.compile(r'(?:https?://)?(?:www.)?akatsuki.pw/(?:s|beatmapsets)/(?P<bsid>[0-9]{1,10})/?'),
    'song_name': re.compile(r'(?P<artist>.+) - (?P<sn>.+)\[(?P<diff>.+)\]'),
    'cmd_prefix': re.compile(r'^[\x21-\x3F\x41-\x7E]{1,8}$'),
    'duration': re.compile(r'^(?P<duration>[1-9]\d*)(?P<period>s|m|h|d|w)?$'),
    'mention': re.compile(r'<@!?\d{18,20}>')
}
