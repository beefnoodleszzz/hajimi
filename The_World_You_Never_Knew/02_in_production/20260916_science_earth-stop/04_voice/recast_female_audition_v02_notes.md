# Recast female voice audition — 2026-09-17

## Result

This is a private A/B audition for the English science-podcast narrator. Both takes use the same script, neutral controllable cloning, 30 inference steps, CFG 2.0, and a human-directed mature-female performance brief.

| Take | Local voice | Direction | Audio QC | Audition file |
|---|---|---|---|---|
| A | `voice_nanzhu_core_01` | Mature yujie / high-position female; grounded, slightly husky, quiet authority | PASS | [A — M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/recast_female_audition_20260917_v02/run_0001/AUD_RECAST_NANZHU_YUJIE/candidate_01_audition.m4a>) · [A — WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/recast_female_audition_20260917_v02/run_0001/AUD_RECAST_NANZHU_YUJIE/candidate_01.wav>) |
| B | `voice_queen_female_01` | Direct mature queen / polished urban confidence; low-mid register | WARN: near full scale, no clipping | [B — M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/recast_female_audition_20260917_v02/run_0001/AUD_RECAST_QUEEN_FEMALE/candidate_01_audition.m4a>) · [B — WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/recast_female_audition_20260917_v02/run_0001/AUD_RECAST_QUEEN_FEMALE/candidate_01.wav>) |

The M4A copies are attenuated by 3 dB for comfortable listening. The canonical raw WAVs are preserved unchanged.

## Important limitation

The available reference clips are Chinese, while this demo is English. The model can transfer timbre and performance direction, but a genuinely native English accent cannot be guaranteed without an authorized English reference from the same speaker. The local `user_supplied` entries remain marked “authorization pending”; do not publish or monetize either take until that authorization is confirmed.

## Next decision

Listen to A and B with the same headphones and choose one by letter. After selection, generate the production voice with three 30-step candidates, then replace the old #4 dry VO in the edit.
