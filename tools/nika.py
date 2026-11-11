"""Nika voice-over, end to end (Cem, 10-11.11.2026): one Gemini TTS request for many lines,
then split the recording into one wav per line by TRANSCRIPT (never by silence alone).

python3 nika.py speak <job> <lines.json> [--style teacher|calm]   # push to tts-drop, wait, download
python3 nika.py split <job>                                        # transcribe runs, align, write voice_NN.wav

lines.json = ["line 0", "line 1", ...]. Output: out/voice_<job>/voice_all.wav and voice_NN.wav (+ align.txt).
Runs in GitHub Actions on branch tts-drop (the workspace cannot reach Google). Free tier: 10 TTS requests a day,
so put all of a day's lines into one or two jobs.
"""
import difflib, json, os, re, shutil, subprocess, sys, time, unicodedata, wave

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLES = {
    "parent": "Read the lines below as Nika, a warm, cheerful, natural American English female voice narrating short videos "
              "of a kids' learning app for parents on Instagram: friendly, gently upbeat, clear, smiling, never robotic, "
              "never shouting. Make a clear pause of about one second after every line. Read only the lines:",
    "teacher": "Read the lines below as Nika, a warm, cheerful and clear native Turkish female English teacher talking "
               "to her students on TikTok: friendly, natural, lively but not shouting, never robotic. English words and "
               "sentences with natural American pronunciation. Make a clear pause of about one second after every line. "
               "Read only the lines:",
    "calm": "Read the lines below as a warm, calm, respectful native Turkish woman: gentle, sincere and dignified, "
            "natural and human, not robotic. English words and sentences with natural American pronunciation. "
            "Make a clear pause of about one second after every line. Read only the lines:",
}


def sh(*a, **k):
    return subprocess.run(a, check=True, text=True, capture_output=True, cwd=k.get("cwd", HERE)).stdout


