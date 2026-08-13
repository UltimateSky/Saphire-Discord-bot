import discord
from discord.ext import commands
import os
import asyncio
from quart import Quart, render_template, request, session, redirect, url_for, jsonify
import hypercorn.asyncio
import hypercorn.config
import database

app = Quart(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.getenv("DASHBOARD_SECRET", "super-secret-key-1234")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin123")

# We need a reference to the bot inside the Quart app
bot_instance = None

@app.after_request
async def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

@app.route("/")
async def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return await render_template("index.html", bot=bot_instance)

@app.route("/login", methods=["GET", "POST"])
async def login():
    if request.method == "POST":
        form = await request.form
        if form.get("password") == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))
        else:
            return await render_template("login.html", error="Invalid password")
    return await render_template("login.html")

@app.route("/logout")
async def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/dashboard")
async def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    guild_id = request.args.get("guild_id")
    guilds = bot_instance.guilds
    
    selected_guild = None
    if guild_id:
        selected_guild = discord.utils.get(guilds, id=int(guild_id))
    elif guilds:
        selected_guild = guilds[0]
        
    bad_words = []
    log_channel_id = None
    ticket_category_id = None
    auto_role_id = None
    automod_enabled = 1
    leveling_enabled = 1
    tickets_enabled = 1
    bot_enabled = 1
    slowmode_delay = 0
    welcome_enabled = 0
    welcome_channel_id = None
    welcome_message = ""
    welcome_bg_url = ""
    
    if selected_guild:
        bad_words = await database.get_bad_words(selected_guild.id)
        log_channel_id = await database.get_config(selected_guild.id, "log_channel_id")
        ticket_category_id = await database.get_config(selected_guild.id, "ticket_category_id")
        auto_role_id = await database.get_config(selected_guild.id, "auto_role_id")
        welcome_channel_id = await database.get_config(selected_guild.id, "welcome_channel_id")
        welcome_message = await database.get_config(selected_guild.id, "welcome_message")
        if welcome_message == "None": welcome_message = ""
        welcome_bg_url = await database.get_config(selected_guild.id, "welcome_bg_url")
        if welcome_bg_url == "None": welcome_bg_url = ""
        
        am_en = await database.get_config(selected_guild.id, "automod_enabled")
        if am_en is not None: automod_enabled = am_en
            
        lv_en = await database.get_config(selected_guild.id, "leveling_enabled")
        if lv_en is not None: leveling_enabled = lv_en
            
        tk_en = await database.get_config(selected_guild.id, "tickets_enabled")
        if tk_en is not None: tickets_enabled = tk_en
            
        bt_en = await database.get_config(selected_guild.id, "bot_enabled")
        if bt_en is not None: bot_enabled = bt_en
            
        sm_dl = await database.get_config(selected_guild.id, "slowmode_delay")
        if sm_dl is not None: slowmode_delay = sm_dl
            
        wl_en = await database.get_config(selected_guild.id, "welcome_enabled")
        if wl_en is not None: welcome_enabled = wl_en
        
    return await render_template("dashboard.html", 
                                 bot=bot_instance, 
                                 guilds=guilds, 
                                 selected_guild=selected_guild, 
                                 bad_words=bad_words,
                                 log_channel_id=log_channel_id,
                                 ticket_category_id=ticket_category_id,
                                 auto_role_id=auto_role_id,
                                 automod_enabled=automod_enabled,
                                 leveling_enabled=leveling_enabled,
                                 tickets_enabled=tickets_enabled,
                                 bot_enabled=bot_enabled,
                                 slowmode_delay=slowmode_delay,
                                 welcome_enabled=welcome_enabled,
                                 welcome_channel_id=welcome_channel_id,
                                 welcome_message=welcome_message,
                                 welcome_bg_url=welcome_bg_url)

@app.route("/auto-moderation")
async def auto_moderation():
    if not session.get("logged_in"): return redirect(url_for("login"))
    guild_id = request.args.get("guild_id")
    guilds = bot_instance.guilds
    selected_guild = discord.utils.get(guilds, id=int(guild_id)) if guild_id else (guilds[0] if guilds else None)
    
    bad_words = []
    anti_link_enabled = 1
    anti_spam_enabled = 1
    anti_toxic_enabled = 1
    
    if selected_guild:
        bad_words = await database.get_bad_words(selected_guild.id)
        al_en = await database.get_config(selected_guild.id, "anti_link_enabled")
        if al_en is not None: anti_link_enabled = al_en
            
        as_en = await database.get_config(selected_guild.id, "anti_spam_enabled")
        if as_en is not None: anti_spam_enabled = as_en
            
        at_en = await database.get_config(selected_guild.id, "anti_toxic_enabled")
        if at_en is not None: anti_toxic_enabled = at_en
        
    return await render_template("auto-moderation.html", bot=bot_instance, guilds=guilds, selected_guild=selected_guild, bad_words=bad_words, anti_link_enabled=anti_link_enabled, anti_spam_enabled=anti_spam_enabled, anti_toxic_enabled=anti_toxic_enabled)

