import os
import asyncio

# ─── Deteksi otomatis: pakai PostgreSQL jika ada DATABASE_URL, else SQLite ───
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Railway / Cloud → PostgreSQL
    import asyncpg
    USE_POSTGRES = True
    # Railway kadang kirim "postgres://" tapi asyncpg butuh "postgresql://"
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    # Lokal → SQLite
    import aiosqlite
    USE_POSTGRES = False
    DB_NAME = "database.db"

# ─── Pool koneksi PostgreSQL (global) ────────────────────────────────────────
_pg_pool = None

async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pg_pool

# ─── Helper: jalankan query di backend yang tepat ────────────────────────────
async def _execute(query, *args, fetch=False, fetchone=False, fetchval=False):
    """Universal query runner: handles both PostgreSQL and SQLite."""
    if USE_POSTGRES:
        # PostgreSQL: ganti ? menjadi $1, $2, ...
        pg_query = query
        idx = [0]
        def replace_placeholder(s):
            result = []
            i = 0
            while i < len(s):
                if s[i] == '?':
                    idx[0] += 1
                    result.append(f'${idx[0]}')
                else:
                    result.append(s[i])
                i += 1
            return ''.join(result)
        pg_query = replace_placeholder(query)
        
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            if fetchone:
                return await conn.fetchrow(pg_query, *args)
            elif fetch:
                rows = await conn.fetch(pg_query, *args)
                # Kembalikan sebagai list of tuples agar kompatibel dengan SQLite
                return [tuple(r) for r in rows]
            elif fetchval:
                return await conn.fetchval(pg_query, *args)
            else:
                await conn.execute(pg_query, *args)
                return None
    else:
        # SQLite
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(query, args) as cursor:
                if fetchone:
                    return await cursor.fetchone()
                elif fetch:
                    return await cursor.fetchall()
                elif fetchval:
                    row = await cursor.fetchone()
                    return row[0] if row else None
                else:
                    await db.commit()
                    return None

async def _execute_many(queries_and_args):
    """Jalankan beberapa query sekaligus (untuk init_db)."""
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                for query, args in queries_and_args:
                    pg_query = query
                    idx = [0]
                    def replace_placeholder(s, idx=idx):
                        result = []
                        for ch in s:
                            if ch == '?':
                                idx[0] += 1
                                result.append(f'${idx[0]}')
                            else:
                                result.append(ch)
                        return ''.join(result)
                    pg_query = replace_placeholder(query)
                    await conn.execute(pg_query, *args)
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            for query, args in queries_and_args:
                await db.execute(query, args)
            await db.commit()

