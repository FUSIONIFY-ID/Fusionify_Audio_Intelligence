import tempfile
import time
import unittest
from pathlib import Path

from scipy.io import wavfile
from fusionify_audio.engine import SR
from fusionify_audio.service import Service
from test_engine import click_track


class ServiceTests(unittest.TestCase):
    def test_timeline_limits_and_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'track.wav'
            wavfile.write(source,SR,click_track(128,4))
            service=Service(root,root/'state')
            try:
                report=service.analyze('track.wav');aid=report['analysis_id']
                timeline=service.timeline(aid,limit=1)
                self.assertTrue(timeline['truncated'])
                self.assertTrue(timeline['energy_truncated'])
                self.assertEqual(len(timeline['beats']),1)
                for bad in ['../private', 'not-an-id']:
                    with self.assertRaises(ValueError):service.record(bad)
                with self.assertRaises(ValueError):service.timeline(aid,limit=0)
                with self.assertRaises(ValueError):service.timeline(aid,start_s=float('nan'))
                # Preserve valid media but change its bytes after the stored analysis.
                wavfile.write(source,SR,click_track(96,4))
                job=service.render(aid,duration_s=1)
                for _ in range(200):
                    status=service.status(job['job_id'])
                    if status['status'] in ('completed','failed'):break
                    time.sleep(.01)
                self.assertEqual(status['status'],'failed')
                self.assertIn('Source changed',status['error'])
            finally:service.close()


if __name__=='__main__':unittest.main()