def push_job(job, spec, extra_files=()):
    """Commit tts/<job>.json (+ extra files) on top of origin/tts-drop and push."""
    sh("git", "fetch", "-q", "origin", "tts-drop")
    wt = f"/tmp/nika_wt_{job}"
    shutil.rmtree(wt, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=HERE)
    sh("git", "worktree", "add", "-f", "--detach", wt, "origin/tts-drop")
    try:
        os.makedirs(f"{wt}/tts", exist_ok=True)
        json.dump(spec, open(f"{wt}/tts/{job}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for src, dst in extra_files:
            os.makedirs(os.path.dirname(f"{wt}/{dst}"), exist_ok=True)
            shutil.copy(src, f"{wt}/{dst}")
        sh("git", "add", "-A", cwd=wt)
        sh("git", "-c", "user.name=pofu-bot", "-c", "user.email=bot@pofukids.com", "commit", "-qm", f"tts {job}", cwd=wt)
        for _ in range(3):
            r = subprocess.run(["git", "push", "-q", "origin", "HEAD:tts-drop"], cwd=wt, capture_output=True, text=True)
            if r.returncode == 0:
                break
            sh("git", "pull", "-q", "--rebase", "origin", "tts-drop", cwd=wt)
        else:
            raise SystemExit("push to tts-drop failed: " + r.stderr)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", wt], cwd=HERE)


def wait_status(job, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(20)
        subprocess.run(["git", "fetch", "-q", "origin", "tts-drop"], cwd=HERE)
        r = subprocess.run(["git", "show", f"origin/tts-drop:tts/{job}/status.txt"], cwd=HERE,
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    raise SystemExit(f"timeout waiting for tts/{job}/status.txt")


def git_file(path, out):
    data = subprocess.run(["git", "show", f"origin/tts-drop:{path}"], cwd=HERE, capture_output=True, check=True).stdout
    open(out, "wb").write(data)


def speak(job, lines_path, style="teacher"):
    lines = json.load(open(lines_path, encoding="utf-8"))
    d = os.path.join(HERE, "out", f"voice_{job}")
    os.makedirs(d, exist_ok=True)
    json.dump(lines, open(f"{d}/lines.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    push_job(job, {"voices": ["Nika"], "single": True, "style": STYLES.get(style, style), "lines": lines})
    st = wait_status(job)
    print(st.strip()[-400:])
    if not st.startswith("OK"):
        raise SystemExit("TTS failed")
    git_file(f"tts/{job}/voice_all.wav", f"{d}/voice_all.wav")
    print("ok", f"{d}/voice_all.wav")


def runs(path, noise="-40dB", dur=0.3):
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", f"silencedetect=n={noise}:d={dur}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", o)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", o)]
    with wave.open(path) as w:
        total = w.getnframes() / w.getframerate()
    out, cur = [], 0.0
    for s, e in zip(st, en):
        if s > cur + 0.08:
            out.append([cur, s])
        cur = e
    if total > cur + 0.08:
        out.append([cur, total])
    return out


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("ı", "i"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).split()


def align(lines, heard, R=None):
    """Monotonic split of the runs into len(lines) non-empty groups, maximising word similarity
    plus a duration fit (speech length of a group vs the line's text length)."""
    import math
    n, m = len(lines), len(heard)
    dur = [b - a for a, b in R] if R else None
    if dur:
        rate = sum(dur) / max(1, sum(len(x) for x in lines))   # seconds per character
    L = [norm(x) for x in lines]
    H = [norm(x) for x in heard]
    NEG = -1e9
    best = [[NEG] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0
    for i in range(1, n + 1):
        for j in range(i, m - (n - i) + 1):
            for k in range(i - 1, j):
                if best[i - 1][k] == NEG:
                    continue
                words = sum(H[k:j], [])
                sim = difflib.SequenceMatcher(None, L[i - 1], words).ratio()
                if dur:
                    gd = sum(dur[k:j]) + 0.25 * (j - k - 1)
                    sim -= 0.6 * abs(math.log(max(gd, 0.05) / max(0.3, len(lines[i - 1]) * rate)))
                v = best[i - 1][k] + sim
                if v > best[i][j]:
                    best[i][j], back[i][j] = v, k
    groups, j = [], m
    for i in range(n, 0, -1):
        k = back[i][j]
        groups.append((k, j))
        j = k
    return groups[::-1]


def split(job):
    d = os.path.join(HERE, "out", f"voice_{job}")
    lines = json.load(open(f"{d}/lines.json", encoding="utf-8"))
    path = f"{d}/voice_all.wav"
    R = runs(path)
    if len(R) < len(lines):
        R = runs(path, "-40dB", 0.18)
    if len(R) < len(lines):
        raise SystemExit(f"only {len(R)} speech runs for {len(lines)} lines")
    seg = f"{d}/runs"
    shutil.rmtree(seg, ignore_errors=True)
    os.makedirs(seg)
    files = []
    for i, (a, b) in enumerate(R):
        f = f"{seg}/r{i:02d}.wav"
        sh("ffmpeg", "-v", "error", "-y", "-i", path, "-ss", f"{max(0, a - 0.05):.3f}", "-to", f"{b + 0.05:.3f}", f)
        files.append((f, f"tts_seg/{job}/r{i:02d}.wav"))
    tj = f"{job}_heard"
    push_job(tj, {"lines": [], "transcribe": [dst for _, dst in files]}, files)
    st = wait_status(tj)
    heard = {}
    for line in st.splitlines():
        mm = re.match(r"heard tts_seg/[^/]+/r(\d+)\.wav: (.*)", line)
        if mm:
            heard[int(mm.group(1))] = mm.group(2)
    H = [heard.get(i, "") for i in range(len(R))]
    groups = align(lines, H, R)
    rep = []
    for i, (k, j) in enumerate(groups):
        a, b = max(0, R[k][0] - 0.06), R[j - 1][1] + 0.12
        sh("ffmpeg", "-v", "error", "-y", "-i", path, "-ss", f"{a:.3f}", "-to", f"{b:.3f}", f"{d}/voice_{i:02d}.wav")
        got = " ".join(H[k:j])
        sim = difflib.SequenceMatcher(None, norm(lines[i]), norm(got)).ratio()
        rep.append(f"{i:02d} {b - a:5.2f}s sim {sim:.2f} | {lines[i]}\n          heard: {got}")
    open(f"{d}/align.txt", "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))
    low = [r for r in rep if float(r.split("sim ")[1][:4]) < 0.5]
    print(f"ok {len(groups)} lines" + (f", CHECK {len(low)} low-similarity lines" if low else ""))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "speak":
        style = sys.argv[sys.argv.index("--style") + 1] if "--style" in sys.argv else "teacher"
        speak(sys.argv[2], sys.argv[3], style)
    elif cmd == "split":
        split(sys.argv[2])
    else:
        raise SystemExit(__doc__)
