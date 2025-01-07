import unittest
from functions import check_time_more_than_day
from datetime import datetime, timedelta
import asyncio

class test_functions(unittest.TestCase):

    tz = datetime.now().astimezone().tzinfo

    def test_less_than_day(self):
        time_object = datetime.now(tz=self.tz) - timedelta(hours=5) # 6 hours behind now
        self.assertFalse(check_time_more_than_day(time_object.timestamp()))
    
    def test_more_than_day(self):
        time_object = datetime.now(tz=self.tz) - timedelta(days=2)
        self.assertTrue(check_time_more_than_day(time_object.timestamp()))

    def test_future_time(self):
        time_object = datetime.now(tz=self.tz) + timedelta(hours=25)
        self.assertFalse(check_time_more_than_day(time_object.timestamp()))


if __name__ == '__main__':
    unittest.main()