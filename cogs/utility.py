from typing import List, Dict
import discord
from discord.ext import commands
from time import time

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def format_period(seconds: int) -> str:
        r: List[str] = []

        if (days := int(seconds / 60 / 60 / 24)):
            r.append(f'{days}d')
        seconds %= (60 * 60 * 24)

        if (hours := int(seconds / 60 / 60)):
            r.append(f'{hours}h')
        seconds %= (60 * 60)

        if (minutes := int(seconds / 60)):
            r.append(f'{minutes}m')
        seconds %= 60

        r.append(f'{seconds:.2f}s')
        return ' '.join(r)

    @commands.command(description = 'Returns the current uptime of Aika.')
    @commands.cooldown(3, 5, commands.BucketType.user)
    async def uptime(self, ctx: commands.Context) -> None:
        uptime = await self.format_period(time() - self.bot.uptime)
        await ctx.send(f"I've been running for **{uptime}**.")

    @commands.command(description = "Aika's power button.", hidden = True)
    @commands.is_owner()
    async def shutdown(self, ctx: commands.Context) -> None:
        await ctx.send('Night night..')
        await self.bot.close()

    @commands.command(description = 'Restrict all commands to bot owner.', hidden = True)
    @commands.is_owner()
    async def lock(self, ctx: commands.Context) -> None:
        # TODO: make this server-based rather than bot-based

        self.bot.locked = not self.bot.locked

        if self.bot.locked:
            self.bot.add_check(commands.is_owner().predicate)
            await ctx.send('Locked all commands.')
        else:
            self.bot.remove_check(commands.is_owner().predicate)
            await ctx.send('Unlocked all commands.')

    # TODO: prune_user() or combine logic for a specific user wipe into prune()

    @commands.command(description = 'Remove messages in bulk.', hidden = True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages = True)
    async def prune(self, ctx: commands.Context, *, count) -> None:
        if not count.isdigit():
            return await ctx.send(
                'Invalid syntax.\n**Correct syntax**: `!prune <count>`.')

        count = int(count)

        await ctx.message.delete() # we don't want this in our removed list for stats
        removed: List[discord.Message] = await ctx.channel.purge(limit = count)

        user_map: Dict[int, int] = {} # userid : message count of messages removed
        for u in (users := m.author for m in removed):
            if u.id not in user_map.keys():
                user_map[u.id] = 0
            user_map[u.id] += 1

        total: int = sum(user_map.values())
        percent_map = { # username : % of messages removed
            self.bot.get_user(k).name: (v / total) * 100 for k, v in user_map.items()
        }
        longest_name: int = max(map(len, percent_map))

        # TODO: Words %? lmao

        e = discord.Embed(
            title = 'Successful prune.',
            description = f'Removed {count} message{"s" if count > 1 else ""}.',
            color = self.bot.config.embed_color
        )
        e.set_thumbnail(url = self.bot.config.thumbnails['global'])
        e.set_footer(text = f'Statistics only for data nerds.\n' \
                             'Being active is no crime.\n' \
                            f'Aika v{self.bot.config.version}')
        e.add_field(
            name = 'User frequency',
            value = '```' + '\n'.join(f'{k:<{longest_name}}{v:>8.2f}%' for k, v in percent_map.items()) + '```'
        )
        await ctx.send(embed = e)

def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))
