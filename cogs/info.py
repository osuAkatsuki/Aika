from typing import Optional, Tuple, Dict, Union
import discord
from discord.ext import commands
from time import time

from objects import glob

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.faq: Tuple[Dict[str, Union[int, str]]] = self._load_faq()

    def _load_faq(self) -> Tuple[Dict[str, Union[int, str]]]:
        if not (res := glob.db.fetchall('SELECT * FROM aika_faq ORDER BY id ASC')):
            raise Exception('\x1b[31mFAQ cog enabled, but FAQ empty in database!\x1b[0m')
        return tuple(res)

    def _add_faq(self, topic: str, title: str, content: str) -> None:
        print(f'\x1b[32mAdding new FAQ topic - {topic}\x1b[0m')
        glob.db.execute('INSERT INTO aika_faq (id, topic, title, content) VALUES (NULL, %s, %s, %s)', [topic, title, content])
        self.faq = self._load_faq() # suboptimal but so rare who cares?

    # TODO: _rm_faq(), although this will be a bit weird with id & topic valid..

    @commands.cooldown(1, 3, commands.BucketType.default) # 3s cooldown global
    @commands.cooldown(1, 6, commands.BucketType.user)    # 6s cooldown for users
    @commands.command(
        description = 'Retrieve the answer to one of our frequently asked questions from our database.',
        aliases     = ['info', 'help', 'answer']
    )
    async def faq(self, ctx: commands.Context) -> None:
        # TODO fix: you can do something like !faq cert 2 (if id for cert was 2) to print a callback twice.

        if len(split := list(dict.fromkeys(ctx.message.content.split(' ')))) not in range(2, 5):
            await ctx.send(embed = discord.Embed(
                title = 'Available topics',
                description = '\n'.join(f'**{i["id"]}**. {i["topic"]}' for i in self.faq)
            ))
            return

        invalid: List[Dict[str, Union[int, str]]] = []
        types: List[str] = []

        for i in split[1:]:
            types.append('id' if i.isdigit() else 'topic')
            for f in self.faq:
                if i == str(f[types[-1]]): break
            else:
                invalid.append(i)

        if invalid:
            await ctx.send(f'The following callbacks could not be resolved: {", ".join(invalid)}.')
            return

        for idx, uinput in enumerate(split[1:]):
            if len(select := [f for f in self.faq if str(f[types[idx]]) == uinput]) and (select := select[0]):
                embed = discord.Embed(
                    title = select['title'],
                    description = select['content'].format(**glob.config['faq_replacements'])
                )
                embed.set_footer(text = f'Aika v{glob.version}')
                embed.set_thumbnail(url = glob.config['thumbnails']['faq'])
                await ctx.send(embed = embed)

    @commands.command(
        description = 'Allows an administrator to add an FAQ object to the database.',
        aliases     = ['newfaq'])
    @commands.has_guild_permissions(ban_members = True) # somewhat arbitrary..
    async def addfaq(self, ctx: commands.Context) -> None:
        # format: topic|title|content
        if len(split := ctx.message.content.split(maxsplit=1)[1].split('|')) != 3:
            await ctx.send('Invalid syntax.\n> Correct syntax: `topic|title|content`')
            return
        else: split = [s.strip() for s in split]

        # topic cannot be an int or it will break id/topic search
        if split[0].isdigit():
            await ctx.send('Topic name cannot be a number (it may include them, but not be limited to just numbers).')
            return

        # Handle separately for premium feel i guess..
        if len(split[0]) > 0x20: # 32 (2*16)
            await ctx.send(f'Your topic is {len(split[0]) - 0x20} characters too long.')
            return
        elif len(split[1]) > 0x7f: # 127 (7*16 + 15*1)
            await ctx.send(f'Your title is {len(split[1]) - 0x7f} characters too long.')
            return
        elif len(split[2]) > 0x400: # 1024 (4*256)
            await ctx.send(f'Your content is {len(split[2]) - 0x400} characters too long.')
            return
        else: self._add_faq(*split)

def setup(bot: commands.Bot):
    bot.add_cog(Info(bot))
