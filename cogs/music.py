import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
import os
import re
from typing import Optional
from dotenv import load_dotenv
import database

load_dotenv()

# Spotify support via yt-dlp (no Premium required)
SPOTIFY_ENABLED = True  # yt-dlp handles Spotify natively

try:
    import lyricsgenius
    GENIUS_TOKEN = os.getenv("GENIUS_API_TOKEN", "")
    if GENIUS_TOKEN:
        genius = lyricsgenius.Genius(GENIUS_TOKEN, remove_section_headers=True, timeout=15)
        genius.verbose = False
    else:
        genius = None
except Exception as e:
    print(f"[Genius] {e}")
    genius = None

from .music_player import (
    Track, GuildMusicState,
    search_youtube, fetch_stream_url, fetch_playlist_tracks, fetch_spotify_tracks,
    FFMPEG_OPTIONS
)

MUSIC_STATES: dict[int, GuildMusicState] = {}

def get_state(guild_id: int) -> GuildMusicState:
    if guild_id not in MUSIC_STATES:
        MUSIC_STATES[guild_id] = GuildMusicState()
    return MUSIC_STATES[guild_id]

def is_spotify_url(url: str) -> bool:
    return "open.spotify.com" in url


class MusicControlView(discord.ui.View):
    def __init__(self, guild_id: int, cog):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.cog = cog

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, custom_id="music_pause")
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(self.guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await interaction.response.send_message("⏸️ Paused.", ephemeral=True)
        elif state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("Tidak ada lagu yang diputar.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary, custom_id="music_skip")
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(self.guild_id)
        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("Tidak ada lagu yang diputar.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music_stop")
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(self.guild_id)
        state.loop_mode = "off"
        state.clear()
        if state.voice_client:
            state.voice_client.stop()
            await state.voice_client.disconnect()
            state.voice_client = None
        await interaction.response.send_message("⏹️ Stopped & disconnected.", ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music_shuffle")
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        import random
        state = get_state(self.guild_id)
        if state.queue:
            random.shuffle(state.queue)
            await interaction.response.send_message("🔀 Queue shuffled!", ephemeral=True)
        else:
            await interaction.response.send_message("Queue kosong.", ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── Internal ──────────────────────────────────────────────
    async def _play_next(self, guild: discord.Guild):
        state = get_state(guild.id)
        if not state.voice_client:
            return

        if state.loop_mode == "single" and state.current:
            next_track = state.current
        elif state.queue:
            next_track = state.queue.pop(0)
            if state.loop_mode == "queue" and state.current:
                state.queue.append(state.current)
        else:
            state.current = None
            if not state.is_247:
                await asyncio.sleep(180)
                if not state.current and state.voice_client and state.voice_client.is_connected():
                    await state.voice_client.disconnect()
                    state.voice_client = None
            return

        stream_url = await fetch_stream_url(next_track.webpage_url)
        if not stream_url:
            await self._play_next(guild)
            return

        next_track.stream_url = stream_url
        state.current = next_track
        state.start_time = time.time()

        # Log to database
        try:
            await database.log_music(
                guild_id=guild.id,
                user_id=next_track.requester.id,
                username=str(next_track.requester),
                song_title=next_track.title,
                song_url=next_track.webpage_url,
                duration=next_track.duration or 0
            )
        except Exception as e:
            print(f"[MusicLog] {e}")

        def after_playing(error):
            if error:
                print(f"[Player Error] {error}")
            asyncio.run_coroutine_threadsafe(self._play_next(guild), self.bot.loop)

        try:
            source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=state.volume)
            state.voice_client.play(source, after=after_playing)
        except Exception as e:
            print(f"[FFmpeg Error] {e}")
            await self._play_next(guild)

    async def _ensure_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        state = get_state(interaction.guild_id)
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Kamu harus join voice channel dulu!", ephemeral=True)
            return None
        ch = interaction.user.voice.channel
        if state.voice_client and state.voice_client.is_connected():
            if state.voice_client.channel != ch:
                await state.voice_client.move_to(ch)
        else:
            try:
                state.voice_client = await ch.connect()
            except Exception as e:
                await interaction.followup.send(f"❌ Gagal connect: {e}", ephemeral=True)
                return None
        return state.voice_client

    def _now_playing_embed(self, state: GuildMusicState) -> discord.Embed:
        t = state.current
        elapsed = state.get_elapsed()
        bar = t.progress_bar(elapsed)
        loop_icons = {"off": "➡️", "single": "🔂", "queue": "🔁"}
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**[{t.title}]({t.webpage_url})**",
            color=0x1DB954
        )
        embed.add_field(
            name="Progress",
            value=f"`{self._fmt(elapsed)}` {bar} `{t.format_duration()}`",
            inline=False
        )
        embed.add_field(name="Requester", value=t.requester.mention, inline=True)
        embed.add_field(name="Loop", value=loop_icons.get(state.loop_mode, "➡️"), inline=True)
        embed.add_field(name="Volume", value=f"{int(state.volume*100)}%", inline=True)
        if t.thumbnail:
            embed.set_thumbnail(url=t.thumbnail)
        embed.set_footer(text="🎶 Professional Music Bot")
        return embed

    def _fmt(self, seconds: int) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    # ─── Commands ──────────────────────────────────────────────

    @app_commands.command(name="playsong", description="Play lagu dari YouTube (nama/URL) atau playlist YouTube.")
    @app_commands.describe(song="Nama lagu, URL YouTube, atau URL playlist YouTube")
    async def playsong(self, interaction: discord.Interaction, song: str):
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if not vc:
            return
        state = get_state(interaction.guild_id)

        is_playlist = "playlist" in song or "list=" in song
        if is_playlist and song.startswith("http"):
            await interaction.followup.send("📋 Loading playlist dari YouTube...", ephemeral=False)
            tracks_data = await fetch_playlist_tracks(song)
            if not tracks_data:
                await interaction.followup.send("❌ Gagal load playlist.", ephemeral=True)
                return
            added = 0
            for td in tracks_data:
                tr = Track(
                    title=td["title"], url=td["url"],
                    duration=td.get("duration", 0),
                    thumbnail=td.get("thumbnail", ""),
                    webpage_url=td["webpage_url"],
                    requester=interaction.user
                )
                state.queue.append(tr)
                added += 1
            embed = discord.Embed(
                title="📋 Playlist Added",
                description=f"Berhasil menambahkan **{added} lagu** ke queue.",
                color=0x1DB954
            )
            await interaction.followup.send(embed=embed)
        else:
            data = await search_youtube(song)
            if not data:
                await interaction.followup.send("❌ Lagu tidak ditemukan.", ephemeral=True)
                return
            tr = Track(
                title=data.get("title", "Unknown"),
                url=data.get("url", ""),
                duration=data.get("duration", 0),
                thumbnail=data.get("thumbnail", ""),
                webpage_url=data.get("webpage_url", ""),
                requester=interaction.user
            )
            state.queue.append(tr)
            if state.current:
                embed = discord.Embed(
                    title="✅ Added to Queue",
                    description=f"**[{tr.title}]({tr.webpage_url})**",
                    color=0x1DB954
                )
                embed.add_field(name="Duration", value=tr.format_duration(), inline=True)
                embed.add_field(name="Position", value=f"#{len(state.queue)}", inline=True)
                if tr.thumbnail:
                    embed.set_thumbnail(url=tr.thumbnail)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"▶️ Loading **{tr.title}**...")

        if not state.current:
            await self._play_next(interaction.guild)

    @app_commands.command(name="playlist", description="Play album/playlist dari Spotify atau YouTube.")
    @app_commands.describe(url="URL playlist/album Spotify atau YouTube")
    async def playlist_cmd(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if not vc:
            return
        state = get_state(interaction.guild_id)

        if is_spotify_url(url):
            await interaction.followup.send("🔍 Resolving Spotify tracks via yt-dlp...")
            tracks_data = await fetch_spotify_tracks(url)
            if not tracks_data:
                await interaction.followup.send("❌ Gagal load dari Spotify. Pastikan URL valid dan playlist/album publik.", ephemeral=True)
                return
            msg = await interaction.channel.send(f"⏳ Loading **{len(tracks_data)}** lagu dari Spotify... (0/{len(tracks_data)})")
            added = 0
            for i, td in enumerate(tracks_data[:100]):
                tr = Track(
                    title=td["title"],
                    url=td.get("url", ""),
                    duration=td.get("duration", 0),
                    thumbnail=td.get("thumbnail", ""),
                    webpage_url=td.get("webpage_url", td.get("url", "")),
                    requester=interaction.user
                )
                state.queue.append(tr)
                added += 1
                if not state.current:
                    await self._play_next(interaction.guild)
                if (i + 1) % 10 == 0:
                    try:
                        await msg.edit(content=f"⏳ Loading Spotify... ({i+1}/{len(tracks_data)})")
                    except:
                        pass
            await msg.edit(content=f"✅ Berhasil load **{added}** lagu dari Spotify ke queue!")
        else:
            await interaction.followup.send("📋 Loading playlist YouTube...")
            tracks_data = await fetch_playlist_tracks(url)
            if not tracks_data:
                await interaction.followup.send("❌ Gagal load playlist.", ephemeral=True)
                return
            for td in tracks_data:
                state.queue.append(Track(
                    title=td["title"], url=td["url"],
                    duration=td.get("duration", 0),
                    thumbnail=td.get("thumbnail", ""),
                    webpage_url=td["webpage_url"],
                    requester=interaction.user
                ))
            await interaction.followup.send(f"✅ **{len(tracks_data)}** lagu dari YouTube playlist masuk ke queue!")
            if not state.current:
                await self._play_next(interaction.guild)

    @app_commands.command(name="nowplaying", description="Tampilkan lagu yang sedang diputar beserta progress bar.")
    async def nowplaying(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        if not state.current:
            await interaction.response.send_message("❌ Tidak ada lagu yang sedang diputar.", ephemeral=True)
            return
        embed = self._now_playing_embed(state)
        view = MusicControlView(interaction.guild_id, self)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="queue", description="Tampilkan antrian lagu yang sedang menunggu.")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        if not state.current and not state.queue:
            await interaction.response.send_message("❌ Queue kosong.", ephemeral=True)
            return
        embed = discord.Embed(title="📋 Music Queue", color=0x1DB954)
        if state.current:
            embed.add_field(
                name="▶️ Now Playing",
                value=f"**[{state.current.title}]({state.current.webpage_url})** `{state.current.format_duration()}` - {state.current.requester.mention}",
                inline=False
            )
        if state.queue:
            lines = []
            for i, t in enumerate(state.queue[:15], 1):
                lines.append(f"`{i}.` **[{t.title}]({t.webpage_url})** `{t.format_duration()}` - {t.requester.mention}")
            if len(state.queue) > 15:
                lines.append(f"*...dan {len(state.queue) - 15} lagu lainnya*")
            embed.add_field(name="⏭️ Up Next", value="\n".join(lines), inline=False)
        total_dur = sum(t.duration or 0 for t in state.queue)
        m, s = divmod(total_dur, 60); h, m = divmod(m, 60)
        embed.set_footer(text=f"Total: {len(state.queue)} lagu | Durasi: {h:02d}:{m:02d}:{s:02d}")
        view = MusicControlView(interaction.guild_id, self)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="skip", description="Skip ke lagu berikutnya dalam queue.")
    async def skip(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        if not state.voice_client or (not state.voice_client.is_playing() and not state.voice_client.is_paused()):
            await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)
            return
        state.voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped!")

    @app_commands.command(name="stop", description="Stop musik dan disconnect bot dari voice channel.")
    async def stop(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        state.loop_mode = "off"
        state.clear()
        if state.voice_client:
            state.voice_client.stop()
            await state.voice_client.disconnect()
            state.voice_client = None
        await interaction.response.send_message("⏹️ Musik dihentikan dan bot disconnect.")

    @app_commands.command(name="pause", description="Pause lagu yang sedang diputar.")
    async def pause(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume lagu yang sedang di-pause.")
    async def resume(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Bot tidak sedang pause.", ephemeral=True)

    @app_commands.command(name="volume", description="Atur volume musik dari 0 hingga 100.")
    @app_commands.describe(level="Volume 0-100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message("❌ Volume harus antara 0-100.", ephemeral=True)
            return
        state = get_state(interaction.guild_id)
        state.volume = level / 100
        if state.voice_client and state.voice_client.source:
            try:
                state.voice_client.source.volume = state.volume
            except:
                pass
        await interaction.response.send_message(f"🔊 Volume diatur ke **{level}%**")

    @app_commands.command(name="loop", description="Toggle mode loop: off, single, atau seluruh queue.")
    async def loop(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        modes = ["off", "single", "queue"]
        idx = modes.index(state.loop_mode)
        state.loop_mode = modes[(idx + 1) % 3]
        icons = {"off": "➡️ Off", "single": "🔂 Single", "queue": "🔁 Queue"}
        await interaction.response.send_message(f"Loop mode: **{icons[state.loop_mode]}**")

    @app_commands.command(name="shuffle", description="Acak urutan lagu dalam queue secara random.")
    async def shuffle(self, interaction: discord.Interaction):
        import random
        state = get_state(interaction.guild_id)
        if not state.queue:
            await interaction.response.send_message("❌ Queue kosong.", ephemeral=True)
            return
        random.shuffle(state.queue)
        await interaction.response.send_message("🔀 Queue sudah diacak!")

    @app_commands.command(name="stay247", description="Toggle mode 24/7 agar bot tetap di voice channel.")
    async def stay_247(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        state.is_247 = not state.is_247
        status = "**aktif** 🟢" if state.is_247 else "**nonaktif** 🔴"
        await interaction.response.send_message(f"🌙 Mode 24/7 sekarang {status}")

    @app_commands.command(name="remove", description="Hapus lagu dari queue berdasarkan nomor urut.")
    @app_commands.describe(position="Nomor urut lagu dalam queue")
    async def remove(self, interaction: discord.Interaction, position: int):
        state = get_state(interaction.guild_id)
        if not state.queue or position < 1 or position > len(state.queue):
            await interaction.response.send_message("❌ Posisi tidak valid.", ephemeral=True)
            return
        removed = state.queue.pop(position - 1)
        await interaction.response.send_message(f"🗑️ Dihapus: **{removed.title}**")

    @app_commands.command(name="clearqueue", description="Hapus semua lagu dari antrian queue.")
    async def clearqueue(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        state.queue.clear()
        await interaction.response.send_message("🗑️ Queue telah dibersihkan.")

    @app_commands.command(name="join", description="Bot bergabung ke voice channel kamu.")
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if vc:
            await interaction.followup.send(f"✅ Joined **{vc.channel.name}**")

    @app_commands.command(name="leave", description="Bot keluar dari voice channel dan bersihkan queue.")
    async def leave(self, interaction: discord.Interaction):
        state = get_state(interaction.guild_id)
        state.clear()
        state.loop_mode = "off"
        if state.voice_client:
            state.voice_client.stop()
            await state.voice_client.disconnect()
            state.voice_client = None
        await interaction.response.send_message("👋 Bye!")

    @app_commands.command(name="lyrics", description="Cari dan tampilkan lirik lagu.")
    @app_commands.describe(song="Nama lagu, kosongkan untuk lirik lagu yang sedang diputar")
    async def lyrics(self, interaction: discord.Interaction, song: Optional[str] = None):
        await interaction.response.defer()
        state = get_state(interaction.guild_id)
        query = song
        if not query:
            if state.current:
                query = state.current.title
            else:
                await interaction.followup.send("❌ Masukkan nama lagu atau play dulu!", ephemeral=True)
                return
        if not genius:
            await interaction.followup.send("❌ Genius API Token belum dikonfigurasi. Tambahkan `GENIUS_API_TOKEN` di `.env`.", ephemeral=True)
            return
        try:
            loop = asyncio.get_event_loop()
            song_obj = await loop.run_in_executor(None, lambda: genius.search_song(query))
            if not song_obj:
                await interaction.followup.send(f"❌ Lirik untuk **{query}** tidak ditemukan.", ephemeral=True)
                return
            lyrics_text = song_obj.lyrics
            if len(lyrics_text) > 3900:
                lyrics_text = lyrics_text[:3900] + "\n...*[lirik terlalu panjang]*"
            embed = discord.Embed(
                title=f"📝 {song_obj.title}",
                description=f"*by {song_obj.artist}*\n\n{lyrics_text}",
                color=0xFFFF64,
                url=song_obj.url
            )
            embed.set_thumbnail(url=song_obj.song_art_image_url or "")
            embed.set_footer(text="Powered by Genius")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Gagal ambil lirik: {e}", ephemeral=True)

    @app_commands.command(name="musichelp", description="Tampilkan semua command musik yang tersedia.")
    async def musichelp(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎵 Music Bot Commands",
            description="Berikut adalah semua command musik yang tersedia:",
            color=0x1DB954
        )
        cmds = [
            ("/playsong <lagu/url>", "Play lagu dari YouTube (nama atau URL)"),
            ("/playlist <url>", "Play playlist/album dari Spotify atau YouTube"),
            ("/nowplaying", "Lihat lagu yang sedang diputar + progress bar"),
            ("/queue", "Lihat antrian lagu"),
            ("/skip", "Skip ke lagu berikutnya"),
            ("/stop", "Stop musik dan disconnect"),
            ("/pause", "Pause lagu"),
            ("/resume", "Resume lagu"),
            ("/volume <0-100>", "Atur volume"),
            ("/loop", "Toggle loop: off → single → queue"),
            ("/shuffle", "Acak urutan queue"),
            ("/247", "Toggle mode 24/7 (bot tetap di VC)"),
            ("/remove <nomor>", "Hapus lagu dari queue"),
            ("/clearqueue", "Hapus semua queue"),
            ("/join", "Bot join VC kamu"),
            ("/leave", "Bot leave VC"),
            ("/lyrics [lagu]", "Tampilkan lirik lagu"),
        ]
        for name, desc in cmds:
            embed.add_field(name=name, value=desc, inline=False)
        embed.set_footer(text="🎶 Professional Music Bot | Supports YouTube & Spotify")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
