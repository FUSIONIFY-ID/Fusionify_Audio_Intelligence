import io
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from scipy.io import wavfile
from starlette.testclient import TestClient

from fusionify_audio.http_app import ArtifactSigner,build_http_app
from fusionify_audio.service import Service
from fusionify_audio.engine import SR
from test_engine import click_track

TOKEN='test-only-'+('x'*48)


class HTTPTests(unittest.TestCase):
    def test_signer_expiry_and_tampering(self):
        signer=ArtifactSigner(TOKEN,'http://127.0.0.1')
        aid='a'*32;expires=int(time.time())+60
        sig=signer.signature(aid,'json',expires)
        self.assertTrue(signer.verify(aid,'json',str(expires),sig))
        self.assertFalse(signer.verify('b'*32,'json',str(expires),sig))
        self.assertFalse(signer.verify(aid,'csv',str(expires),sig))
        self.assertFalse(signer.verify(aid,'json',str(int(time.time())-1),sig))
        self.assertFalse(signer.verify(aid,'json',str(expires),'bad'))
        with self.assertRaises(ValueError):ArtifactSigner('short','https://example.com')
        with self.assertRaises(ValueError):ArtifactSigner(TOKEN,'http://example.com')

    def test_upload_auth_project_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=Service(root,root/'state')
            try:
                with TestClient(build_http_app(s,TOKEN,'http://127.0.0.1'),base_url='http://127.0.0.1') as client:
                    self.assertEqual(client.get('/healthz').status_code,200)
                    self.assertIn('Your music. Your next edit.',client.get('/').text)
                    self.assertIn("script-src 'self'",client.get('/').headers['content-security-policy'])
                    self.assertEqual(client.post('/api/call',json={}).status_code,401)
                    self.assertEqual(client.post('/api/call',headers=[(b'authorization',b'\xff')],json={}).status_code,401)
                    headers={'Authorization':'Bearer '+TOKEN}
                    self.assertEqual(client.post('/api/call',headers={**headers,'Origin':'https://evil.example'},json={}).status_code,403)
                    wav=io.BytesIO();wavfile.write(wav,SR,click_track(128,3))
                    response=client.post('/api/upload',headers={**headers,'X-Filename':'track.wav'},content=wav.getvalue())
                    self.assertEqual(response.status_code,201,response.text)
                    aid=response.json()['asset_id']
                    def call(name,args):
                        r=client.post('/api/call',headers=headers,json={'operation':name,'arguments':args})
                        self.assertEqual(r.status_code,200,r.text);return r.json()
                    analysis=call('analyze_audio',{'audio_path':aid})
                    project=call('create_video_project',{'analysis_id':analysis['analysis_id'],'options':{'title':'HTTP test'}})
                    exported=call('export_video_timeline',{'project_id':project['project_id'],'format':'json'})
                    link=urlsplit(exported['download_url'])
                    downloaded=client.get(link.path+'?'+link.query)
                    self.assertEqual(downloaded.status_code,200)
                    self.assertEqual(downloaded.json()['project_id'],project['project_id'])
                    self.assertEqual(client.get(link.path+'?'+link.query+'bad').status_code,403)
                    self.assertEqual(client.post('/api/upload',headers={**headers,'X-Filename':'photo.jpg'},content=b'not a photo').status_code,400)
                    self.assertEqual(client.post('/api/upload',headers={**headers,'X-Filename':'../x.wav'},content=wav.getvalue()).status_code,400)
            finally:s.close()


if __name__=='__main__':unittest.main()