@app.route("/auto-responder")
async def auto_responder():
    if not session.get("logged_in"): return redirect(url_for("login"))
    guild_id = request.args.get("guild_id")
    guilds = bot_instance.guilds
    selected_guild = discord.utils.get(guilds, id=int(guild_id)) if guild_id else (guilds[0] if guilds else None)
    
    commands_list = []
    if selected_guild:
        commands_list = await database.get_custom_commands(selected_guild.id)
        
    return await render_template("auto-responder.html", bot=bot_instance, guilds=guilds, selected_guild=selected_guild, commands_list=commands_list)

@app.route("/leveling")
async def leveling():
    if not session.get("logged_in"): return redirect(url_for("login"))
    guild_id = request.args.get("guild_id")
    search_query = request.args.get("search", "").strip().lower()
    guilds = bot_instance.guilds
    selected_guild = discord.utils.get(guilds, id=int(guild_id)) if guild_id else (guilds[0] if guilds else None)
    
    leaderboard_data = []
    if selected_guild:
        raw_lb = await database.get_leaderboard(selected_guild.id, 100)
        for user_id, xp, level in raw_lb:
            member = selected_guild.get_member(user_id) or bot_instance.get_user(user_id)
            name = member.name if member else f"Unknown User ({user_id})"
            if search_query and search_query not in name.lower():
                continue
            leaderboard_data.append({"user_id": user_id, "name": name, "xp": xp, "level": level})
            
    return await render_template("leveling.html", bot=bot_instance, guilds=guilds, selected_guild=selected_guild, leaderboard=leaderboard_data, search_query=search_query)

@app.route("/tickets")
async def tickets():
    if not session.get("logged_in"): return redirect(url_for("login"))
    guild_id = request.args.get("guild_id")
    guilds = bot_instance.guilds
    selected_guild = discord.utils.get(guilds, id=int(guild_id)) if guild_id else (guilds[0] if guilds else None)
    
    transcripts = []
    if selected_guild:
        raw_transcripts = await database.get_transcripts(selected_guild.id)
        for t in raw_transcripts:
            t_id, opened_by_id, ticket_name, created_at = t
            user = bot_instance.get_user(opened_by_id)
            username = user.name if user else f"User {opened_by_id}"
            transcripts.append({
                "id": t_id,
                "username": username,
                "ticket_name": ticket_name,
                "created_at": created_at
            })
            
    return await render_template("tickets.html", bot=bot_instance, guilds=guilds, selected_guild=selected_guild, transcripts=transcripts)

@app.route("/music")
async def music():
    if not session.get("logged_in"): return redirect(url_for("login"))
    guild_id = request.args.get("guild_id")
    guilds = bot_instance.guilds
    selected_guild = discord.utils.get(guilds, id=int(guild_id)) if guild_id else (guilds[0] if guilds else None)

    music_logs = []
    now_playing = None
    queue_list = []

    if selected_guild:
        raw_logs = await database.get_music_logs(selected_guild.id, limit=100)
        for row in raw_logs:
            log_id, user_id, username, song_title, song_url, duration, played_at = row
            m, s = divmod(duration or 0, 60)
            music_logs.append({
                "id": log_id,
                "username": username,
                "song_title": song_title,
                "song_url": song_url,
                "duration": f"{m:02d}:{s:02d}",
                "played_at": played_at
            })

        # Get live now playing from music state
        from cogs.music import get_state
        state = get_state(selected_guild.id)
        if state.current:
            elapsed = state.get_elapsed()
            dur = state.current.duration or 0
            m, s = divmod(dur, 60)
            now_playing = {
                "title": state.current.title,
                "url": state.current.webpage_url,
                "thumbnail": state.current.thumbnail,
                "duration": f"{m:02d}:{s:02d}",
                "requester": str(state.current.requester),
                "loop": state.loop_mode,
                "volume": int(state.volume * 100),
                "is_247": state.is_247,
                "elapsed": elapsed,
                "elapsed_pct": min(int((elapsed / dur) * 100), 100) if dur else 0,
            }
        queue_list = [
            {"title": t.title, "url": t.webpage_url, "duration": f"{t.duration//60:02d}:{t.duration%60:02d}", "requester": str(t.requester)}
            for t in state.queue[:20]
        ]

    return await render_template("music.html",
                                 bot=bot_instance,
                                 guilds=guilds,
                                 selected_guild=selected_guild,
                                 music_logs=music_logs,
                                 now_playing=now_playing,
                                 queue_list=queue_list)

