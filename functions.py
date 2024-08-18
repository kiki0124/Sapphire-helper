from sqlalchemy import create_engine, Column, Integer, String, delete
from sqlalchemy.orm import sessionmaker, declarative_base
import datetime

engine = create_engine("sqlite:///data.db")
Base = declarative_base()

class ClosingPending(Base):
    __tablename__ = "Closing-pending"
    post_id = Column(Integer, primary_key=True)
    time_str = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def AddPostToPending(post_id: int, time: datetime.datetime) -> None:
    """  
    Move a post from Unanswered posts db to ClosingPending db
    """
    data = ClosingPending(post_id=post_id, time_str=time.replace(second=0, microsecond=0).isoformat())
    session.add(data)
    session.commit()

def GetPendingPosts() -> list:
    """  
    Returns a list[int] of posts (post ids) with status "closing pending", or None if no posts are currently in the db
    """
    posts = [post_id[0] for post_id in session.query(ClosingPending.post_id).all()]
    return posts

def RemovePostFromPending(post_id: int) -> None:
    """  
    Remove a post form closing pending db
    """
    stmt = delete(ClosingPending).where(ClosingPending.post_id==post_id)
    session.execute(stmt)
    session.commit()

def CheckPostLastMessageTime(post_id: int) -> bool:
    """
    Check if the time str of a post is more than one day ago.
    """
    time_str = session.query(ClosingPending).where(ClosingPending.post_id==post_id).first()
    loaded_time = datetime.datetime.fromisoformat(time_str.time_str)
    now = datetime.datetime.now()
    one_day_ago = now - datetime.timedelta(days=1)
    return not one_day_ago.replace(tzinfo=None) <= loaded_time.replace(tzinfo=None) <= now.replace(tzinfo=None)

def CheckTimeLessDay(time: datetime) -> bool:
    """  
    Check if the given time is more than a day ago
    """
    now = datetime.datetime.now().replace(second=0, microsecond=0)
    one_day_ago = now - datetime.timedelta(days=1)
    return not one_day_ago <= time <= now
