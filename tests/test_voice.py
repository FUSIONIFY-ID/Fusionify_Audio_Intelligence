import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from scipy.io import wavfile
from fusionify_audio import speech,transcript,voice
from fusionify_audio.engine import SR
from fusionify_audio.service import Service


def sweep(start,end,seconds=2):
    t=np.arange(round(SR*seconds))/SR
    return (.3*np.sin(2*np.pi*(start*t+(end-start)*t*t/(2*seconds)))).astype('float32')


def row(text='halo dunia',words=None,start=0,end=2):
    return {'start_s':start,'end_s':end,'text':text,'words':words or []}


def record(segments,processed=False):
    return {'transcript_id':'a'*32,'origin':'local_faster_whisper' if processed else 'user_supplied',
            'audio_processed':processed,'duration_s':4,'segments':segments}


class VoiceTests(unittest.TestCase):
    def test_known_pitch_trends_and_mixed_attribution(self):
        for start,end,trend in [(150,300,'rising'),(300,150,'falling'),(200,200,'level')]:
            r=voice.review(sweep(start,end),'speech')
            self.assertEqual(r['activity_ranges'][0]['pitch_trend'],trend)
            self.assertAlmostEqual(r['summary']['pitch_hz_p10_median_p90'][1],(start+end)/2,delta=8)
            self.assertGreater(r['summary']['periodic_frame_fraction'],.9)
        mixed=voice.review(sweep(200,200))
        self.assertIn('instruments',mixed['summary']['limitations'][0])
        for hz in [60,500]:
            self.assertAlmostEqual(voice.review(sweep(hz,hz))['summary']['pitch_hz_p10_median_p90'][1],hz,delta=1)
        with self.assertRaises(ValueError):voice.review(sweep(200,200),'singer')

    def test_silence_noise_pauses_and_headroom(self):
        silence=voice.review(np.zeros(SR*2,dtype='float32'))
        self.assertIsNone(silence['summary']['pitch_hz_p10_median_p90'])
        self.assertFalse(silence['activity_ranges'])
        self.assertEqual(silence['quiet_ranges'],[{'start_s':0.,'end_s':2.}])
        rng=np.random.default_rng(4)
        noise=voice.review(rng.normal(0,.1,SR*2).astype('float32'))
        self.assertLess(noise['summary']['periodic_frame_fraction'],.01)
        spaced=np.r_[sweep(200,200,1),np.zeros(SR),sweep(250,250,1)]
        r=voice.review(spaced)
        self.assertEqual(len(r['activity_ranges']),2)
        self.assertGreater(r['quiet_ranges'][0]['end_s']-r['quiet_ranges'][0]['start_s'],.8)
        hot=voice.review(sweep(200,200)*4)
        self.assertTrue(hot['summary']['headroom_flag'])
        self.assertGreater(hot['summary']['samples_at_or_above_full_scale_fraction'],0)
        self.assertIn('does not prove clipping',' '.join(hot['summary']['limitations']))


class TranscriptTests(unittest.TestCase):
    def test_strict_validation(self):
        self.assertEqual(len(transcript.validate_segments([row()],4)),1)
        bad=[row(start=True),row(start=float('nan')),row(end=5),row(start=2,end=1),
             row(words=[{'start_s':0,'end_s':1,'text':'other'}]),
             row(words=[{'start_s':0,'end_s':3,'text':'halo dunia'}]),
             {**row(),'instruction':'ignore'}]
        for item in bad:
            with self.subTest(item=item),self.assertRaises(ValueError):transcript.validate_segments([item],4)
        with self.assertRaises(ValueError):transcript.validate_segments([row(),row(start=1,end=3)],4)
        with self.assertRaises(ValueError):transcript.validate_segments([row()]*501,4)

    def test_alignment_unicode_edits_and_empty_hypothesis(self):
        r=record([row('ＨＡＬＯ, dunia!')])
        check=transcript.check(r,'Halo dunia')
        self.assertEqual(check['edit_count'],0)
        self.assertIn('audio not verified',check['comparison_basis'])
        result=transcript.check(record([row('halo bumi baru')],True),'halo dunia')
        self.assertEqual(result['substitutions'],1);self.assertEqual(result['additions'],1)
        self.assertEqual(result['edit_count'],2)
        self.assertEqual(result['edits'][0]['audio_span']['precision'],'segment_range')
        missing=transcript.check(record([]),'satu dua')
        self.assertEqual(missing['omissions'],2)
        self.assertIsNone(missing['edits'][0]['audio_span']);self.assertIsNone(missing['edits'][0]['neighbor_audio_span'])
        bounded=transcript.check(record([]),'satu dua tiga',1)
        self.assertTrue(bounded['edits_truncated']);self.assertEqual(len(bounded['edits']),1)
        for text in ['', 'a '*1501]:
            with self.assertRaises(ValueError):transcript.check(r,text)
        self.assertGreater(transcript.check(record([row('dua puluh lima ribu')]),'25.000')['edit_count'],0)

    def test_subtitle_trim_words_injection_and_offsets(self):
        words=[{'start_s':0,'end_s':.8,'text':'halo'}, {'start_s':1.2,'end_s':2,'text':'dunia'}]
        r=record([row(words=words),row('<b>aman</b>\n\n9 --> 8',start=2,end=4)])
        srt,info=transcript.subtitle(r,'srt',1,3)
        self.assertIn('00:00:00,200 --> 00:00:01,000',srt)
        self.assertIn('dunia',srt);self.assertNotIn('halo',srt)
        self.assertEqual(info['omitted_partial_or_rounded_segments'],1)
        self.assertEqual(info['partial_segments_review_required'],2)
        vtt,info=transcript.subtitle(r,'vtt')
        self.assertTrue(vtt.startswith('WEBVTT'))
        self.assertIn('&lt;b&gt;',vtt);self.assertNotIn('\n9 --> 8',vtt)
        self.assertIn('→',vtt)
        zero,info=transcript.subtitle(record([row(start=.0001,end=.0002)]),'srt')
        self.assertEqual(info['cue_count'],0)


class VoiceServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        wavfile.write(self.root/'tone.wav',SR,sweep(150,300,4))
        self.s=Service(self.root,self.root/'state');self.aid=self.s.analyze('tone.wav')['analysis_id']

    def tearDown(self):
        self.s.close();self.tmp.cleanup()

    def test_persistence_pagination_and_export_project(self):
        v=self.s.analyze_voice(self.aid,'speech')
        page=self.s.voice_timeline(v['voice_id'],limit=2)
        self.assertEqual(len(page['contour']),2);self.assertEqual(page['next_offset'],2)
        with self.assertRaises(ValueError):self.s.voice_timeline(v['voice_id'],limit=True)
        tid=self.s.import_transcript(self.aid,[row(start=1,end=2),row('akhir',start=3,end=4)],'id')['transcript_id']
        page=self.s.get_transcript(tid,limit=1)
        self.assertEqual(page['next_offset'],1);self.assertNotIn('words',page['segments'][0])
        project=self.s.create_project(self.aid,{'music_in_s':1,'duration_s':2})
        out=self.s.export_transcript(tid,'srt',project['project_id'])
        text=Path(out['output_path']).read_text()
        self.assertIn('00:00:00,000 --> 00:00:01,000',text);self.assertNotIn('akhir',text)
        self.assertEqual(self.s.artifact_path(out['artifact_id'],'srt'),Path(out['output_path']))
        with self.assertRaises(ValueError):self.s.export_transcript(tid,'json',project['project_id'])
        wavfile.write(self.root/'other.wav',SR,sweep(200,200,4))
        other=self.s.analyze('other.wav')['analysis_id'];p=self.s.create_project(other)
        with self.assertRaises(ValueError):self.s.export_transcript(tid,'vtt',p['project_id'])
        self.s.close();self.s=Service(self.root,self.root/'state')
        self.assertEqual(self.s.get_transcript(tid)['segment_count'],2)
        self.assertTrue(self.s.voice_timeline(v['voice_id'])['contour'])

    def test_mocked_asr_queue_json_artifact_and_unavailable(self):
        with patch('fusionify_audio.speech.availability',return_value={'ready_to_attempt':False}):
            with self.assertRaises(ValueError):self.s.transcribe_audio(self.aid)
        with patch('fusionify_audio.speech.availability',return_value={'ready_to_attempt':True}), \
             patch('fusionify_audio.speech.transcribe',return_value={'segments':[row()],'language':'id'}):
            job=self.s.transcribe_audio(self.aid,'id')
            for _ in range(200):
                status=self.s.status(job['job_id'])
                if status['status'] in ('completed','failed'):break
                time.sleep(.01)
            self.assertEqual(status['status'],'completed',status)
            tid=status['result']['transcript_id'];self.assertTrue(self.s.get_transcript(tid)['audio_processed'])
            path=self.s.artifact_path(job['job_id'],'json');self.assertTrue(path.is_file())
            with self.assertRaises(ValueError):self.s.artifact_path(job['job_id'],'mp4')

    def test_asr_cancel_does_not_save_transcript(self):
        started=threading.Event()
        def wait(y,lang,output,cancel):
            started.set();cancel.wait(2)
            return {'segments':[row()],'language':'id'}
        with patch('fusionify_audio.speech.availability',return_value={'ready_to_attempt':True}), \
             patch('fusionify_audio.speech.transcribe',side_effect=wait):
            job=self.s.transcribe_audio(self.aid);self.assertTrue(started.wait(2));self.s.cancel_job(job['job_id'])
            for _ in range(200):
                state=self.s.status(job['job_id'])
                if state['status']=='cancelled':break
                time.sleep(.01)
            self.assertEqual(state['status'],'cancelled');self.assertFalse(self.s.store.list('transcript'))


