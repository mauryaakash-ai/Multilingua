import unittest
from multilingua.timing_fit import rebalance

class TimingFitTests(unittest.TestCase):
    def test_last_phrase_can_borrow_across_multiple_neighbours(self):
        edges=[0,3,13,20,29,30]
        rows=[dict(start=a,end=b,text='text',translation='हिन्दी') for a,b in zip(edges,edges[1:])]
        durations=dict(enumerate([3.448163,10.34449,8.370794,11.006259,2.02]))
        fitted=rebalance(rows,durations)
        self.assertEqual(fitted[0]['start'],0)
        self.assertEqual(fitted[-1]['end'],30)
        self.assertLess(fitted[-1]['start'],29)
        for i,row in enumerate(fitted):
            self.assertLessEqual(durations[i]/(row['end']-row['start']),1.25+1e-8)
            self.assertEqual(row['translation'],rows[i]['translation'])
            if i:self.assertEqual(fitted[i-1]['end'],row['start'])
        self.assertEqual(rows[-1]['start'],29)
    def test_does_not_borrow_across_a_silence(self):
        rows=[dict(start=0,end=4),dict(start=4,end=5),dict(start=5,end=6)]
        with self.assertRaises(ValueError):rebalance(rows,{0:1,2:2})
    def test_rejects_excessive_shift_or_insufficient_budget(self):
        for durations in [{0:1,1:4},{0:5,1:5}]:
            with self.assertRaises(ValueError):rebalance([dict(start=0,end=3),dict(start=3,end=4)],durations)
