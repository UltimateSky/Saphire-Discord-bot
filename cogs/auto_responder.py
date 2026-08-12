import discord
from discord.ext import commands
import database

class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
            
        bot_enabled = await database.get_config(message.guild.id, "bot_enabled")
        if bot_enabled == 0:
            return

        # Simple auto-responder matching
        content_lower = message.content.lower().strip()
        custom_commands = await database.get_custom_commands(message.guild.id)
        
        for cmd_id, trigger, response in custom_commands:
            if content_lower == trigger:
                try:
                    await message.channel.send(response.replace("{user}", message.author.mention))
                except discord.Forbidden:
                    pass
                break # Only trigger one

async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
