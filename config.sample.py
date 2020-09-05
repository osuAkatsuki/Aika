# -*- coding: utf-8 -*-

# extensions to be used on boot
initial_extensions = ('user', 'utility', 'guild')

# bot owner's discord ID.
discord_owner = 123456789012345678

# bot's discord token (for auth)
discord_token = 'your token here owo'

# filter for single whitespace-separated words in chat.
# {'single', 'word', 'matches'}
filters = {}

# filter for substring matches, no whitespace separation required.
# {'sub w-', 'ord', 'matc', 'hes'}
substring_filters = {}

# mysql database information
mysql = {
    'database': 'the_data_dungeon',
    'host': 'localhost',
    'password': 'drowssap',
    'user': 'root'
}

# Aika's version #
version = 1.0

# Thumbnails to be used throughout the program in embeds.
thumbnails = {
    'faq': 'https://link.to/faq_thumbnail.png'
}

# some controls over experience gain for users.
xp = {
    'ratelimit': 60, # how often a user can gain xp
    'range': (2, 7)
}

# replace keys .format() style with values in FAQ output.
# useful for dynamic command prefix changes and stuff.
faq_replacements = {
    'key': 'val'
}

embed_colour = 0xAC88D8 # colour for embeds
server_build = False # whether the server is running live
