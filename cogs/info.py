# -*- coding: utf-8 -*-

from typing import Tuple, Dict, Union
import discord
from discord.ext import commands

from Aika import Ansi, Leaderboard, ContextWrap
from utils import akatsuki_only

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.faq: Tuple[Dict[str, Union[int, str]]] = self.load_faq()

    def load_faq(self) -> Tuple[Dict[str, Union[int, str]]]:
        if not (res := self.bot.db.fetchall('SELECT * FROM aika_faq ORDER BY id ASC')):
            raise Exception('FAQ cog enabled, but FAQ empty in database!')
        return tuple(res)

    def add_faq(self, topic: str, title: str, content: str) -> None:
        print(f'{Ansi.GREEN!r}Adding new FAQ topic - {topic}{Ansi.RESET!r}')
        self.bot.db.execute(
            'INSERT INTO aika_faq (id, topic, title, content) '
            'VALUES (NULL, %s, %s, %s)', [topic, title, content])
        self.faq = self.load_faq() # suboptimal but so rare who cares?

    # TODO: _rm_faq(), although this will be a bit weird with id & topic valid..

    @commands.command(aliases = ['info', 'answer'])
    @commands.guild_only()
    @commands.check(akatsuki_only)
    @commands.cooldown(1, 3, commands.BucketType.default) # 3s cooldown global
    @commands.cooldown(1, 6, commands.BucketType.user)    # 6s cooldown for users
    async def faq(self, ctx: ContextWrap) -> None:
        # TODO fix: you can do something like !faq cert 2 (if id for cert was 2) to print a callback twice.
        if len(split := list(dict.fromkeys(ctx.message.content.split(' ')))) not in range(2, 5):
            if not (res := self.bot.db.fetchall(
                'SELECT topic title, title value FROM aika_faq')):
                return await ctx.send(
                    'No FAQ callbacks could be fetched from MySQL.')

            e = discord.Embed(
                colour = self.bot.config.embed_colour,
                title = 'Availble topics',
                description = '\n'.join([
                    f"You'll need to provide an id or topic (accepts multiple delimited by space; max 4).",
                    f'**Syntax**: `!{ctx.invoked_with} <id/topic>`',
                    repr(Leaderboard(res))
                ])
            )

            e.set_footer(text = f'Aika v{self.bot.config.version}')
            return await ctx.send(embed = e)

        invalid: List[Dict[str, Union[int, str]]] = []
        types: List[str] = []

        # TODO: man this is so damn ugly
        for i in split[1:]:
            types.append('id' if i.isdecimal() else 'topic')
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
                    description = select['content'].format(**self.bot.config.faq_replacements),
                    colour = self.bot.config.embed_colour
                )
                e.set_footer(text = f'Aika v{self.bot.config.version}')
                e.set_thumbnail(url = self.bot.config.thumbnails['faq'])
                await ctx.send(embed = e)

    @commands.command(aliases = ['newfaq'], hidden = True)
    @commands.guild_only()
    @commands.check(akatsuki_only)
    @commands.has_guild_permissions(ban_members = True) # somewhat arbitrary..
    async def addfaq(self, ctx: ContextWrap, *, new_faq) -> None:
        # format: topic|title|content
        if len(split := new_faq.split('|')) != 3:
            return await ctx.send('\n'.join([
                'Invalid syntax.',
                '> Correct syntax: `topic|title|content`'
            ]))

        split = [s.strip() for s in split]

        # topic cannot be an int or it will break id/topic search
        if split[0].isdecimal():
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

        self.add_faq(*split)
        await ctx.send('New FAQ topic added!')

def setup(bot: commands.Bot):
    bot.add_cog(Info(bot))
