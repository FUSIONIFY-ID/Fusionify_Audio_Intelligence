"""Local audio decoding and DSP. No semantic audio-model claims."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from scipy import signal

SR, HOP, FFT = 22050, 220, 1024
MAX_SECONDS, MAX_BYTES = 180, 64 * 1024 * 1024
DEMUXERS = {".mp3": "mp3", ".wav": "wav", ".flac": "flac", ".ogg": "ogg", ".m4a": "mov"}


def media_file(root: Path, value: str) -> Path:
    root = root.expanduser().resolve(strict=True)
    requested = Path(value).expanduser()
    path = (requested if requested.is_absolute() else root / requested).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Audio must be a regular file inside FAI_MEDIA_ROOT.")
    if path.suffix.lower() not in DEMUXERS:
        raise ValueError("Supported files: MP3, WAV, FLAC, OGG, M4A.")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Audio exceeds the 64 MiB input limit.")
    return path


def checked_run(args: list[str], timeout: int = 45) -> bytes:
    try:
        return subprocess.run(args, capture_output=True, check=True, timeout=timeout).stdout
    except FileNotFoundError as exc:
        raise RuntimeError("Install FFmpeg and ffprobe and add them to PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError("Media decoding failed; verify the selected audio file.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Media processing exceeded its time limit.") from exc


def decode(path: Path) -> tuple[np.ndarray, dict]:
    demuxer = DEMUXERS[path.suffix.lower()]
    options = ["-v", "error", "-protocol_whitelist", "file,pipe", "-f", demuxer]
    info = json.loads(checked_run(["ffprobe", *options, "-show_entries", "format=duration:stream=sample_rate,channels", "-of", "json", str(path)]))
    length = info.get("format", {}).get("duration")
    if length is not None and (not math.isfinite(float(length)) or float(length) > MAX_SECONDS):
        raise ValueError("Maximum audio duration is 180 seconds in v0.1.")
    raw = checked_run(["ffmpeg", "-nostdin", *options, "-i", str(path), "-map", "0:a:0", "-t", str(MAX_SECONDS + 1), "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1"])
    y = np.frombuffer(raw, dtype="<f4").copy()
    if len(y) < FFT or len(y) > SR * MAX_SECONDS or not np.all(np.isfinite(y)):
        raise ValueError("Audio must decode to finite samples between 0.05 and 180 seconds.")
    return y, info


def measure(y: np.ndarray, sr: int = SR) -> dict:
    """Estimate a global editing pulse; downbeats and genre are not inferred."""
    if sr != SR or len(y) < FFT or not np.all(np.isfinite(y)):
        raise ValueError("Expected finite mono samples at 22050 Hz, at least 1024 samples.")
    duration = len(y) / sr
    freqs, times, z = signal.stft(y, fs=sr, nperseg=FFT, noverlap=FFT-HOP, boundary=None)
    mag = np.abs(z)
    flux = np.maximum(np.diff(np.log1p(300*mag), axis=1, prepend=np.log1p(300*mag[:, :1])), 0)
    env = np.zeros(len(times))
    kernel = min(101, len(times) if len(times) % 2 else len(times)-1)
    for lo, hi, weight in [(35, 180, .55), (180, 2500, .30), (2500, 9000, .15)]:
        a = flux[(freqs >= lo) & (freqs < hi)].mean(axis=0)
        a = np.maximum(a - .8*signal.medfilt(a, kernel), 0)
        env += weight * a / (np.percentile(a, 95) + 1e-10)
    fps = sr/HOP
    warnings = ["Timing is estimated, not human-validated. Half/double-time readings are possible.",
                "Global tempo only; inspect tempo-changing and non-rhythmic music manually."]
    tempo = None
    beats = []
    confidence = None
    xc = env - env.mean()
    if duration >= 2 and np.sqrt(np.mean(y*y)) > 1e-6 and np.dot(xc, xc) > 1e-8:
        ac = signal.correlate(xc, xc, mode="full", method="fft")[len(xc)-1:]
        ac /= np.arange(len(ac), 0, -1)
        lags = np.arange(int(fps*60/210), min(int(fps*60/65)+1, len(ac)-1))
        peaks, _ = signal.find_peaks(ac[lags])
        if len(peaks):
            candidates = lags[peaks]
            # Broad prior limits half-time preference; it does not establish musical meter.
            score = ac[candidates]*np.exp(-.5*(np.log2((60*fps/candidates)/120)/.7)**2)
            lag = int(candidates[np.argmax(score)])
            confidence = float(np.clip(ac[lag]/max(ac[0], 1e-10), 0, 1))
            if confidence >= .08:
                period = lag/fps
                phases = np.linspace(0, period, 160, endpoint=False)
                phase_score = [np.interp(np.arange(p, duration, period), times, env).mean() for p in phases]
                anchor = float(phases[np.argmax(phase_score)])
                pp, _ = signal.find_peaks(env, prominence=.2, distance=max(1, int(.65*period*fps)))
                pt = times[pp]
                idx = np.rint((pt-anchor)/period)
                selected = np.abs(pt-(anchor+idx*period)) < .12*period
                if np.count_nonzero(selected) >= 4:
                    new_period, new_anchor = np.polyfit(idx[selected], pt[selected], 1)
                    if abs(new_period-period) < .04*period:
                        period, anchor = float(new_period), float(new_anchor)
                tempo = round(60/period, 3)
                grid = anchor + np.arange(math.ceil(-anchor/period), math.floor((duration-anchor)/period)+1)*period
                for g in grid:
                    near = np.flatnonzero(np.abs(times-g) <= .075)
                    if len(near):
                        k = int(near[np.argmax(env[near])])
                        # Suppress weak grid guesses; expose remaining onsets as candidates.
                        if env[k] >= .2:
                            beats.append({"time_s": round(float(times[k]), 4), "strength": round(float(env[k]), 4)})
    if tempo is None:
        warnings.append("No reliable repeating pulse found; do not invent beat markers.")
    energy = []
    for start in np.arange(0, duration, .25):
        chunk = y[int(start*sr):min(len(y), int((start+.25)*sr))]
        rms = float(np.sqrt(np.mean(chunk*chunk)))
        energy.append({"time_s": round(float(start), 4), "rms_dbfs": round(20*math.log10(max(rms, 1e-12)), 2)})
    # Energy rises are candidates, never automatic semantic drop labels.
    transitions = []
    if len(energy) > 8:
        rms = np.array([10**(x['rms_dbfs']/20) for x in energy])
        rise = np.diff(signal.savgol_filter(rms, 5, 2))
        ps, _ = signal.find_peaks(rise, distance=8)
        threshold = max(.005, float(np.mean(rise)+2*np.std(rise)))
        transitions = [{"time_s": energy[int(k)+1]['time_s'], "kind": "energy_rise_candidate"}
                       for k in sorted(ps, key=lambda k: rise[k], reverse=True)[:5]
                       if rise[k] > threshold and 1 < energy[int(k)+1]['time_s'] < duration-1]
        transitions.sort(key=lambda x: x['time_s'])
    return {"duration_s": round(duration, 5), "tempo_bpm_estimate": tempo,
            "pulse_periodicity_score": None if confidence is None else round(confidence, 4),
            "score_note": "Autocorrelation strength; not calibrated detection accuracy.",
            "beats": beats, "energy": energy, "transitions": transitions,
            "semantic_model_used": False, "warnings": warnings}


def analyze(path: Path) -> tuple[dict, np.ndarray]:
    y, metadata = decode(path)
    result = measure(y)
    result.update({"schema_version": "0.1.0", "source": {"filename": path.name,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
                   "time_reference": "seconds from the beginning of this exact source file",
                   "method": "spectral flux + autocorrelation + onset-aligned pulse fit",
                   "source_streams": metadata.get("streams", [])})
    return result, y


def doctor() -> dict:
    return {"ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")),
            "max_duration_s": MAX_SECONDS, "max_input_mib": MAX_BYTES//1024//1024,
            "formats": list(DEMUXERS)}
