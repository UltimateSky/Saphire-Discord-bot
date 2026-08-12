import discord
from discord.ext import commands
from discord import app_commands
import database
import random

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cooldown to prevent spamming XP (store user IDs)
        self.xp_cooldown = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
            
        # Give random XP between 5 and 15
        xp_gain = random.randint(5, 15)
        new_xp, new_level, leveled_up = await database.add_user_xp(message.guild.id, message.author.id, xp_gain)
        
        if leveled_up:
            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"Selamat {message.author.mention}, Anda baru saja naik ke **Level {new_level}**! Teruslah aktif mengobrol.",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await message.channel.send(embed=embed)

    @app_commands.command(name="rank", description="Melihat level dan XP Anda atau pengguna lain.")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        if target.bot:
            await interaction.response.send_message("Bot tidak memiliki level/XP.", ephemeral=True)
            return
            
        xp, level = await database.get_user_xp(interaction.guild_id, target.id)
        next_level_xp = (level * 10) ** 2
        
        embed = discord.Embed(
            title=f"🏆 Kartu Peringkat: {target.display_name}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="XP", value=f"**{xp} / {next_level_xp}**", inline=True)
        
        # Simple progress bar visualization
        progress = xp / next_level_xp
        filled_blocks = int(progress * 10)
        empty_blocks = 10 - filled_blocks
        progress_bar = "🟩" * filled_blocks + "⬜" * empty_blocks
        
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Melihat 10 pengguna dengan level tertinggi di server ini.")
    async def leaderboard(self, interaction: discord.Interaction):
        top_users = await database.get_leaderboard(interaction.guild_id, limit=10)
        if not top_users:
            await interaction.response.send_message("Belum ada data XP di server ini.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="📊 Papan Peringkat Server (Leaderboard)",
            color=discord.Color.gold()
        )
        
        desc = ""
        for i, (user_id, xp, level) in enumerate(top_users):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"Unknown User ({user_id})"
            
            medal = "🏅"
            if i == 0: medal = "🥇"
            elif i == 1: medal = "🥈"
            elif i == 2: medal = "🥉"
                
            desc += f"{medal} **#{i+1}** {name} — **Lvl {level}** ({xp} XP)\n"
            
        embed.description = desc
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
