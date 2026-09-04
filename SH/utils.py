from __future__ import annotations

from datetime import datetime, UTC, timedelta
import asqlite as sql
from string import ascii_letters, digits
import random
from typing import Any, TYPE_CHECKING
from pathlib import Path

from collections import OrderedDict

if TYPE_CHECKING:
    from collections.abc import Sequence
    from discord import User, Member

DB_PATH = str(Path(__file__).parent / 'database' / 'data.db')

# other functions

async def setup_db():
    """  
    Called once whenever the bot is turned on (in setup_hook)
    Creates DB tables
    """
    async with sql.connect(DB_PATH) as conn: 
        async with conn.cursor() as cu:
            await cu.execute("CREATE TABLE IF NOT EXISTS reminder_waiting(post_id INTEGER PRIMARY KEY NOT NULL, timestamp INTEGER NOT NULL)")
            await cu.execute("CREATE TABLE IF NOT EXISTS locked_channels_permissions(channel_id INTEGER PRIMARY KEY NOT NULL, allow BIGINT, deny BIGINT)")
            await cu.execute("CREATE TABLE IF NOT EXISTS tags(name TEXT UNIQUE NOT NULL, content TEXT NULL, creator_id INTEGER NOT NULL, created_ts INTEGER, uses INTEGER NOT NULL DEFAULT 0)")
            await conn.commit()

def generate_random_id() -> str:
    """  
    Generates a random 6 letter id made of letters (lower and upper case) and numbers.
    """
    characters = ascii_letters + digits
    return ''.join(random.choice(characters) for _ in range(6))

def check_time_more_than(timestamp: float, to_compare: timedelta) -> bool:
    """  
    Check if the given timestamp is older than to_compare(e.g 1d) ago
    """
    timestamp_dt = datetime.fromtimestamp(timestamp, UTC)

    return timestamp_dt + to_compare <  datetime.now(UTC)

def format_list(items: Sequence, conjunction: str = "or") -> str:
    return ", ".join(items[:-1]) + f" {conjunction} " + items[-1]

def format_recommended_by(user: User | Member) -> str:
    """
    Formats the 'recommended by' footer used by messages with cv2.
    """
    return f"-# Recommended by [@{user.name}](https://discord.com/users/{user.id})"


def str_to_timedelta(duration: str) -> timedelta:
    td = timedelta()
    duration_list = duration.replace(" ", "").split(",")
    for duration in duration_list:
        if duration.endswith("s"):
            new_time = duration.rstrip("s")
            td += timedelta(seconds=float(new_time))
        elif duration.endswith("sec"):
            new_time = duration.rstrip("sec")
            td += timedelta(seconds=float(new_time))

        elif duration.endswith("m"):
            new_time = duration.rstrip("m")
            td += timedelta(minutes=float(new_time))
        elif duration.endswith("min"):
            new_time = duration.rstrip("min")
            td += timedelta(minutes=float(new_time))

        elif duration.endswith("h"):
            new_time = duration.rstrip("h")
            td += timedelta(hours=float(new_time))
        elif duration.endswith("hour"):
            new_time = duration.rstrip("hour")
            td += timedelta(hours=float(new_time))

        elif duration.endswith("d"):
            new_time = duration.rstrip("d")
            td += timedelta(days=float(new_time))
        elif duration.endswith("day"):
            new_time = duration.rstrip("day")
            td += timedelta(days=float(new_time))

        else:
            raise ValueError(f"`{duration}` is invalid!")
    return td



class MaxCache:
    """
    A custom cache that acts as a set/dict with a max size.
    When the max size is reached upon adding new a item, the oldest item in the cache is removed.
    """
    __slots__ = ('_cache', 'max_size')
    
    def __init__(self, max_size: int) -> None:
        self._cache = OrderedDict()
        self.max_size = max_size

    def __str__(self) -> str:
        return str(self._cache)

    def __repr__(self) -> str:
        return repr(self._cache)

    def __len__(self) -> int:
        return len(self._cache)

    def __bool__(self) -> bool:
        return bool(self._cache)

    def __contains__(self, item) -> bool:
        return item in self._cache

    
    # dict-like functions
    def __setitem__(self, key, value) -> None:
        if len(self) == self.max_size:
            self._cache.popitem(last=False)
        self._cache[key] = value

    def __getitem__(self, key) -> Any:
        return self._cache[key]

    def get(self, key, default = None) -> Any:
        return self._cache.get(key, default)

    def pop(self, key, default = None) -> Any:
        return self._cache.pop(key, default)


    def popitem(self, last: bool = True) -> Any:
        return self._cache.popitem(last)


    # set-like functions
    def add(self, key) -> None:
        """Add to the cache with the value as ``None``"""
        self.__setitem__(key, None)

    def remove(self, key) -> None:
        """Remove element elem from the cache. Raises :exec:`KeyError` if elem is not contained in the cache."""
        del self._cache[key]

    def discard(self, key) -> None:
        """Remove element elem from the cache if it is present."""
        self._cache.pop(key, None)


