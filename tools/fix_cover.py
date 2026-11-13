#!/usr/bin/env python3
"""Make sure a reel never starts on a black or fading-in frame (Instagram uses frame 0 as the cover).

    python3 tools/fix_cover.py check media/*.mp4          # lists leading dark frames per file
    python3 tools/fix_cover.py fix <in.mp4> <out.mp4>     # replaces them with the first good frame

The fix keeps the duration and audio sync: the dark frames are dropped and the first
good frame is cloned in their place (video re-encoded, audio copied).
"""
import re, subprocess, sys

DARK = 20.0   # mean luma below this counts as black
FADE = 0.92   # a frame darker than 92% of the frame at ~0.5 s is part of a fade-in


def leading_dark(path, limit=1.5):
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-t", str(limit), "-an", "-vf",
         "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"],
        capture_output=True, text=True).stdout
    ys = [float(y) for y in re.findall(r"YAVG=([0-9.]+)", out)]
    if not ys:
        return 0
    ref = ys[min(15, len(ys) - 1)]
    n = 0
    for y in ys:
        if y < DARK or y < FADE * ref:
            n += 1
        else:
            return n
    return n


def fix(src, dst):
    n = leading_dark(src)
    if n == 0:
        subprocess.run(["cp", src, dst], check=True)
        print(f"{src}: frame 0 ok, copied")
        return
    vf = f"select='gte(n,{n})',setpts=N/FRAME_RATE/TB,tpad=start={n}:start_mode=clone"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-c:v", "libx264",
                    "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    "-movflags", "+faststart", dst], check=True)
    left = leading_dark(dst)
    print(f"{src}: {n} dark frame(s) replaced -> {dst} (now {left})")
    if left:
        sys.exit(f"still dark at start: {dst}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        bad = 0
        for p in sys.argv[2:]:
            n = leading_dark(p)
            bad += n > 0
            print(f"{p}: {'OK' if n == 0 else f'{n} dark frame(s) at start'}")
        sys.exit(1 if bad else 0)
    elif len(sys.argv) == 4 and sys.argv[1] == "fix":
        fix(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
