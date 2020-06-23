# extensions to be used on boot
initial_extensions = [
    'user', 'utility', 'info'
]

# command prefix for all commands.
command_prefix = '!'

# bot owner's discord ID.
discord_owner = 123456789012345678

# bot's discord token (for auth)
discord_token = 'your token here owo'

# filter for single whitespace-separated words in chat.
filters = {'single', 'word', 'matches'}

# filter for substring matches, no whitespace separation required.
substring_filters = {'sub w-', 'ord', 'matc', 'hes'}

# mysql database information
mysql = {
    'database': '',
    'host': '',
    'password': '',
    'user': ''
}

# Aika's version #
version = 3.0

# Thumbnails to be used throughout the program in embeds.
thumbnails = {
    'faq': 'https://link.to/faq_thumbnail.png'
}

# some controls over experience gain for users.
xp = {
    'ratelimit': 60, # how often a user can gain xp
    'range': {
        'start': 2, # min they can gain at random
        'stop':  7  # max they can gain at random
    }
}

# replace keys .format() style with values in FAQ output.
# useful for dynamic command prefix changes and stuff.
faq_replacements = {
    'key': 'val'
}

embed_color = 0xAC88D8 # colour for embeds
server_build = False
