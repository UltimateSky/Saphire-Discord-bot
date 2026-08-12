import discord
from discord.ext import commands
import database
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_image(self, url: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
        return None

    def create_welcome_card(self, avatar_bytes: bytes, bg_bytes: bytes, username: str, member_count: int) -> io.BytesIO:
        # Load avatar
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((200, 200))
        
        # Create circular mask for avatar
        mask = Image.new("L", (200, 200), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 200, 200), fill=255)
        
        # Apply mask to avatar
        circular_avatar = Image.new("RGBA", (200, 200), (0,0,0,0))
        circular_avatar.paste(avatar, (0, 0), mask=mask)

        # Base Canvas (800 x 400)
        base = Image.new("RGBA", (800, 400), (44, 47, 51, 255))
        
        # Load or create Background
        if bg_bytes:
            try:
                bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
                # Resize bg to fill base, crop center if needed
                bg_aspect = bg.width / bg.height
                base_aspect = 800 / 400
                if bg_aspect > base_aspect:
                    # bg is wider
                    new_w = int(bg.height * base_aspect)
                    offset = (bg.width - new_w) // 2
                    bg = bg.crop((offset, 0, offset + new_w, bg.height))
                else:
                    # bg is taller
                    new_h = int(bg.width / base_aspect)
                    offset = (bg.height - new_h) // 2
                    bg = bg.crop((0, offset, bg.width, offset + new_h))
                    
                bg = bg.resize((800, 400))
                base.paste(bg, (0, 0))
            except:
                pass
                
        # Draw a dark overlay for text readability
        overlay = Image.new("RGBA", (800, 400), (0, 0, 0, 150))
        base = Image.alpha_composite(base, overlay)

        # Paste Avatar (centered horizontally, shifted up)
        base.paste(circular_avatar, (300, 50), mask=circular_avatar)

        # Draw text
        draw = ImageDraw.Draw(base)
        
        # We try to load a default font, otherwise use default bitmap font
        try:
            # Note: This might fail on windows if font doesn't exist, we fallback
            font_large = ImageFont.truetype("arial.ttf", 40)
            font_small = ImageFont.truetype("arial.ttf", 25)
        except IOError:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Text coordinates (approximate center)
        text_welcome = "WELCOME"
        text_name = f"{username}"
        text_count = f"Member #{member_count}"

        # We can't easily center text without textbbox in newer Pillow, using basic math:
        # Pillow 10.0+ uses textbbox
        try:
            w_w = draw.textbbox((0,0), text_welcome, font=font_large)[2]
            n_w = draw.textbbox((0,0), text_name, font=font_large)[2]
            c_w = draw.textbbox((0,0), text_count, font=font_small)[2]
            
            draw.text(((800 - w_w)/2, 260), text_welcome, fill=(255, 255, 255), font=font_large)
            draw.text(((800 - n_w)/2, 310), text_name, fill=(255, 215, 0), font=font_large) # Gold name
            draw.text(((800 - c_w)/2, 360), text_count, fill=(200, 200, 200), font=font_small)
        except AttributeError:
            # Fallback for old pillow
            w_w, w_h = draw.textsize(text_welcome, font=font_large)
            n_w, n_h = draw.textsize(text_name, font=font_large)
            c_w, c_h = draw.textsize(text_count, font=font_small)
            
            draw.text(((800 - w_w)/2, 260), text_welcome, fill=(255, 255, 255), font=font_large)
            draw.text(((800 - n_w)/2, 310), text_name, fill=(255, 215, 0), font=font_large)
            draw.text(((800 - c_w)/2, 360), text_count, fill=(200, 200, 200), font=font_small)

        buffer = io.BytesIO()
        base.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        
        bot_enabled = await database.get_config(guild.id, "bot_enabled")
        if bot_enabled == 0:
            return
            
        welcome_enabled = await database.get_config(guild.id, "welcome_enabled")
        if not welcome_enabled:
            return
            
        channel_id = await database.get_config(guild.id, "welcome_channel_id")
        if not channel_id:
            return
            
        channel = guild.get_channel(channel_id)
        if not channel:
            return
            
        # Get settings
        message_template = await database.get_config(guild.id, "welcome_message")
        if not message_template:
            message_template = "Halo {user}, selamat datang di **{server}**!"
            
        # Format message
        message = message_template.replace("{user}", member.mention).replace("{server}", guild.name)
        
        bg_url = await database.get_config(guild.id, "welcome_bg_url")
        bg_bytes = None
        if bg_url:
            bg_bytes = await self.fetch_image(bg_url)
            
        # Get Avatar
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        # Discord avatars can be converted to png
        avatar_url = str(avatar_url).replace(".webp", ".png").replace(".gif", ".png")
        avatar_bytes = await self.fetch_image(avatar_url)
        
        if avatar_bytes:
            try:
                # Run image generation in a separate thread to not block the event loop
                import asyncio
                loop = asyncio.get_event_loop()
                buffer = await loop.run_in_executor(None, self.create_welcome_card, avatar_bytes, bg_bytes, str(member), guild.member_count)
                
                file = discord.File(fp=buffer, filename="welcome.png")
                await channel.send(content=message, file=file)
            except Exception as e:
                print(f"Error generating welcome card: {e}")
                await channel.send(content=message)
        else:
            await channel.send(content=message)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
