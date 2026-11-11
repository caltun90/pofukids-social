"""Lay a Nika narration over a Pofu Kids reel.

python3 tools/narrate.py <video.mp4> <voice.wav> <out.mp4> [--start 0.5]

The game audio stays, but is ducked to 30% while Nika speaks. If the narration would run past the end,
the last frame (the end card) is held longer. Output loudness: -14 LUFS.
"""
import subprocess, sys, json
import numpy as np

SR = 44100


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True, check=True).stdout)


def dec(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def main():
    a = sys.argv[1:]
    video, voice, out = a[0], a[1], a[2]
    start = float(a[a.index("--start") + 1]) if "--start" in a else 0.5
    D = dur(video)
    v = dec(voice)
    nz = np.nonzero(np.abs(v[:, 0]) > 1e-3)[0]
    v = v[nz[0]:nz[-1] + 1]
    N = len(v) / SR
    end = start + N
    pad = max(0.0, end + 0.8 - D)
    T = D + pad
    game = dec(video)
    mix = np.zeros((int(T * SR) + SR, 2))
    mix[:len(game)] += game
    # duck the game under the voice
    g = np.ones(len(mix))
    a0, a1 = int((start - 0.25) * SR), int((end + 0.3) * SR)
    ramp = int(0.25 * SR)
    g[max(a0, 0):a1] = 0.3
    g[max(a0 - ramp, 0):max(a0, 0)] = np.linspace(1, 0.3, max(a0, 0) - max(a0 - ramp, 0))
    g[a1:a1 + ramp] = np.linspace(0.3, 1, len(g[a1:a1 + ramp]))
    mix *= g[:, None]
    # voice a little louder than the game
    vr = np.sqrt(np.mean(v ** 2)) + 1e-9
    v = v * (0.12 / vr)
    i0 = int(start * SR)
    mix[i0:i0 + len(v)] += v[:len(mix) - i0]
    mix = mix[:int(T * SR)]
    pk = np.max(np.abs(mix)) + 1e-9
    if pk > 0.95:
        mix *= 0.95 / pk
    wav = out + ".mix.wav"
    import wave
    w = wave.open(wav, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes()); w.close()
    vf = f"tpad=stop_mode=clone:stop_duration={pad:.2f}" if pad > 0 else "null"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", "-shortest", out], check=True)
    import os
    os.remove(wav)
    print(json.dumps({"out": out, "video": round(D, 2), "voice": round(N, 2), "padded": round(pad, 2), "total": round(T, 2)}))


if __name__ == "__main__":
    main()
