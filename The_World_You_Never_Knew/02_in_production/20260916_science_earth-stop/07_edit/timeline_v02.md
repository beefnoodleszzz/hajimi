# Timeline V2 — captioned review draft

V2 is the V1 picture lock plus four key information captions. It deliberately does not use word-by-word subtitles; the full narration remains available as audio and the captions emphasize only the claims called out in the edit plan.

Voice status: the previous #4 voice is superseded by the 2026-09-17 recast audition; the picture and caption timing remain a draft until the replacement voice is selected.

## Added overlays

| Text | Time | Position | Purpose |
|---|---:|---|---|
| `EARTH STOPS` | 00:00.000–00:02.500 | upper safe area | Match the first premise |
| `YOU KEEP MOVING` | 00:02.500–00:06.500 | center | State the relative-motion contrast |
| `GRAVITY STILL WORKS` | 00:24.500–00:29.000 | upper safe area | Correct the space misconception |
| `WHAT MOVES FIRST?` | 00:41.500–00:46.240 | center | Close on the comment prompt |

## Status

- Rendered: `draft_v02/short_review_v02.mp4`
- Media probe: 1080×1920, 30 fps, 46.233333 s video, 48 kHz mono AAC, no encode errors.
- Audio probe: mean `-18.4 dB`, max `-3.1 dB`; no limiting or loudness mastering applied yet.
- Visual QC: exact-time contact sheet checked; the only blackdetect ranges are the intentional dark information-graphic shots 05 and 09.
- Audio remains dry VO only; BGM and SFX are intentionally deferred until the user listens to the selected voice take.
- Text is rasterized with ImageMagick and composited with FFmpeg `overlay`; this avoids the host FFmpeg build's missing `drawtext` filter.
- The full narration is not timecoded by ASR yet; captions are key-claim cards and are not presented as a transcript.
