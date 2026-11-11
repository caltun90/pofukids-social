"""Turn a Pofu Kids single photo (1080x1350) into a voiced reel (Cem, 11.11.2026: photos must not go out silent).

python3 tools/photo_reel.py <photo.jpg> <voice.wav> <seed> <out.mp4>

1080x1920, 30 fps: blurred photo as background, the photo itself in the middle with a slow zoom (frame 0 = the
full photo, so it works as the cover). Nika's line starts at 0.5 s, the clip ends 1.3 s after it. A light music bed
(tools/light_music.py, different per seed) is ducked under the voice. Loudness -14 LUFS.
"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageFilter, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True, check=True).stdout)


def main():
    photo, voice, seed, out = sys.argv[1:5]
    tmp = tempfile.mkdtemp()
    # trim silence around the voice
    v = f"{tmp}/v.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", voice, "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse", "-ar", "44100", "-ac", "2", v],
                   check=True)
    V = dur(v)
    D = round(0.5 + V + 1.3, 2)
    im = Image.open(photo).convert("RGB")
    bg = im.resize((int(1920 * im.width / im.height), 1920), Image.LANCZOS)
    x = (bg.width - 1080) // 2
    bg = bg.crop((x, 0, x + 1080, 1920)).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.92)
    bg.save(f"{tmp}/bg.png")
    music = f"{tmp}/m.wav"
    subprocess.run([sys.executable, f"{HERE}/light_music.py", music, str(D + 1), seed], check=True,
                   capture_output=True)
    fg_w = 1000
    fc = (f"[1:v]scale=w='trunc({fg_w}*(1+0.045*t/{D})/2)*2':h=-2:eval=frame[fg];"
          f"[0:v][fg]overlay=x='(W-w)/2':y='(H-h)/2':eval=frame,format=yuv420p[v];"
          f"[2:a]adelay=500|500,apad,atrim=0:{D}[vo];"
          f"[3:a]volume=0.32,atrim=0:{D},afade=t=in:d=0.4,afade=t=out:st={D - 1.0}:d=1.0[mu];"
          f"[vo]asplit[vo1][vo2];[mu][vo1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck];"
          f"[duck][vo2]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", str(D), "-i", f"{tmp}/bg.png",
                    "-loop", "1", "-framerate", "30", "-t", str(D), "-i", photo, "-i", v, "-i", music,
                    "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(D),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], check=True)
    print("ok", out, f"{D:.2f}s")


if __name__ == "__main__":
    main()
