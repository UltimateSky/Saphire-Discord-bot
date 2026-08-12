import discord
from discord.ext import commands
from discord import app_commands
import database
import asyncio

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Tutup Tiket", style=discord.ButtonStyle.danger, custom_id="persistent_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Menutup tiket dalam 5 detik dan menyimpan transkrip...")
        
        try:
            # Ambil history chat
            messages = [m async for m in interaction.channel.history(limit=500, oldest_first=True)]
            transcript_lines = []
            for m in messages:
                timestamp = m.created_at.strftime('%Y-%m-%d %H:%M:%S')
                transcript_lines.append(f"[{timestamp}] {m.author.name}: {m.content}")
            transcript_text = "\n".join(transcript_lines)
            
            await database.save_transcript(interaction.guild_id, interaction.user.id, interaction.channel.name, transcript_text)
        except Exception as e:
            print(f"Failed to save transcript: {e}")
            
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Buka Tiket", style=discord.ButtonStyle.primary, custom_id="persistent_ticket_button")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        category_id = await database.get_config(interaction.guild_id, 'ticket_category_id')
        category = interaction.guild.get_channel(category_id) if category_id else None

        # Set permissions for private ticket channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        
        embed = discord.Embed(
            title=f"Tiket Dukungan: {interaction.user.name}",
            description="Halo! Silakan jelaskan masalah atau keluhan Anda di sini.\nTim moderator akan segera membantu.\n\nKlik tombol di bawah untuk menutup tiket ini.",
            color=discord.Color.blue()
        )
        
        view = CloseTicketView()
        await channel.send(f"{interaction.user.mention} Tiket berhasil dibuat!", embed=embed, view=view)
        await interaction.response.send_message(f"✅ Tiket Anda telah dibuat: {channel.mention}", ephemeral=True)

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent views for buttons to work after bot restarts
        self.bot.add_view(TicketButton())
        self.bot.add_view(CloseTicketView())

    # --- Auto Role ---
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role_id = await database.get_config(member.guild.id, 'auto_role_id')
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    print("Missing permissions to give role.")

    @app_commands.command(name="setautorole", description="Admin: Atur role yang otomatis diberikan ke member baru.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_autorole(self, interaction: discord.Interaction, role: discord.Role):
        await database.set_config(interaction.guild_id, 'auto_role_id', role.id)
        await interaction.response.send_message(f"✅ Auto-role diatur ke {role.mention}", ephemeral=True)

    # --- Ticket System ---
    @app_commands.command(name="setticketcategory", description="Admin: Atur kategori/folder letak pembuatan channel tiket.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_ticket_category(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        await database.set_config(interaction.guild_id, 'ticket_category_id', category.id)
        await interaction.response.send_message(f"✅ Kategori tiket diatur ke **{category.name}**", ephemeral=True)

    @app_commands.command(name="setupticket", description="Admin: Kirimkan pesan dengan tombol untuk membuka tiket.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_ticket(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📩 Pusat Bantuan & Laporan",
            description="Jika Anda memiliki pertanyaan, masalah, atau ingin melaporkan sesuatu ke Admin secara privat, silakan klik tombol **Buka Tiket** di bawah ini.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed, view=TicketButton())
        await interaction.response.send_message("Panel tiket berhasil dibuat.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))
