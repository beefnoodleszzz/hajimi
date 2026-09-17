# 女性播客克隆声线英文旁白试听

同一版 130 词英文旁白，均使用本地已登记的克隆参考声，VoxCPM2 BF16，`neutral + controllable clone`，10-step fast audition。M4A 仅为方便试听的压缩副本；原始 48 kHz、单声道、PCM-24 WAV 同目录保留。

| 编号 | 声音条目 | 方向 | 试听 |
|---|---|---|---|
| 主声 | `voice_podcast_female_01` | 知性优雅女声，播客 | [M4A](</Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/voice_audition_20260916_v03/run_0001/AUD_PODCAST_FEMALE/candidate_01.m4a>) · [WAV](</Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/voice_audition_20260916_v03/run_0001/AUD_PODCAST_FEMALE/candidate_01.wav>) |
| A | `female_mature_intellectual_01` | 知性沉稳成熟女声，科学/知识表达 | [M4A](</Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/female_voice_audition_20260916_v02/run_0001/AUD_FEMALE_INTELLECTUAL/candidate_01.m4a>) · [WAV](</Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/female_voice_audition_20260916_v02/run_0001/AUD_FEMALE_INTELLECTUAL/candidate_01.wav>) |
| B | `female_young_gentle_01` | 温和治愈年轻女声，轻松播客 | [M4A](</Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/female_voice_audition_20260916_v02/run_0001/AUD_FEMALE_GENTLE/candidate_01.m4a>) · [WAV](</Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/female_voice_audition_20260916_v02/run_0001/AUD_FEMALE_GENTLE/candidate_01.wav>) |

## 验证

- 女性新候选音频审计：2/2 通过；主声线上一轮审计通过。
- 所有原始 WAV：48 kHz、mono、PCM-24。
- 英文 SenseVoice ASR 未配置；元数据中的转写验收为 `ERROR`，不作为听感或音频质量结论。
- A、B 两条参考分别约 4.64 秒和 4.32 秒，目录标记为短参考 warning；主声线参考约 7.8 秒且参考 QC 通过。
- 上一轮淘汰的男声 Demo 和有波形警告的清冷女声 Demo 已移入系统废纸篓，未删除原始克隆声库。
