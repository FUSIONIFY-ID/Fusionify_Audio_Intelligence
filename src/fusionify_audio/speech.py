"""Explicit optional offline ASR; no model-name downloads or network processing."""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from scipy.io import wavfile
from scipy.signal import resample_poly
from .transcript import language_code


def model_directory():
    value=os.environ.get('FAI_WHISPER_MODEL_DIR','')
    if not value:raise ValueError('Set FAI_WHISPER_MODEL_DIR to a complete local converted Whisper model directory.')
    path=Path(value).expanduser().resolve()
    if not path.is_dir() or not all((path/name).is_file() for name in ('model.bin','config.json','tokenizer.json')):
        raise ValueError('Local Whisper model requires model.bin, config.json and tokenizer.json; no automatic download is allowed.')
    return path


def availability():
    installed=importlib.util.find_spec('faster_whisper') is not None
    try:model_directory();configured=True
    except (ValueError,OSError):configured=False
    return {'backend':'optional local faster-whisper','installed':installed,'model_configured':configured,
            'ready_to_attempt':installed and configured,'network_audio_processing':False,
            'note':'Configuration is not proof of inference quality. Word times are estimates; install the speech extra and supply local model files.'}


def transcribe(y,language,output,cancel):
    language_code(language);model=model_directory()
    if not availability()['installed']:raise ValueError('Install the optional speech extra before local transcription.')
    from .montage import run_process
    with tempfile.TemporaryDirectory(prefix='fai-speech-',dir=output.parent) as tmp:
        audio=Path(tmp)/'audio.wav';result=Path(tmp)/'transcript.json'
        wavfile.write(audio,16000,resample_poly(y,320,441).astype('float32'))
        try:
            run_process([sys.executable,'-m','fusionify_audio.speech',str(model),str(audio),str(result),language or 'auto'],cancel,timeout=180)
        except RuntimeError:
            raise ValueError('Local transcription stopped, failed, or exceeded 180 seconds. Check local model/runtime compatibility.') from None
        if not result.is_file() or result.stat().st_size>2*1024*1024:raise ValueError('Local transcript is missing or exceeds 2 MiB.')
        return json.loads(result.read_text(encoding='utf-8'))


def worker(model,audio,output,language):
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1')
    # Recheck required local files immediately before constructing the backend.
    os.environ['FAI_WHISPER_MODEL_DIR']=model
    path=model_directory()
    from faster_whisper import WhisperModel
    backend=WhisperModel(str(path),device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,local_files_only=True)
    segments,info=backend.transcribe(audio,language=None if language=='auto' else language,
                                   word_timestamps=True,vad_filter=False,beam_size=5,condition_on_previous_text=False)
    rows=[];chars=0;words_total=0
    for s in segments:
        chars+=len(s.text)
        words=[{'start_s':w.start,'end_s':w.end,'text':w.word,'probability':w.probability}
               for w in (s.words or []) if w.end>w.start and w.word.strip()]
        words_total+=len(words)
        if len(rows)>=500 or chars>40000 or words_total>5000:raise ValueError('Transcript limit exceeded.')
        if s.end>s.start and s.text.strip():
            rows.append({'start_s':s.start,'end_s':s.end,'text':s.text,'words':words})
    Path(output).write_text(json.dumps({'segments':rows,'language':info.language},ensure_ascii=False,allow_nan=False),encoding='utf-8')


if __name__=='__main__':worker(*sys.argv[1:])
