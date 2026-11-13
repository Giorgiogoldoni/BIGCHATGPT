import unittest

from big_validation import _metrics


class BigValidationTests(unittest.TestCase):
    def test_metrics_summarize_forward_returns(self):
        items = [
            {"t": "A", "forward_return": 2.0},
            {"t": "B", "forward_return": -1.0},
            {"t": "C", "forward_return": 3.0},
        ]
        result = _metrics(items)
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["median"], 2.0)
        self.assertEqual(result["mean"], 1.33)
        self.assertEqual(result["positive_pct"], 66.7)

    def test_empty_metrics_are_safe(self):
        result = _metrics([])
        self.assertEqual(result["n"], 0)
        self.assertIsNone(result["median"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