# ─── Inisialisasi Database ────────────────────────────────────────────────────
async def init_db():
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS warnings (
                        user_id BIGINT,
                        guild_id BIGINT,
                        count INTEGER DEFAULT 0,
                        PRIMARY KEY (user_id, guild_id)
                    )
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS bad_words (
                        guild_id BIGINT,
                        word TEXT,
                        PRIMARY KEY (guild_id, word)
                    )
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS config (
                        guild_id BIGINT PRIMARY KEY,
                        log_channel_id BIGINT,
                        ticket_category_id BIGINT,
                        auto_role_id BIGINT,
                        automod_enabled INTEGER DEFAULT 1,
                        anti_link_enabled INTEGER DEFAULT 1,
                        anti_spam_enabled INTEGER DEFAULT 1,
                        anti_toxic_enabled INTEGER DEFAULT 1,
                        leveling_enabled INTEGER DEFAULT 1,
                        tickets_enabled INTEGER DEFAULT 1,
                        bot_enabled INTEGER DEFAULT 1,
                        slowmode_delay INTEGER DEFAULT 0,
                        welcome_channel_id BIGINT,
                        welcome_message TEXT,
                        welcome_bg_url TEXT,
                        welcome_enabled INTEGER DEFAULT 0
                    )
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS xp (
                        guild_id BIGINT,
                        user_id BIGINT,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        PRIMARY KEY (guild_id, user_id)
                    )
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS transcripts (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT,
                        opened_by_id BIGINT,
                        ticket_name TEXT,
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS custom_commands (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT,
                        trigger TEXT,
                        response TEXT
                    )
                ''')
    else:
        # SQLite (lokal)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS warnings (
                    user_id INTEGER,
                    guild_id INTEGER,
                    count INTEGER,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bad_words (
                    guild_id INTEGER,
                    word TEXT,
                    PRIMARY KEY (guild_id, word)
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    guild_id INTEGER PRIMARY KEY,
                    log_channel_id INTEGER,
                    ticket_category_id INTEGER,
                    auto_role_id INTEGER,
                    automod_enabled INTEGER DEFAULT 1,
                    anti_link_enabled INTEGER DEFAULT 1,
                    anti_spam_enabled INTEGER DEFAULT 1,
                    anti_toxic_enabled INTEGER DEFAULT 1,
                    leveling_enabled INTEGER DEFAULT 1,
                    tickets_enabled INTEGER DEFAULT 1,
                    bot_enabled INTEGER DEFAULT 1,
                    slowmode_delay INTEGER DEFAULT 0,
                    welcome_channel_id INTEGER,
                    welcome_message TEXT,
                    welcome_bg_url TEXT,
                    welcome_enabled INTEGER DEFAULT 0
                )
            ''')
            # Alter untuk database lama
            for col in ['automod_enabled','anti_link_enabled','anti_spam_enabled','anti_toxic_enabled','leveling_enabled','tickets_enabled','bot_enabled']:
                try: await db.execute(f'ALTER TABLE config ADD COLUMN {col} INTEGER DEFAULT 1')
                except: pass
            for col in ['slowmode_delay','welcome_enabled']:
                try: await db.execute(f'ALTER TABLE config ADD COLUMN {col} INTEGER DEFAULT 0')
                except: pass
            try: await db.execute('ALTER TABLE config ADD COLUMN welcome_channel_id INTEGER')
            except: pass
            try: await db.execute('ALTER TABLE config ADD COLUMN welcome_message TEXT')
            except: pass
            try: await db.execute('ALTER TABLE config ADD COLUMN welcome_bg_url TEXT')
            except: pass
            await db.execute('''
                CREATE TABLE IF NOT EXISTS xp (
                    guild_id INTEGER,
                    user_id INTEGER,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    opened_by_id INTEGER,
                    ticket_name TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS custom_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    trigger TEXT,
                    response TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS music_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    song_title TEXT,
                    song_url TEXT,
                    duration INTEGER DEFAULT 0,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()

# ─── Warning Functions ────────────────────────────────────────────────────────
async def add_warning(guild_id: int, user_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT count FROM warnings WHERE guild_id = $1 AND user_id = $2',
                guild_id, user_id
            )
            if row:
                new_count = row['count'] + 1
                await conn.execute(
                    'UPDATE warnings SET count = $1 WHERE guild_id = $2 AND user_id = $3',
                    new_count, guild_id, user_id
                )
            else:
                new_count = 1
                await conn.execute(
                    'INSERT INTO warnings (guild_id, user_id, count) VALUES ($1, $2, $3)',
                    guild_id, user_id, new_count
                )
            return new_count
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT count FROM warnings WHERE guild_id = ? AND user_id = ?', (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                new_count = (row[0] + 1) if row else 1
                if row:
                    await db.execute('UPDATE warnings SET count = ? WHERE guild_id = ? AND user_id = ?', (new_count, guild_id, user_id))
                else:
                    await db.execute('INSERT INTO warnings (guild_id, user_id, count) VALUES (?, ?, ?)', (guild_id, user_id, new_count))
            await db.commit()
            return new_count

async def get_warnings(guild_id: int, user_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval('SELECT count FROM warnings WHERE guild_id = $1 AND user_id = $2', guild_id, user_id)
            return val or 0
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT count FROM warnings WHERE guild_id = ? AND user_id = ?', (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

async def clear_warnings(guild_id: int, user_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM warnings WHERE guild_id = $1 AND user_id = $2', guild_id, user_id)
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('DELETE FROM warnings WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
            await db.commit()

# ─── Bad Words Functions ──────────────────────────────────────────────────────
async def add_bad_word(guild_id: int, word: str):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO bad_words (guild_id, word) VALUES ($1, $2) ON CONFLICT DO NOTHING',
                guild_id, word.lower()
            )
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('INSERT OR IGNORE INTO bad_words (guild_id, word) VALUES (?, ?)', (guild_id, word.lower()))
            await db.commit()

async def remove_bad_word(guild_id: int, word: str):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM bad_words WHERE guild_id = $1 AND word = $2', guild_id, word.lower())
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('DELETE FROM bad_words WHERE guild_id = ? AND word = ?', (guild_id, word.lower()))
            await db.commit()

async def get_bad_words(guild_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch('SELECT word FROM bad_words WHERE guild_id = $1', guild_id)
            return [r['word'] for r in rows]
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT word FROM bad_words WHERE guild_id = ?', (guild_id,)) as cursor:
                return [row[0] for row in await cursor.fetchall()]

# ─── Config Functions ─────────────────────────────────────────────────────────
async def set_config(guild_id: int, key: str, value):
    # Whitelist kolom yang boleh diupdate (keamanan)
    allowed_keys = {
        'log_channel_id','ticket_category_id','auto_role_id',
        'automod_enabled','anti_link_enabled','anti_spam_enabled','anti_toxic_enabled',
        'leveling_enabled','tickets_enabled','bot_enabled','slowmode_delay',
        'welcome_channel_id','welcome_message','welcome_bg_url','welcome_enabled'
    }
    if key not in allowed_keys:
        raise ValueError(f"Key '{key}' tidak diizinkan")
    
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(f'''
                INSERT INTO config (guild_id, {key}) VALUES ($1, $2)
                ON CONFLICT (guild_id) DO UPDATE SET {key} = EXCLUDED.{key}
            ''', guild_id, value)
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT guild_id FROM config WHERE guild_id = ?', (guild_id,)) as cursor:
                if await cursor.fetchone():
                    await db.execute(f'UPDATE config SET {key} = ? WHERE guild_id = ?', (value, guild_id))
                else:
                    await db.execute(f'INSERT INTO config (guild_id, {key}) VALUES (?, ?)', (guild_id, value))
            await db.commit()

async def get_config(guild_id: int, key: str):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f'SELECT {key} FROM config WHERE guild_id = $1', guild_id)
            return row[key] if row else None
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(f'SELECT {key} FROM config WHERE guild_id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

# ─── XP Functions ─────────────────────────────────────────────────────────────
async def get_user_xp(guild_id: int, user_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT xp, level FROM xp WHERE guild_id = $1 AND user_id = $2', guild_id, user_id)
            return (row['xp'], row['level']) if row else (0, 1)
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT xp, level FROM xp WHERE guild_id = ? AND user_id = ?', (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                return row if row else (0, 1)

async def add_user_xp(guild_id: int, user_id: int, xp_to_add: int):
    current_xp, current_level = await get_user_xp(guild_id, user_id)
    new_xp = current_xp + xp_to_add
    new_level = current_level
    next_level_xp = (current_level * 10) ** 2
    leveled_up = False
    if new_xp >= next_level_xp:
        new_level += 1
        leveled_up = True

    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO xp (guild_id, user_id, xp, level) VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET xp = EXCLUDED.xp, level = EXCLUDED.level
            ''', guild_id, user_id, new_xp, new_level)
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            try:
                await db.execute('''
                    INSERT INTO xp (guild_id, user_id, xp, level) 
                    VALUES (?, ?, ?, ?) 
                    ON CONFLICT(guild_id, user_id) 
                    DO UPDATE SET xp = excluded.xp, level = excluded.level
                ''', (guild_id, user_id, new_xp, new_level))
            except Exception:
                await db.execute('UPDATE xp SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?', (new_xp, new_level, guild_id, user_id))
            await db.commit()
    return new_xp, new_level, leveled_up

