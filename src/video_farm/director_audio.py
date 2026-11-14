"""Narration concatenation and original procedural sound design (no third-party music)."""
from __future__ import annotations
import math, wave, hashlib, subprocess
from pathlib import Path
from typing import Any
import numpy as np

SAMPLE_RATE=24_000

def _read_wav(path: Path):
    with wave.open(str(path),"rb") as wf:
        ch=wf.getnchannels(); sr=wf.getframerate(); sw=wf.getsampwidth(); frames=wf.getnframes()
        raw=wf.readframes(frames)
    if sw!=2 or ch!=1 or sr!=SAMPLE_RATE:
        raise ValueError(f"{path}: expected mono PCM16 {SAMPLE_RATE} Hz, got ch={ch}, sr={sr}, width={sw}")
    return np.frombuffer(raw,dtype="<i2").astype(np.float32)/32768.0

def _write_wav(path: Path, samples: np.ndarray):
    path.parent.mkdir(parents=True,exist_ok=True)
    values=np.clip(samples,-0.98,0.98)
    pcm=(values*32767.0).astype("<i2")
    with wave.open(str(path),"wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())

def _effect(name: str, duration: float=0.45) -> np.ndarray:
    n=max(1,int(SAMPLE_RATE*duration)); t=np.arange(n,dtype=np.float32)/SAMPLE_RATE
    key=name.lower()
    env=np.exp(-t*5.5)
    if any(x in key for x in ("ding","success","chime","ping")):
        sig=np.sin(2*np.pi*880*t)+0.55*np.sin(2*np.pi*1320*t)*np.exp(-t*2)
        env=np.exp(-t*4)
    elif any(x in key for x in ("error","buzzer","wrong")):
        sig=np.sin(2*np.pi*145*t)+0.35*np.sin(2*np.pi*190*t)
        env=np.minimum(1,t*45)*np.exp(-t*2)
    elif any(x in key for x in ("whoosh","shatter","sweep")):
        seed=int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:4],"big")
        rng=np.random.default_rng(seed)
        noise=rng.normal(0,1,n).astype(np.float32)
        smooth=np.convolve(noise,np.ones(35,dtype=np.float32)/35,mode="same")
        sig=noise*0.35+smooth*1.8
        env=np.sin(np.clip(t/duration,0,1)*math.pi)**1.5
    elif any(x in key for x in ("typing","key","click","tap","pop")):
        sig=np.sin(2*np.pi*(620+180*np.sin(t*35))*t)
        env=np.exp(-t*30)
    else:
        sig=np.sin(2*np.pi*520*t)+0.25*np.sin(2*np.pi*780*t)
    return (sig*env*0.20).astype(np.float32)

def _music_pad(duration: float, cue: str) -> np.ndarray:
    # Durations often originate from an exact integer sample count divided by
    # SAMPLE_RATE. Floating-point multiplication can produce N-ε, so int()
    # would silently drop the final sample (e.g. 215278.99999999997).
    n=max(0,int(round(SAMPLE_RATE*duration)))
    if not n: return np.zeros(0,dtype=np.float32)
    t=np.arange(n,dtype=np.float32)/SAMPLE_RATE
    text=(cue or "").lower()
    if any(x in text for x in ("ominous","tense","mystery","тревог","напряж")):
        freqs=(82.4,123.5,164.8); volume=0.025
    elif any(x in text for x in ("upbeat","lo-fi","light","весел","лёгк")):
        freqs=(146.8,220.0,293.7); volume=0.018
    else:
        freqs=(110.0,164.8,220.0); volume=0.018
    slow=0.78+0.22*np.sin(2*np.pi*0.12*t)
    pad=sum(np.sin(2*np.pi*f*t + i*0.4)/(i+1) for i,f in enumerate(freqs))
    fade=np.minimum(1.0,np.minimum(t/0.35,(duration-t)/0.35)).clip(0,1)
    return (pad*slow*fade*volume).astype(np.float32)

def _decode_music(path: Path, ffmpeg: str = "ffmpeg") -> np.ndarray:
    """Decode any FFmpeg-supported music file to mono float PCM at SAMPLE_RATE."""
    if not path.is_file():
        raise FileNotFoundError(f"Музыкальный файл не найден: {path}")
    command = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-2500:]
        raise RuntimeError(f"FFmpeg не смог прочитать музыкальный файл {path}: {detail}")
    if not result.stdout:
        raise ValueError(f"Музыкальный файл пуст или не содержит аудио: {path}")
    return np.frombuffer(result.stdout, dtype="<i2").astype(np.float32) / 32768.0


