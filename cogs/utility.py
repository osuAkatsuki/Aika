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
        uptime = await self.format_period(time() - glob.start_time)
        await ctx.send(f"I've been running for **{uptime}**.")

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
            return await ctx.send(
                'The `!lock` command takes no parameters, and is simply a toggle.')

        glob.locked = not glob.locked

        if glob.locked:
            glob.bot.add_check(commands.is_owner().predicate)
            await ctx.send('Locked all commands.')
        else:
            glob.bot.remove_check(commands.is_owner().predicate)
            await ctx.send('Unlocked all commands.')

    # TODO: prune_user() or combine logic for a specific user wipe into prune()
    @commands.command(description = 'Remove messages in bulk.')
    @commands.guild_only()
    @commands.has_permissions(manage_messages = True)
    async def prune(self, ctx: commands.Context) -> None:
        if len(split := ctx.message.content.split()) != 2 or not split[1].isdigit() or not (split := int(split[1])):
            return await ctx.send(
                'Invalid syntax.\n> Correct syntax: `!prune <count>`.')

        await ctx.message.delete() # we don't want this in our removed list for stats
        removed: List[discord.Message] = await ctx.channel.purge(limit = split)

        user_map: Dict[int, int] = {} # userid : message count of messages removed
        for u in (users := m.author for m in removed):
            if u.id not in user_map.keys():
                user_map[u.id] = 0
            user_map[u.id] += 1

        total: int = sum(user_map.values())
        percent_map = { # username : % of messages removed
            glob.bot.get_user(k).name: (v / total) * 100 for k, v in user_map.items()
        }
        longest_name: int = max(map(len, percent_map))

        # TODO: Words %

        e = discord.Embed(
            title = 'Successful prune.',
            description = f'Removed {split} message{"s" if split > 1 else ""}.',
            color = glob.config['embed_color']
        )
        e.set_thumbnail(url = glob.config['thumbnails']['global'])
        e.set_footer(text = f'Statistics only for data nerds.\n' \
                             'Being active is no crime.\n' \
                            f'Aika v{glob.version}')
        e.add_field(
            name = 'User frequency',
            value = '```' + '\n'.join(f'{k:<{longest_name}}{v:>8.2f}%' for k, v in percent_map.items()) + '```'
        )
        await ctx.send(embed = e)

def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))
