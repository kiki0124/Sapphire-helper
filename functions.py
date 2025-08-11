import datetime
import asqlite as sql
from string import ascii_letters, digits
import random
from typing import Optional

DB_PATH = "database\data.db"

# other functions

async def main():
    """  
    Called once whenever the bot is turned on (in setup_hook)
    Creates DB tables (pending posts and readthedamnrules)
    """
    async with sql.connect(DB_PATH) as conn: 
        async with conn.cursor() as cu:
            await cu.execute("CREATE TABLE IF NOT EXISTS pending_posts(post_id INTEGER NOT NULL PRIMARY KEY, timestamp INTEGER NOT NULL)")
            await cu.execute("CREATE TABLE IF NOT EXISTS readthedamnrules(post_id INTEGER NOT NULL PRIMARY KEY, user_id INTEGER NOT NULL)")
            await cu.execute("CREATE TABLE IF NOT EXISTS reminder_waiting(post_id INTEGER PRIMARY KEY NOT NULL, timestamp INTEGER NOT NULL)")
            await cu.execute("CREATE TABLE IF NOT EXISTS locked_channels_permissions(channel_id INTEGER PRIMARY KEY NOT NULL, allow BIGINT, deny BIGINT)")
            await cu.execute("CREATE TABLE IF NOT EXISTS epi_config(started_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, message STRING NULL DEFAULT NULL, message_id INTEGER NULL DEFAULT NULL, sticky BOOL NOT NULL)")
            await cu.execute("CREATE TABLE IF NOT EXISTS epi_users(user_id INTEGER UNIQUE NOT NULL)")
            await cu.execute("CREATE TABLE IF ONT EXISTS epi_messages(thread_id INTEGER UNIQUE NOT NULL, message_id INTEGER UNIQUE NOT NULL)")
            await conn.commit()

def generate_random_id() -> str:
    """  
    Generates a random 6 letter id made of letters (lower and upper case) and numbers.
    """
    characters = ascii_letters + digits
    return ''.join(random.choice(characters) for _ in range(6))

def check_time_more_than_day(timestamp: int) -> bool:
    """  
    Check if the given time is more than a day ago
    """
    tz_info = datetime.datetime.now().astimezone().tzinfo
    time = datetime.datetime.fromtimestamp(timestamp, tz=tz_info)
    one_day_ago = datetime.datetime.now(tz=tz_info) - datetime.timedelta(days=1)
    return not one_day_ago < time 

# reminder system related functions

async def execute_sql(cmd: str) -> Optional[tuple|Exception]:
    """  
    Execute the given sql command and return the result or None if there is no result, if an error was raised when executing the sql command it will be returned
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            try:
                await cu.execute(cmd)
            except Exception as e: # could be an invalid command or any other sql error
                return e
            await conn.commit()
            return await cu.fetchall()

async def add_post_to_pending(post_id: int) -> None:
    """
    Add the post with the given id and timestamp to pending db
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            timestamp = int(datetime.datetime.now().timestamp())
            await cu.execute(f"INSERT INTO pending_posts (post_id, timestamp) VALUES (?, ?) ON CONFLICT (post_id) DO NOTHING", (post_id, timestamp,))
            await conn.commit()

async def get_pending_posts():
    """
    Get all posts in pending posts table. Returns a list of integers.
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT post_id FROM pending_posts")
            return [row[0] for row in await cu.fetchall()]

async def remove_post_from_pending(post_id: int) -> None:
    """  
    Remove a post from closing pending db
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"DELETE FROM pending_posts WHERE post_id=?", (post_id,))
            await conn.commit()

async def get_post_timestamp(post_id: int) -> Optional[int]:
    """  
    Returns the saved timestamp for the post with given id or None if its not in the db
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"SELECT timestamp FROM pending_posts WHERE post_id=?", (post_id,))
            result = await cu.fetchone()
            if result:
                return result[0]
            else:
                return None

async def check_post_last_message_time(post_id: int) -> bool:
    """
    Returns if the timestamp of a post (from db) is more than one day ago (24 hours).
    """
    timestamp = await get_post_timestamp(post_id)
    return check_time_more_than_day(timestamp)

# readthedamnrules system related functions

async def add_post_to_rtdr(post_id: int, user_id: int) -> None:
    """  
    Add post with given id to readthedamnrules table/system
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"INSERT INTO readthedamnrules (post_id, user_id) VALUES (?, ?) ON CONFLICT (post_id) DO NOTHING", (post_id, user_id,))
            await conn.commit()

async def get_post_creator_id(post_id: int) -> Optional[int]:
    """  
    Get the id of whoever the post was created for if its part of readthedamnrules system
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"SELECT user_id FROM readthedamnrules WHERE post_id=?", (post_id,))
            result = None
            result = await cu.fetchone()
            return result[0] if result else None

async def remove_post_from_rtdr(post_id: int) -> None:
    """  
    Remove post with given id from readthedamnrules system
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"DELETE FROM readthedamnrules WHERE post_id=?", (post_id,))
            await conn.commit()
        
