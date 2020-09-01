# -*- coding: utf-8 -*-

from discord.ext import commands

from utils import akatsuki_only
from objects.aika import ContextWrap, Aika

class Tourney(commands.Cog):
    def __init__(self, bot: Aika):
        self.bot = bot
        self.t_roles = self.bot.config.akatsuki['roles']['tourney']
        self.ev_manager = self.t_roles.pop('manager')

    @commands.command(aliases = ['ev'])
    @commands.guild_only()
    @commands.check(akatsuki_only)
    async def event(self, ctx: ContextWrap) -> None:
        # A command for Haruki, our lovely event manager.
        # Syntax: !ev [add/rm] [@role] [@user1 @user2 ...]
        if self.ev_manager not in {r.id for r in ctx.author.roles}:
            return # No perms :(

        if len(s := ctx.message.content.lower().split(' ', 2)) != 3 \
        or (role := ctx.message.role_mentions[0]).id not in self.t_roles.values() \
        or len(ctx.message.role_mentions) != 1 or not ctx.message.mentions \
        or s[1] not in {'add', 'rm'}: return await ctx.send(
            'Incorrect syntax.\n'
            '> Correct syntax: `!ev [add/rm] [@trole] [@user1 @user2 ...]`'
        )

        reason = f"{'Added' if (adding := s[1] == 'add') else 'Removed'} via !ev"

        for u in ctx.message.mentions:
            await (u.add_roles if adding else u.remove_roles)(role, reason = reason)

        await ctx.send(f"Successfully {'added' if adding else 'removed'} roles.")

def setup(bot: Aika):
    bot.add_cog(Tourney(bot))
