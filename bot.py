import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import database

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')  # Optional: for instant slash command sync

# Intents are required to track messages, members, etc.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class ProfessionalBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        
    async def setup_hook(self):
        # Initialize the database
        await database.init_db()
        print("Database initialized.")
        
        # Load cogs
        initial_extensions = [
            'cogs.logger',
            'cogs.moderation',
            'cogs.utility',
            'cogs.leveling',
            'cogs.web_dashboard',
            'cogs.welcome',
            'cogs.auto_responder',
            'cogs.music'
        ]
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                print(f"Loaded extension: {ext}")
            except Exception as e:
                import traceback
                print(f"Failed to load extension {ext}: {e}")
                traceback.print_exc()
        
        # Sync slash commands
        print("Syncing slash commands...")
        if GUILD_ID and GUILD_ID.strip().isdigit():
            guild_obj = discord.Object(id=int(GUILD_ID.strip()))
            # copy_global_to WAJIB agar commands global (dari cog) masuk ke guild
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
            cmd_count = len(self.tree.get_commands(guild=guild_obj))
            print(f"Slash commands synced to guild {GUILD_ID}: {cmd_count} commands (instant).")
        else:
            await self.tree.sync()
            print("Slash commands synced globally (may take up to 1 hour).")
        print("Done!")

bot = ProfessionalBot()

@bot.tree.interaction_check
async def global_interaction_check(interaction: discord.Interaction):
    if interaction.guild_id:
        bot_enabled = await database.get_config(interaction.guild_id, "bot_enabled")
        if bot_enabled == 0:
            # Optionally send an ephemeral message
            try:
                await interaction.response.send_message("Bot sedang dimatikan dari Web Dashboard.", ephemeral=True)
            except:
                pass
            return False
    return True

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    invite_url = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions(administrator=True))
    print(f"INVITE LINK: {invite_url}")
    print('------')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="over the server"))

import asyncio
from cogs.web_dashboard import start_web_server

async def main():
    await database.init_db()
    print("Database initialized.")
    
    initial_extensions = [
        'cogs.logger',
        'cogs.moderation',
        'cogs.utility',
        'cogs.leveling',
        'cogs.web_dashboard',
        'cogs.welcome',
        'cogs.auto_responder',
        'cogs.music'
    ]
    for ext in initial_extensions:
        try:
            await bot.load_extension(ext)
            print(f"Loaded extension: {ext}")
        except Exception as e:
            import traceback
            print(f"Failed to load extension {ext}: {e}")
            traceback.print_exc()

    # Start Web Dashboard server task early so Railway proxy health check passes
    web_task = await start_web_server(bot)

    token = os.getenv('DISCORD_TOKEN')
    if not token or token == 'your_bot_token_here':
        print("WARNING: DISCORD_TOKEN is missing or default. Bot will stay offline, but Web Dashboard remains active.")
        await web_task
    else:
        try:
            print("Connecting to Discord...")
            await bot.start(token)
        except Exception as e:
            print(f"ERROR starting Discord Bot: {e}")
            print("Web Dashboard will remain active.")
            await web_task

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")

