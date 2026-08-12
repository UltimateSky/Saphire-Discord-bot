import discord
from discord.ext import commands
from discord import app_commands
import database
import datetime
import re
import asyncio

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_cooldown = {}

    def build_regex_pattern(self, word):
        pattern_parts = []
        for char in word:
            if char.isalnum():
                pattern_parts.append(f"{re.escape(char)}+[\\W_]*")
            else:
                pattern_parts.append(re.escape(char))
        return r"\b" + "".join(pattern_parts)

    async def log_action(self, guild, action, target, moderator, reason):
        channel_id = await database.get_config(guild.id, 'log_channel_id')
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"🛡️ Mod Action: {action}",
                    color=discord.Color.dark_red(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                embed.add_field(name="Target", value=f"{target.mention} ({target.id})", inline=False)
                embed.add_field(name="Moderator", value=moderator.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    async def apply_warning(self, message: discord.Message, reason: str):
        warnings_count = await database.add_warning(message.guild.id, message.author.id)
        
        try:
            embed = discord.Embed(
                title="⚠️ Peringatan Moderasi",
                description=f"Pesan Anda di **{message.guild.name}** dihapus.\n**Alasan:** {reason}\n**Total Peringatan:** {warnings_count}/3",
                color=discord.Color.red()
            )
            await message.author.send(embed=embed)
        except discord.Forbidden:
            await message.channel.send(f"⚠️ {message.author.mention}, {reason} (Peringatan {warnings_count}/3)", delete_after=10.0)

        if warnings_count >= 3:
            try:
                timeout_duration = datetime.timedelta(hours=1)
                await message.author.timeout(timeout_duration, reason="Mencapai batas 3 peringatan otomatis.")
                await message.channel.send(f"🚫 {message.author.mention} telah di-timeout selama 1 jam karena mencapai batas peringatan.")
                await database.clear_warnings(message.guild.id, message.author.id)
                await self.log_action(message.guild, "Auto-Timeout (3 Warnings)", message.author, self.bot.user, reason)
            except discord.Forbidden:
                await message.channel.send(f"⚠️ {message.author.mention} mencapai batas peringatan, tapi saya tidak memiliki izin untuk melakukan timeout.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
            
        bot_enabled = await database.get_config(message.guild.id, "bot_enabled")
        if bot_enabled == 0:
            return
            
        automod_enabled = await database.get_config(message.guild.id, "automod_enabled")
        if automod_enabled == 0:
            return
            
        content_lower = message.content.lower()
        is_admin = message.author.guild_permissions.administrator

        anti_link_enabled = await database.get_config(message.guild.id, "anti_link_enabled")
        anti_spam_enabled = await database.get_config(message.guild.id, "anti_spam_enabled")
        anti_toxic_enabled = await database.get_config(message.guild.id, "anti_toxic_enabled")

        # 1. Anti-Link (Discord Invites)
        if anti_link_enabled != 0 and not is_admin and ("discord.gg/" in content_lower or "discord.com/invite/" in content_lower):
            try: await message.delete()
            except discord.Forbidden: pass
            await self.apply_warning(message, "Dilarang mengirim link invite server Discord lain!")
            return

        # 2. Anti-Spam
        if anti_spam_enabled != 0 and not is_admin:
            author_id = message.author.id
            guild_id = message.guild.id
            now = datetime.datetime.now().timestamp()
            
            if (guild_id, author_id) not in self.spam_cooldown:
                self.spam_cooldown[(guild_id, author_id)] = []
                
            timestamps = self.spam_cooldown[(guild_id, author_id)]
            timestamps.append(now)
            
            # Keep timestamps within last 5 seconds
            timestamps = [t for t in timestamps if now - t <= 5]
            self.spam_cooldown[(guild_id, author_id)] = timestamps
            
            if len(timestamps) > 5: # Limit: 5 messages per 5 seconds
                try: await message.delete()
                except discord.Forbidden: pass
                # Clear cooldown to prevent multiple warnings at once
                self.spam_cooldown[(guild_id, author_id)] = []
                await self.apply_warning(message, "Tolong jangan melakukan spam!")
                return

        # 3. Anti-Toxic
        if anti_toxic_enabled != 0:
            bad_words = await database.get_bad_words(message.guild.id)
            if bad_words:
                content_normalized = content_lower.translate(str.maketrans('4103@', 'aioea'))
                found_toxic = False
                
                for bw in bad_words:
                    bw_clean = bw.strip().lower()
                    if bw_clean in content_normalized or bw_clean in content_lower:
                        found_toxic = True
                        break
                        
                if found_toxic:
                    try: await message.delete()
                    except discord.Forbidden: pass
                    await self.apply_warning(message, "Menggunakan kata-kata kasar atau tidak pantas.")
                    return

    # --- Warning Management ---
    @app_commands.command(name="checkwarnings", description="Admin: Cek jumlah peringatan member.")
    @app_commands.checks.has_permissions(administrator=True)
    async def check_warnings(self, interaction: discord.Interaction, member: discord.Member):
        count = await database.get_warnings(interaction.guild_id, member.id)
        await interaction.response.send_message(f"Member {member.mention} saat ini memiliki **{count}** peringatan.", ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Admin: Putihkan/hapus semua peringatan dari member.")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        await database.clear_warnings(interaction.guild_id, member.id)
        await interaction.response.send_message(f"✅ Peringatan untuk {member.mention} berhasil diputihkan menjadi 0.", ephemeral=True)

    # --- Bad Word Management ---
    @app_commands.command(name="addbadword", description="Admin: Tambahkan kata kotor ke daftar filter.")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_badword(self, interaction: discord.Interaction, word: str):
        await database.add_bad_word(interaction.guild_id, word.lower())
        await interaction.response.send_message(f"✅ Kata `{word}` berhasil ditambahkan ke filter.", ephemeral=True)

    @app_commands.command(name="removebadword", description="Admin: Hapus kata dari daftar filter.")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_badword(self, interaction: discord.Interaction, word: str):
        await database.remove_bad_word(interaction.guild_id, word.lower())
        await interaction.response.send_message(f"✅ Kata `{word}` berhasil dihapus dari filter.", ephemeral=True)

    @app_commands.command(name="listbadword", description="Admin: Lihat daftar kata kotor yang difilter.")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_badword(self, interaction: discord.Interaction):
        words = await database.get_bad_words(interaction.guild_id)
        if words:
            word_list = ", ".join(words)
            await interaction.response.send_message(f"📝 **Daftar Kata Terlarang:**\n{word_list}", ephemeral=True)
        else:
            await interaction.response.send_message("📝 Belum ada kata terlarang yang diatur.", ephemeral=True)

    # --- Moderation Tools ---
    @app_commands.command(name="clear", description="Admin: Hapus sejumlah pesan di channel ini.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear_messages(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"✅ Berhasil menghapus {len(deleted)} pesan.")

    @app_commands.command(name="purgeuser", description="Admin: Hapus pesan dari member tertentu di semua channel.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_user(self, interaction: discord.Interaction, member: discord.Member, limit: int = 100):
        await interaction.response.defer(ephemeral=True)
        
        total_deleted = 0
        
        def is_member(m):
            return m.author.id == member.id
            
        for channel in interaction.guild.text_channels:
            try:
                deleted = await channel.purge(limit=limit, check=is_member)
                total_deleted += len(deleted)
            except (discord.Forbidden, discord.HTTPException):
                continue
                
        await interaction.followup.send(f"✅ Berhasil menghapus total {total_deleted} pesan dari {member.mention} di semua channel (Mengecek {limit} pesan terakhir/channel).")
        await self.log_action(interaction.guild, "Purge User (Global)", member, interaction.user, f"Menghapus {total_deleted} pesan di semua channel.")

    @app_commands.command(name="timeout", description="Admin: Timeout member sementara.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_member(self, interaction: discord.Interaction, member: discord.Member, menit: int, alasan: str = "Tidak ada alasan"):
        duration = datetime.timedelta(minutes=menit)
        await member.timeout(duration, reason=alasan)
        await interaction.response.send_message(f"✅ {member.mention} berhasil di-timeout selama {menit} menit. Alasan: {alasan}")
        await self.log_action(interaction.guild, f"Timeout ({menit}m)", member, interaction.user, alasan)

    @app_commands.command(name="kick", description="Admin: Kick member dari server.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_member(self, interaction: discord.Interaction, member: discord.Member, alasan: str = "Tidak ada alasan"):
        await member.kick(reason=alasan)
        await interaction.response.send_message(f"✅ {member.mention} berhasil di-kick. Alasan: {alasan}")
        await self.log_action(interaction.guild, "Kick", member, interaction.user, alasan)

    @app_commands.command(name="ban", description="Admin: Ban member dari server.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_member(self, interaction: discord.Interaction, member: discord.Member, alasan: str = "Tidak ada alasan"):
        await member.ban(reason=alasan)
        await interaction.response.send_message(f"✅ {member.mention} berhasil di-ban. Alasan: {alasan}")
        await self.log_action(interaction.guild, "Ban", member, interaction.user, alasan)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
