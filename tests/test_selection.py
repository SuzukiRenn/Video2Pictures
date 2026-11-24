import unittest

from video2pictures.selection import select_frames


class SelectionTests(unittest.TestCase):
    def test_all_and_single_frame(self):
        self.assertEqual(list(select_frames(4, "all")), [1, 2, 3, 4])
        self.assertEqual(list(select_frames(1, "uniform", "1")), [1])
        self.assertEqual(list(select_frames(7, "uniform", "1")), [1])

    def test_uniform_endpoints_midpoint_and_no_duplicate_frames(self):
        self.assertEqual(list(select_frames(10, "uniform", "3")), [1, 6, 10])
        for total in range(2, 40):
            for count in range(2, total + 1):
                frames = list(select_frames(total, "uniform", str(count)))
                self.assertEqual((frames[0], frames[-1]), (1, total))
                self.assertEqual(len(frames), count)
                self.assertEqual(frames, sorted(set(frames)))

    def test_ranges_are_sorted_and_deduplicated(self):
        plan = select_frames(10, "ranges", " 8，3 - 5, 2-4, 8-10, 1, 5 ")
        self.assertEqual(list(plan), [1, 2, 3, 4, 5, 8, 9, 10])
        self.assertEqual(plan.count, 8)
        self.assertEqual(list(select_frames(1, "ranges", "1-1")), [1])

    def test_large_ranges_remain_compact(self):
        plan = select_frames(10**9, "ranges", "1-1000000000")
        self.assertEqual(plan.count, 10**9)
        self.assertEqual(next(iter(plan)), 1)
        self.assertEqual(len(plan.spans), 1)

    def test_invalid_values(self):
        for mode, values in (
            ("uniform", ["", "0", "11", "1.2", "-1", "x"]),
            ("ranges", ["", "0", "11", "3-2", "1--2", "1,", "1, ,4", "a", "9-11"]),
        ):
            for value in values:
                with self.subTest(mode=mode, value=value), self.assertRaises(ValueError):
                    select_frames(10, mode, value)
        with self.assertRaises(ValueError):
            select_frames(0, "all")
        with self.assertRaises(ValueError):
            select_frames(10, "unknown")
