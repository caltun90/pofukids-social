"""Runs in GitHub Actions on branch tts-drop (the workspace cannot reach Google).
Reads tts/<job>.json, writes tts/<job>/voice_NN.wav and tts/<job>/status.txt.

tts/<job>.json: {"voices": ["Nika", "Kore"], "style": "...", "lines": ["...", ...],
                 "transcribe": ["tts/<job>/voice_00.wav", ...]}   # optional: written to status.txt
"""
import base64, glob, io, json, os, sys, time, urllib.error, urllib.request, wave

KEY = os.environ["GEMINI_API_KEY"]
CLOUD_KEY = os.environ.get("GOOGLE_TTS_KEY") or KEY
CLOUD = "https://texttospeech.googleapis.com/v1"


_TOKEN = []


def cloud_auth():
    """Service account JSON (secret GOOGLE_TTS_SA) wins; Cloud TTS refuses AI Studio keys."""
    sa = os.environ.get("GOOGLE_TTS_SA", "").strip()
    if not sa:
        return {"x-goog-api-key": CLOUD_KEY}
    if not _TOKEN:
        from google.oauth2 import service_account
        import google.auth.transport.requests
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa), scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        _TOKEN.append(creds.token)
    return {"Authorization": f"Bearer {_TOKEN[0]}"}


def cloud_req(path, body=None):
    req = urllib.request.Request(CLOUD + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", **cloud_auth()})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def cloud_voice(lang, prefer, log):
    """First preferred name that exists, else a female Chirp3-HD voice, else any female voice."""
    voices = cloud_req(f"/voices?languageCode={lang}")["voices"]
    names = [v["name"] for v in voices]
    log.append(f"{lang} voices: " + ", ".join(n for n in names if "Chirp3" in n or "Wavenet" in n)[:600])
    for p in prefer:
        if p in names:
            return p
    fem = [v["name"] for v in voices if v.get("ssmlGender") == "FEMALE"]
    return next((n for n in fem if "Chirp3-HD" in n), fem[0] if fem else names[0])


def cloud_speak(text, voice, lang=None, model=None, prompt=None):
    """Chirp3-HD voice by full name, or a Gemini TTS voice (model + short name like "Kore")."""
    lang = lang or "-".join(voice.split("-")[:2])
    v = {"languageCode": lang, "name": voice}
    inp = {"text": text}
    if model:
        v["modelName"] = model
        if prompt:
            inp["prompt"] = prompt
    d = cloud_req("/text:synthesize", {"input": inp, "voice": v,
                                        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}})
    raw = base64.b64decode(d["audioContent"])
    if raw[:4] == b"RIFF":
        with wave.open(io.BytesIO(raw)) as w:
            return w.readframes(w.getnframes())
    return raw
MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]


def call(model, voice, text):
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps({"contents": [{"parts": [{"text": text}]}],
                         "generationConfig": {"responseModalities": ["AUDIO"],
                                              "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": KEY})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    raw = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    if raw[:4] == b"RIFF":   # the model returns a WAV file (plus a metadata trailer), not bare PCM
        with wave.open(io.BytesIO(raw)) as w:
            return w.readframes(w.getnframes())
    return raw


def transcribe(path, log):
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    for model in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-flash-latest"]:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps({"contents": [{"parts": [
                {"text": "Write exactly the words spoken in this audio, nothing else."},
                {"inlineData": {"mimeType": "audio/wav", "data": b64}}]}]}).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": KEY})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.load(r)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            log.append(f"transcribe {model}: {e}")
    return "?"


def speak(models, voices, text, log):
    last = ""
    for model in models:
        for voice in voices:
            for attempt in range(5):
                try:
                    return call(model, voice, text), model, voice
                except urllib.error.HTTPError as e:
                    last = f"{model} {voice} HTTP {e.code}: {e.read().decode()[:900]}"
                    log.append(last)
                    print(last, flush=True)
                    if e.code == 429 and ("PerDay" in last or "per day" in last):
                        raise RuntimeError(last)      # daily quota: waiting will not help
                    if e.code == 429 or e.code >= 500:
                        time.sleep(40)
                        continue
                    break
                except Exception as e:                 # e.g. the model answered without audio
                    last = f"{model} {voice} {type(e).__name__}: {e}"
                    log.append(last)
                    print(last, flush=True)
                    if attempt >= 1:
                        break
                    time.sleep(5)
    raise RuntimeError(last)