@app.route("/api/clear_music_logs", methods=["POST"])
async def api_clear_music_logs():
    if not session.get("logged_in"): return jsonify({"error": "Unauthorized"}), 401
    data = await request.json
    guild_id = data.get("guild_id")
    if guild_id:
        await database.clear_music_logs(int(guild_id))
        return jsonify({"success": True})
    return jsonify({"error": "Invalid data"}), 400

@app.route("/transcript/<int:transcript_id>")
async def view_transcript(transcript_id):
    if not session.get("logged_in"): return redirect(url_for("login"))
    transcript = await database.get_transcript_by_id(transcript_id)
    if not transcript:
        return "Transcript not found", 404
        
    guild_id, opened_by_id, ticket_name, content, created_at = transcript
    guilds = bot_instance.guilds
    selected_guild = discord.utils.get(guilds, id=int(guild_id))
    
    return await render_template("transcript.html", bot=bot_instance, guilds=guilds, selected_guild=selected_guild, content=content, ticket_name=ticket_name, created_at=created_at)

@app.route("/api/add_bad_word", methods=["POST"])
async def api_add_bad_word():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    data = await request.json
    guild_id = data.get("guild_id")
    word = data.get("word")
    if guild_id and word:
        await database.add_bad_word(int(guild_id), word)
        return jsonify({"success": True, "word": word})
    return jsonify({"error": "Invalid data"}), 400

@app.route("/api/remove_bad_word", methods=["POST"])
async def api_remove_bad_word():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    data = await request.json
    guild_id = data.get("guild_id")
    word = data.get("word")
    if guild_id and word:
        await database.remove_bad_word(int(guild_id), word)
        return jsonify({"success": True})
    return jsonify({"error": "Invalid data"}), 400

@app.route("/api/add_custom_command", methods=["POST"])
async def api_add_custom_command():
    if not session.get("logged_in"): return jsonify({"error": "Unauthorized"}), 401
    data = await request.json
    guild_id = data.get("guild_id")
    trigger = data.get("trigger")
    response_text = data.get("response")
    if guild_id and trigger and response_text:
        await database.add_custom_command(int(guild_id), trigger, response_text)
        return jsonify({"success": True})
    return jsonify({"error": "Invalid data"}), 400

@app.route("/api/remove_custom_command", methods=["POST"])
async def api_remove_custom_command():
    if not session.get("logged_in"): return jsonify({"error": "Unauthorized"}), 401
    data = await request.json
    command_id = data.get("command_id")
    if command_id:
        await database.remove_custom_command(int(command_id))
        return jsonify({"success": True})
    return jsonify({"error": "Invalid data"}), 400

@app.route("/api/save_config", methods=["POST"])
async def api_save_config():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    data = await request.json
    guild_id = data.get("guild_id")
    
    if guild_id:
        try:
            guild_id = int(guild_id)
            
            # Text inputs / Selects
            if "prefix" in data:
                val = data.get("prefix")
                await database.set_config(guild_id, "prefix", str(val) if val else "!")

            if "log_channel_id" in data:
                val = data.get("log_channel_id")
                await database.set_config(guild_id, "log_channel_id", int(val) if val else None)
            
            if "ticket_category_id" in data:
                val = data.get("ticket_category_id")
                await database.set_config(guild_id, "ticket_category_id", int(val) if val else None)
                
            if "auto_role_id" in data:
                val = data.get("auto_role_id")
                await database.set_config(guild_id, "auto_role_id", int(val) if val else None)
                
            # Toggles
            if "automod_enabled" in data:
                await database.set_config(guild_id, "automod_enabled", int(data.get("automod_enabled")))
                
            if "anti_link_enabled" in data:
                await database.set_config(guild_id, "anti_link_enabled", int(data.get("anti_link_enabled")))
                
            if "anti_spam_enabled" in data:
                await database.set_config(guild_id, "anti_spam_enabled", int(data.get("anti_spam_enabled")))
                
            if "anti_toxic_enabled" in data:
                await database.set_config(guild_id, "anti_toxic_enabled", int(data.get("anti_toxic_enabled")))
                
            if "leveling_enabled" in data:
                await database.set_config(guild_id, "leveling_enabled", int(data.get("leveling_enabled")))
                
            if "tickets_enabled" in data:
                await database.set_config(guild_id, "tickets_enabled", int(data.get("tickets_enabled")))
                
            if "bot_enabled" in data:
                bt_en = int(data.get("bot_enabled"))
                await database.set_config(guild_id, "bot_enabled", bt_en)
                
                # Change presence immediately
                if bt_en == 0:
                    await bot_instance.change_presence(status=discord.Status.offline)
                else:
                    await bot_instance.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.watching, name="over the server"))
                
            if "welcome_enabled" in data:
                await database.set_config(guild_id, "welcome_enabled", int(data.get("welcome_enabled")))
                
            if "welcome_channel_id" in data:
                val = data.get("welcome_channel_id")
                await database.set_config(guild_id, "welcome_channel_id", int(val) if val else None)
                
            if "welcome_message" in data:
                val = data.get("welcome_message")
                await database.set_config(guild_id, "welcome_message", str(val) if val is not None else "")
                
            if "welcome_bg_url" in data:
                val = data.get("welcome_bg_url")
                await database.set_config(guild_id, "welcome_bg_url", str(val) if val is not None else "")
                
            if "slowmode_delay" in data:
                delay = int(data.get("slowmode_delay"))
                await database.set_config(guild_id, "slowmode_delay", delay)
                # Apply slowmode to discord channels
                guild = bot_instance.get_guild(guild_id)
                if guild:
                    for channel in guild.text_channels:
                        try:
                            if channel.slowmode_delay != delay:
                                await channel.edit(slowmode_delay=delay)
                        except discord.Forbidden:
                            pass
                        except Exception as e:
                            print(f"Error setting slowmode for {channel.name}: {e}")
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Guild ID required"}), 400
                
