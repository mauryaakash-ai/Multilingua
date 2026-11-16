import unittest
from multilingua.timeline import slots,subtitles
from multilingua.streaming import simulate

class TimelineTests(unittest.TestCase):
    def test_gaps_preserved(self):
        result=list(slots([{'start':1,'end':2,'text':'Hi','translation':'नमस्ते'}],3))
        self.assertEqual([(x['start'],x['end']) for x in result],[(0,1),(1,2),(2,3)])
    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            list(slots([{'start':0,'end':2},{'start':1,'end':3}],4))
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError): list(slots([{'start':0,'end':float('nan')}],3))
    def test_out_of_bounds_rejected(self):
        with self.assertRaises(ValueError): list(slots([{'start':0,'end':6}],3))
    def test_subtitles_keep_unicode(self):
        result=subtitles([{'start':1.25,'end':2.5,'translation':'नमस्ते'}])
        self.assertIn('00:00:01,250 --> 00:00:02,500',result)
        self.assertIn('नमस्ते',result)
    def test_fast_stream_no_queue(self):
        rows=simulate([2,4,6],[1,1,1])
        self.assertEqual([x['queue_seconds'] for x in rows],[0,0,0])
    def test_slow_stream_overflows(self):
        with self.assertRaises(OverflowError): simulate([1,2,3,4],[10]*4,max_waiting=1)
    def test_delay_includes_wait(self):
        rows=simulate([1,2],[3,3])
        self.assertEqual(rows[1]['ready_delay_seconds'],5)

if __name__=='__main__': unittest.main()
