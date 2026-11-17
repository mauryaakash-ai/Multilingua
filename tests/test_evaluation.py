import unittest

from multilingua.evaluation import error_rates, percentiles


class EvaluationTests(unittest.TestCase):
    def test_known_word_errors(self):
        self.assertAlmostEqual(error_rates("one two three", "one four")["wer"], 2 / 3)

    def test_hindi_punctuation(self):
        self.assertEqual(error_rates("नमस्ते, भारत।", "नमस्ते भारत")["wer"], 0)

    def test_insertions_can_exceed_one(self):
        self.assertEqual(error_rates("one", "one two three")["wer"], 2)

    def test_empty_reference_rejected(self):
        with self.assertRaises(ValueError):
            error_rates("", "words")

    def test_nearest_rank(self):
        self.assertEqual(percentiles([1, 2, 3, 4, 5])["p95"], 5)