@app.route("/api/bot_status")
async def api_bot_status():
    if not bot_instance:
        return jsonify({"status": "offline", "ping": 0, "guilds": 0, "users": 0})
    return jsonify({
        "status": "online",
        "bot_name": str(bot_instance.user),
        "bot_id": bot_instance.user.id if bot_instance.user else None,
        "ping": round(bot_instance.latency * 1000, 2) if bot_instance.latency else 0,
        "guilds_count": len(bot_instance.guilds),
        "users_count": len(bot_instance.users),
    })

@app.route("/api/guilds")
async def api_guilds():
    if not bot_instance:
        return jsonify({"guilds": []})
    guilds_list = []
    for g in bot_instance.guilds:
        guilds_list.append({
            "id": str(g.id),
            "name": g.name,
            "member_count": g.member_count,
            "icon_url": g.icon.url if g.icon else None,
            "text_channels": [{"id": str(c.id), "name": c.name} for c in g.text_channels],
            "categories": [{"id": str(cat.id), "name": cat.name} for cat in g.categories],
            "roles": [{"id": str(r.id), "name": r.name} for r in g.roles if r.name != '@everyone' and not r.is_bot_managed()]
        })
@app.route("/api/guild_data")
async def api_guild_data():
    guild_id_raw = request.args.get("guild_id")
    if not guild_id_raw or not guild_id_raw.isdigit():
        return jsonify({"error": "Invalid guild_id"}), 400
    guild_id = int(guild_id_raw)
    
    # 1. Config
    config_keys = [
        'prefix','log_channel_id','ticket_category_id','auto_role_id',
        'automod_enabled','anti_link_enabled','anti_spam_enabled','anti_toxic_enabled',
        'leveling_enabled','tickets_enabled','bot_enabled','slowmode_delay',
        'welcome_channel_id','welcome_message','welcome_bg_url','welcome_enabled'
    ]
    config_data = {}
    for k in config_keys:
        val = await database.get_config(guild_id, k)
        config_data[k] = val
        
    # 2. Bad Words
    bad_words = await database.get_bad_words(guild_id)
    
    # 3. Custom Commands (Auto Responder)
    custom_cmds_raw = await database.get_custom_commands(guild_id)
    custom_commands = [{"id": r[0], "trigger": r[1], "response": r[2]} for r in custom_cmds_raw]
    
    # 4. Leaderboard
    lb_raw = await database.get_leaderboard(guild_id, limit=20)
    leaderboard = []
    guild_obj = bot_instance.get_guild(guild_id) if bot_instance else None
    for r in lb_raw:
        u_id, u_xp, u_lvl = r[0], r[1], r[2]
        user_name = f"User#{u_id % 9000 + 1000}"
        if guild_obj:
            mem = guild_obj.get_member(u_id)
            if mem:
                user_name = str(mem)
        leaderboard.append({
            "user_id": str(u_id),
            "username": user_name,
            "xp": u_xp,
            "level": u_lvl
        })
        
    # 5. Transcripts
    ts_raw = await database.get_transcripts(guild_id)
    transcripts = []
    for r in ts_raw[:10]:
        t_id, opened_by, ticket_name, created_at = r[0], r[1], r[2], str(r[3])
        opener_name = f"User#{opened_by}"
        if guild_obj:
            mem = guild_obj.get_member(opened_by)
            if mem: opener_name = str(mem)
        transcripts.append({
            "id": t_id,
            "opened_by_id": str(opened_by),
            "opened_by_name": opener_name,
            "ticket_name": ticket_name,
            "created_at": created_at
        })

    # 6. Music State
    music_info = {"is_playing": False, "current": None, "queue": [], "volume": 50, "loop_mode": "off"}
    try:
        from .music import get_state
        state = get_state(guild_id)
        music_info["volume"] = int(state.volume * 100)
        music_info["loop_mode"] = state.loop_mode
        music_info["is_playing"] = bool(state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()))
        if state.current:
            music_info["current"] = {
                "title": state.current.title,
                "duration": state.current.duration or 0,
                "elapsed": state.get_elapsed(),
                "requester": str(state.current.requester) if state.current.requester else "Unknown",
                "thumbnail": state.current.thumbnail,
                "webpage_url": state.current.webpage_url
            }
        music_info["queue"] = [
            {
                "title": t.title,
                "duration": t.duration or 0,
                "requester": str(t.requester) if t.requester else "Unknown",
                "webpage_url": t.webpage_url
            } for t in state.queue[:10]
        ]
    except Exception as e:
        print(f"[MusicData Error] {e}")

    return jsonify({
        "guild_id": str(guild_id),
        "config": config_data,
        "bad_words": bad_words,
        "custom_commands": custom_commands,
        "leaderboard": leaderboard,
        "transcripts": transcripts,
        "music": music_info
    })

