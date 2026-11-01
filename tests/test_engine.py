import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from fusionify_audio.engine import SR, analyze, measure, media_file
from fusionify_audio.render import edit_plan


def click_track(bpm, duration=12):
    y=np.zeros(int(duration*SR),dtype=np.float32)
    tx=np.arange(int(.035*SR))/SR
    click=(.7*np.sin(2*np.pi*180*tx)*np.exp(-100*tx)).astype(np.float32)
    for t in np.arange(.4,duration-.1,60/bpm):
        k=int(t*SR);y[k:k+len(click)]+=click[:len(y)-k]
    return y


class AnalysisTests(unittest.TestCase):
    def test_known_pulses(self):
        for bpm in (96,128,160):
            with self.subTest(bpm=bpm):
                report=measure(click_track(bpm))
                self.assertIsNotNone(report['tempo_bpm_estimate'])
                ratios=[report['tempo_bpm_estimate']/bpm/f for f in (.5,1,2)]
                self.assertLess(min(abs(1-r) for r in ratios),.03)
                times=np.array([b['time_s'] for b in report['beats']])
                self.assertGreater(len(times),8)
                # A marker may occur anywhere inside the 35 ms onset, not an arbitrary grid.
                distances=np.abs((times-.4+30/bpm)%(60/bpm)-30/bpm)
                self.assertLess(float(np.median(distances)),.045)
                json.dumps(report,allow_nan=False)

    def test_silence_has_no_fabricated_beats(self):
        report=measure(np.zeros(5*SR,dtype=np.float32))
        self.assertIsNone(report['tempo_bpm_estimate'])
        self.assertEqual(report['beats'],[])
        self.assertEqual(report['transitions'],[])
        json.dumps(report,allow_nan=False)

    def test_short_and_nonfinite_input(self):
        with self.assertRaises(ValueError):measure(np.zeros(10))
        with self.assertRaises(ValueError):measure(np.full(2048,np.nan))
        report=measure(np.zeros(1200,dtype=np.float32))
        self.assertEqual(report['beats'],[])

    def test_decoding_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'music';root.mkdir()
            track=root/'click.wav';wavfile.write(track,SR,click_track(128,4))
            report,_=analyze(media_file(root,'click.wav'))
            self.assertAlmostEqual(report['duration_s'],4,places=3)
            self.assertEqual(len(report['source']['sha256']),64)
            outside=Path(tmp)/'outside.wav';outside.write_bytes(track.read_bytes())
            with self.assertRaises(ValueError):media_file(root,'../outside.wav')
            try:(root/'link.wav').symlink_to(outside)
            except OSError:pass
            else:
                with self.assertRaises(ValueError):media_file(root,'link.wav')

    def test_trim_keeps_source_and_video_times_separate(self):
        report=measure(click_track(128))
        plan=edit_plan(report,2,5,'high')
        self.assertEqual(plan['duration_s'],5)
        self.assertFalse(plan['flash_enabled'])
        for e in plan['events']:
            self.assertAlmostEqual(e['video_time_s'],e['source_time_s']-2,places=3)
            self.assertTrue(0<=e['video_time_s']<5)
        self.assertAlmostEqual(edit_plan(report)['duration_s'],12)
        for start,duration in [(0,20),(float('nan'),2),(0,float('inf'))]:
            with self.assertRaises(ValueError):edit_plan(report,start,duration)


if __name__=='__main__':unittest.main()
