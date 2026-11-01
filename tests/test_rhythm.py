import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from fusionify_audio.engine import SR, measure
from fusionify_audio.rhythm import estimate_taps, tempo_map_beats
from fusionify_audio.service import Service
from test_engine import click_track


class RhythmTests(unittest.TestCase):
    def test_taps_with_jitter_and_missed_pulse(self):
        taps=[.4,.902,1.399,1.901,2.901,3.402,3.899,4.401]
        estimate=estimate_taps(taps)
        self.assertAlmostEqual(estimate['tempo_bpm_estimate'],120,delta=1)
        self.assertEqual(estimate['discarded_intervals'],1)
        self.assertLess(estimate['interval_jitter_ratio'],.02)
        for bad in [[],[0,.5,1],[0,.5,.5,1],[0,.5,True,1.5],[0,.5,float('nan'),2],
                    [0,.1,.2,.3],[0,1,1.4,3.4,3.5,4.9],list(np.arange(130))]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):estimate_taps(bad)

    def test_changing_tempo_offsets_gaps_and_exclusive_end(self):
        report={'duration_s':12,'onsets':[]}
        regions=[{'start_s':1,'end_s':5,'bpm':120,'first_beat_s':1.25},
                 {'start_s':6,'end_s':10,'bpm':180,'first_beat_s':6}]
        beats,parsed=tempo_map_beats(report,regions)
        self.assertEqual(parsed,regions)
        times=[b['time_s'] for b in beats]
        np.testing.assert_allclose(times[:8],np.arange(1.25,5,.5),atol=1e-6)
        np.testing.assert_allclose(times[8:],np.arange(6,10,1/3),atol=1e-6)
        self.assertFalse(any(5<=t<6 for t in times))
        exact,_=tempo_map_beats(report,[{'start_s':0,'end_s':2,'bpm':120,'first_beat_s':0}])
        self.assertEqual([b['time_s'] for b in exact],[0,.5,1,1.5])

    def test_snap_only_to_measured_nearby_onsets_and_reject_bad_regions(self):
        report={'duration_s':4,'onsets':[{'time_s':.42,'strength':2},{'time_s':.99,'strength':3},{'time_s':1.45,'strength':2}]}
        region={'start_s':0,'end_s':2,'bpm':120,'first_beat_s':.4}
        beats,_=tempo_map_beats(report,[region],.05)
        self.assertEqual(beats[0]['time_s'],.42)
        self.assertEqual(beats[0]['provenance'],'user_grid_snapped_to_measured_onset')
        self.assertEqual(beats[1]['time_s'],.9)
        self.assertEqual(beats[1]['provenance'],'user_tempo_grid')
        for regions in [[],[region]*33,[region,{**region,'start_s':1}],
                        [{**region,'end_s':5}],[{**region,'first_beat_s':2}],
                        [{**region,'bpm':True}],[{**region,'bpm':'120'}],[{**region,'bpm':float('inf')}],
                        [{**region,'filter':'anything'}]]:
            with self.subTest(regions=regions):
                with self.assertRaises(ValueError):tempo_map_beats(report,regions)
        for bad in [-.1,.101,float('nan'),True,'0.1']:
            with self.assertRaises(ValueError):tempo_map_beats(report,[region],bad)

    def test_onsets_are_measured_independently_and_silence_empty(self):
        r=measure(click_track(128,4));onsets=[o['time_s'] for o in r['onsets']]
        self.assertGreater(len(onsets),5)
        for t in np.arange(.4,3.9,60/128):self.assertLess(min(abs(t-o) for o in onsets),.045)
        self.assertEqual(measure(np.zeros(SR*3,dtype=np.float32))['onsets'],[])

    def test_immutable_lineage_review_and_plan_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'track.wav',SR,click_track(128,5))
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id'];original=json.dumps(s.record(aid),sort_keys=True)
                old=s.create_project(aid)
                result=s.apply_tempo_map(aid,[{'start_s':0,'end_s':5,'bpm':120,'first_beat_s':.4}],.05)
                mapped=result['analysis_id'];review=s.rhythm_review(mapped)
                self.assertEqual(review['parent_analysis_id'],aid)
                self.assertEqual(len(review['waveform']),1200)
                self.assertNotIn('source_path',review)
                self.assertEqual(json.dumps(s.record(aid),sort_keys=True),original)
                self.assertEqual(s.project(old['project_id'])['analysis_id'],aid)
                new=s.create_project(mapped,{'music_in_s':1,'duration_s':2,'intensity':'high'})
                for e in new['timeline']['events']:
                    self.assertEqual(e['status'],'user-directed')
                    self.assertAlmostEqual(e['source_time_s']-1,e['video_time_s'],places=4)
                self.assertIn('user tempo map',new['timeline']['scene_boundary_source'])
                manual=s.correct_beats(mapped,[.5,1,1.5])['analysis_id']
                self.assertNotIn('tempo_map',s.record(manual)['report'])
                self.assertEqual(s.record(manual)['report']['parent_analysis_id'],mapped)
                exported=json.loads(Path(s.export(new['project_id'])['output_path']).read_text())
                self.assertEqual(exported['analysis_id'],mapped)
                (root/'track.wav').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'changed'):s.rhythm_review(mapped)
            finally:s.close()

    def test_original_review_duration_gain_and_click_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);y=click_track(128,3);wavfile.write(root/'track.wav',SR,y)
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id']
                def render(volume):
                    job=s.beat_preview(aid,click_volume=volume)
                    for _ in range(200):
                        state=s.status(job['job_id'])
                        if state['status'] in ('completed','failed'):break
                        time.sleep(.02)
                    self.assertEqual(state['status'],'completed',state)
                    raw=subprocess.check_output(['ffmpeg','-v','error','-i',state['output_path'],'-ar',str(SR),'-ac','1','-f','f32le','pipe:1'])
                    return np.frombuffer(raw,dtype='<f4')
                original=render(0);clicked=render(1)
                self.assertAlmostEqual(len(original)/SR,3,delta=.01)
                self.assertGreater(float(np.corrcoef(original[:len(y)],y)[0,1]),.98)
                self.assertAlmostEqual(float(np.linalg.norm(original[:len(y)])/np.linalg.norm(y)),1,delta=.1)
                self.assertGreater(float(np.linalg.norm(clicked-original)),.1)
                for bad in [-1,2.1,float('inf'),True]:
                    with self.assertRaises(ValueError):s.beat_preview(aid,click_volume=bad)
            finally:s.close()


if __name__=='__main__':unittest.main()
