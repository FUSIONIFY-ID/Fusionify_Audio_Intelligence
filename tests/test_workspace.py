import csv
import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from scipy.io import wavfile
from fusionify_audio.assets import local_media,validate_remote
from fusionify_audio.engine import SR
from fusionify_audio.service import Service
from test_engine import click_track


class WorkspaceTests(unittest.TestCase):
    def test_persistence_revision_and_manual_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'track.wav',SR,click_track(128,4))
            s=Service(root,root/'state')
            try:
                aid=s.analyze('track.wav')['analysis_id']
                corrected=s.correct_beats(aid,[.4,.9,1.4,1.9,2.4,2.9,3.4])['analysis_id']
                self.assertNotEqual(aid,corrected)
                self.assertNotEqual(s.record(aid)['report']['beats'],s.record(corrected)['report']['beats'])
                p=s.create_project(corrected,{'title':'First','music_in_s':.5,'duration_s':2,'style':'promo'})
                changed=s.revise_project(p['project_id'],1,{'title':'Updated','intensity':'low'})
                self.assertEqual(changed['revision'],2)
                with self.assertRaisesRegex(ValueError,'conflict'):s.revise_project(p['project_id'],1,{'title':'Stale'})
                with self.assertRaises(ValueError):s.revise_project(p['project_id'],2,{'filter':'arbitrary code'})
                for bad in [[1,1],[2,1],[float('nan')],[-.2],[4],[True]]:
                    with self.assertRaises(ValueError):s.correct_beats(aid,bad)
                output=s.export(p['project_id'],'csv')
                rows=list(csv.DictReader(io.StringIO(Path(output['output_path']).read_text())))
                self.assertTrue(rows)
                self.assertAlmostEqual(float(rows[0]['music_start_s']),.5)
            finally:s.close()
            s=Service(root,root/'state')
            try:
                self.assertEqual(s.project(p['project_id'])['revision'],2)
                self.assertEqual(s.record(corrected)['report']['parent_analysis_id'],aid)
            finally:s.close()

    def test_asset_validation_and_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(300,200),'blue').save(root/'photo.png')
            s=Service(root,root/'state')
            try:
                asset=s.register_asset('photo.png')
                self.assertEqual(asset['kind'],'image')
                self.assertNotIn('path',s.assets()[0])
                (root/'bad.jpg').write_bytes((root/'photo.png').read_bytes())
                with self.assertRaises(ValueError):s.register_asset('bad.jpg')
                (root/'photo.png').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'changed'):s.asset(asset['asset_id'],verify=True)
                with self.assertRaises(ValueError):local_media(root,str(root.parent))
            finally:s.close()

    def test_url_public_ip_and_allowlist(self):
        public=[(2,1,6,'',('8.8.8.8',443))]
        with patch('fusionify_audio.assets.socket.getaddrinfo',return_value=public):
            _,ip=validate_remote('https://example.com/track.mp3',{'example.com'})
            self.assertEqual(ip,'8.8.8.8')
            for url in ['http://example.com/a.mp3','https://user:pass@example.com/a.mp3',
                        'https://elsewhere.com/a.mp3','https://example.com:8443/a.mp3']:
                with self.assertRaises(ValueError):validate_remote(url,{'example.com'})
        for ip in ['127.0.0.1','10.0.0.1','169.254.169.254','::1','fc00::1']:
            with patch('fusionify_audio.assets.socket.getaddrinfo',return_value=[(2,1,6,'',(ip,443))]):
                with self.assertRaises(ValueError):validate_remote('https://example.com/a.mp3',{'example.com'})

    def test_queue_cancel_and_restart_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=Service(root,root/'state');started=threading.Event();release=threading.Event()
            def worker(output,cancel,progress):
                started.set();release.wait(3)
                if not cancel.is_set():output.write_bytes(b'test')
            try:
                first=s._queue('test',{},worker);self.assertTrue(started.wait(2))
                second=s._queue('test',{},worker)
                self.assertEqual(s.cancel_job(second['job_id'])['status'],'cancelled')
                release.set()
                for _ in range(100):
                    if s.status(first['job_id'])['status']=='completed':break
                    time.sleep(.02)
            finally:release.set();s.close()
            s=Service(root,root/'state')
            try:self.assertEqual(s.status(first['job_id'])['status'],'completed')
            finally:s.close()

    def test_scene_overrides_motion_and_editorial_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wavfile.write(root/'silent.wav',SR,__import__('numpy').zeros(SR*3,dtype='float32'))
            s=Service(root,root/'state')
            try:
                aid=s.analyze('silent.wav')['analysis_id'];images=[]
                for i in range(3):
                    Image.new('RGB',(200,200),(i*50,20,60)).save(root/f'{i}.png')
                    images.append(s.register_asset(f'{i}.png')['asset_id'])
                p=s.create_project(aid,{'asset_ids':images,'motion_amount':0,'fit_mode':'contain'})
                self.assertEqual({scene['asset_id'] for scene in p['timeline']['scenes']},set(images))
                self.assertIn('editorial',p['timeline']['scene_boundary_source'])
                self.assertEqual(s.record(aid)['report']['beats'],[])
                overrides=[{'start_s':0,'end_s':1,'asset_id':images[1],'effect':'cut'},
                           {'start_s':1,'end_s':3,'asset_id':images[0],'effect':'pan'}]
                changed=s.revise_project(p['project_id'],1,{'scene_overrides':overrides})
                self.assertEqual(changed['timeline']['scene_boundary_source'],'user overrides')
                with self.assertRaises(ValueError):s.revise_project(p['project_id'],2,{'scene_overrides':[overrides[0]]})
            finally:s.close()


if __name__=='__main__':unittest.main()