@app.route("/api/music_control", methods=["POST"])
async def api_music_control():
    data = await request.json or {}
    guild_id = data.get("guild_id")
    action = data.get("action")
    if not guild_id or not action:
        return jsonify({"error": "Missing parameters"}), 400
    try:
        guild_id = int(guild_id)
        from .music import get_state
        state = get_state(guild_id)
        if action == "pause":
            if state.voice_client and state.voice_client.is_playing():
                state.voice_client.pause()
        elif action == "resume":
            if state.voice_client and state.voice_client.is_paused():
                state.voice_client.resume()
        elif action == "skip":
            if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
                state.voice_client.stop()
        elif action == "stop":
            state.clear()
            if state.voice_client:
                state.voice_client.stop()
                await state.voice_client.disconnect()
                state.voice_client = None
        elif action == "volume":
            vol = int(data.get("value", 50))
            state.volume = max(0, min(100, vol)) / 100.0
            if state.voice_client and state.voice_client.source:
                try: state.voice_client.source.volume = state.volume
                except: pass
        elif action == "loop":
            modes = ["off", "single", "queue"]
            idx = modes.index(state.loop_mode) if state.loop_mode in modes else 0
            state.loop_mode = modes[(idx + 1) % 3]
        return jsonify({"success": True, "action": action, "loop_mode": state.loop_mode, "volume": int(state.volume*100)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/get_transcript_detail")
async def api_transcript_detail():
    t_id = request.args.get("id")
    if not t_id or not t_id.isdigit():
        return jsonify({"error": "Invalid transcript id"}), 400
    data = await database.get_transcript_by_id(int(t_id))
    if not data:
        return jsonify({"error": "Transcript not found"}), 404
    return jsonify({
        "guild_id": str(data[0]),
        "opened_by_id": str(data[1]),
        "ticket_name": data[2],
        "content": data[3],
        "created_at": str(data[4])
    })

_web_server_task = None

async def start_web_server(bot=None):
    global bot_instance, _web_server_task
    if bot:
        bot_instance = bot
    if _web_server_task is not None and not _web_server_task.done():
        return _web_server_task
    port = int(os.getenv("PORT", 5000))
    host = "0.0.0.0"
    config = hypercorn.config.Config()
    config.bind = [f"{host}:{port}"]
    print(f"Web Dashboard starting on http://{host}:{port}")
    _web_server_task = asyncio.create_task(hypercorn.asyncio.serve(app, config))
    return _web_server_task

class WebDashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        global bot_instance
        bot_instance = bot
        
    async def cog_load(self):
        await start_web_server(self.bot)
        
    async def cog_unload(self):
        global _web_server_task
        if _web_server_task and not _web_server_task.done():
            _web_server_task.cancel()

async def setup(bot):
    await bot.add_cog(WebDashboard(bot))
