import copy
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.io import wavfile

from fusionify_audio.direction import music_direction
from fusionify_audio.engine import SR,measure
from fusionify_audio.motion import MotionFrames
from fusionify_audio.project import ProjectOptions,preview_excerpt,project_timeline
from fusionify_audio.service import Service
from test_engine import click_track


def wait_for(s,job):
    for _ in range(700):
        state=s.status(job['job_id'])
        if state['status'] in ('completed','failed'):break
        time.sleep(.03)
    if state['status']!='completed':raise AssertionError(state)
    return state


def pixels(path,t):
    raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
    return np.frombuffer(raw,dtype=np.uint8).reshape(-1,3)


class CueTests(unittest.TestCase):
    def test_anchor_times_are_source_relative_and_unlocked_sections_fill_between(self):
        report=measure(click_track(128,36))
        anchors=[{'section_index':2,'source_time_s':14},{'section_index':4,'source_time_s':28}]
        d=music_direction(report,2,30,section_anchors=anchors)
        self.assertEqual(len(d['sections']),5)
        for index,source in [(2,14),(4,28)]:
            section=d['sections'][index]
            self.assertEqual(section['source_start_s'],source)
            self.assertEqual(section['start_s'],source-2)
            self.assertTrue(section['boundary_locked'])
            self.assertEqual(section['boundary_evidence'],'user source-time anchor')
        for a,b in zip(d['sections'],d['sections'][1:]):self.assertEqual(a['end_s'],b['start_s'])
        self.assertEqual(d['sections'][-1]['end_s'],30)
        self.assertTrue(all(s['end_s']>s['start_s'] for s in d['sections']))

    def test_anchor_validation_and_incompatible_project_modes(self):
        report=measure(click_track(128,30));good={'section_index':2,'source_time_s':12}
        for bad in [[{**good,'section_index':True}],[{**good,'source_time_s':True}],
                    [{**good,'source_time_s':float('nan')}],[{**good,'source_time_s':'12'}],
                    [good,good],[good,{'section_index':1,'source_time_s':18}],
                    [{'section_index':1,'source_time_s':20},good],
                    [{'section_index':5,'source_time_s':28}],[{**good,'source_time_s':31}],
                    [{'section_index':1,'source_time_s':.2}],[{**good,'label':'drop'}]]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):music_direction(report,section_anchors=bad)
        with self.assertRaises(ValueError):project_timeline(report,ProjectOptions(section_anchors=[good]))
        with self.assertRaisesRegex(ValueError,'More assets'):
            project_timeline(report,ProjectOptions(pacing_mode='musical',section_anchors=[good],asset_ids=[str(i)*32 for i in range(6)]))

    def test_targeted_native_frames_keep_story_clock_pulse_and_original_layout(self):
        y=click_track(128,36);report=measure(y)
        opts=ProjectOptions(visual_mode='motion_graphics',resolution=480,music_in_s=2,duration_s=30,
                            section_anchors=[{'section_index':2,'source_time_s':14}],story_blocks=[
                                {'headline':f'Story {i}','visual':'globe' if i%2 else 'orbit'} for i in range(5)]).model_dump()
        timeline=project_timeline(report,ProjectOptions.model_validate(opts));before=copy.deepcopy(timeline)
        excerpt=preview_excerpt(timeline,opts,{},12.5,3)
        self.assertEqual(excerpt['music_direction']['sections'][0]['index'],2)
        full=MotionFrames(y,timeline,opts);part=MotionFrames(y,excerpt,opts)
        for t in [0,.5,1.3,2.5]:
            a,b=full.state(12.5+t),part.state(t)
            self.assertAlmostEqual(a['pulse'],b['pulse'])
            self.assertEqual(a['motion_clock_s'],b['motion_clock_s'])
            np.testing.assert_array_equal(np.asarray(full.frame(12.5+t)),np.asarray(part.frame(t)))
        self.assertEqual(timeline,before)
        self.assertTrue(any(a['video_time_s']<0 for a in excerpt['music_direction']['accents']))

    def test_render_excerpt_keeps_audio_offset_job_range_and_saved_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);y=click_track(128,16);wavfile.write(root/'track.wav',SR,y)
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id']
                p=s.create_project(aid,{'visual_mode':'motion_graphics','music_in_s':1,'duration_s':12,'resolution':480,
                    'section_anchors':[{'section_index':2,'source_time_s':9}],
                    'story_blocks':[{'headline':word} for word in ['Open','Middle','Close']]})
                job=s.render_project(p['project_id'],True,8,2)
                self.assertEqual(job['preview_start_s'],8);self.assertEqual(job['preview_duration_s'],2)
                state=wait_for(s,job)
                self.assertEqual(state['revision'],1)
                self.assertEqual(state['project_id'],p['project_id'])
                saved=s.project(p['project_id'])
                self.assertEqual(saved,p)
                spec=s.store.get('job',job['job_id'])['spec']
                self.assertEqual(spec['timeline']['music_direction']['sections'][0]['index'],2)
                self.assertEqual(spec['timeline']['music_in_s'],9)
                raw=subprocess.check_output(['ffmpeg','-v','error','-i',state['output_path'],'-ac','1','-ar',str(SR),'-f','f32le','pipe:1'])
                actual=np.frombuffer(raw,dtype='<f4');expected=y[9*SR:11*SR];n=min(len(actual),len(expected))
                self.assertGreater(float(np.corrcoef(actual[:n],expected[:n])[0,1]),.98)
                changed=s.revise_project(p['project_id'],1,{'title':'Revised title'})
                self.assertEqual(changed['timeline']['music_direction']['sections'][2]['source_start_s'],9)
            finally:s.close()

    def test_excerpt_does_not_restart_continue_or_source_sync_footage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'track.wav',SR,np.zeros(SR*12,dtype=np.float32))
            Image.new('RGB',(100,100),'white').save(root/'photo.png')
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=red:s=160x160:r=30:d=2',
                '-f','lavfi','-i','color=blue:s=160x160:r=30:d=2','-f','lavfi','-i','color=0x00ff00:s=160x160:r=30:d=8',
                '-filter_complex','[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]','-map','[v]','-c:v','libx264','-threads','1',
                '-pix_fmt','yuv420p',str(root/'clip.mp4')],check=True)
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id'];ids=[s.register_asset(n)['asset_id'] for n in ['clip.mp4','photo.png']]
                for playback,channel in [('continue',2),('source_sync',1)]:
                    p=s.create_project(aid,{'asset_ids':ids,'pacing_mode':'musical','video_playback':playback,
                        'text_overlay':False,'motion_amount':0,'resolution':480})
                    state=wait_for(s,s.render_project(p['project_id'],True,6.2,1))
                    rgb=pixels(state['output_path'],.2).mean(axis=0)
                    self.assertGreater(rgb[channel],180)
                    self.assertLess(rgb[0],20)
            finally:s.close()

    def test_montage_excerpt_keeps_zoom_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'track.wav',SR,np.zeros(SR*4,dtype=np.float32))
            grid=np.zeros((600,600,3),dtype=np.uint8)
            grid[::20,:,:]=255;grid[:,::20,:]=255;Image.fromarray(grid).save(root/'grid.png')
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id'];image=s.register_asset('grid.png')['asset_id']
                p=s.create_project(aid,{'asset_ids':[image],'resolution':480,'aspect':'1:1','style':'jj','motion_amount':1,'text_overlay':False})
                full=wait_for(s,s.render_project(p['project_id']))
                part=wait_for(s,s.render_project(p['project_id'],True,2,1))
                a=pixels(full['output_path'],2.4).astype(float);b=pixels(part['output_path'],.4).astype(float)
                self.assertLess(float(np.abs(a-b).mean()),3)
            finally:s.close()

    def test_preview_arguments_cannot_shorten_final_or_modify_saved_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'track.wav',SR,click_track(128,4));s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id'];p=s.create_project(aid)
                cases=[{'preview_start_s':1},{'preview_duration_s':2},{'preview':'false'},
                       {'preview':True,'preview_start_s':True},{'preview':True,'preview_start_s':float('nan')},
                       {'preview':True,'preview_start_s':4},{'preview':True,'preview_duration_s':9},
                       {'preview':True,'preview_start_s':3,'preview_duration_s':2},
                       {'preview':True,'preview_duration_s':.01}]
                for args in cases:
                    with self.subTest(args=args):
                        with self.assertRaises(ValueError):s.render_project(p['project_id'],**args)
                self.assertEqual(s.list_jobs(),[])
                self.assertEqual(s.project(p['project_id']),p)
            finally:s.close()


if __name__=='__main__':unittest.main()
