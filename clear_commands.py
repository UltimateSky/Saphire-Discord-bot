"""
Script untuk menghapus SEMUA slash commands yang terduplikasi di Discord.
Jalankan SEKALI sebelum restart bot.
"""
import asyncio
import discord
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID", "").strip()

async def clear_all_commands():
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    async with client:
        await client.login(TOKEN)

        # Hapus semua GLOBAL commands
        print("Menghapus semua global slash commands...")
        client.http.token = TOKEN
        await client.http.bulk_upsert_global_commands(client.application_id, [])
        print("Global commands dihapus!")

        # Jika ada GUILD_ID, hapus juga guild-specific commands
        if GUILD_ID and GUILD_ID.isdigit():
            print(f"Menghapus guild commands dari server {GUILD_ID}...")
            await client.http.bulk_upsert_guild_commands(client.application_id, int(GUILD_ID), [])
            print("Guild commands dihapus!")

        print("\nSemua command berhasil dihapus!")
        print("Sekarang restart bot dengan: python bot.py")

asyncio.run(clear_all_commands())
