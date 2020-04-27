from typing import List, Dict
import discord
from discord.ext import commands
from time import time

from objects import glob

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

        r.append(f'{seconds}s')
        return ' '.join(r)

    @commands.command(description = 'Returns the current uptime of Aika.')
    @commands.cooldown(
        glob.config['cooldowns']['default_user_count'],
        glob.config['cooldowns']['default_user_per'],
        commands.BucketType.user)
    async def uptime(self, ctx: commands.Context) -> None:
        await ctx.send(f"I've been running for **{await self.format_period(time() - glob.start_time)}**.")

    @commands.command(description = "Aika's power button.")
    @commands.is_owner()
    async def shutdown(self, ctx: commands.Context) -> None:
        await ctx.send('Night night..')

        await glob.bot.close()
        glob.shutdown = True

    @commands.command(description = 'Restrict all commands to bot owner.')
    @commands.is_owner()
    async def lock(self, ctx: commands.Context) -> None:
        if ctx.message.content != '!lock':
            await ctx.send('The `!lock` command takes no parameters, and is simply a toggle.')
            return

        glob.locked = not glob.locked

        if glob.locked:
            glob.bot.add_check(commands.is_owner().predicate)
            await ctx.send('Locked all commands.')
        else:
            glob.bot.remove_check(commands.is_owner().predicate)
            await ctx.send('Unlocked all commands.')

    # TODO: prune_user() or combine logic for a specific user wipe into prune()
    @commands.command(description = 'Remove messages in bulk.')
    @commands.has_permissions(manage_messages = True)
    async def prune(self, ctx: commands.Context) -> None:
        if len(split := ctx.message.content.split()) != 2 or not split[1].isdigit() or not (split := int(split[1])):
            await ctx.send('Invalid syntax.\n> Correct syntax: `!prune <count>`.')
            return

        await ctx.message.delete() # we don't want this in our removed list for stats
        removed: List[discord.Message] = await ctx.channel.purge(limit = split)

        # Users %
        id2count_map: Dict[int, int] = {}
        for u in (users := m.author for m in removed):
            if u.id not in id2count_map.keys():
                id2count_map[u.id] = 0
            id2count_map[u.id] += 1

        total: int = sum(id2count_map.values())
        # now change to names since it's safe:tm:
        name2perc_map = { glob.bot.get_user(k).name: (v / total) * 100 for k, v in id2count_map.items() }

        longest_name: int = max(map(len, name2perc_map))

        # TODO: Words %

        embed = discord.Embed(
            title = 'Successful prune.',
            description = f'Removed {split} message{"s" if split > 1 else ""}.',
            color = glob.config['embed_color']
        )
        embed.set_thumbnail(url = glob.config['thumbnails']['global'])
        embed.set_footer(text = f'Statistics only for data nerds.\nBeing active is no crime.\nAika v{glob.version}')
        embed.add_field(
            name = 'User frequency',
            value = '```' + '\n'.join(f'{k:<{longest_name}}{v:>8.2f}%' for k, v in name2perc_map.items()) + '```'
        )
        await ctx.send(embed = embed)

def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))
