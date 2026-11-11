"""Light, gently upbeat background music, synthesised with numpy (royalty-free), DIFFERENT for every seed.
For the photo-post videos (Cem, 11.11.2026: "arka fona hafif hareketli müzik, her seferinde farklı müzik").

python3 light_music.py out.wav <seconds> <seed>      e.g. seed = "2026-11-11-hata"
The seed picks key, tempo (92-116 bpm), chord progression, lead instrument, arpeggio pattern and groove,
so every post gets its own track. Stereo, 44.1 kHz, normalised to -1 dBFS.
"""
import hashlib, sys, wave
import numpy as np

SR = 44100
PROGS = [[0, 7, 9, 5], [9, 5, 0, 7], [0, 9, 5, 7], [2, 7, 0, 9], [0, 5, 9, 7], [5, 0, 7, 9], [0, 4, 9, 5], [9, 7, 5, 7]]
QUAL = {0: "M", 2: "m", 4: "m", 5: "M", 7: "M", 9: "m"}
PATTERNS = [[0, 1, 2, 3, 2, 1, 0, 1], [0, 2, 1, 3, 0, 2, 1, 2], [0, 1, 2, 1, 3, 2, 1, 2], [0, 2, 3, 2, 1, 2, 3, 1],
            [0, -1, 2, -1, 1, 3, -1, 2]]


def hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def tone(kind, f, dur, vol):
    t = np.arange(int(dur * SR)) / SR
    if kind == "marimba":
        x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 18)
        env = np.exp(-t * 7)
    elif kind == "pluck":
        x = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.3 for k in range(1, 7))
        env = np.exp(-t * 9)
    elif kind == "epiano":
        x = np.sin(2 * np.pi * f * t + 1.2 * np.sin(2 * np.pi * f * t) * np.exp(-t * 4))
        env = np.exp(-t * 3.2)
    elif kind == "bell":
        x = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)
        env = np.exp(-t * 4)
    else:  # soft square-ish synth
        x = np.tanh(2.2 * np.sin(2 * np.pi * f * t)) * 0.7
        env = np.exp(-t * 6)
    return vol * x * env * np.minimum(1, t / 0.004)


def pad(freqs, dur, vol):
    t = np.arange(int(dur * SR)) / SR
    x = sum(np.sin(2 * np.pi * (f + d) * t) for f in freqs for d in (-0.7, 0.7)) / (2 * len(freqs))
    return vol * x * np.minimum(1, t / 0.4) * np.minimum(1, np.maximum(0, dur - t) / 0.4)


def kick(vol):
    t = np.arange(int(0.25 * SR)) / SR
    return vol * np.sin(2 * np.pi * (50 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 14)


def noise_hit(rng, dur, vol, decay, hp=True):
    x = rng.standard_normal(int(dur * SR))
    if hp:
        x = np.diff(x, prepend=0)
    t = np.arange(len(x)) / SR
    return vol * x * np.exp(-t * decay)


def add(buf, x, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    x = x[:len(buf) - i]
    buf[i:i + len(x)] += x


def render(seconds, seed):
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    rng = np.random.default_rng(h % 2 ** 32)
    key = 57 + int(rng.integers(0, 12)) - 6                # tonic around A3
    bpm = float(rng.integers(92, 117))
    prog = PROGS[int(rng.integers(len(PROGS)))]
    lead = ["marimba", "pluck", "epiano", "bell", "synth"][int(rng.integers(5))]
    pat = PATTERNS[int(rng.integers(len(PATTERNS)))]
    swing = float(rng.choice([0.0, 0.0, 0.08]))
    clap = bool(rng.integers(0, 2))
    beat = 60.0 / bpm
    bar = 4 * beat
    n = int((seconds + 2) * SR)
    L, Rr = np.zeros(n), np.zeros(n)
    t, b = 0.0, 0
    while t < seconds + 1:
        deg = prog[b % len(prog)]
        root = key + deg
        third = 3 if QUAL[deg] == "m" else 4
        chord = [root, root + third, root + 7, root + 12]
        p = pad([hz(x) for x in chord[:3]], bar + 0.3, 0.05)
        add(L, p, t); add(Rr, p, t)
        for s in range(8):                                  # eighth-note arpeggio
            k = pat[s]
            if k < 0:
                continue
            at = t + s * beat / 2 + (swing * beat if s % 2 else 0)
            x = tone(lead, hz(chord[k] + 12), beat * 1.2, 0.16)
            pan = 0.35 + 0.3 * (k / 3)
            add(L, x * (1 - pan), at); add(Rr, x * pan, at)
        for s in range(4):                                  # bass on the beat
            x = tone("pluck", hz(root - 12 if s % 2 == 0 else root - 5), beat * 0.9, 0.22)
            add(L, x, t + s * beat); add(Rr, x, t + s * beat)
        for s in (0, 2):
            k = kick(0.35)
            add(L, k, t + s * beat); add(Rr, k, t + s * beat)
        for s in (1, 3):
            x = noise_hit(rng, 0.18, 0.10 if clap else 0.06, 22 if clap else 40)
            add(L, x, t + s * beat); add(Rr, x * 0.9, t + s * beat)
        for s in range(8):
            x = noise_hit(rng, 0.05, 0.035, 90)
            add(L, x * 0.7, t + s * beat / 2 + (swing * beat if s % 2 else 0)); add(Rr, x, t + s * beat / 2)
        t += bar
        b += 1
    m = int(seconds * SR)
    st = np.stack([L[:m], Rr[:m]], 1)
    fi, fo = int(0.5 * SR), int(1.8 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    st /= np.max(np.abs(st)) + 1e-9
    info = f"key {key} bpm {bpm:.0f} prog {prog} lead {lead}"
    return (st * 0.89 * 32767).astype(np.int16), info


if __name__ == "__main__":
    out, secs, seed = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    a, info = render(secs, seed)
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())
    print("ok", out, f"{secs:.1f}s", info)
