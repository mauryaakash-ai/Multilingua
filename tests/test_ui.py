import unittest

from multilingua.ui import review_rows, reviewed_segments


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.original = [dict(start=0.4, end=1.4, text="Hello", translation="नमस्ते")]

    def test_only_translation_can_change(self):
        rows = review_rows(self.original)
        rows[0][4] = "आप कैसे हैं?"
        result = reviewed_segments(rows, self.original, 2)
        self.assertEqual(result[0]["translation"], "आप कैसे हैं?")
        self.assertEqual(self.original[0]["translation"], "नमस्ते")

    def test_tampered_source_or_timing_rejected(self):
        for column, value in ((0, 2), (1, 0), (2, 2), (3, "Altered original")):
            rows = review_rows(self.original)
            rows[0][column] = value
            with self.assertRaises(ValueError):
                reviewed_segments(rows, self.original, 2)

    def test_removed_rows_and_empty_translation_rejected(self):
        with self.assertRaises(ValueError):
            reviewed_segments([], self.original, 2)
        rows = review_rows(self.original)
        rows[0][4] = ""
        with self.assertRaises(ValueError):
            reviewed_segments(rows, self.original, 2)

    def test_ui_builds_without_model_configuration(self):
        try:
            import gradio  # noqa: F401
        except ImportError:
            self.skipTest("Install the ui extra for interface checks")
        from multilingua.ui import build_app

        app = build_app("/nonexistent/multilingua.json")
        self.assertIn("Dubbing Studio", app.title)
