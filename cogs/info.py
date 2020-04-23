from typing import Optional, Tuple, Dict, Union
import discord
from discord.ext import commands

from objects import glob

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.faq: Tuple[Dict[str, Union[int, str]]] = self._load_faq()

    def _load_faq(self) -> Tuple[Dict[str, Union[int, str]]]:
        if not (res := glob.db.fetchall('SELECT * FROM aika_faq ORDER BY id ASC')):
            raise Exception('FAQ cog enabled, but FAQ empty in database!')
        return tuple(res)

    def _add_faq(self, topic: str, title: str, content: str) -> None:
        print(f'\x1b[32mAdding new FAQ topic - {topic}\x1b[0m')
        glob.db.execute('INSERT INTO aika_faq (id, topic, title, content) VALUES (NULL, %s, %s, %s)', [topic, title, content])
        self.faq = self._load_faq() # suboptimal but so rare who cares?

    @commands.command(
        name = 'faq',
        description = 'Retrieve the answer to one of our frequently asked questions from our database.',
        aliases = ['info', 'help', 'answer']
    )
    async def get_faq(self, ctx) -> None:
        if len(split := ctx.message.content.split(' ')) != 2:
            await ctx.send('Invalid syntax.')
            return

        _type: bool = split[1].isdigit()
        if len(_faq := [x for x in self.faq if str(x['id' if _type else 'topic']) == split[1]]) and (_faq := _faq[0]):
            await ctx.send(embed = discord.Embed(
                title = _faq['title'],
                description = _faq['content']
            ))
        else:
            await ctx.send(embed = discord.Embed(
                title = 'Available topics',
                description = '\n'.join(f'**{i["id"]}**. {i["topic"]}' for i in self.faq)
            ))

    @commands.command(
        name = 'addfaq',
        description = 'Allows an administrator to add an FAQ object to the database.',
        aliases = ['newfaq'])
    @commands.has_guild_permissions(ban_members = True) # somewhat arbitrary..
    async def add_faq(self, ctx) -> None:
        # format: topic|title|content
        if len(split := ctx.message.content.split(maxsplit=1)[1].split('|')) != 3:
            await ctx.send('Invalid syntax.\n> Correct syntax: `topic|title|content`')
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
