import discord
from discord.ext import commands
from discord import app_commands
import database
import datetime

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_log_channel(self, guild: discord.Guild):
        channel_id = await database.get_config(guild.id, 'log_channel_id')
        if channel_id:
            return guild.get_channel(channel_id)
        return None

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
            
        log_channel = await self.get_log_channel(message.guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted (Ghost Tracker)",
            description=f"**Author:** {message.author.mention} ({message.author.name})\n**Channel:** {message.channel.mention}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        content = message.content if message.content else "*No text content*"
        # Discord embed fields have a max length of 1024 characters
        if len(content) > 1024:
            content = content[:1020] + "..."
            
        embed.add_field(name="Content", value=content, inline=False)
        
        if message.attachments:
            embed.add_field(name="Attachments", value=", ".join([a.url for a in message.attachments]), inline=False)

        embed.set_footer(text=f"User ID: {message.author.id} | Message ID: {message.id}")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print("Missing permissions to send message in log channel.")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content:
            return

        log_channel = await self.get_log_channel(before.guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"**Author:** {before.author.mention} ({before.author.name})\n**Channel:** {before.channel.mention}\n[Jump to Message]({after.jump_url})",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        before_content = before.content or "*Empty*"
        after_content = after.content or "*Empty*"
        
        if len(before_content) > 1024: before_content = before_content[:1020] + "..."
        if len(after_content) > 1024: after_content = after_content[:1020] + "..."

        embed.add_field(name="Before", value=before_content, inline=False)
        embed.add_field(name="After", value=after_content, inline=False)
        embed.set_footer(text=f"User ID: {before.author.id} | Message ID: {after.id}")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print("Missing permissions to send message in log channel.")

    @app_commands.command(name="setlogchannel", description="Admin: Set channel untuk menyimpan log pesan yang dihapus dan diedit.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(interaction.guild_id, 'log_channel_id', channel.id)
        await interaction.response.send_message(f"✅ Channel log berhasil diatur ke {channel.mention}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Logger(bot))
