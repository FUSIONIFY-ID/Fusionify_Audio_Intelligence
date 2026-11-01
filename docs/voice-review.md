# Voice delivery, script checking and subtitles

v0.6 adds seven MCP/API tools. All timing uses the exact analyzed source; default processing retains the full recording up to 180 seconds.

| Tool | Result |
| --- | --- |
| `analyze_voice` | Persistent voice_id plus pitch/level summary; declared source type is speech or mixed_audio |
| `get_voice_timeline` | Paginated contour, signal activity and quiet ranges; offset applies to each array, limit 1–500 |
| `transcribe_audio` | Queued optional local ASR; poll get_job_status for result.transcript_id |
| `import_transcript` | Persistent timed text supplied by the user; audio is explicitly unverified |
| `get_transcript` | Pages of at most 100 segments; optional word timing |
| `check_spoken_text` | Token differences, word error rate, provenance and review spans, at most 100 returned edits |
| `export_transcript` | SRT, VTT or source-relative JSON; optional matching-source project trim for subtitles |

## Offline delivery measurements

Use `analyze_voice` after `analyze_audio`. Pitch is an overlap-normalized autocorrelation heuristic from 60 to 500 Hz on 64 ms frames at a 20 ms hop, summarized in approximately 100 ms contour bins. It rejects weak periodicity; no detected pitch does not imply no speech. Activity uses a relative RMS threshold with a -55 dBFS floor, bridging short gaps. It is signal activity, not a trained speech detector. Phrase pitch trends compare early and late periodic samples; they cannot establish correctness or emotion.

A mixed song can track a bass/synth rather than a vocalist. Octave errors, polyphony, background noise and low/high voices limit interpretation. Peak/headroom measurements concern decoded mono samples, not true peak, source stems or a clinical voice assessment. A full-scale sample is a review flag, not proof of hard clipping. Voice review does not modify or separate the source audio.

## Optional local transcription

The base installation remains model-free. To enable ASR in a local operator environment:

```bash
uv sync --frozen --extra speech
export FAI_WHISPER_MODEL_DIR="/absolute/path/to/converted-whisper-model"
uv run --frozen --extra speech fusionify-audio serve
```

Use `serve-http` with the same extra for HTTP mode and preserve its documented auth settings. For Claude Code's `.mcp.json` or generated Desktop config, add `--extra`, `speech` after `--frozen` in the actual uv args. Export the model directory in the launching process. Default plugin commands load only base dependencies.

The directory must already contain `model.bin`, `config.json`, `tokenizer.json` and any other files required by the selected converted CTranslate2 Whisper model. Obtain compatible model files separately from a trusted distributor and follow their license. Tools cannot choose a model name, download files, set model paths, or supply executable code. The adapter requires a local directory and local tokenizer, sets offline Hugging Face flags, loads with `local_files_only=True`, and disables optional VAD model loading. It runs on CPU/int8 with two threads in a subprocess, one shared queue worker, and a 180-second deadline. Slow/large models may time out. Cancellation kills the inference process. The adapter returns a sanitized failure, not backend file paths.

The implementation follows the [official faster-whisper usage](https://github.com/SYSTRAN/faster-whisper#usage) and [local loading/word timestamp API](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py). A configured directory only means ready to attempt, not a validated model. Repository ASR tests use a mocked backend; no real model is bundled or inference-quality claim made.

## Script review example

After analyzing the actual source, import user-provided timed text if ASR is unavailable:

```json
{
  "analysis_id": "ACTUAL_ANALYSIS_ID",
  "language": "id",
  "segments": [{
    "start_s": 0.5,
    "end_s": 2.2,
    "text": "Halo dunia",
    "words": [
      {"start_s": 0.5, "end_s": 1.1, "text": "Halo"},
      {"start_s": 1.2, "end_s": 2.2, "text": "dunia"}
    ]
  }]
}
```

Then compare the returned transcript_id with `expected_text: "Halo semua"`. This identifies a transcript substitution with a word range. It does not prove the recording actually said either word. Automatic transcription produces the same schema with origin `local_faster_whisper` and `audio_processed: true`, but still requires listening review.

Alignment uses Unicode NFKC, case folding and punctuation-separated word tokens. Expected script: at most 20,000 characters and 1,500 tokens. Transcript: at most 500 segments, 40,000 characters and 5,000 word records; comparison supports up to 5,000 normalized observed tokens. WER is an edit ratio and can exceed one. Numbers written as digits vs spoken words, homophones, and brand spellings are not automatically equated. No pass/fail, pronunciation or emotion score is generated.

## Subtitle timing

SRT/VTT exports are escaped plain text. Passing project_id verifies the original audio hash and shifts source times onto the saved project's music range. A crossing segment needs complete in-range timed words; otherwise it is omitted with a count. Words that themselves cross a trim are omitted. Review such omissions before publishing. Exports do not alter a saved project or burn captions into the video. JSON exports preserve source times and cannot take project_id.