def _loop_music(samples: np.ndarray, target_length: int) -> np.ndarray:
    """Fit music to narration length; repeated loops use a short crossfade."""
    if target_length <= 0:
        return np.zeros(0, dtype=np.float32)
    if len(samples) == 0:
        raise ValueError("Музыкальный файл не содержит декодируемых аудиосэмплов")
    if len(samples) >= target_length:
        out = samples[:target_length].copy()
    else:
        overlap = min(int(SAMPLE_RATE * 0.8), len(samples) // 4)
        if overlap < 16:
            repeats = int(np.ceil(target_length / len(samples)))
            out = np.tile(samples, repeats)[:target_length].copy()
        else:
            fade_out = np.linspace(1.0, 0.0, overlap, dtype=np.float32)
            fade_in = 1.0 - fade_out
            seam = samples[-overlap:] * fade_out + samples[:overlap] * fade_in
            cycle = np.concatenate((samples[:-overlap], seam)).astype(np.float32)
            repeats = int(np.ceil(target_length / len(cycle)))
            out = np.tile(cycle, repeats)[:target_length].copy()
    fade = min(int(SAMPLE_RATE * 1.8), max(1, len(out) // 3))
    if fade > 1:
        out[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
        out[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return out


def _music_ducking_gain(narration: np.ndarray, block_samples: int = 240,
                        voice_gain: float = 0.08, pause_gain: float = 0.22) -> np.ndarray:
    """Lower music while speech is active; use 10 ms blocks and smoothed gain."""
    if len(narration) == 0:
        return np.zeros(0, dtype=np.float32)
    block_count = int(np.ceil(len(narration) / block_samples))
    padded = np.pad(narration, (0, block_count * block_samples - len(narration)))
    blocks = padded.reshape(block_count, block_samples)
    rms = np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-12)
    targets = np.where(rms >= 0.010, voice_gain, pause_gain).astype(np.float32)
    smoothed = np.empty_like(targets)
    current = pause_gain
    for index, target in enumerate(targets):
        coefficient = 0.58 if target < current else 0.18
        current += (float(target) - current) * coefficient
        smoothed[index] = current
    return np.repeat(smoothed, block_samples)[:len(narration)]

def build_master_audio(beats: list[dict[str,Any]], output_path: Path,
                      *, pause_seconds: float=0.12,
                      add_procedural_bed: bool=False,
                      music_path: Path|None=None,
                      music_metadata: dict[str,Any]|None=None,
                      ffmpeg: str="ffmpeg",
                      enable_sfx: bool=False) -> dict[str,Any]:
    """Join narration WAVs and optionally mix a real, ducked music track.

    The spoken track remains the primary and self-sufficient explanation. A real
    music file is optional; no synthetic tonal bed or generated SFX is added by
    default.
    """
    if not beats:
        raise ValueError("Нет аудиобитов")
    narration_parts=[]
    timeline=[]
    cursor=0.0
    for index,beat in enumerate(beats):
        samples=_read_wav(Path(beat["audio_path"]))
        duration=len(samples)/SAMPLE_RATE
        gap=pause_seconds if index<len(beats)-1 else 0.0
        narration_parts.append(samples)
        if gap:
            narration_parts.append(np.zeros(int(round(SAMPLE_RATE*gap)),dtype=np.float32))
        timeline.append({"scene_id":beat["scene_id"],"beat_id":beat["beat_id"],
            "start_sec":round(cursor,4),"voice_end_sec":round(cursor+duration,4),
            "end_sec":round(cursor+duration+gap,4),"voice_duration_sec":round(duration,4),
            "gap_after_sec":gap})
        cursor += duration+gap
    narration=np.concatenate(narration_parts).astype(np.float32)
    mixed=narration.copy()
    offsets={(x["scene_id"],x["beat_id"]):x["start_sec"] for x in timeline}

    # Compatibility switch is intentionally disabled by default. Production never
    # enables it: the former synthesized chord pad caused the monotonous tonal bed.
    if add_procedural_bed:
        for beat,slot in zip(beats,timeline):
            start=max(0,min(len(mixed),int(round(slot["start_sec"]*SAMPLE_RATE))))
            end=max(start,min(len(mixed),int(round(slot["end_sec"]*SAMPLE_RATE))))
            target_length=end-start
            if target_length <= 0:
                continue
            bed=_music_pad(target_length/SAMPLE_RATE,beat.get("music_cue", ""))
            mixed[start:end] += bed[:target_length]

    music_report=None
    music_gain_report=None
    if music_path is not None:
        music_file=Path(music_path)
        decoded=_decode_music(music_file,ffmpeg=ffmpeg)
        track=_loop_music(decoded,len(narration))
        gain=_music_ducking_gain(narration)
        mixed += track*gain
        music_gain_report={"voice_gain":0.08,"pause_gain":0.22,"ducking":"speech_rms_10ms"}
        details=music_metadata or {}
        music_report={
            "path":str(music_file.resolve()),
            "title":details.get("title") or music_file.stem,
            "creator":details.get("creator"),
            "license":details.get("license"),
            "source_url":details.get("source_url"),
            "source":details.get("source"),
            "decoded_sample_rate":SAMPLE_RATE,
            "looped_to_narration":len(decoded)<len(narration),
            "crossfade_seconds":0.8 if len(decoded)<len(narration) and len(decoded)>=64 else 0.0,
        }

    effect_count=0
    if enable_sfx:
        for beat,slot in zip(beats,timeline):
            for sfx in beat.get("audio_sfx",[])[:1]:
                name=str(sfx.get("name", ""))
                if not name.strip():
                    continue
                fx=_effect(name)
                start=min(len(mixed),int(round((slot["start_sec"]+0.08)*SAMPLE_RATE)))
                end=min(len(mixed),start+len(fx))
                if end>start:
                    mixed[start:end] += fx[:end-start]
                    effect_count += 1

    peak=float(np.max(np.abs(mixed))) if len(mixed) else 0.0
    if peak>0.98:
        mixed *= 0.98/peak
    _write_wav(output_path,mixed)
    return {"path":str(output_path.resolve()),"sample_rate":SAMPLE_RATE,
            "duration_seconds":round(len(mixed)/SAMPLE_RATE,4),"beat_count":len(beats),
            "silence_between_beats_sec":pause_seconds,
            "procedural_bed":bool(add_procedural_bed),
            "effect_count":effect_count,
            "music_track":music_report,
            "music_ducking":music_gain_report,
            "timeline":timeline,
            "note":"Narration is the primary audio. A real music track is mixed only when supplied; synthetic bed and SFX are disabled by default."}
