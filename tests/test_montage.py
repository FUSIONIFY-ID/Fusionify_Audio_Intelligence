import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.io import wavfile
from fusionify_audio.engine import SR
from fusionify_audio.service import Service
from test_engine import click_track


class MontageTests(unittest.TestCase):
    def test_video_loop_pan_and_beat_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'track.wav',SR,click_track(128,4))
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc=size=320x240:rate=15',
                            '-f','lavfi','-i','sine=frequency=900:sample_rate=22050','-t','1.5',
                            '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(root/'clip.mp4')],check=True)
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id'];asset=s.register_asset('clip.mp4')
                self.assertEqual(asset['kind'],'video')
                p=s.create_project(aid,{'asset_ids':[asset['asset_id']],'style':'cinematic','duration_s':2.2,
                                       'music_in_s':.4,'aspect':'16:9','resolution':480,'fit_mode':'contain','motion_amount':.2})
                for job in [s.render_project(p['project_id']),s.beat_preview(aid)]:
                    for _ in range(600):
                        state=s.status(job['job_id'])
                        if state['status'] in ('completed','failed'):break
                        time.sleep(.05)
                    self.assertEqual(state['status'],'completed',state)
                    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',state['output_path']]))
                    self.assertAlmostEqual(float(info['format']['duration']),4 if state['format']=='mp3' else 2.2,delta=.08)
                for fmt in ('json','svg'):
                    out=s.export_analysis(aid,fmt);self.assertTrue(Path(out['output_path']).is_file())
            finally:s.close()

    def test_photo_render_with_trimmed_original_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'track.wav',SR,click_track(128,4))
            Image.new('RGB',(600,400),(30,70,160)).save(root/'one.png')
            Image.new('RGB',(400,600),(180,90,30)).save(root/'two.png')
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id']
                images=[s.register_asset(name)['asset_id'] for name in ('one.png','two.png')]
                project=s.create_project(aid,{'title':'Photo test','caption':'Original music','asset_ids':images,
                                             'music_in_s':.3,'duration_s':1.4,'aspect':'1:1','resolution':480,'intensity':'high'})
                job=s.render_project(project['project_id'])
                for _ in range(600):
                    status=s.status(job['job_id'])
                    if status['status'] in ('failed','completed'):break
                    time.sleep(.05)
                self.assertEqual(status['status'],'completed',status)
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',status['output_path']]))
                video=next(x for x in probe['streams'] if x['codec_type']=='video')
                self.assertEqual((video['width'],video['height']),(480,480))
                self.assertAlmostEqual(float(probe['format']['duration']),1.4,delta=.06)
                raw=subprocess.check_output(['ffmpeg','-v','error','-i',status['output_path'],'-ac','1','-ar',str(SR),'-f','f32le','-'])
                actual=np.frombuffer(raw,dtype='<f4')
                expected=click_track(128,4)[round(.3*SR):round(1.7*SR)]
                n=min(len(actual),len(expected))
                self.assertGreater(float(np.corrcoef(actual[:n],expected[:n])[0,1]),.95)
            finally:s.close()


if __name__=='__main__':unittest.main()