async def get_rtdr_posts() -> list[int]:
    """  
    Returns a list of all post ids in rtdr system
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT post_id FROM readthedamnrules")
            result = await cu.fetchall()
            if result:
                return [row[0] for row in result]
            else:
                return []

# reminders-redone

async def save_post_as_pending(post_id: int, timestamp: int) -> None:
    """  
    Adds the given post id with timestamp of 24 hours to the future (now + 24 hours)
    to pending table in db
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("INSERT INTO pending_posts (post_id, timestamp) VALUES (?, ?)", (post_id, timestamp))
            await conn.commit()

async def get_pending_posts_data():
    """
    returns the id and timestamp of all pending posts
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute('SELECT * FROM pending_posts')
            return await cu.fetchall()

# reminders redone- reminder_waiting

async def get_waiting_posts() -> list[int]:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT post_id FROM reminder_waiting")
            result = await cu.fetchall()
            if result:
                return [row[0] for row in result]
            else:
                return []

async def remove_post_from_waiting(post_id: int) -> None:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("DELETE FROM reminder_waiting WHERE post_id=?", (post_id,))
            await conn.commit()

async def add_post_to_waiting(post_id: int, timestamp: int = None) -> None:
    if timestamp is None: timestamp = int(datetime.datetime.now().timestamp())
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("INSERT INTO reminder_waiting (post_id, timestamp) VALUES (?, ?)", (post_id, timestamp,))
            await conn.commit()

async def get_waiting_posts_data():
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT * FROM reminder_waiting")
            return await cu.fetchall()

# epi - locked channel permissions

async def save_channel_permissions(channel_id: int, allow: int, deny: int) -> None:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("INSERT INTO locked_channels_permissions (channel_id, allow, deny) VALUES (?, ?, ?)", (channel_id, allow, deny,))
            await conn.commit()

async def get_channel_permissions(channel_id: int) -> tuple[int, int]:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT allow, deny FROM locked_channels_permissions WHERE channel_id=?", (channel_id,))
            return await cu.fetchone()

async def get_locked_channels() -> list[int]:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT channel_id FROM locked_channels_permissions")
            result = await cu.fetchall()
            if result:
                return [int(row[0]) for row in result]
            else:
                return []

async def delete_channel_permissions(channel_id: int) -> None:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("DELETE FROM locked_channels_permissions WHERE channel_id=?", (channel_id,))
            await conn.commit()

# EPI

async def save_epi_config(sticky: bool, message: str = None, message_id: int = None) -> None:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("INSERT INTO epi_config (message, message_id, sticky) VALUES (?, ?, ?)", (message, message_id, sticky,))
            await conn.commit()

async def toggle_epi_user(user_id: int) -> None:
    """  
    Add the user id to the list if they aren't in it, and remove them from it if they are in it.
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("INSERT INTO epi_users (user_id) VALUES (?) ON CONFLICT (user_id) DO DELETE FROM epi_users WHERE user_id=? ", (user_id, user_id,))
            await conn.commit()

async def get_epi_users() -> list[Optional[int]]:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT user_id FROM epi_users")
            result = await cu.fetchall()
            if result: 
                return [int(user_id) for user_id in result]
            else: 
                return []

async def get_epi_config() -> Optional[dict[str, int, str, str, str, int, str, bool]]: # {"started_ts": 123, "message": "low taper fade is still massive", "message_id": 123, sticky: True}
    """  
    Returns a dict of the saved config in this format
    {
        "started_ts": int(123),
        "message": str("low taper fade is still massive") | None,
        "message_id": int(123456) | None,
        "sticky": bool(False)
        }
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT * FROM epi_config")
            result = await cu.fetchall()
            if result:
                return {
                    "started_ts": result[0],
                    "message": result[1],
                    "message_id": result[2],
                    "sticky": result[3]
                }
""" 
async def get_epi_msg() -> Optional[str]:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT message FROM epi_config")
            result = await cu.fetchone()
            if result:
                return result[0]
            else:
                None

async def get_epi_message_id() -> Optional[int]:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT message_id FROM epi_config")
            result = await cu.fetchone()
            if result:
                return result[0]
            else:
                return None """

async def add_epi_message(message_id: int, thread_id: int) -> None:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("INSERT INTO epi_messages (thread_id, message_id) VALUES (?, ?) ON CONFLICT (thread_id, message_id) DO NOTHING", (thread_id, message_id,))

async def get_epi_messages() -> dict[int, int]: # {thread_id: message_id}
    """  
    Get a dict of {int(thread_id): int(message_id)} of all saved epi messages
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT * FROM epi_messages")
            result = await cu.fetchall()
            data = {}
            for row in result:
                data[row[0]] = row[1] # row[0] - thread id, row[1] - message id
            return data

async def delete_epi_messages() -> None:
    """  
    Delete all epi messages from the DB
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("DELETE FROM epi_messages")
            await conn.commit()