START = time.time()
for path in sorted(glob.glob("tts/*.json")):
    job = path[:-5]
    if os.path.exists(f"{job}/status.txt"):
        continue
    spec = json.load(open(path, encoding="utf-8"))
    os.makedirs(job, exist_ok=True)
    log, ok = [], True
    voices = spec.get("voices", ["Kore"])
    cloud = {}
    gem = spec.get("gemini")          # {"models": [...], "voices": [...], "prompt": "..."}: Gemini TTS through Cloud TTS
    gem_pick = []
    if spec.get("engine") == "cloud" and not gem:
        try:
            for lang, prefer in spec.get("cloud_voices", {"tr-TR": [], "en-US": []}).items():
                cloud[lang] = cloud_voice(lang, prefer, log)
            log.append(f"cloud voices: {cloud}")
        except urllib.error.HTTPError as e:
            ok = False
            log.append(f"cloud voices HTTP {e.code}: {e.read().decode()[:600]}")
        except Exception as e:
            ok = False
            log.append(f"cloud voices {type(e).__name__}: {e}")
    if spec.get("single") and ok:     # one request for all lines (free tier: 10 requests a day); split on silence later
        text = f'{spec.get("style", "")}\n' + "\n".join(l["text"] if isinstance(l, dict) else l for l in spec["lines"])
        try:
            pcm, model, voice = speak(MODELS, voices, text, log)
            with wave.open(f"{job}/voice_all.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            log.append(f"single ok {model} {voice} {len(pcm)} bytes")
        except Exception as e:
            ok = False
            log.append(f"single failed: {e}")
        spec["lines"] = []
    for i, line in enumerate(spec["lines"] if ok else []):
        if spec.get("engine") == "cloud":
            text, lang = (line["text"], line["lang"]) if isinstance(line, dict) else (line, "tr-TR")
            pcm = None
            if gem:
                combos = gem_pick or [(m, v) for m in gem["models"] for v in gem["voices"]]
                for m, v in combos:
                    try:
                        pcm = cloud_speak(text, v, lang, m, gem.get("prompt"))
                        gem_pick[:] = [(m, v)]
                        used = f"{m} {v}"
                        break
                    except urllib.error.HTTPError as e:
                        log.append(f"line {i} {m} {v} HTTP {e.code}: {e.read().decode()[:300]}")
                if pcm is None:
                    ok = False
                    break
            else:
                try:
                    pcm = cloud_speak(text, cloud[lang])
                    used = cloud[lang]
                except urllib.error.HTTPError as e:
                    ok = False
                    log.append(f"line {i} HTTP {e.code}: {e.read().decode()[:600]}")
                    break
            log.append(f"line {i} ok cloud {used} {len(pcm)} bytes")
            with wave.open(f"{job}/voice_{i:02d}.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            continue
        if time.time() - START > 13 * 60:
            ok = False
            log.append(f"line {i}: out of time")
            break
        try:
            text = f'{spec.get("style", "")} {line}'.strip()
            pcm, model, voice = speak(MODELS, voices, text, log)
        except Exception as e:
            ok = False
            log.append(f"line {i} failed: {e}")
            break
        log.append(f"line {i} ok {model} {voice} {len(pcm)} bytes")
        print(log[-1], flush=True)
        with wave.open(f"{job}/voice_{i:02d}.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
        time.sleep(8)
    for t in spec.get("transcribe", []):
        log.append(f"heard {t}: {transcribe(t, log)}")
    with open(f"{job}/status.txt", "w", encoding="utf-8") as f:
        f.write(("OK\n" if ok else "FAILED\n") + "\n".join(log) + "\n")
    print("\n".join(log))
