import discord
from discord.ext import commands, tasks

from datetime import datetime as dt, timezone as tz

from collections import defaultdict
from Aika import Ansi

class osu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.manage_roles.start()

    def cog_unload(self):
        self.manage_roles.cancel()

    @commands.command()
    @commands.guild_only()
    async def linkosu(self, ctx: commands.Context) -> None:
        res = self.bot.db.fetch(
            'SELECT osu_id FROM aika_users WHERE id = %s',
            [ctx.author.id]
        )

        if not (res and res['osu_id']):
            # "Unlock" the account by setting the ID to 0 instead of null
            self.bot.db.execute(
                'UPDATE aika_users SET osu_id = 0 WHERE id = %s',
                [ctx.author.id])

            await ctx.send('\n'.join([
                'Please paste the following command into #osu (or dm with Aika) ingame.',
                f'> `!vdiscord {ctx.author.id}`'
            ]))
        else:
            await ctx.send('\n'.join([
                'Your Discord has already been linked to an osu!Akatsuki account!',
                'If you would like to remove this, please contact cmyui#0425 directly.',
                f'> **https://akatsuki.pw/u/{res["osu_id"]}**'
            ]))

    @commands.command(hidden = True)
    @commands.guild_only()
    async def next_roleupdate(self, ctx: commands.Context) -> None:
        t = (self.manage_roles.next_iteration - dt.now(tz.utc)).total_seconds()
        minutes = int(t // 60)
        seconds = int(t % 60)
        await ctx.send(
            f'Next iteration in {minutes}:{seconds:02d}.')

    @tasks.loop(minutes = 15)
    async def manage_roles(self) -> None:
        await self.bot.wait_until_ready()

        akatsuki = discord.utils.get(
            self.bot.guilds, id = self.bot.config.akatsuki['id'])

        premium = discord.utils.get(akatsuki.roles, name = 'Premium')
        supporter = discord.utils.get(akatsuki.roles, name = 'Supporter')

        res = defaultdict(lambda: 0, {
            row['id']: row['privileges'] for row in self.bot.db.fetchall(
                'SELECT aika_users.id, users.privileges FROM aika_users '
                'LEFT JOIN users ON users.id = aika_users.osu_id '
                'WHERE aika_users.osu_id NOT IN (NULL, 0)'
            )
        })

        col = Ansi.LIGHT_YELLOW

        # Remove roles
        for u in filter(lambda u: premium in u.roles, akatsuki.members):
            if not res[u.id] & (1 << 23):
                print(f"{col!r}Removing {u}'s premium.{Ansi.RESET!r}")
                await u.remove_roles(premium)

        for u in filter(lambda u: supporter in u.roles, akatsuki.members):
            if not res[u.id] & (1 << 2):
                print(f"{col!r}Removing {u}'s supporter.{Ansi.RESET!r}")
                await u.remove_roles(supporter)

        # Add roles
        no_role = lambda u: not any(r in u.roles for r in {supporter, premium})
        for u in filter(lambda u: u.id in res and no_role(u), akatsuki.members):
            if res[u.id] & (1 << 23):
                print(f"{col!r}Adding {u}'s premium.{Ansi.RESET!r}")
                await u.add_roles(premium)
            elif res[u.id] & (1 << 2):
                print(f"{col!r}Adding {u}'s supporter.{Ansi.RESET!r}")
                await u.add_roles(supporter)

def setup(bot: commands.Bot):
    bot.add_cog(osu(bot))
