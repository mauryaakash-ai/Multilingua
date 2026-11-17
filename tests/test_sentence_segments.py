import unittest
from multilingua.timeline import sentence_segments

class SentenceSegmentsTests(unittest.TestCase):
    def test_joins_mid_sentence_without_mutating_asr(self):
        source=[dict(start=0,end=3.78,text='Our neighboring states notice right to work'),dict(start=3.78,end=5.78,text='will affect Wisconsin.')]
        result=sentence_segments(source)
        self.assertEqual(len(result),1)
        self.assertEqual((result[0]['start'],result[0]['end']),(0,5.78))
        self.assertEqual(source[0]['end'],3.78)
    def test_stops_at_sentence_pause_or_duration_bound(self):
        for first,second in [
            (dict(start=0,end=2,text='Done.'),dict(start=2,end=3,text='Next')),
            (dict(start=0,end=2,text='Part'),dict(start=3,end=4,text='next')),
            (dict(start=0,end=8,text='Part'),dict(start=8,end=13,text='next')),
        ]:
            self.assertEqual(len(sentence_segments([first,second])),2)