async def get_leaderboard(guild_id: int, limit: int = 10):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch('SELECT user_id, xp, level FROM xp WHERE guild_id = $1 ORDER BY xp DESC LIMIT $2', guild_id, limit)
            return [(r['user_id'], r['xp'], r['level']) for r in rows]
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT user_id, xp, level FROM xp WHERE guild_id = ? ORDER BY xp DESC LIMIT ?', (guild_id, limit)) as cursor:
                return await cursor.fetchall()

# ─── Transcript Functions ─────────────────────────────────────────────────────
async def save_transcript(guild_id: int, opened_by_id: int, ticket_name: str, content: str):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO transcripts (guild_id, opened_by_id, ticket_name, content) VALUES ($1, $2, $3, $4)',
                guild_id, opened_by_id, ticket_name, content
            )
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('INSERT INTO transcripts (guild_id, opened_by_id, ticket_name, content) VALUES (?, ?, ?, ?)', (guild_id, opened_by_id, ticket_name, content))
            await db.commit()

async def get_transcripts(guild_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch('SELECT id, opened_by_id, ticket_name, created_at FROM transcripts WHERE guild_id = $1 ORDER BY created_at DESC', guild_id)
            return [(r['id'], r['opened_by_id'], r['ticket_name'], r['created_at']) for r in rows]
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT id, opened_by_id, ticket_name, created_at FROM transcripts WHERE guild_id = ? ORDER BY created_at DESC', (guild_id,)) as cursor:
                return await cursor.fetchall()

async def get_transcript_by_id(transcript_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT guild_id, opened_by_id, ticket_name, content, created_at FROM transcripts WHERE id = $1', transcript_id)
            return (row['guild_id'], row['opened_by_id'], row['ticket_name'], row['content'], row['created_at']) if row else None
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT guild_id, opened_by_id, ticket_name, content, created_at FROM transcripts WHERE id = ?', (transcript_id,)) as cursor:
                return await cursor.fetchone()

# ─── Custom Commands Functions ────────────────────────────────────────────────
async def add_custom_command(guild_id: int, trigger: str, response: str):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute('INSERT INTO custom_commands (guild_id, trigger, response) VALUES ($1, $2, $3)', guild_id, trigger.lower(), response)
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('INSERT INTO custom_commands (guild_id, trigger, response) VALUES (?, ?, ?)', (guild_id, trigger.lower(), response))
            await db.commit()

async def remove_custom_command(command_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM custom_commands WHERE id = $1', command_id)
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('DELETE FROM custom_commands WHERE id = ?', (command_id,))
            await db.commit()

async def get_custom_commands(guild_id: int):
    if USE_POSTGRES:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch('SELECT id, trigger, response FROM custom_commands WHERE guild_id = $1', guild_id)
            return [(r['id'], r['trigger'], r['response']) for r in rows]
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT id, trigger, response FROM custom_commands WHERE guild_id = ?', (guild_id,)) as cursor:
                return await cursor.fetchall()

# ─── Music Log Functions ──────────────────────────────────────────────────────
async def log_music(guild_id: int, user_id: int, username: str, song_title: str, song_url: str, duration: int = 0):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'INSERT INTO music_logs (guild_id, user_id, username, song_title, song_url, duration) VALUES (?, ?, ?, ?, ?, ?)',
            (guild_id, user_id, username, song_title, song_url, duration)
        )
        await db.commit()

async def get_music_logs(guild_id: int, limit: int = 50):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            'SELECT id, user_id, username, song_title, song_url, duration, played_at FROM music_logs WHERE guild_id = ? ORDER BY played_at DESC LIMIT ?',
            (guild_id, limit)
        ) as cursor:
            return await cursor.fetchall()

async def clear_music_logs(guild_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM music_logs WHERE guild_id = ?', (guild_id,))
        await db.commit()
