"""Overlay Final Audio Mix (Voiceover + Soft House Beat) and burn in subtitles onto screen recording."""

import sys
from pathlib import Path
import subprocess
import imageio_ffmpeg

def process_recorded_video(input_video_path: Path, output_video_path: Path = None):
    if not input_video_path.exists():
        print(f"Error: Could not find recording at {input_video_path}")
        return

    media_dir = input_video_path.parent
    if output_video_path is None:
        output_video_path = media_dir / "det_official_demo.mp4"

    audio_mix = media_dir / "final_audio_mix.m4a"
    srt_file = media_dir / "det_demo_subtitles.srt"

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    # Escape path for FFmpeg subtitles filter on Windows (forward slashes and escaped colon)
    srt_filter_path = srt_file.resolve().as_posix().replace(":", r"\:")

    print(f"Input Video:  {input_video_path}")
    print(f"Audio Track:  {audio_mix}")
    print(f"Subtitles:    {srt_file}")
    print(f"Output Video: {output_video_path}")
    print("\nEncoding final video with burned-in subtitles and mixed soundtrack...")

    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(input_video_path),
        "-i", str(audio_mix),
        "-filter_complex",
        f"[0:v]subtitles='{srt_filter_path}':force_style='Fontname=Segoe UI,Fontsize=18,Bold=1,PrimaryColour=&H00FFFFFF,BackColour=&H80000000,BorderStyle=4,MarginV=35'[v_out]",
        "-map", "[v_out]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_video_path)
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode == 0:
        sz = output_video_path.stat().st_size / (1024 * 1024)
        print(f"\n🎉 Official Product Demo video ready!")
        print(f"File: {output_video_path} ({sz:.2f} MB)")
    else:
        err = proc.stderr.decode("utf-8", errors="replace")
        print(f"FFmpeg error: {err}")

if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("media/linkedin/screen_record.mp4")
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("media/linkedin/det_official_demo.mp4")
    process_recorded_video(src, dst)
