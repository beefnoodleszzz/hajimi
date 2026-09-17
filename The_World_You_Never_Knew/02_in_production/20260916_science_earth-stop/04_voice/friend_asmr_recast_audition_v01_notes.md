# Friend-supplied ASMR reference recast audition — 2026-09-17

## Result

This is a private A/B audition for the English science-podcast narrator. The source is a friend-supplied ASMR recording; it was split into two clean speech windows and recast with an explicit direction to remove whispering, close-mic mouth sounds, seductive sleep-aid pacing, and excessive breathiness.

| Take | Reference window | Reference QC | Generated duration | Generated audio QC | Audition |
|---|---:|---|---:|---|---|
| A | 0.00–8.55 s | PASS | 50.08 s | PASS | [M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_audition_20260917_v01/run_0001/AUD_FRIEND_ASMR_A/candidate_01_audition.m4a>) · [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_audition_20260917_v01/run_0001/AUD_FRIEND_ASMR_A/candidate_01.wav>) |
| B | 9.18–17.62 s | PASS | 49.44 s | PASS | [M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_audition_20260917_v01/run_0001/AUD_FRIEND_ASMR_B/candidate_01_audition.m4a>) · [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/friend_asmr_recast_audition_20260917_v01/run_0001/AUD_FRIEND_ASMR_B/candidate_01.wav>) |

## Source and preparation

- Original: [`A_Bath_And_A_Breed_Before_Bed_30s_正规对话段.m4a`](</Users/zhangxiaolong/Desktop/A_Bath_And_A_Breed_Before_Bed_30s_正规对话段.m4a>)
- The original 30-second M4A was not modified or uploaded.
- Extracted private references: [A WAV](external_reference_candidates/A_0.00-8.55s.wav) · [B WAV](external_reference_candidates/B_9.18-17.62s.wav)
- Both references were normalized to mono 48 kHz PCM for VoxCPM2. Reference QC passed with no clipping or non-finite samples.
- Local English ASR supplied working transcript text for conditioning, but the transcript is not speaker-verified. The transcript must be checked with the friend before any production use.

## Generation settings

- Backend: local Apple-Silicon VoxCPM2 BF16
- Inference: 30 steps, CFG 2.0, one candidate per reference
- Direction: natural adult English woman, mature low-mid register, calm confident podcast delivery; preserve identity cues while removing ASMR mannerisms
- Manifest: `/Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/friend_asmr_recast_audition_20260917_v01/run_0001/manifest.json`
- Audit: 2 files, 0 errors, 0 warnings

## Authorization boundary

At the time of this audition both temporary entries were marked pending. The user later confirmed complete authorization for the selected A voice; A is now the project default. B remains an inactive historical audition asset. Human listening is still required to judge whether residual ASMR breathiness or close-mic texture remains.

## Next decision

Listen to A and B with the same headphones and reply with `A`, `B`, or `都不要`. If one is selected and the friend confirms authorization plus the transcript, generate three final 30-step candidates; if the ASMR texture remains too strong, request a fresh 12–15 second neutral English recording from the friend.
