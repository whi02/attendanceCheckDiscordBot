import unittest
from datetime import date, datetime

from bot.streak import (
    KST,
    best_streak,
    build_ranking,
    current_streak,
    is_check_in_open,
    next_open_at,
    weekend_of,
)


def d(month: int, day: int) -> date:
    return date(2026, month, day)


CASE_1 = {d(9, 25), d(9, 26), d(9, 27), d(10, 2), d(10, 3)}


class StreakExampleTest(unittest.TestCase):
    """Examples from section 4 of docs/PLANNING.md."""

    cases = [
        # (#, records, today, current, best)
        (1, CASE_1, d(10, 3), 5, 5),
        (2, CASE_1, d(10, 4), 5, 5),
        (3, CASE_1, d(10, 5), 0, 5),
        (4, {d(9, 26), d(9, 27), d(10, 3)}, d(10, 3), 1, 2),
        (5, {d(9, 27), d(10, 2)}, d(10, 2), 2, 2),
        (6, {d(9, 26), d(9, 27)}, d(10, 1), 2, 2),
        (7, {d(9, 26), d(9, 27)}, d(10, 2), 2, 2),
        (8, {d(9, 26), d(9, 27)}, d(10, 3), 0, 2),
        (
            9,
            {d(9, 18), d(9, 19), d(9, 20), d(9, 25), d(9, 26), d(10, 2), d(10, 3)},
            d(10, 3),
            2,
            5,
        ),
    ]

    def test_examples(self):
        for number, records, today, current, best in self.cases:
            with self.subTest(example=number):
                self.assertEqual(current_streak(records, today), current)
                self.assertEqual(best_streak(records), best)

    def test_empty(self):
        self.assertEqual(current_streak(set(), d(10, 3)), 0)
        self.assertEqual(best_streak(set()), 0)


class CheckInWindowTest(unittest.TestCase):
    def kst(self, month, day, hour, minute=0, second=0):
        return datetime(2026, month, day, hour, minute, second, tzinfo=KST)

    def test_friday_boundary(self):
        self.assertFalse(is_check_in_open(self.kst(10, 2, 16, 59, 59)))
        self.assertTrue(is_check_in_open(self.kst(10, 2, 17, 0, 0)))

    def test_weekend_and_weekdays(self):
        self.assertTrue(is_check_in_open(self.kst(10, 3, 0)))
        self.assertTrue(is_check_in_open(self.kst(10, 4, 23, 59, 59)))
        self.assertFalse(is_check_in_open(self.kst(10, 5, 0)))
        self.assertFalse(is_check_in_open(self.kst(10, 1, 23)))

    def test_utc_input_is_converted(self):
        # 2026-10-02 08:00 UTC == Friday 17:00 KST
        utc = datetime.fromisoformat("2026-10-02T08:00:00+00:00")
        self.assertTrue(is_check_in_open(utc))

    def test_next_open_at(self):
        expected = self.kst(10, 9, 17)
        self.assertEqual(next_open_at(self.kst(10, 5, 9)), expected)  # Monday
        self.assertEqual(next_open_at(self.kst(10, 8, 23)), expected)  # Thursday
        self.assertEqual(next_open_at(self.kst(10, 9, 10)), expected)  # Friday morning

    def test_weekend_of(self):
        weekend = (d(10, 2), d(10, 3), d(10, 4))
        for today in (d(9, 28), d(10, 1), d(10, 2), d(10, 3), d(10, 4)):
            with self.subTest(today=today):
                self.assertEqual(weekend_of(today), weekend)


class RankingTest(unittest.TestCase):
    def test_ties_share_rank_and_skip(self):
        today = d(10, 4)
        records = {
            1: {d(10, 2), d(10, 3), d(10, 4)},  # 3
            2: {d(10, 3), d(10, 4)},  # 2
            3: {d(10, 3), d(10, 4)},  # 2
            4: {d(10, 4)},  # 1
            5: {d(9, 26)},  # broken
        }
        ranks = {e.user_id: e.rank for e in build_ranking(records, today)}
        self.assertEqual(ranks, {1: 1, 2: 2, 3: 2, 4: 4, 5: None})

    def test_total_breaks_order_but_not_rank(self):
        today = d(10, 4)
        records = {
            10: {d(10, 4)},
            20: {d(9, 19), d(10, 4)},  # same current, more total
        }
        entries = build_ranking(records, today)
        self.assertEqual([e.user_id for e in entries], [20, 10])
        self.assertEqual([e.rank for e in entries], [1, 1])


if __name__ == "__main__":
    unittest.main()
