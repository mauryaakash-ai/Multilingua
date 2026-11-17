import unittest
from multilingua.languages import validate_model_route


class LanguageRouteTests(unittest.TestCase):
    def test_spanish_rejects_indic_adapters(self):
        with self.assertRaisesRegex(ValueError, 'Spanish requires'):
            validate_model_route({'target_language':'es','commands':{'translate':['python','translate.py'],'tts':['python','tts_parler.py']}})

    def test_spanish_requires_both_adapters(self):
        config={'target_language':'es','commands':{'translate':['python','translate_nllb.py'],'tts':['python','tts_xtts.py']}}
        validate_model_route(config)
        config['target_language']='hi'
        with self.assertRaisesRegex(ValueError, 'Indic target'):
            validate_model_route(config)
