import unittest
from functions import check_time_more_than_day
from datetime import datetime, timedelta, UTC

class TestDatetime(unittest.TestCase):

    def test_less_than_day(self):
        time_object = datetime.now(UTC) - timedelta(hours=5)
        self.assertFalse(check_time_more_than_day(time_object.timestamp()))
    
    def test_more_than_day(self):
        time_object = datetime.now(UTC) - timedelta(days=2)
        self.assertTrue(check_time_more_than_day(time_object.timestamp()))

    def test_future_time(self):
        time_object = datetime.now(UTC) + timedelta(hours=25)
        self.assertFalse(check_time_more_than_day(time_object.timestamp()))


if __name__ == '__main__':
    unittest.main()