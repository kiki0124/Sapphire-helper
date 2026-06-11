import unittest
from functions import check_time_more_than
from datetime import datetime, timedelta, UTC

class test_functions(unittest.TestCase):
    def test_less_than_day(self):
        time_object = datetime.now(UTC) - timedelta(hours=5)
        self.assertFalse(check_time_more_than(time_object.timestamp(), timedelta(days=1)))
    
    def test_more_than_day(self):
        time_object = datetime.now(UTC) - timedelta(days=2)
        self.assertTrue(check_time_more_than(time_object.timestamp(),  timedelta(days=1)))

    def test_future_time(self):
        time_object = datetime.now(UTC) + timedelta(hours=25)
        self.assertFalse(check_time_more_than(time_object.timestamp(),  timedelta(days=1)))


if __name__ == '__main__':
    unittest.main()