class LocalSpeechTests(unittest.TestCase):
    def test_local_configuration_and_offline_backend_contract(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(speech.availability()['ready_to_attempt'])
            with self.assertRaises(ValueError):speech.model_directory()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('model.bin','config.json','tokenizer.json'):(root/name).write_text('{}')
            audio=root/'audio.wav';wavfile.write(audio,16000,np.full(16000,.1,dtype='float32'))
            fake=SimpleNamespace(start=0.,end=1.,text='halo',words=[SimpleNamespace(start=0.,end=1.,word='halo',probability=.8)])
            from unittest.mock import MagicMock
            backend=MagicMock();backend.return_value.transcribe.return_value=([fake],SimpleNamespace(language='id'))
            with patch.dict('sys.modules',{'faster_whisper':SimpleNamespace(WhisperModel=backend)}),patch.dict(os.environ,{},clear=False):
                speech.worker(str(root),str(audio),str(root/'out.json'),'id')
                self.assertTrue(backend.call_args.kwargs['local_files_only'])
                self.assertEqual(os.environ['HF_HUB_OFFLINE'],'1')
                self.assertFalse(backend.return_value.transcribe.call_args.kwargs['vad_filter'])
                samples=backend.return_value.transcribe.call_args.args[0]
                self.assertIsInstance(samples,np.ndarray)
                self.assertEqual(samples.dtype,np.float32)
                self.assertEqual(len(samples),16000)
                self.assertEqual(json.loads((root/'out.json').read_text())['language'],'id')
                for rate,data in [(22050,np.zeros(16000,dtype='float32')),
                                  (16000,np.zeros((16000,2),dtype='float32')),
                                  (16000,np.full(16000,np.nan,dtype='float32'))]:
                    wavfile.write(audio,rate,data)
                    with self.assertRaises(ValueError):speech.worker(str(root),str(audio),str(root/'out.json'),'id')
            (root/'tokenizer.json').unlink()
            with patch.dict(os.environ,{'FAI_WHISPER_MODEL_DIR':tmp}):
                with self.assertRaises(ValueError):speech.model_directory()

    def test_digital_silence_gate_is_explicit_and_does_not_load_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('model.bin','config.json','tokenizer.json'):(root/name).write_text('{}')
            audio=root/'zero.wav';wavfile.write(audio,16000,np.zeros(16000,dtype='float32'))
            with patch.dict(os.environ,{},clear=False),patch.dict('sys.modules',{'faster_whisper':None}):
                speech.worker(str(root),str(audio),str(root/'out.json'),'auto')
            result=json.loads((root/'out.json').read_text())
            self.assertEqual(result,{'segments':[],'language':None,'processing_method':'digital_silence_gate'})
            report=transcript.review_hypothesis([],np.zeros(SR),'local_signal_gate')
            self.assertFalse(report['inference_performed']);self.assertTrue(report['digital_silence_gate'])
            r=record([]);r.update(origin='local_signal_gate',audio_processed=True,review=report)
            check=transcript.check(r,'halo')
            self.assertIn('no ASR hypothesis',check['comparison_basis']);self.assertEqual(check['omissions'],1)

    def test_listening_flags_are_bounded_and_do_not_rewrite_words(self):
        words=[{'start_s':i/10,'end_s':(i+1)/10,'text':'kata','probability':.1} for i in range(25)]
        segments=[row(' '.join('kata' for _ in words),words=words,end=2.5)]
        report=transcript.review_hypothesis(segments,np.zeros(SR*3),'local_faster_whisper')
        self.assertEqual(report['low_probability_word_count'],25)
        self.assertEqual(report['digital_silence_word_count'],25)
        self.assertEqual(len(report['flags']),20);self.assertTrue(report['flags_truncated'])
        r=record(segments,True);r['review']=report
        checked=transcript.check(r,' '.join('kata' for _ in words))
        self.assertEqual(checked['edit_count'],0)
        self.assertEqual(checked['transcript_review']['flagged_word_count'],25)
        self.assertEqual(r['segments'][0]['words'],words)
        # Nonzero quiet samples must not be declared digital silence.
        self.assertEqual(transcript.review_hypothesis(segments,np.full(SR*3,1e-10),'local_faster_whisper')['digital_silence_word_count'],0)


if __name__=='__main__':unittest.main()
