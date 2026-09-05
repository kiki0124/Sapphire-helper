import unittest
from utils import check_time_more_than, MaxCache
from datetime import datetime, timedelta, UTC

class TestDatetime(unittest.TestCase):

    def test_less_than_day(self):
        time_object = datetime.now(UTC) - timedelta(hours=5)
        self.assertFalse(check_time_more_than(time_object.timestamp(), timedelta(days=1)))
    
    def test_more_than_day(self):
        time_object = datetime.now(UTC) - timedelta(days=2)
        self.assertTrue(check_time_more_than(time_object.timestamp(), timedelta(days=1)))

    def test_future_time(self):
        time_object = datetime.now(UTC) + timedelta(hours=25)
        self.assertFalse(check_time_more_than(time_object.timestamp(), timedelta(days=1)))


class TestMaxCache(unittest.TestCase):

    def test_more_than_max_size(self):
        max_size = 10
        cache = MaxCache(max_size)

        for i in range(max_size + 5): # 0 - 14
            if i > 7:
                cache.add(i)
            else:
                cache[i] = None

        # cache: {5, 6, 7, 8, 9, 10, 11, 12, 13, 14}
        for i in range(5, max_size + 5):
            if i < 10:
                self.assertTrue(cache[i] is None, f"__contains__: {i} not in cache")
            else:
                self.assertTrue(cache.pop(i, -1) is None, f"pop: {i} not in cache")


if __name__ == '__main__':
    unittest.main()