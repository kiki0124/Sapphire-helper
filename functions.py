import datetime # python module for using datetime objects
import aiosqlite as sql # asynchronous, sqlite based, database wrapper for Python

async def main(): # main function, create the table, should only be called once
    async with sql.connect("data.db") as conn: # create an asynchronous connection with the db
        async with conn.cursor() as cu: # create an asynchronous connection with the db cursor
            await cu.execute("CREATE TABLE IF NOT EXISTS pending_posts(post_id INTEGER UNIQUE NOT NULL, timestamp INTEGER NOT NULL)") # execute given command
            await conn.commit() # commit changes

async def add_post_to_pending(post_id: int, timestamp) -> None:
    """
    Add the post with the given id and timestamp to pending db
    """
    async with sql.connect('data.db') as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"INSERT INTO pending_posts (post_id, timestamp) VALUES ({post_id}, {timestamp})") # insert post id and timestamp
            await conn.commit()

async def get_pending_posts() -> list[int]:
    """
    Get all posts in pending posts table. Returns a list of integers.
    """
    async with sql.connect('data.db') as conn:
        async with conn.cursor() as cu:
            await cu.execute("SELECT post_id FROM pending_posts") # select all post_ids from pending posts table
            return [int(post_id[0]) for post_id in await cu.fetchall()]

async def remove_post_from_pending(post_id: int) -> None:
    """  
    Remove a post form closing pending db
    """
    async with sql.connect('data.db') as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"DELETE FROM pending_posts WHERE post_id={post_id}") # delete a post with the given id from db
            await conn.commit()

def check_time_more_than_day(timestamp: int) -> bool:
    """  
    Check if the given time is more than a day ago
    """
    time = datetime.datetime.fromtimestamp(timestamp, tz=datetime.datetime.now().astimezone().tzinfo) # turn the time from timestamp (int) to an aware datetime object
    one_day_ago = datetime.datetime.now(tz=datetime.datetime.now().astimezone().tzinfo) - datetime.timedelta(days=1) # define a datetime object that is 1 day ago
    return not one_day_ago <= time # check if the time (from given timestamp) is "more or equal to" (before) 1 day ago datetime object

async def check_post_last_message_time(post_id: int) -> bool:
    """
    Returns if the timestamp of a post (from db) is more than one day ago (24 hours).
    """
    async with sql.connect('data.db') as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"SELECT timestamp FROM pending_posts WHERE post_id={post_id}") # get the timestamp of the post with the given id
            result = await cu.fetchone()
            timestamp = result[0] # result is tuple, select the first item
            return check_time_more_than_day(timestamp) # check if the time is more than a day with the timestamp