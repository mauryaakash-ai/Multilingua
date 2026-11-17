import unittest

from multilingua.languages import validate_model_route


class LanguageRouteTests(unittest.TestCase):
    def test_hindi_route_accepted(self):
        config = {"target_language": "hi"}
        self.assertEqual(validate_model_route(config)["name"], "Hindi")

    def test_default_route_is_hindi(self):
        config = {}
        self.assertEqual(validate_model_route(config)["name"], "Hindi")

    def test_non_hindi_route_rejected(self):
        for code in ("es", "ta", "te", "fr", "de"):
            with self.assertRaisesRegex(ValueError, "Only English to Hindi"):
                validate_model_route({"target_language": code})
