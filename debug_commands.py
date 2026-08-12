import asyncio, os, aiohttp
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID", "").strip()

async def main():
    headers = {"Authorization": f"Bot {TOKEN}"}
    async with aiohttp.ClientSession() as s:
        # Get application info
        async with s.get("https://discord.com/api/v10/applications/@me", headers=headers) as r:
            app = await r.json()
        app_id = app["id"]
        print(f"App ID: {app_id}")
        print(f"Guild ID dari .env: {GUILD_ID}")
        print()

        # Global commands
        async with s.get(f"https://discord.com/api/v10/applications/{app_id}/commands", headers=headers) as r:
            cmds = await r.json()
        print(f"=== GLOBAL COMMANDS ({len(cmds)}) ===")
        for c in cmds:
            print(f"  - /{c['name']}")

        # Guild commands
        if GUILD_ID:
            async with s.get(f"https://discord.com/api/v10/applications/{app_id}/guilds/{GUILD_ID}/commands", headers=headers) as r:
                gcmds = await r.json()
            print(f"\n=== GUILD COMMANDS untuk {GUILD_ID} ({len(gcmds)}) ===")
            for c in gcmds:
                print(f"  - /{c['name']}")

asyncio.run(main())
