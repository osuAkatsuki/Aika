from typing import Optional, Tuple, Dict, Union
import discord
from discord.ext import commands
from time import time

from objects import glob

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.faq: Tuple[Dict[str, Union[int, str]]] = self.load_faq()

    def load_faq(self) -> Tuple[Dict[str, Union[int, str]]]:
        if not (res := glob.db.fetchall('SELECT * FROM aika_faq ORDER BY id ASC')):
            raise Exception('\x1b[31mFAQ cog enabled, but FAQ empty in database!\x1b[0m')
        return tuple(res)

    def add_faq(self, topic: str, title: str, content: str) -> None:
        print(f'\x1b[32mAdding new FAQ topic - {topic}\x1b[0m')
        glob.db.execute('INSERT INTO aika_faq (id, topic, title, content) VALUES (NULL, %s, %s, %s)', [topic, title, content])
        self.faq = self.load_faq() # suboptimal but so rare who cares?

    # TODO: _rm_faq(), although this will be a bit weird with id & topic valid..

    @commands.command(
        description = 'Retrieve the answer to one of our frequently asked questions from our database.',
        aliases     = ['info', 'answer']
    )
    @commands.cooldown(1, 3, commands.BucketType.default) # 3s cooldown global
    @commands.cooldown(1, 6, commands.BucketType.user)    # 6s cooldown for users
    @commands.guild_only()
    async def faq(self, ctx: commands.Context) -> None:
        # TODO fix: you can do something like !faq cert 2 (if id for cert was 2) to print a callback twice.

        if len(split := list(dict.fromkeys(ctx.message.content.split(' ')))) not in range(2, 5):
            return await ctx.send(embed = discord.Embed(
                title = 'Available topics',
                description = '\n'.join(f'**{i["id"]}**. {i["topic"]}' for i in self.faq),
                color = glob.config['embed_color']
            ))

        invalid: List[Dict[str, Union[int, str]]] = []
        types: List[str] = []

        for i in split[1:]:
            types.append('id' if i.isdigit() else 'topic')
            for f in self.faq:
                if i == str(f[types[-1]]): break
            else:
                invalid.append(i)

        if invalid:
            return await ctx.send(
                f'The following callbacks could not be resolved: {", ".join(invalid)}.')

        for idx, uinput in enumerate(split[1:]):
            if len(select := [f for f in self.faq if str(f[types[idx]]) == uinput]) and (select := select[0]):
                e = discord.Embed(
                    title = select['title'],
                    description = select['content'].format(**glob.config['faq_replacements']),
                    color = glob.config['embed_color']
                )
                e.set_footer(text = f'Aika v{glob.version}')
                e.set_thumbnail(url = glob.config['thumbnails']['faq'])
                await ctx.send(embed = e)

    @commands.command(
        description = 'Allows an administrator to add an FAQ object to the database.',
        aliases     = ['newfaq'])
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members = True) # somewhat arbitrary..
    async def addfaq(self, ctx: commands.Context) -> None:
        # format: topic|title|content
        if len(split := ctx.message.content.split(maxsplit=1)[1].split('|')) != 3:
            return await ctx.send(
                'Invalid syntax.\n> Correct syntax: `topic|title|content`')

        else: split = [s.strip() for s in split]

        # topic cannot be an int or it will break id/topic search
        if split[0].isdigit():
            return await ctx.send(
                'Topic name cannot be a number (it may include them, but not be limited to just numbers).')

        if (e := len(split[0]) - 0x20) > 0:
            return await ctx.send(
                f'Your topic is {e} characters too long.')
        elif (e := len(split[1]) - 0x7f) > 0:
            return await ctx.send(
                f'Your title is {e} characters too long.')
        elif (e := len(split[2]) - 0x400) > 0:
            return await ctx.send(
                f'Your content is {e} characters too long.')
        else:
            self.add_faq(*split)

def setup(bot: commands.Bot):
    bot.add_cog(Info(bot))
