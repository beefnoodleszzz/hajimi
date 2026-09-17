# Story Draft V02 — production handoff

## Status

`earth_stop_story_v02_review.mp4` 已完成可审片版本。这个版本的重点是修复内容设计：把原来的知识点串烧改成一条可追踪的事件链——同一条赤道城市道路发生“地面停顿”，人和小票继续向东，空气/云/海保有动量，地面重启后发生错位，最后回到同一条道路。

当前仍是用户审片版本，未上传发布。

## Fixed voice

- Voice identity: `voice_friend_asmr_ref_a_20260917`
- Active take: `04_voice/story_v02/voiceover_story_v02.wav`
- Format: WAV, 48 kHz, mono, PCM_24
- Duration: 39.520167 s
- The Flow clips' generated audio was discarded; only the fixed narrator is used in the final mux.

## Visual pipeline

- Keyframes: ImageGen assets in `05_visuals/generated_v03_story/`
- Motion generation: Google Flow project `Earth Stop — Story Rebuild V02`
- Flow project: <https://flow.google.com/project/fdb4450e-fa81-4389-bb56-69070b2df218>
- Downloaded motion segments: `flow_segments/`
- Deterministic information graphics: `graphics/`
- Burned-in overlays: ImageMagick PNG cards composited with FFmpeg `overlay`; this host FFmpeg does not include `drawtext`.

## Timeline contract

| Time | Visual | Narrative function |
|---:|---|---|
| 00:00–07.50 | street hook | Establish the stop and begin the eastward contradiction |
| 07.50–13.42 | inertia continuation | Person and receipt keep moving while the road stays fixed |
| 13.42–21.80 | aerial plate + 465 m graphic | Make the distance legible |
| 21.80–25.36 | gravity/sideways graphic | Correct the “floating upward” misconception |
| 25.36–27.98 | city/coast/air layer | Scale the event from body to atmosphere and ocean |
| 27.98–35.98 | three-layer restart mismatch | Deliver the consequence |
| 35.98–39.52 | callback street | Return to the opening place and ask the final question |

## QC completed

- FFmpeg decode check: pass.
- Media probe: 1080×1920, 24 fps, H.264, AAC mono 48 kHz.
- Final duration: about 39.6 s including normal AAC/container padding.
- Loudness probe: mean `-15.8 dB`, max `-1.5 dB`.
- Whisper ASR check: all 103 narration words recovered in order; final question ends at approximately 39.36 s.
- Visual contact sheet checked at four-second intervals; no unexpected full-black frames or broken overlays.

## Deliverable

`earth_stop_story_v02_review.mp4`