def sql_to_dict(sql_results: list[tuple]) -> dict[str, Any]:
    """Formats a sql.Row into dict"""

    possible_queries = ('post_id', 'timestamp', 'user_id', 'channel_id', 'allow', 'deny', 'name', 'content', 'uses', 'creator_id', 'created_ts') #All the possible queries in all the tables
    data: dict[str, Any] = {}
    for row in sql_results: # fetchall() returns a list of tuples, so we loop through the list
        for query in possible_queries: 
            try:
                value = row[query] # Try to fetch the value from the row
            except IndexError:
                continue
            if query in data: # For example 'SELECT user_id FROM epi_users', it will make user_id a list
                if not isinstance(data[query], list):
                    data[query] = [data[query]] if query in data else []
                data[query].append(value)
            else:
                data[query] = value
                
    return data

async def execute_sql(cmd: str) -> dict[str, Any] | Exception:
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
            result = await cu.fetchall()
            return sql_to_dict(result)


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
                return [row['post_id'] for row in result]
            else:
                return []

async def remove_post_from_waiting(post_id: int) -> None:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("DELETE FROM reminder_waiting WHERE post_id=?", (post_id,))
            await conn.commit()

async def add_post_to_waiting(post_id: int, timestamp: int | None = None) -> None:
    if timestamp is None: 
        timestamp = int(datetime.now(UTC).timestamp())
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
                return [row['channel_id'] for row in result]
            return []

async def delete_channel_permissions(channel_id: int) -> None:
    async with sql.connect(DB_PATH) as conn:
        async with conn.cursor() as cu:
            await cu.execute("DELETE FROM locked_channels_permissions WHERE channel_id=?", (channel_id,))
            await conn.commit()

# Tags

async def check_tag_exists(name: str) -> bool:
    async with sql.connect(DB_PATH) as conn:
        result = await conn.fetchone("SELECT content FROM tags WHERE name=?", (name,))
        return bool(result)

async def save_tag( name: str, content: str, creator_id: int):
    async with sql.connect(DB_PATH) as conn:
        await conn.execute("INSERT INTO tags (name, content, creator_id, created_ts) VALUES (?, ?, ?, ?)", 
                           (name, content, creator_id, round(datetime.now(UTC).timestamp())))
        await conn.commit()

async def get_tag_content(name: str) -> str | None:
    async with sql.connect(DB_PATH) as conn:
        result = await conn.fetchone("SELECT content FROM tags WHERE name=?", (name,))
        if result:
            return result['content']

        return None
    
async def increment_tag_uses(name: str) -> None:
    async with sql.connect(DB_PATH) as conn:
        await conn.execute("UPDATE tags SET uses=uses+1 WHERE name=?", (name, ))
        await conn.commit()

async def get_tag_data(name: str) -> dict[str, Any] | None:
    async with sql.connect(DB_PATH) as conn:
        result = await conn.fetchone("SELECT * FROM tags WHERE name=?", (name, ))
        if result:
            return result # type: ignore
        return None

async def update_tag_name(original_name: str, new_name: str):
    async with sql.connect(DB_PATH) as conn:
        await conn.execute("UPDATE tags SET name=? WHERE name=?", (new_name, original_name))
        await conn.commit()

async def update_tag_content(name: str, content: str):
    async with sql.connect(DB_PATH) as conn:
        await conn.execute("UPDATE tags SET content=? WHERE name=?", (content, name))
        await conn.commit()

async def get_most_used_tags() -> list[str]:
    """  
    Returns the most used tags, max 100
    """
    async with sql.connect(DB_PATH) as conn:
        result = await conn.fetchall("SELECT name FROM tags ORDER BY uses LIMIT 100")
        return [tag['name'] for tag in result]

async def delete_tag(name: str):
    async with sql.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM tags WHERE name=?", (name,))
        await conn.commit()
