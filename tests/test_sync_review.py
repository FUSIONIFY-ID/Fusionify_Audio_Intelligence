import copy
import json
import math
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.io import wavfile

from fusionify_audio.engine import SR
from fusionify_audio.service import Service
from fusionify_audio.motion import MotionFrames
from fusionify_audio.sync_review import review_music_sync
from test_engine import click_track


def fixture(boundary=1.01, native=False):
    sections=[{'start_s':0,'end_s':boundary},{'start_s':boundary,'end_s':3,
              'boundary_locked':True,'boundary_evidence':'user source-time anchor'}]
    project={'project_id':'c'*32,'analysis_id':'a'*32,'revision':4,
             'options':{'visual_mode':'motion_graphics' if native else 'auto',
                        'asset_ids':[] if native else ['b'*32],'scene_overrides':[]},
             'timeline':{'music_in_s':2,'duration_s':3,'scenes':copy.deepcopy(sections),
                         'music_direction':{'sections':sections},'scene_boundary_source':'test'}}
    report={'beats':[{'time_s':1.99,'strength':1},{'time_s':2.98,'strength':1,'provenance':'user_corrected'}],
            'transitions':[{'time_s':3.2,'kind':'energy_rise_candidate'},{'time_s':5,'kind':'energy_rise_candidate'}]}
    return project,report


