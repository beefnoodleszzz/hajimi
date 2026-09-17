# Friend-supplied reference A — production candidates — 2026-09-17

## Result

Reference A is locked for the next production audition. Three 30-step candidates were generated with the same English science-podcast direction and the same temporary voice entry `voice_friend_asmr_ref_a_20260917`.

| Candidate | Duration | Audio QC | Audition |
|---|---:|---|---|
| 01 | 46.40 s | WARN: `waveform_discontinuity` | [M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_production_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_01_audition.m4a>) · [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_production_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_01.wav>) |
| 02 | 47.52 s | WARN: `waveform_discontinuity` | [M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_production_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_02_audition.m4a>) · [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_production_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_02.wav>) |
| 03 | 51.04 s | PASS | [M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_production_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_03_audition.m4a>) · [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_production_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_03.wav>) |

All raw WAVs are 48 kHz mono PCM_24. Batch audit: 3 files, 0 errors, 0 warnings. The local transcript check remains `ERROR` because the installed SenseVoiceSmall backend is configured for Chinese; it is not an acoustic failure. Human listening is required for naturalness, pronunciation, residual ASMR texture, and final take selection.

## Generation settings

- Backend: local Apple-Silicon VoxCPM2 BF16
- Inference: 30 steps, CFG 2.0, custom policy with no early stop
- Direction: mature adult woman, low-to-mid register, calm authority, natural podcast delivery; remove whispering, mouth sounds, close-mic breathiness, seductive delivery, and sleep-aid pacing
- Manifest: `/Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/friend_asmr_recast_production_20260917_v01/run_0001/manifest.json`
- Audit report: `/Users/zhangxiaolong/AI/voxcpm2-local/outputs/qc/audits/933c5599ba0df7d3/3b7cf7594c684c089cc0a55748f4221a.json`

## Authorization boundary

The user confirmed on 2026-09-17 that the friend granted complete permission for voice cloning and intended project use, including publication and monetization. The active voice entry is recorded as `authorization_status: authorized` with `commercial_use: true`.

## Next decision

Listen to candidates 01–03 and reply with the candidate number. Candidate 03 is the cleanest by engineering QC, but that does not determine the perceptual winner.

## Optimization pass — candidate 03 tail repair

Human listening found a current-like artifact near the end of candidate 03. Inspection confirmed a short raw-generation transient at 47.816–47.821 s; it was present in the source WAV and survived M4A decoding, so it was not an encoder issue. A fresh 30-step tail render was made from the same reference A. Tail candidate 01 had the cleanest jump profile and was joined at 47.10 s with a 40 ms crossfade.

- [Optimized audition M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_optimized_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_03_optimized_audition.m4a>)
- [Optimized master WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_optimized_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_03_optimized.wav>)
- Optimized audit: 1 file, 0 errors, 0 warnings
- Decoded M4A check: the former 47.7–47.9 s window has zero jumps over 0.25; the original candidate 03 remains preserved.

This is still pending final human listening and friend authorization; the optimized file is not yet the canonical production voice.

## Optimization pass v02 — earlier tail replacement

Follow-up listening reported that the noise was already increasing from about 40 s. The v01 repair only replaced the final question, so the main candidate 03 audio from 30–46.5 s remained unchanged. v02 therefore keeps the original candidate 03 only through 35.70 s, then joins a fresh 30-step render of the complete remaining passage using tail candidate 02.

- [Optimized v02 audition M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_optimized_v02_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_03_optimized_v02_audition.m4a>)
- [Optimized v02 master WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_optimized_v02_20260917_v01/run_0001/PROD_FRIEND_ASMR_A/candidate_03_optimized_v02.wav>)
- Tail source: `friend_asmr_tail_repair_20260917_v02`, candidate 02
- Join: 35.70 s with 40 ms crossfade; final duration 50.22 s
- Optimized v02 audit: 1 file, 0 errors, 0 warnings

The v01 optimized file remains preserved as an intermediate; v02 is the current listening lead.

## Full redo v01 — whole narration regenerated

The v01/v02 splice repairs above are historical intermediates and are not the current delivery. Because listening found a front/back timbre change, the narration was regenerated from scratch in two sentence-boundary segments using the same reference A, the same model, the same seed, and the same direction. No audio from the old candidate 03 was reused.

Only WAV is retained for this redo: 48 kHz mono PCM_24, dry voice, no M4A generated. The two fresh segments were joined with 0.35 s of digital silence; no crossfade, pitch shift, denoise, compression, or normalization was applied.

| Candidate | Duration | Segment QC | Full-file audit | Delivery |
|---|---:|---|---|---|
| 01 | 50.11 s | main WARN / tail PASS | 0 errors, 0 warnings | [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_full_redo_20260917_v01/run_0001/FULL_CANDIDATES/full_candidate_01.wav>) |
| 02 | 54.91 s | main PASS / tail PASS | 0 errors, 0 warnings | [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_full_redo_20260917_v01/run_0001/FULL_CANDIDATES/full_candidate_02.wav>) |
| 03 | 50.91 s | main WARN / tail PASS | 0 errors, 0 warnings | [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_full_redo_20260917_v01/run_0001/FULL_CANDIDATES/full_candidate_03.wav>) |

Candidate 02 is the objective-QC recommendation because both newly generated segments passed without waveform-discontinuity warnings. This does not replace human listening for timbre continuity, naturalness, pronunciation, or the residual electrical-like noise reported in the earlier long render. The old production, v01, and v02 files remain preserved as historical references and were not overwritten.

- Batch manifest: `/Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/friend_asmr_full_redo_20260917_v01/run_0001/manifest.json`
- Full-file audit: `/Users/zhangxiaolong/AI/voxcpm2-local/outputs/qc/audits/e8ba8d56f1ae8e6a/2a84da0f39f14a958b4ee9fc49a49c01.json`
- Authorization record: the user confirmed complete friend permission; the active voice entry is `authorization_status: authorized` with `commercial_use: true`.

## Project decision — candidate 02 locked as default

On 2026-09-17 the user confirmed full-redo candidate 02 as the project’s main voice. All subsequent primary narration for this project should default to this same voice library entry and delivery direction unless the user explicitly changes it.

- Active voice: `voice_friend_asmr_ref_a_20260917`
- Active master: `/Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/friend_asmr_full_redo_20260917_v01/run_0001/FULL_CANDIDATES/full_candidate_02.wav`
- Format: WAV only, 48 kHz mono PCM_24
- Candidate 01 and 03 remain comparison backups; old #4, the original long candidate 03, and v01/v02 splice repairs are not active.
- The user’s complete authorization confirmation covers this project’s production, publication, and monetization use.
