import datetime # python module for using datetime objects
import aiosqlite as sql # asynchronous, sqlite based, database wrapper for Python


async def main(): # main function, create the table, should only be called once
    async with sql.connect("data.db") as conn: # create an asynchronous connection with the db
        async with conn.cursor() as cu: # create an asynchronous connection with the db cursor
            await cu.execute("CREATE TABLE IF NOT EXISTS pending_posts(post_id INTEGER UNIQUE NOT NULL PRIMARY KEY, timestamp INTEGER NOT NULL)") # execute given command
            await cu.execute("CREATE TABLE IF NOT EXISTS readthedamnrules(post_id INTEGER UNIQUE NOT NULL PRIMARY KEY, user_id INTEGER NOT NULL)")
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
            return [int(post_id[0]) for post_id in await cu.fetchall()] # change the return type to list[int]

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

# readthedamnrules system related functions

async def add_post_to_rtdr(post_id: int, user_id: int) -> None:
    """  
    Add post with given id to readthedamnrules table/system
    """
    async with sql.connect('data.db') as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"INSERT INTO readthedamnrules (post_id, user_id) VALUES ({post_id}, {user_id})") # insert the post to the table with the post id and user/author id
            await conn.commit()

async def get_post_creator_id(post_id: int) -> int|None:
    """  
    Get the id of whoever the post was created for if its part of readthedamnrules system
    """
    async with sql.connect('data.db') as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"SELECT user_id FROM readthedamnrules WHERE post_id={post_id}") # select only the user id (as thats what needed to return)
            result = None
            result = await cu.fetchone() # there should only be one returned result, so fetchone
            return result[0] if result else None # .fetchone() returns a tuple, return the first item or None if there isn't a first item

async def remove_post_from_rtdr(post_id: int) -> None:
    """  
    Remove post with given id from readthedamnrules system
    """
    async with sql.connect('data.db') as conn:
        async with conn.cursor() as cu:
            await cu.execute(f"DELETE FROM readthedamnrules WHERE post_id={post_id}")
            await conn.commit()
