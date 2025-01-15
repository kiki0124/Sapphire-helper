import datetime
import aiosqlite as sql
from string import ascii_letters, digits
import random

DB_PATH = "app/database/data.db"

# other functions

async def main():
    async with sql.connect(DB_PATH) as conn: 
        async with conn.cursor() as cu:
            await cu.execute("CREATE TABLE IF NOT EXISTS pending_posts(post_id INTEGER UNIQUE NOT NULL PRIMARY KEY, timestamp INTEGER NOT NULL)")
            await cu.execute("CREATE TABLE IF NOT EXISTS readthedamnrules(post_id INTEGER UNIQUE NOT NULL PRIMARY KEY, user_id INTEGER NOT NULL)")
            await conn.commit()

def generate_random_id() -> str:
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

async def add_post_to_pending(post_id: int, timestamp: int) -> None:
    """
    Add the post with the given id and timestamp to pending db
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"INSERT INTO pending_posts (post_id, timestamp) VALUES ({post_id}, {timestamp})")
            await conn.commit()

async def get_pending_posts() -> list[int]:
    """
    Get all posts in pending posts table. Returns a list of integers.
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT post_id FROM pending_posts")
            return [int(post_id[0]) for post_id in await cu.fetchall()]

async def remove_post_from_pending(post_id: int) -> None:
    """  
    Remove a post form closing pending db
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"DELETE FROM pending_posts WHERE post_id={post_id}")
            await conn.commit()

async def check_post_last_message_time(post_id: int) -> bool:
    """
    Returns if the timestamp of a post (from db) is more than one day ago (24 hours).
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"SELECT timestamp FROM pending_posts WHERE post_id={post_id}")
            result = await cu.fetchone()
            timestamp = result[0]
            return check_time_more_than_day(timestamp)

# readthedamnrules system related functions

async def add_post_to_rtdr(post_id: int, user_id: int) -> None:
    """  
    Add post with given id to readthedamnrules table/system
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"INSERT INTO readthedamnrules (post_id, user_id) VALUES ({post_id}, {user_id})")
            await conn.commit()

async def get_post_creator_id(post_id: int) -> int|None:
    """  
    Get the id of whoever the post was created for if its part of readthedamnrules system
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"SELECT user_id FROM readthedamnrules WHERE post_id={post_id}")
            result = None
            result = await cu.fetchone()
            return result[0] if result else None

async def remove_post_from_rtdr(post_id: int) -> None:
    """  
    Remove post with given id from readthedamnrules system
    """
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"DELETE FROM readthedamnrules WHERE post_id={post_id}")
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
                return [post_id for post_id in result[0]]
            else:
                return []