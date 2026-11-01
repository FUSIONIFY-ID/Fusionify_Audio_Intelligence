import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from fusionify_audio.semantic import describe


class SemanticTests(unittest.TestCase):
    def test_consent_and_config_are_required_without_network(self):
        with patch('fusionify_audio.semantic.checked_run') as decode:
            with self.assertRaises(ValueError):describe(Path('track.mp3'),'Describe mood',False)
            with patch.dict(os.environ,{},clear=True):
                with self.assertRaises(ValueError):describe(Path('track.mp3'),'Describe mood',True)
            decode.assert_not_called()

    def test_mocked_provider_json_contract(self):
        expected={'summary':'A rhythmic excerpt','mood':['energetic'],'audible_elements':['percussion'],
                  'editing_suggestions':['Use selected strong beats'],'limitations':['Interpretive']}
        response=MagicMock(status_code=200)
        response.json.return_value={'candidates':[{'content':{'parts':[{'text':json.dumps(expected)}]}}]}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test-only-key','FAI_GEMINI_MODEL':'test-model'}), \
             patch('fusionify_audio.semantic.checked_run',return_value=b'test-audio'), \
             patch('fusionify_audio.semantic.httpx.Client') as client:
            client.return_value.__enter__.return_value.post.return_value=response
            result=describe(Path('track.mp3'),'Describe mood',True)
            self.assertEqual(result['interpretation'],expected)
            args=client.return_value.__enter__.return_value.post.call_args
            self.assertEqual(args.kwargs['headers']['x-goog-api-key'],'test-only-key')
            self.assertNotIn('test-only-key',json.dumps(result))


if __name__=='__main__':unittest.main()