class SyncReviewTests(unittest.TestCase):
    def test_trim_frame_offset_provenance_and_range(self):
        p,r=fixture();result=review_music_sync(p,r)
        row=result['boundaries'][0]
        self.assertEqual((row['frame_index'],row['video_time_s'],row['source_time_s']),(30,1,3))
        self.assertEqual(row['frame_shift_ms'],-10)
        self.assertEqual(row['nearest_pulse']['offset_ms'],20)
        self.assertEqual(row['nearest_pulse']['provenance'],'user_corrected')
        self.assertEqual(row['nearest_energy_rise']['offset_ms'],-200)
        self.assertEqual(result['reference_counts'],{'pulse':1,'energy_rise':1})
        self.assertEqual(row['candidate_status'],'near_reference')
        self.assertNotIn('accuracy',result)

    def test_native_frame_clock_and_energy_match(self):
        p,r=fixture(native=True)
        r['transitions']=[{'time_s':2+31/30}]
        row=review_music_sync(p,r,tolerance_ms=0)['boundaries'][0]
        self.assertEqual(row['frame_index'],31)
        self.assertAlmostEqual(row['frame_shift_ms'],23.333333,places=6)
        self.assertEqual(row['closest_reference']['kind'],'energy_rise')
        self.assertEqual(row['candidate_status'],'near_reference')
        self.assertTrue(row['user_directed'])

    def test_silence_visualizer_and_suppressed_scenes(self):
        p,r=fixture();r={'beats':[],'transitions':[]}
        result=review_music_sync(p,r)
        self.assertEqual(result['status'],'no_reference')
        self.assertIsNone(result['boundaries'][0]['closest_reference'])
        p['options']['asset_ids']=[]
        result=review_music_sync(p,r)
        self.assertEqual(result['status'],'no_scene_boundaries')
        self.assertEqual(result['boundaries'],[])
        self.assertEqual(result['suggested_previews'],[])
        p['options']['asset_ids']=['b'*32]
        p['timeline']['scenes']=[{'start_s':0,'end_s':1},{'start_s':1,'end_s':1.001},
                                 {'start_s':1.001,'end_s':3}]
        self.assertEqual([b['scene_index'] for b in review_music_sync(p,r)['boundaries']],[2])

    def test_immutable_user_direction_and_preview_scope(self):
        p,r=fixture(native=True);before=copy.deepcopy((p,r))
        result=review_music_sync(p,r,tolerance_ms=1)
        self.assertEqual(result['counts']['outside_tolerance'],1)
        self.assertTrue(result['boundaries'][0]['user_directed'])
        self.assertEqual((p,r),before)
        for window in result['suggested_previews']:
            self.assertEqual(window['revision'],4)
            self.assertGreaterEqual(window['preview_start_s'],0)
            self.assertGreaterEqual(window['preview_duration_s'],1/30)
            self.assertLessEqual(window['preview_duration_s'],8)
            self.assertLessEqual(window['preview_start_s']+window['preview_duration_s'],3)

    def test_pagination_full_counts_and_bounded_previews(self):
        p,r=fixture();p['timeline']['duration_s']=120
        p['timeline']['scenes']=[{'start_s':i/5,'end_s':(i+1)/5} for i in range(600)]
        page=review_music_sync(p,r,offset=100,limit=100)
        self.assertEqual(page['boundary_count'],599)
        self.assertEqual(len(page['boundaries']),100)
        self.assertEqual(page['boundaries'][0]['scene_index'],101)
        self.assertEqual(page['next_offset'],200)
        self.assertEqual(sum(page['counts'].values()),599)
        self.assertLessEqual(len(page['suggested_previews']),3)
        self.assertEqual(review_music_sync(p,r,offset=999)['boundaries'],[])

    def test_strict_arguments(self):
        p,r=fixture()
        for bad in (True,False,-1,251,math.nan,math.inf,'80',None):
            with self.subTest(tolerance=bad),self.assertRaises(ValueError):review_music_sync(p,r,bad)
        for kw in ({'offset':True},{'offset':-1},{'offset':1.5},{'limit':False},{'limit':0},{'limit':101}):
            with self.subTest(arguments=kw),self.assertRaises(ValueError):review_music_sync(p,r,**kw)
        self.assertEqual(review_music_sync(p,r,20)['counts']['near_reference'],1)
        self.assertEqual(review_music_sync(p,r,19.99)['counts']['outside_tolerance'],1)

    def test_service_cli_persistence_and_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'click.wav',SR,click_track(128,12))
            s=Service(root,root/'state')
            try:
                aid=s.analyze('click.wav')['analysis_id']
                derived=s.correct_beats(aid,[1,3,5,7,9,11])['analysis_id']
                p=s.create_project(derived,{'visual_mode':'motion_graphics','music_in_s':1,'duration_s':10,
                    'story_blocks':[{'headline':'Open'},{'headline':'Close'}],
                    'section_anchors':[{'section_index':1,'source_time_s':5.01}]})
                before=copy.deepcopy(s.project(p['project_id']))
                result=s.music_sync(p['project_id'])
                self.assertEqual(result['analysis_id'],derived)
                self.assertEqual(s.project(p['project_id']),before)
                boundary=result['boundaries'][0]
                frames=MotionFrames(click_track(128,12),p['timeline'],p['options'])
                self.assertEqual(frames.state((boundary['frame_index']-1)/30)['section'],0)
                self.assertEqual(frames.state(boundary['video_time_s'])['section'],1)
            finally:s.close()
            cli=subprocess.check_output([sys.executable,'-m','fusionify_audio.cli','--media-root',str(root),
                '--state-root',str(root/'state'),'review-sync',p['project_id'],'--limit','1'],text=True)
            result=json.loads(cli)
            self.assertEqual(result['revision'],1)
            self.assertEqual(result['boundaries'][0]['nearest_pulse']['provenance'],'user')
            s=Service(root,root/'state')
            try:
                s.revise_project(p['project_id'],1,{'caption':'Revision check'})
                self.assertEqual(s.music_sync(p['project_id'])['revision'],2)
            finally:s.close()

    def test_review_matches_actual_montage_frame_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'click.wav',SR,click_track(128,4))
            s=Service(root,root/'state')
            try:
                aids=[]
                for color in ('red','blue'):
                    Image.new('RGB',(120,120),color).save(root/f'{color}.png')
                    aids.append(s.register_asset(f'{color}.png')['asset_id'])
                aid=s.analyze('click.wav')['analysis_id']
                p=s.create_project(aid,{'asset_ids':aids,'music_in_s':.5,'duration_s':2,
                    'text_overlay':False,'motion_amount':0,'resolution':480,
                    'scene_overrides':[{'start_s':0,'end_s':1.01,'asset_id':aids[0]},
                                       {'start_s':1.01,'end_s':2,'asset_id':aids[1]}]})
                row=s.music_sync(p['project_id'])['boundaries'][0]
                self.assertEqual((row['frame_index'],row['source_time_s']),(30,1.5))
                job=s.render_project(p['project_id'])
                for _ in range(300):
                    state=s.status(job['job_id'])
                    if state['status'] in ('completed','failed'):break
                    time.sleep(.03)
                self.assertEqual(state['status'],'completed',state)
                raw=subprocess.check_output(['ffmpeg','-v','error','-i',state['output_path'],
                    '-vf',r'select=between(n\,29\,30)','-vsync','0','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
                frames=np.frombuffer(raw,dtype=np.uint8).reshape(2,-1,3).mean(axis=1)
                self.assertGreater(frames[0,0],200);self.assertLess(frames[0,2],20)
                self.assertGreater(frames[1,2],200);self.assertLess(frames[1,0],20)
            finally:s.close()


if __name__=='__main__':unittest.main()
