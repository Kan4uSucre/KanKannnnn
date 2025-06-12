# database_handler.py
import aiosqlite
import datetime

DB_FILE = "bot_v2.db"

async def setup_database():
    """Crée TOUTES les tables nécessaires pour le bot V2 si elles n'existent pas."""
    async with aiosqlite.connect(DB_FILE) as db:
        # --- PERMISSIONS ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                UNIQUE(guild_id, role_id, command)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS permission_constraints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_id INTEGER NOT NULL,
                type TEXT NOT NULL, -- 'max_duration', 'max_amount'
                value INTEGER NOT NULL,
                FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE,
                UNIQUE(permission_id, type)
            )
        """)
        
        # --- SANCTIONS ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sanctions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL, sanction_type TEXT NOT NULL, reason TEXT,
                start_time TIMESTAMP NOT NULL, end_time TIMESTAMP, active BOOLEAN NOT NULL,
                role_id INTEGER -- Colonne pour temprole
            )
        """)
        
        # --- PRISON ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prisoned_user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL
            )
        """)
        
        # --- AUTOMATISATION ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                message_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (message_id, emoji)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS autoreact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                emoji TEXT NOT NULL
            )
        """)

        # --- SETTINGS, LOGS & ANTI-RAID (VERSION COMPLÈTE) ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                modlog_channel_id INTEGER,
                raidlog_channel_id INTEGER,
                messagelog_channel_id INTEGER,
                voicelog_channel_id INTEGER,
                rolelog_channel_id INTEGER,
                boostlog_channel_id INTEGER,
                
                raid_ping_role_id INTEGER,
                creation_limit_seconds INTEGER DEFAULT 0,
                
                antiupdate_on BOOLEAN DEFAULT 0, antiupdate_punishment TEXT DEFAULT 'kick',
                antichannel_on BOOLEAN DEFAULT 0, antichannel_punishment TEXT DEFAULT 'kick',
                antirole_on BOOLEAN DEFAULT 0, antirole_punishment TEXT DEFAULT 'kick',
                antiwebhook_on BOOLEAN DEFAULT 0, antiwebhook_punishment TEXT DEFAULT 'ban',
                antiunban_on BOOLEAN DEFAULT 0, antiunban_punishment TEXT DEFAULT 'kick',
                antibot_on BOOLEAN DEFAULT 0, antibot_punishment TEXT DEFAULT 'kick',
                antiban_on BOOLEAN DEFAULT 0, antiban_sensitivity TEXT DEFAULT '3/10s', antiban_punishment TEXT DEFAULT 'ban',
                antieveryone_on BOOLEAN DEFAULT 0, antieveryone_sensitivity TEXT DEFAULT '3/10s', antieveryone_punishment TEXT DEFAULT 'kick',
                antideco_on BOOLEAN DEFAULT 0, antideco_sensitivity TEXT DEFAULT '5/10s', antideco_punishment TEXT DEFAULT 'kick',
                blrank_on BOOLEAN DEFAULT 0,

                welcome_channel_id INTEGER, 
                welcome_message TEXT DEFAULT 'Bienvenue {member.mention} sur **{server.name}** !',
                leave_channel_id INTEGER, 
                leave_message TEXT DEFAULT '{member.name} nous a quitté.',
                autorole_id INTEGER, 
                support_role_id INTEGER, 
                support_message TEXT,
                prison_role_id INTEGER,
                prison_channel_id INTEGER
            )
        """)
        
        # --- ANTI-RAID WHITELIST & BLACKLIST RANK ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS antiraid_whitelist (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blrank_users (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # --- OWNER / BOT BLACKLIST ---
        await db.execute("CREATE TABLE IF NOT EXISTS bot_owners (user_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS blacklist (user_id INTEGER PRIMARY KEY, reason TEXT)")
        
        await db.commit()

# --- Fonctions de Permissions ---
async def grant_permission(guild_id: int, role_id: int, command: str):
    async with aiosqlite.connect(DB_FILE) as db:
        try:
            await db.execute("INSERT INTO permissions (guild_id, role_id, command) VALUES (?, ?, ?)", (guild_id, role_id, command))
            await db.commit()
            return True
        except aiosqlite.IntegrityError: return False

async def revoke_permission(guild_id: int, role_id: int, command: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM permissions WHERE guild_id = ? AND role_id = ? AND command = ?", (guild_id, role_id, command))
        await db.commit()

async def set_permission_constraint(guild_id: int, role_id: int, command: str, constraint_type: str, value: int):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT id FROM permissions WHERE guild_id = ? AND role_id = ? AND command = ?", (guild_id, role_id, command))
        perm_id_row = await cursor.fetchone()
        if not perm_id_row: return None
        perm_id = perm_id_row[0]
        await db.execute("INSERT INTO permission_constraints (permission_id, type, value) VALUES (?, ?, ?) ON CONFLICT(permission_id, type) DO UPDATE SET value = excluded.value", (perm_id, constraint_type, value))
        await db.commit()
        return True

async def check_permission_for_role(role_id: int, command: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT id FROM permissions WHERE role_id = ? AND command = ?", (role_id, command))
        return await cursor.fetchone() is not None

async def get_permission_constraint(role_id: int, command: str, constraint_type: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT pc.value FROM permission_constraints pc JOIN permissions p ON p.id = pc.permission_id WHERE p.role_id = ? AND p.command = ? AND pc.type = ?", (role_id, command, constraint_type))
        result = await cursor.fetchone()
        return result[0] if result else None

async def get_permissions_for_role(guild_id: int, role_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT command FROM permissions WHERE guild_id = ? AND role_id = ?", (guild_id, role_id))
        return [row[0] for row in await cursor.fetchall()]

# --- Fonctions de Sanctions ---
async def add_sanction(guild_id, user_id, moderator_id, sanc_type, reason, duration_seconds=None, role_id=None):
    start_time = datetime.datetime.now(datetime.timezone.utc)
    end_time = start_time + datetime.timedelta(seconds=duration_seconds) if duration_seconds else None
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO sanctions (guild_id, user_id, moderator_id, sanction_type, reason, start_time, end_time, active, role_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, sanc_type, reason, start_time, end_time, True, role_id)
        )
        await db.commit()
        
async def delete_sanction_by_id(sanction_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM sanctions WHERE id = ?", (sanction_id,))
        await db.commit()

async def get_user_sanctions(guild_id, user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT * FROM sanctions WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        return await cursor.fetchall()

async def deactivate_sanction(guild_id, user_id, sanc_type):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE sanctions SET active = 0 WHERE id = (SELECT id FROM sanctions WHERE guild_id = ? AND user_id = ? AND sanction_type = ? AND active = 1 ORDER BY start_time DESC LIMIT 1)", (guild_id, user_id, sanc_type))
        await db.commit()

async def get_expired_sanctions():
    now = datetime.datetime.now(datetime.timezone.utc)
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT * FROM sanctions WHERE end_time IS NOT NULL AND end_time <= ? AND active = 1", (now,))
        return await cursor.fetchall()

# --- Fonctions de Prison ---
async def store_user_roles(guild_id, user_id, roles):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM prisoned_user_roles WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        if roles:
            await db.executemany("INSERT INTO prisoned_user_roles (guild_id, user_id, role_id) VALUES (?, ?, ?)", [(guild_id, user_id, r.id) for r in roles])
        await db.commit()

async def restore_user_roles(guild_id, user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT role_id FROM prisoned_user_roles WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        role_ids = [row[0] for row in await cursor.fetchall()]
        await db.execute("DELETE FROM prisoned_user_roles WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()
        return role_ids

# --- Fonctions d'Automatisation ---
async def add_reaction_role(guild_id, message_id, emoji, role_id):
    async with aiosqlite.connect(DB_FILE) as db:
        try:
            await db.execute("INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)", (guild_id, message_id, emoji, role_id))
            await db.commit()
            return True
        except aiosqlite.IntegrityError: return False
async def get_reaction_role(message_id, emoji):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji))
        result = await cursor.fetchone()
        return result[0] if result else None
async def add_autoreact(guild_id, channel_id, emoji):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO autoreact (guild_id, channel_id, emoji) VALUES (?, ?, ?)", (guild_id, channel_id, emoji))
        await db.commit()
async def remove_autoreact(guild_id, channel_id, emoji):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM autoreact WHERE guild_id = ? AND channel_id = ? AND emoji = ?", (guild_id, channel_id, emoji))
        await db.commit()
async def get_autoreact_for_channel(channel_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT emoji FROM autoreact WHERE channel_id = ?", (channel_id,))
        return [row[0] for row in await cursor.fetchall()]

# --- Fonctions Anti-Raid ---
async def add_to_whitelist(guild_id, user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        try:
            await db.execute("INSERT INTO antiraid_whitelist (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
            await db.commit()
            return True
        except aiosqlite.IntegrityError: return False
async def remove_from_whitelist(guild_id, user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM antiraid_whitelist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()
async def get_whitelist(guild_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT user_id FROM antiraid_whitelist WHERE guild_id = ?", (guild_id,))
        return [row[0] for row in await cursor.fetchall()]
async def is_whitelisted(user_id, guild_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT 1 FROM antiraid_whitelist WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        return await cursor.fetchone() is not None

# --- Fonctions Owner & Blacklist ---
async def add_bot_owner(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        try:
            await db.execute("INSERT INTO bot_owners (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return True
        except aiosqlite.IntegrityError: return False
async def remove_bot_owner(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM bot_owners WHERE user_id = ?", (user_id,))
        await db.commit()
async def get_bot_owners():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT user_id FROM bot_owners")
        return [row[0] for row in await cursor.fetchall()]
async def add_to_blacklist(user_id, reason):
    async with aiosqlite.connect(DB_FILE) as db:
        try:
            await db.execute("INSERT INTO blacklist (user_id, reason) VALUES (?, ?)", (user_id, reason))
            await db.commit()
            return True
        except aiosqlite.IntegrityError: return False
async def remove_from_blacklist(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
        await db.commit()
async def is_blacklisted(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None

# --- Fonctions de Settings ---
async def get_guild_setting(guild_id, setting_name):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
        cursor = await db.execute(f"PRAGMA table_info(guild_settings)")
        columns = [row[1] for row in await cursor.fetchall()]
        if setting_name not in columns: return None
        cursor = await db.execute(f"SELECT {setting_name} FROM guild_settings WHERE guild_id = ?", (guild_id,))
        result = await cursor.fetchone()
        return result[0] if result else None
async def set_guild_setting(guild_id, setting_name, value):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
        await db.execute(f"UPDATE guild_settings SET {setting_name} = ? WHERE guild_id = ?", (value, guild_id))
        await db.commit()