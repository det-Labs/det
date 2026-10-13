"""Synthesize voiceover segments and matching subtitle tracks (.srt) using Windows SAPI TTS."""

import subprocess
import tempfile
from pathlib import Path
import wave

VOICE_SEGMENTS = [
    ("Welcome to det — the fast, local-first SQL ETL workspace powered by Apache DataFusion.", 0.5),
    ("Adding data sources is effortless. We declare a new Parquet source with strict schemas and rich descriptions.", 0.5),
    ("With one click, DataFusion inspects the Parquet schema, column contracts, and instant tabular previews.", 0.5),
    ("Next, we add our CSV customer master file and preview live records directly in the catalog.", 0.5),
    ("In the ETL module, we create a new pipeline. Step 1 writes pure ANSI SQL directly joining Parquet and CSV — zero Jinja templating.", 0.5),
    ("We attach markdown documentation notes to Step 1, then add Step 2 to compute regional aggregate sales and configure our destination sink.", 0.5),
    ("We run pre-flight DataFusion logical plan validation, then hit Save and Run. Execution completes in sub-second vectorized time.", 0.5),
    ("Running it a second time captures real-time audit telemetry. In Monitoring, we inspect 100% pipeline health, step latencies, and logs.", 0.5),
    ("Finally, we generate living HTML documentation with embedded schema lineage DAGs. That's det: fast, modular, and pure SQL.", 0.5)
]

def synthesize_speech(text: str, output_wav: Path, voice_name: str = "Microsoft Zira Desktop", rate: int = 0):
    ps_content = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('{voice_name}')
$synth.Rate = {rate}
$synth.SetOutputToWaveFile('{output_wav.resolve().as_posix()}')
$synth.Speak('{text.replace("'", "''")}')
$synth.Dispose()
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as tf:
        tf.write(ps_content)
        ps_path = Path(tf.name)

    try:
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_path)], check=True, stdout=subprocess.DEVNULL)
    finally:
        if ps_path.exists():
            ps_path.unlink()

def get_wav_duration(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)

def format_srt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def build_voiceover_and_subtitles(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_wavs = []
    srt_lines = []
    
    current_time = 0.5 # Start slightly after 0
    
    print("Generating voiceover narration and subtitle track...")
    for idx, (text, pause_after) in enumerate(VOICE_SEGMENTS):
        seg_wav = output_dir / f"voice_seg_{idx+1}.wav"
        synthesize_speech(text, seg_wav)
        dur = get_wav_duration(seg_wav)
        temp_wavs.append((seg_wav, dur, pause_after))
        
        start_t = current_time
        end_t = current_time + dur
        
        srt_lines.append(f"{idx + 1}")
        srt_lines.append(f"{format_srt_time(start_t)} --> {format_srt_time(end_t)}")
        srt_lines.append(text)
        srt_lines.append("")
        
        current_time += dur + pause_after
        print(f"  Segment {idx+1}/{len(VOICE_SEGMENTS)}: {dur:.1f}s — \"{text[:45]}...\"")

    srt_path = output_dir / "det_demo_subtitles.srt"
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    print(f"Subtitles written to: {srt_path}")

    # Combine audio segments into master voice track
    master_voice_wav = output_dir / "master_voiceover.wav"
    total_samples = int(44100 * (current_time + 1.0))
    import numpy as np

    full_audio = np.zeros(total_samples, dtype=np.int16)
    
    insert_pos = 0.5
    for seg_wav, dur, pause_after in temp_wavs:
        with wave.open(str(seg_wav), "rb") as wf:
            n_chan = wf.getnchannels()
            n_frames = wf.getnframes()
            data = wf.readframes(n_frames)
            seg_samples = np.frombuffer(data, dtype=np.int16)
            if n_chan == 2:
                seg_samples = seg_samples[::2] # to mono
            
            # Resample if needed
            rate = wf.getframerate()
            if rate != 44100:
                # simple linear resample
                target_len = int(len(seg_samples) * 44100 / rate)
                seg_samples = np.interp(
                    np.linspace(0, len(seg_samples), target_len, endpoint=False),
                    np.arange(len(seg_samples)),
                    seg_samples
                ).astype(np.int16)

            start_idx = int(insert_pos * 44100)
            end_idx = min(start_idx + len(seg_samples), total_samples)
            actual = end_idx - start_idx
            full_audio[start_idx:end_idx] = seg_samples[:actual]
            insert_pos += dur + pause_after
        
        # Cleanup segment
        seg_wav.unlink()

    # Write master mono/stereo voice
    with wave.open(str(master_voice_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(full_audio.tobytes())

    print(f"Master voiceover generated: {master_voice_wav} ({current_time:.1f}s)")
    return master_voice_wav, srt_path, current_time

if __name__ == "__main__":
    out_dir = Path("media/linkedin")
    build_voiceover_and_subtitles(out_dir)
