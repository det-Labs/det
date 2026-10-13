"""Synthesize a chilled, soft techno house track in the background."""

import math
from pathlib import Path
import wave
import numpy as np

def generate_soft_house_track(output_path: Path, duration_sec: float = 85.0, sample_rate: int = 44100):
    total_samples = int(sample_rate * duration_sec)
    bpm = 122.0
    beat_sec = 60.0 / bpm
    sixteenth_sec = beat_sec / 4.0
    total_beats = int(duration_sec / beat_sec)

    t = np.linspace(0, duration_sec, total_samples, endpoint=False)
    left = np.zeros(total_samples, dtype=np.float64)
    right = np.zeros(total_samples, dtype=np.float64)

    # 1. SOFT 4-ON-THE-FLOOR KICK
    kick_len = int(sample_rate * 0.22)
    kick_t = np.linspace(0, 0.22, kick_len, endpoint=False)
    kick_freq = 42.0 + 80.0 * np.exp(-kick_t * 26.0)
    kick_phase = 2 * np.pi * np.cumsum(kick_freq) / sample_rate
    kick_env = np.exp(-kick_t * 12.0)
    kick_sample = np.sin(kick_phase) * kick_env * 0.55

    for b in range(total_beats):
        s_idx = int(b * beat_sec * sample_rate)
        e_idx = min(s_idx + kick_len, total_samples)
        act = e_idx - s_idx
        if act > 0:
            left[s_idx:e_idx] += kick_sample[:act]
            right[s_idx:e_idx] += kick_sample[:act]

    # 2. SOFT CLAP / RIM (Beats 2 and 4)
    clap_len = int(sample_rate * 0.14)
    clap_t = np.linspace(0, 0.14, clap_len, endpoint=False)
    clap_noise = np.random.uniform(-1.0, 1.0, clap_len) * np.exp(-clap_t * 30.0) * 0.25
    clap_tone = np.sin(2 * np.pi * 320.0 * clap_t) * np.exp(-clap_t * 40.0) * 0.15
    clap_sample = clap_noise + clap_tone

    for b in range(total_beats):
        if b % 2 == 1:
            s_idx = int(b * beat_sec * sample_rate)
            e_idx = min(s_idx + clap_len, total_samples)
            act = e_idx - s_idx
            if act > 0:
                left[s_idx:e_idx] += clap_sample[:act] * 0.5
                right[s_idx:e_idx] += clap_sample[:act] * 0.5

    # 3. SOFT OFFBEAT HI-HAT & SHAKER
    hat_len = int(sample_rate * 0.05)
    hat_t = np.linspace(0, 0.05, hat_len, endpoint=False)
    hat_sample = np.random.uniform(-0.6, 0.6, hat_len) * np.exp(-hat_t * 70.0) * 0.22

    for b in range(total_beats):
        # Offbeat (between beats)
        offbeat_time = (b + 0.5) * beat_sec
        s_idx = int(offbeat_time * sample_rate)
        e_idx = min(s_idx + hat_len, total_samples)
        act = e_idx - s_idx
        if act > 0:
            left[s_idx:e_idx] += hat_sample[:act] * 0.6
            right[s_idx:e_idx] += hat_sample[:act] * 0.7

    # 4. WARM ROLLING DEEP HOUSE BASSLINE (Eighth notes)
    # Chord progression: Fm -> Ab -> Db -> C (MIDI notes: F1=43.65, Ab1=51.91, Db1=34.65, C1=32.70)
    root_freqs = [43.65, 43.65, 51.91, 51.91, 34.65, 34.65, 32.70, 32.70]
    total_eighths = int(duration_sec / (beat_sec / 2.0))
    for eth in range(total_eighths):
        f_idx = (eth // 4) % len(root_freqs)
        freq = root_freqs[f_idx]
        eth_len = int(sample_rate * (beat_sec / 2.0) * 0.85)
        eth_t = np.linspace(0, (beat_sec / 2.0) * 0.85, eth_len, endpoint=False)
        # Warm filtered saw/sine blend
        bass_s = (0.7 * np.sin(2 * np.pi * freq * eth_t) + 0.3 * np.sin(2 * np.pi * freq * 2 * eth_t)) * np.exp(-eth_t * 5.0) * 0.35
        
        s_idx = int(eth * (beat_sec / 2.0) * sample_rate)
        e_idx = min(s_idx + eth_len, total_samples)
        act = e_idx - s_idx
        if act > 0:
            left[s_idx:e_idx] += bass_s[:act]
            right[s_idx:e_idx] += bass_s[:act]

    # 5. LUSH CHORD PADS (Warm Rhodes / Pad sound)
    # Chords: Fm9, Abmaj7, Dbmaj7, Cm7
    chords = [
        [174.61, 207.65, 261.63, 311.13, 349.23], # Fm9
        [207.65, 261.63, 311.13, 392.00],         # Abmaj7
        [138.59, 174.61, 207.65, 261.63],         # Dbmaj7
        [130.81, 155.56, 196.00, 233.08],         # Cm7
    ]
    bar_sec = beat_sec * 4.0
    total_bars = int(duration_sec / bar_sec) + 1
    for bar in range(total_bars):
        chord = chords[bar % len(chords)]
        b_start = int(bar * bar_sec * sample_rate)
        b_len = int(bar_sec * sample_rate)
        b_t = np.linspace(0, bar_sec, b_len, endpoint=False)
        
        # Soft swell envelope
        swell = np.sin(np.pi * (b_t / bar_sec)) ** 1.3 * 0.16
        
        chord_mix_l = np.zeros(b_len, dtype=np.float64)
        chord_mix_r = np.zeros(b_len, dtype=np.float64)
        for i, f in enumerate(chord):
            detune = 1.002 if i % 2 == 0 else 0.998
            chord_mix_l += np.sin(2 * np.pi * f * b_t) * swell
            chord_mix_r += np.sin(2 * np.pi * f * detune * b_t) * swell
            
        e_idx = min(b_start + b_len, total_samples)
        act = e_idx - b_start
        if act > 0:
            left[b_start:e_idx] += chord_mix_l[:act]
            right[b_start:e_idx] += chord_mix_r[:act]

    # Normalize and Soft Limiter
    max_val = max(np.max(np.abs(left)), np.max(np.abs(right)), 1e-6)
    left = np.tanh(left / max_val * 0.92)
    right = np.tanh(right / max_val * 0.92)

    int_left = (left * 32767).astype(np.int16)
    int_right = (right * 32767).astype(np.int16)

    stereo_interleaved = np.empty((total_samples * 2,), dtype=np.int16)
    stereo_interleaved[0::2] = int_left
    stereo_interleaved[1::2] = int_right

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo_interleaved.tobytes())

    print(f"Synthesized soft techno house track: {output_path} ({duration_sec:.1f}s)")

if __name__ == "__main__":
    generate_soft_house_track(Path("media/linkedin/soft_house_beat.wav"), duration_sec=85.0)
