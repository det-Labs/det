"""Synthesize a futuristic tech / synthwave electronic soundtrack for the demo video."""

import math
from pathlib import Path
import struct
import wave
import numpy as np

def generate_futuristic_track(output_path: Path, duration_sec: float = 35.0, sample_rate: int = 44100):
    total_samples = int(sample_rate * duration_sec)
    bpm = 124.0
    beat_sec = 60.0 / bpm
    sixteenth_sec = beat_sec / 4.0
    total_beats = int(duration_sec / beat_sec)

    t = np.linspace(0, duration_sec, total_samples, endpoint=False)
    left = np.zeros(total_samples, dtype=np.float64)
    right = np.zeros(total_samples, dtype=np.float64)

    # 1. KICK DRUM (Every beat: 0, 1, 2, 3...)
    kick_len = int(sample_rate * 0.28)
    kick_t = np.linspace(0, 0.28, kick_len, endpoint=False)
    # Pitch drop from 150 Hz to 45 Hz with exponential envelope
    kick_freq = 45.0 + 105.0 * np.exp(-kick_t * 30.0)
    kick_phase = 2 * np.pi * np.cumsum(kick_freq) / sample_rate
    kick_env = np.exp(-kick_t * 14.0)
    kick_sample = np.sin(kick_phase) * kick_env * 0.85
    # Click transient
    kick_sample[:int(sample_rate * 0.005)] += np.random.uniform(-0.3, 0.3, int(sample_rate * 0.005))

    for b in range(total_beats):
        start_idx = int(b * beat_sec * sample_rate)
        end_idx = min(start_idx + kick_len, total_samples)
        actual_len = end_idx - start_idx
        if actual_len > 0:
            left[start_idx:end_idx] += kick_sample[:actual_len]
            right[start_idx:end_idx] += kick_sample[:actual_len]

    # 2. SNARE / CLAP (Beats 2 and 4)
    snare_len = int(sample_rate * 0.22)
    snare_t = np.linspace(0, 0.22, snare_len, endpoint=False)
    snare_tone = np.sin(2 * np.pi * 185.0 * snare_t) * np.exp(-snare_t * 22.0) * 0.35
    snare_noise = np.random.uniform(-1.0, 1.0, snare_len) * np.exp(-snare_t * 18.0) * 0.45
    snare_sample = snare_tone + snare_noise

    for b in range(total_beats):
        if b % 2 == 1:  # beats 1 and 3 (0-indexed: 1, 3, 5...)
            start_idx = int(b * beat_sec * sample_rate)
            end_idx = min(start_idx + snare_len, total_samples)
            actual_len = end_idx - start_idx
            if actual_len > 0:
                left[start_idx:end_idx] += snare_sample[:actual_len] * 0.7
                right[start_idx:end_idx] += snare_sample[:actual_len] * 0.7

    # 3. HI-HATS (Every 16th note)
    total_16ths = int(duration_sec / sixteenth_sec)
    hh_len = int(sample_rate * 0.045)
    hh_t = np.linspace(0, 0.045, hh_len, endpoint=False)
    hh_sample = np.random.uniform(-0.8, 0.8, hh_len) * np.exp(-hh_t * 90.0)

    for s in range(total_16ths):
        accent = 0.35 if s % 2 == 0 else 0.18
        if s % 4 == 2: accent = 0.45  # offbeat open feel
        start_idx = int(s * sixteenth_sec * sample_rate)
        end_idx = min(start_idx + hh_len, total_samples)
        actual_len = end_idx - start_idx
        if actual_len > 0:
            # Slight stereo pan for shimmer
            pan_l = 0.8 if s % 2 == 0 else 0.4
            pan_r = 0.4 if s % 2 == 0 else 0.8
            left[start_idx:end_idx] += hh_sample[:actual_len] * accent * pan_l
            right[start_idx:end_idx] += hh_sample[:actual_len] * accent * pan_r

    # 4. ROLLING BASSLINE (16th notes in D Minor: D2, F2, G2, A2)
    # MIDI notes: D2 = 73.42 Hz, F2 = 87.31 Hz, G2 = 98.00 Hz, A2 = 110.00 Hz
    bass_notes = [73.42, 73.42, 87.31, 73.42, 98.00, 73.42, 110.00, 87.31]
    bass_sub_len = int(sixteenth_sec * sample_rate)
    bass_t = np.linspace(0, sixteenth_sec, bass_sub_len, endpoint=False)

    for s in range(total_16ths):
        freq = bass_notes[s % len(bass_notes)]
        # Sawtooth + sub sine
        saw = (2.0 * (bass_t * freq - np.floor(bass_t * freq + 0.5))) * 0.25
        sub = np.sin(2 * np.pi * freq * bass_t) * 0.4
        bass_env = np.exp(-bass_t * 18.0)
        note_sample = (saw + sub) * bass_env

        start_idx = int(s * sixteenth_sec * sample_rate)
        end_idx = min(start_idx + bass_sub_len, total_samples)
        actual_len = end_idx - start_idx
        if actual_len > 0:
            left[start_idx:end_idx] += note_sample[:actual_len] * 0.55
            right[start_idx:end_idx] += note_sample[:actual_len] * 0.55

    # 5. RETRO SYNTH PAD CHORDS (Dm9, Bbmaj7, Fmaj7, C)
    chords = [
        [146.83, 220.00, 261.63, 329.63], # Dm9 (D3, A3, C4, E4)
        [116.54, 174.61, 220.00, 261.63], # Bbmaj7 (Bb2, F3, A3, C4)
        [174.61, 220.00, 261.63, 349.23], # Fmaj7 (F3, A3, C4, F4)
        [130.81, 196.00, 261.63, 329.63], # C (C3, G3, C4, E4)
    ]
    chord_dur = beat_sec * 4.0 # 1 bar per chord
    num_bars = int(duration_sec / chord_dur)

    for bar in range(num_bars):
        c_freqs = chords[bar % len(chords)]
        bar_start = int(bar * chord_dur * sample_rate)
        bar_end = min(int((bar + 1) * chord_dur * sample_rate), total_samples)
        bar_len = bar_end - bar_start
        if bar_len <= 0: continue
        bt = np.linspace(0, bar_len / sample_rate, bar_len, endpoint=False)
        pad_sig = np.zeros(bar_len)
        for f in c_freqs:
            # Dual detuned sines for rich analog warmth
            pad_sig += np.sin(2 * np.pi * f * bt) * 0.08
            pad_sig += np.sin(2 * np.pi * (f * 1.004) * bt) * 0.06
        # Envelope: soft attack & gentle release
        att = int(sample_rate * 0.15)
        rel = int(sample_rate * 0.15)
        env = np.ones(bar_len)
        if bar_len > att: env[:att] = np.linspace(0, 1, att)
        if bar_len > rel: env[-rel:] = np.linspace(1, 0, rel)

        left[bar_start:bar_end] += pad_sig * env * 0.6
        right[bar_start:bar_end] += pad_sig * env * 0.6

    # 6. ARPEGGIATED LEAD SYNTH (Crystal shimmering lead)
    arp_notes = [587.33, 659.25, 698.46, 880.00, 1046.50, 880.00, 698.46, 659.25] # D5, E5, F5, A5, C6...
    arp_step = sixteenth_sec
    for s in range(total_16ths):
        if s < 16: continue # Enter after 1 bar
        freq = arp_notes[s % len(arp_notes)]
        step_len = int(arp_step * sample_rate)
        st = np.linspace(0, arp_step, step_len, endpoint=False)
        lead_wave = (np.sin(2 * np.pi * freq * st) + 0.3 * np.sin(2 * np.pi * freq * 2.0 * st)) * np.exp(-st * 16.0)
        start_idx = int(s * arp_step * sample_rate)
        end_idx = min(start_idx + step_len, total_samples)
        actual_len = end_idx - start_idx
        if actual_len > 0:
            pan_l = 0.3 + 0.4 * np.sin(s * 0.5)
            pan_r = 1.0 - pan_l
            left[start_idx:end_idx] += lead_wave[:actual_len] * 0.32 * pan_l
            right[start_idx:end_idx] += lead_wave[:actual_len] * 0.32 * pan_r

    # MASTER ENVELOPE (Smooth fade in and fade out)
    fade_in_len = int(sample_rate * 0.8)
    fade_out_len = int(sample_rate * 2.0)
    master_env = np.ones(total_samples)
    master_env[:fade_in_len] = np.linspace(0, 1, fade_in_len)
    master_env[-fade_out_len:] = np.linspace(1, 0, fade_out_len)

    left *= master_env
    right *= master_env

    # Soft Limiter / Normalization
    max_val = max(np.max(np.abs(left)), np.max(np.abs(right)), 1e-6)
    scale = 0.92 / max_val
    left_int = (left * scale * 32767.0).astype(np.int16)
    right_int = (right * scale * 32767.0).astype(np.int16)

    # Interleave stereo
    stereo = np.empty((total_samples, 2), dtype=np.int16)
    stereo[:, 0] = left_int
    stereo[:, 1] = right_int

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo.tobytes())

    print(f"Synthesized futuristic tech track ({duration_sec}s, 44.1kHz stereo) at {output_path}")

if __name__ == "__main__":
    generate_futuristic_track(Path("media/linkedin/demo_soundtrack.wav"), duration_sec=35.0)
