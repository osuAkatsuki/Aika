import discord
from discord.ext import commands

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, msg: discord.Message) -> None:
        if msg.channel.id != self.bot.config.akatsuki['channels']['verify']:
            return

        role = msg.guild.get_role(self.bot.config.akatsuki['roles']['member'])

        if role not in msg.author.roles and msg.content == '!verify':
            await msg.author.add_roles(role)

            general = msg.guild.get_channel(
                self.bot.config.akatsuki['channels']['general'])

            faq_id = self.bot.config.akatsuki['channels']['faq']
            help_id = self.bot.config.akatsuki['channels']['help']

            await general.send('\n'.join([
                f'Welcome {msg.author.mention} to Akatsuki!',
                f'If you need help, check out <#{faq_id}>, or ask in <#{help_id}>.'
            ]))

        await msg.delete()

def setup(bot: commands.Bot):
    bot.add_cog(Verification(bot))
