# Pofu Kids: otomatik Instagram paylaşımı (runbook)

Instagram @pofukids, ENGLISH captions only, no em dashes, max 5 hashtags, single photos (never carousels). Videos only from English-language recordings. Replies to Cem in Turkish.

- Buffer org `6ae39aa9d09e51b79d4807b8` (Europe/Istanbul, free plan: max 10 scheduled posts per channel). Pofu Kids Instagram channel `6af3aa3762b70b94b0eb79af` (business). Do NOT touch the Engrow channels.
- Daily slots: 11:00 photo, 14:00 reel, 17:00 reel (Cem, 11.11.2026) (Istanbul, +03:00).
- **Never post a silent photo (Cem, 11.11.2026: "Basitçe seslendirelim demiştim. Boş fotoğraf paylaşmışsın.").** The 11:00 "photo" slot goes out as a short voiced reel: `python3 tools/photo_reel.py media/single_<x>.jpg <voice.wav> <seed> media/photo_<x>.mp4` (photo centered on its blurred copy, slow zoom, one Nika parent-style line ending with "Pofu Kids, free on the App Store.", light music from `tools/light_music.py`, different per seed). In plan.json these entries are `kind: reel`, `file: photo_<x>.mp4`, `photo_source: single_<x>.jpg`.
- Nika note: the single-request TTS sometimes reads the style prompt aloud first (photos1: first ~21 s). Find each line's end with MFCC DTW on the closing phrase and check speech rate (12-16 chars/s) before cutting.
- `plan.json` = the queue: date, time, file, kind, public url (`https://raw.githubusercontent.com/caltun90/pofukids-social/main/media/<file>`), text (final caption), buffer_id once scheduled.
- Photo post: `create_post` with image asset (+ altText), `metadata.instagram {type:"post", shouldShareToFeed:true}`. Reel: video asset `{video:{url, metadata:{thumbnailOffset: 500}}}`, `{type:"reel", shouldShareToFeed:true}`. `schedulingType:"automatic"`, `mode:"customScheduled"`, `dueAt` with +03:00.
- Keep about 3 days scheduled (9 posts, under the 10 limit). Before creating, `list_posts` (scheduled) for the channel and skip anything already scheduled with the same media URL.

## Making new reels (when the plan runs out)
- Source videos: `/home/claude/vid` (render.py, specs*.json; English recordings n1-n3, m1-m8). Narration: Gemini TTS voice "Nika" via GitHub Actions on branch `tts-drop` (secret GEMINI_API_KEY, 10 requests/day): `python3 tools/nika.py speak <job> <lines.json> --style parent`.
- Splitting: each line ends with "Pofu Kids, free on the App Store." Find that phrase with MFCC DTW (librosa) against a known occurrence and cut after each match (the Gemini per-run transcription job is too slow, it hit the 20 min Actions timeout on 67 runs).
- Mix: `python3 tools/narrate.py <video> <voice.wav> <out.mp4> --start 0.6` (ducks game audio, -14 LUFS).
- **Cover = frame 0, never black (Cem, 13.11.2026: the profile grid showed black squares).** The old reels started with an 8-frame fade-in from black and Instagram took frame 0 as the cover. Every reel must pass `python3 tools/fix_cover.py check <mp4>` before it goes into plan.json; if not, `python3 tools/fix_cover.py fix <in> <out_v2.mp4>` (clones the first bright frame over the fade, same duration and audio sync). Never add a fade-in from black in a renderer. When scheduling, also set `thumbnailOffset: 500` on the video asset as a second guard. A fixed file always gets a NEW name (`_v2`): Buffer caches by URL.
- Commit the mp4 to `media/`, check the raw URL returns 200, add entries to plan.json.
