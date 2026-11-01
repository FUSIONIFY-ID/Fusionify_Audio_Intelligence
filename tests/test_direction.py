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
from fusionify_audio.motion import MotionFrames,fit_text
from fusionify_audio.project import ProjectOptions,project_timeline
from fusionify_audio.service import Service
from test_engine import click_track


class DirectionTests(unittest.TestCase):
    def test_sections_hold_while_pulses_continue_and_offsets_are_explicit(self):
        report=measure(click_track(128,36))
        direction=music_direction(report,2,30,'medium',5,'Product story with global reach')
        self.assertEqual(len(direction['sections']),5)
        self.assertGreater(direction['accent_count'],40)
        for i,s in enumerate(direction['sections']):
            self.assertGreater(s['end_s']-s['start_s'],4.5)
            self.assertAlmostEqual(s['source_start_s']-s['start_s'],2,places=5)
            if i:self.assertEqual(direction['sections'][i-1]['end_s'],s['start_s'])
        self.assertEqual(direction['sections'][-1]['end_s'],30)
        self.assertIn('editorial',direction['note'].lower())
        plan=project_timeline(report,ProjectOptions(pacing_mode='musical'))
        self.assertEqual(len(plan['scenes']),5)
        self.assertGreater(len(plan['music_direction']['accents']),len(plan['scenes'])*5)
        with_rise={**report,'transitions':[{'time_s':4.25,'kind':'energy_rise_candidate'}]}
        self.assertEqual(music_direction(with_rise)['sections'][0]['end_s'],4.25)

    def test_silence_no_invented_accents_and_invalid_direction(self):
        report=measure(np.zeros(SR*12,dtype=np.float32))
        d=music_direction(report)
        self.assertEqual(d['accents'],[])
        self.assertTrue(all('editorial' in s['boundary_evidence'] for s in d['sections'][1:]))
        for values in [{'section_count':True},{'section_count':9},{'content_brief':'x'*301}]:
            with self.assertRaises(ValueError):music_direction(report,**values)
        with self.assertRaises(ValueError):project_timeline(report,ProjectOptions(visual_mode='motion_graphics',asset_ids=['a'*32]))
        with self.assertRaises(ValueError):project_timeline(report,ProjectOptions(story_blocks=[{'headline':'hello'}]))
        with self.assertRaisesRegex(ValueError,'too short'):
            project_timeline(report,ProjectOptions(visual_mode='motion_graphics',duration_s=2,story_blocks=[{'headline':'one'},{'headline':'two'}]))

    def test_native_layout_bounds_and_continuous_clock(self):
        y=click_track(128,18);report=measure(y)
        for aspect in ['9:16','16:9','1:1']:
            opts=ProjectOptions(visual_mode='motion_graphics',aspect=aspect,resolution=480,story_blocks=[
                {'headline':'A'*80,'support':'Long supporting sentence '*5,'visual':'globe'},
                {'headline':'Second scene','visual':'market'}]).model_dump()
            timeline=project_timeline(report,ProjectOptions.model_validate(opts))
            renderer=MotionFrames(y,timeline,opts)
            boundary=timeline['music_direction']['sections'][1]['start_s']
            a,b=renderer.state(boundary-.01),renderer.state(boundary+.01)
            self.assertEqual(a['section'],0);self.assertEqual(b['section'],1)
            self.assertAlmostEqual(b['motion_clock_s']-a['motion_clock_s'],.02)
            self.assertGreater(b['motion_clock_s'],5)
            for lines,font,leading in renderer.text_layout:
                self.assertLessEqual(len(lines)*leading,renderer.text_height)
                self.assertTrue(all(font.getlength(line)<=renderer.text_width for line in lines))
            self.assertEqual(renderer.frame(boundary+.01).size,(renderer.width,renderer.height))

    def test_native_render_and_preview_keep_saved_story_and_original_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);y=click_track(128,18);wavfile.write(root/'track.wav',SR,y)
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id']
                p=s.create_project(aid,{'visual_mode':'motion_graphics','pacing_mode':'musical','resolution':480,
                    'story_blocks':[{'headline':'First composition','visual':'globe'},{'headline':'Second composition','visual':'orbit'}]})
                job=s.render_project(p['project_id'],True)
                for _ in range(600):
                    state=s.status(job['job_id'])
                    if state['status'] in ('completed','failed'):break
                    time.sleep(.03)
                self.assertEqual(state['status'],'completed',state)
                stored=s.store.get('job',job['job_id'])['spec']['timeline']
                self.assertEqual(len(stored['music_direction']['sections']),1)
                self.assertEqual(stored['music_direction']['sections'][0]['end_s'],8)
                self.assertEqual(s.project(p['project_id'])['timeline']['duration_s'],18)
                self.assertEqual(len(s.project(p['project_id'])['timeline']['music_direction']['sections']),2)
                meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',state['output_path']]))
                self.assertAlmostEqual(float(meta['format']['duration']),8,delta=.08)
                raw=subprocess.check_output(['ffmpeg','-v','error','-i',state['output_path'],'-ac','1','-ar',str(SR),'-f','f32le','pipe:1'])
                audio=np.frombuffer(raw,dtype='<f4');n=min(len(audio),8*SR)
                self.assertGreater(float(np.corrcoef(audio[:n],y[:n])[0,1]),.98)
            finally:s.close()

    def test_source_sync_footage_and_overlay_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'track.wav',SR,click_track(128,4))
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=red:s=160x160:r=30:d=1',
                '-f','lavfi','-i','color=blue:s=160x160:r=30:d=2','-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]',
                '-map','[v]','-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(root/'clip.mp4')],check=True)
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id'];asset=s.register_asset('clip.mp4')['asset_id']
                p=s.create_project(aid,{'asset_ids':[asset],'music_in_s':1.5,'duration_s':1,
                    'video_playback':'source_sync','text_overlay':False,'motion_amount':0,'resolution':480})
                job=s.render_project(p['project_id'])
                for _ in range(200):
                    state=s.status(job['job_id'])
                    if state['status'] in ('completed','failed'):break
                    time.sleep(.03)
                self.assertEqual(state['status'],'completed',state)
                raw=subprocess.check_output(['ffmpeg','-v','error','-ss','0.2','-i',state['output_path'],'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
                image=np.frombuffer(raw,dtype=np.uint8).reshape(-1,3)
                self.assertGreater(float(image[:,2].mean()),150)
                self.assertLess(float(image[:,0].mean()),20)
                wavfile.write(root/'long.wav',SR,click_track(128,16))
                long_id=s.analyze('long.wav')['analysis_id'];Image.new('RGB',(200,200),'white').save(root/'photo.png')
                photo=s.register_asset('photo.png')['asset_id']
                bad=s.create_project(long_id,{'asset_ids':[asset,photo],'intensity':'high'})
                flags={f['code'] for f in s.content_fit(bad['project_id'])['flags']}
                self.assertTrue({'rapid_scene_changes','check_existing_text','footage_clock_may_drift','short_clip_loops'}<=flags)
                s.revise_project(bad['project_id'],1,{'pacing_mode':'musical','text_overlay':False,'video_playback':'source_sync'})
                remaining={f['code'] for f in s.content_fit(bad['project_id'])['flags']}
                self.assertEqual(remaining,{'short_clip_loops'})
            finally:s.close()


if __name__=='__main__':unittest.main()
