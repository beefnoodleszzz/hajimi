# Native-English reference audition — Hi-Fi TTS / 2026-09-17

## Source and selection

- Dataset: [Hi-Fi Multi-Speaker English TTS / OpenSLR SLR109](https://www.openslr.org/109/)
- Exact mirror used for the small audition shard: [MikhailT/hifi-tts](https://huggingface.co/datasets/MikhailT/hifi-tts)
- Selected speaker: `92 / Cori Samuel`, female, `test.clean`
- Exact source clip: `audio/92_clean/10425/secretagent_06_conrad_0302.flac`
- Source duration: 9.94 s at 44.1 kHz mono; normalized locally to 9.94 s at 48 kHz mono
- Source text: `It is only when our appointed activities seem by a lucky accident to obey the particular earnestness of our temperament that we can taste the comfort of complete self-deception.`
- Reference QC: PASS; no clipping, no non-finite samples, no silence-only signal

The dataset paper reports that Hi-Fi TTS kept high-quality recordings with at least 13 kHz bandwidth, at least 32 dB SNR, verified text/audio alignment, and native English speakers. This makes it a materially better English pronunciation reference than the previous Chinese clips, but it does not guarantee a “御姐” timbre or a specific age.

## Generated candidates

All candidates use the same English science script, the same reference, neutral controllable cloning, CFG 2.0, and 30 inference steps.

| Candidate | Duration | Audio QC | Audition |
|---|---:|---|---|
| 01 | 55.20 s | PASS | [M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/hifitts_cori_audition_20260917_v01/run_0001/AUD_HIFITTS_CORI_92/candidate_01_audition.m4a>) · [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/hifitts_cori_audition_20260917_v01/run_0001/AUD_HIFITTS_CORI_92/candidate_01.wav>) |
| 02 | 52.80 s | PASS | [M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/hifitts_cori_audition_20260917_v01/run_0001/AUD_HIFITTS_CORI_92/candidate_02_audition.m4a>) · [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/hifitts_cori_audition_20260917_v01/run_0001/AUD_HIFITTS_CORI_92/candidate_02.wav>) |
| 03 | 50.08 s | PASS | [M4A](<../../../../../../AI/voxcpm2-local/outputs/raw/hifitts_cori_audition_20260917_v01/run_0001/AUD_HIFITTS_CORI_92/candidate_03_audition.m4a>) · [WAV](<../../../../../../AI/voxcpm2-local/outputs/raw/hifitts_cori_audition_20260917_v01/run_0001/AUD_HIFITTS_CORI_92/candidate_03.wav>) |

Manifest: `/Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/hifitts_cori_audition_20260917_v01/run_0001/manifest.json`

## License and use boundary

The dataset is marked CC BY 4.0, so attribution is required. That license covers the dataset material; it is not, by itself, a blanket guarantee that commercial voice impersonation or identity transfer is permitted in every jurisdiction. Keep this candidate private until the intended use and voice-rights review are complete. No YouTube, Bilibili, podcast, or other random third-party recording was downloaded.

## Other sources checked

- [VCTK / Edinburgh DataShare](https://datashare.ed.ac.uk/items/30e7453c-9ea8-48b4-8e18-f96d0dc62928): high-quality 48 kHz English multi-speaker recordings under CC BY 4.0; female speakers are mostly young, so it is better for accent comparison than mature-yujie casting.
- [LJ Speech](https://keithito.com/LJ-Speech-Dataset/): public-domain single-female English audiobook speech; easy to use but more read-aloud and only 1–10 s per clip.
- [Mozilla Common Voice terms](https://github.com/mozilla/legal-docs/blob/main/en/common_voice_terms.md): CC0 contributions, but the dataset asks users not to determine speaker identities; it is not a good choice for targeted identity/timbre cloning.

## Next action

Listen to candidates 01–03 and choose one. If none is sufficiently mature or yujie-like, the next responsible route is an authorized 8–15 s English sample from a consenting mature female speaker—not scraping a recognizable public creator.
