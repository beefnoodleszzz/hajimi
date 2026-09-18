# Hajimi V2 — 世界一流 AI 视觉叙事工作室重构总规范

> 目标：彻底删除当前 `hajimi` 中以“AI 图片/视频生成 + FFmpeg 拼接”为核心的旧生产体系，从零重建为一套 **AI 驱动的小型动画 / 视觉叙事工作室**。
> 适用对象：Codex / Claude Code / 其他本地 AI Agent。
> 目标频道：`The World You Never Knew`，英文知识娱乐 Shorts + 后续长视频。
> 核心成功标准：**Stop-scroll、强叙事、强镜头、强声音、视觉可解释、可持续复用、快速 QC、可自动发布。**

---

# 0. 一句话架构

新的 Hajimi 不是“视频生成脚本仓库”，而是：

```text
Research
  ↓
Creative Direction
  ↓
Reference Deconstruction
  ↓
Script / Beat Design
  ↓
Storyboard
  ↓
Animatic Gate
  ↓
Shot Production
  ├── Blender / deterministic 3D
  ├── AI Video
  ├── AI Image
  ├── Motion Graphics
  └── Licensed / public-domain footage
  ↓
Fast Shot QC
  ↓
Resolve Picture Edit
  ↓
Fusion Compositing
  ↓
Fairlight Sound Design
  ↓
Master QC
  ↓
YouTube Studio publish via ego-browser
  ↓
Analytics Learning Loop
```

核心原则：

> **先导演，再生产；先 Animatic，再花生成成本；先做成片质量，再做自动化。**

---

# 1. 必须删除什么

当前仓库的内容生产结构全部视为 V1 历史，不继续修补。

## 1.1 删除范围

删除工作树中的：

```text
The_World_You_Never_Knew/
The_World_You_Never_Knew_视频生产策略与SOP_2026-09-16.md
海外AI内容矩阵赚钱路线_2026-09-16.md
当前所有 story_draft / flow_draft / generated_v01~v04
当前所有旧脚本、旧镜头表、旧 FFmpeg 成片脚本
当前占位式 CLAUDE.md
当前只包含 beads 的 agents skill 体系
当前所有与旧生产管线强绑定的临时文件
```

## 1.2 不做“旧结构兼容层”

禁止：

- 在旧目录上继续追加 V05/V06。
- 在旧 `story_draft_v03` 上继续补音效。
- 继续复用 V02/V03/V04 跨版本素材。
- 保留“为了以后也许有用”的旧 Prompt。
- 新旧 pipeline 并存。
- 给旧 shell 脚本再包一层 Python。

## 1.3 删除前只做一个动作

仓库本身已有 Git 历史，因此不需要把旧文件留在工作树。

重构前创建一个 Git tag 即可：

```bash
git tag hajimi-v1-before-rebuild
```

此 tag 只作为历史回滚点。

---

# 2. 新系统目标

## 2.1 质量目标

每条 Shorts 必须同时满足：

1. **0–1.5 秒内发生异常或结果。**
2. 前 3 秒无需声音也能大致理解冲突。
3. 每 1–3 秒存在一次有意义的视觉变化。
4. 每 8–12 秒至少一个视觉或声音峰值。
5. 不出现 5 秒以上“只有一张图慢推拉”的段落。
6. 不出现“旁白解释完了，画面只是陪衬”的镜头。
7. 每一条视频至少存在 1 个可被截图传播的 Hero Shot。
8. 音频必须是多层声音设计，而非裸旁白。
9. 镜头设计优先于生成模型。
10. 科学类内容中，关键运动和尺度尽量使用确定性动画，而不是让生成视频模型猜物理。

## 2.2 工程目标

系统必须具备：

- episode manifest 单一事实源。
- 所有资产有状态、有版本、有 hash。
- 所有 QC 结果可缓存。
- 所有生成结果可追踪到 prompt / model / seed / source。
- 每个镜头都有 shot ID。
- 任何镜头改动只触发自身和下游步骤，不全量重跑。
- AI Agent 不得把大量图片/视频逐个塞进上下文。
- QC 必须支持批量、低分辨率、硬件解码、并行。
- Resolve 负责编辑和声音；FFmpeg 只做机械媒体处理。
- ego-browser 负责最终网页发布流程。

---

# 3. 推荐技术栈

## 3.1 总体技术栈

| 层 | 技术 | 用途 |
|---|---|---|
| Orchestration | Python 3.12+ | pipeline、QC、manifest、任务编排 |
| Python env | `uv` | 极速依赖管理 |
| Local DB | SQLite + SQLModel/SQLAlchemy | episode、shot、asset、QC、publish 状态 |
| Analytics | DuckDB + Parquet | 历史数据分析 |
| Media core | FFmpeg / ffprobe | 转码、代理、抽帧、音频分析、master |
| Scene detection | PySceneDetect | 快速切镜检测 |
| Image/video | OpenCV | 轻量视觉指标、光流、模糊、边缘检测 |
| Similarity | pHash / dHash | 重复帧、近重复镜头检测 |
| Optional perceptual | LPIPS / CLIP embedding | 疑似视觉异常二次检测 |
| ASR | faster-whisper | 快速旁白转写和字幕核对 |
| Editor | DaVinci Resolve 21.1 | 主剪辑 |
| Compositing | Resolve Fusion | 标注、动态图形、合成 |
| Audio | Resolve Fairlight | BGM、SFX、ambience、VO、响度 |
| 3D | Blender | 科学动画、确定性运动、物理模拟、镜头 |
| Browser | ego lite + `ego-browser` skill | YouTube Studio 自动发布 |
| Issue tracking | Beads (`bd`) | Agent 任务跟踪 |
| Shell | Bash/Zsh | 薄启动脚本，不承载业务逻辑 |
| Node | Node 22+ | ego-browser 运行时 / 少量浏览器工具 |
| Package manager | pnpm | Node 工具 |

---

# 4. 为什么必须引入 Blender

AI 视频只应该承担：

- impossible reconstruction；
- cinematic hero shot；
- atmospheric insert；
- 复杂自然质感；
- 很难精确建模但允许一定生成自由度的镜头。

以下内容优先 Blender / Fusion：

- 速度 / 距离 / 轨迹。
- 行星运动。
- 切面结构。
- 城市尺度。
- 相对运动。
- 光线方向。
- 相机精确移动。
- 物理时间线。
- layer mismatch。
- 拆解、爆炸、粒子、流体等需要确定性的机制展示。

原因：

> 知识类顶级短片最怕“画面漂亮但物理逻辑不清晰”。

Blender 的作用不是替代 AI，而是成为科学类内容的 **deterministic backbone**。

---

# 5. 新仓库目录结构

```text
hajimi/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── uv.lock
├── package.json
├── pnpm-lock.yaml
├── .env.example
├── .gitignore
├── .codex/
│   ├── config.toml
│   └── hooks.json
├── .agents/
│   └── skills/
│       ├── creative-director/
│       │   └── SKILL.md
│       ├── reference-deconstructor/
│       │   └── SKILL.md
│       ├── research-editor/
│       │   └── SKILL.md
│       ├── short-script-editor/
│       │   └── SKILL.md
│       ├── storyboard-director/
│       │   └── SKILL.md
│       ├── animatic-director/
│       │   └── SKILL.md
│       ├── shot-designer/
│       │   └── SKILL.md
│       ├── blender-shot/
│       │   └── SKILL.md
│       ├── ai-visual-producer/
│       │   └── SKILL.md
│       ├── resolve-editor/
│       │   └── SKILL.md
│       ├── sound-designer/
│       │   └── SKILL.md
│       ├── fast-media-qc/
│       │   └── SKILL.md
│       ├── final-master-qc/
│       │   └── SKILL.md
│       ├── youtube-publisher/
│       │   └── SKILL.md
│       ├── analytics-reviewer/
│       │   └── SKILL.md
│       └── beads/
│           └── SKILL.md
├── config/
│   ├── studio.yaml
│   ├── qc.yaml
│   ├── render.yaml
│   ├── youtube.yaml
│   └── models.yaml
├── studio/
│   ├── cli.py
│   ├── db/
│   ├── manifests/
│   ├── pipeline/
│   ├── media/
│   ├── qc/
│   ├── resolve/
│   ├── blender/
│   ├── publish/
│   └── analytics/
├── brand/
│   ├── visual_language.md
│   ├── sound_language.md
│   ├── typography.md
│   └── narrator.md
├── references/
│   ├── channels/
│   ├── videos/
│   └── shot_patterns/
├── assets/
│   ├── music/
│   ├── sfx/
│   ├── ambience/
│   ├── blender/
│   ├── fonts/
│   └── reusable/
├── episodes/
│   └── EP001_earth-stop/
│       ├── episode.yaml
│       ├── research/
│       ├── script/
│       ├── storyboard/
│       ├── animatic/
│       ├── shots/
│       │   ├── S001/
│       │   ├── S002/
│       │   └── ...
│       ├── edit/
│       ├── audio/
│       ├── qc/
│       ├── master/
│       └── publish/
├── tools/
│   ├── bootstrap.sh
│   ├── proxy.py
│   ├── contact_sheet.py
│   ├── qc.py
│   └── publish.py
└── tests/
```

---

# 6. Episode Manifest：全系统唯一事实源

每集只允许一个：

```text
episodes/<episode_id>/episode.yaml
```

示例：

```yaml
episode_id: EP001_earth-stop
status: animatic
channel: The World You Never Knew
format: youtube_short
language: en-US
aspect_ratio: 9:16
master:
  width: 1080
  height: 1920
  fps: 30
  sample_rate: 48000

creative:
  promise: "If Earth stopped for one second, the ground stops. You don't."
  emotion:
    - danger
    - scale
    - awe
  hero_shot: S005
  target_duration_sec: 36

script:
  version: 3
  path: script/script_v03.md
  locked: true

audio:
  narrator: science_female_main
  target_lufs: -14
  true_peak_max_db: -1.0

shots:
  - id: S001
    role: hook
    duration_target: 1.2
    method: blender
    status: approved
  - id: S002
    role: human_inertia
    duration_target: 2.8
    method: ai_video
    status: qc_pending
  - id: S003
    role: speed_scale
    method: fusion
    status: blocked

publish:
  title: null
  description: null
  ai_disclosure: true
  visibility: private
```

任何 Agent 都不得另建“临时真相”。

---

# 7. 完整生产流程

---

## Stage 1 — Topic Discovery

输出：

```text
topic_brief.md
```

要求：

- 一句话问题。
- 一句话反直觉点。
- 一句话最终 payoff。
- 3 个可视化峰值。
- 事实来源。
- 是否适合 Shorts。
- 是否值得发展长视频。

禁止在这一步写完整脚本。

---

## Stage 2 — Reference Deconstruction

每个重要主题至少拆 5–10 条高表现参考内容。

不是“总结别人讲了什么”，而是拆：

```text
0.0–1.0  hook visual
1.0–2.0  motion
2.0–4.0  information
...
```

记录：

- 第一帧。
- 1 秒动作。
- 平均镜头时长。
- camera movement。
- overlay 类型。
- 音乐进入点。
- SFX 类型。
- narrative escalation。
- hero shot。
- loop strategy。
- comment hook。
- 视觉峰值间隔。

输出结构化 JSON：

```json
{
  "video_id": "...",
  "hook": {
    "type": "immediate_consequence",
    "visual": "person displaced before explanation",
    "time_to_anomaly": 0.4
  },
  "avg_shot_duration": 1.9,
  "visual_peaks": [0.4, 8.2, 18.0, 29.5],
  "audio": {
    "music": true,
    "impact_sfx": 6,
    "ambience": true
  }
}
```

---

## Stage 3 — Creative Direction

Creative Director 输出：

```text
creative_brief.md
```

必须明确：

- 视频的 emotional curve。
- viewer expectation。
- visual thesis。
- 一帧记忆点。
- 三个视觉峰值。
- 哪一部分必须 deterministic。
- 哪一部分允许 AI 自由发挥。
- 什么东西绝对不能做成“静态图推拉”。

---

# 8. Script：从科普稿变成短片剧本

脚本不是段落，而是 beat。

格式：

```text
BEAT 01
time: 0.0–1.2
voice: "The ground stops. You don't."
visual: human still moving across frozen street
sound: hard vacuum-drop + low hit
purpose: hook

BEAT 02
time: 1.2–4.0
voice: "At the equator, you're already moving east at 465 meters per second."
visual: human + object vector
sound: rising air rush
purpose: scale
```

硬约束：

- 0–1.5 秒出现事件。
- 第一秒禁止介绍背景。
- 一个句子只承担一个 punch。
- 口播数字只说一次。
- 同一信息不做“数字 + 换算 + 重新解释”三连。
- 结尾不强行问一个物理上没有真实选项的问题。
- 尽量使用 loop ending。

---

# 9. Storyboard

每个 beat 至少有：

```yaml
shot_id:
composition:
lens:
camera_height:
camera_motion:
subject_motion:
screen_direction:
visual_information:
transition_in:
transition_out:
sound_event:
expected_duration:
production_method:
risk:
```

每个镜头必须回答：

> 这个镜头如果删掉，信息、情绪或节奏损失是什么？

回答“不明显”的镜头直接删除。

---

# 10. Animatic Gate：整个新系统最重要的质量门

在正式生产高成本镜头前：

1. temp VO。
2. storyboard still。
3. 简单 camera move。
4. temp music。
5. temp SFX。
6. rough typography。

快速剪成 25–45 秒。

### 必须通过以下检查才进入 Production

- 静音看一遍：前 3 秒能理解发生了什么。
- 只听声音：有节奏变化。
- 1x 看：不拖。
- 1.5x 看：信息仍可理解。
- 每 3 秒至少有新视觉信息。
- 没有连续 5 秒“一个镜头不变化”。
- Hero Shot 已经能在 storyboard 阶段成立。
- 在没有“AI 高清质感”的情况下就已经有吸引力。

如果 animatic 不成立：

> 禁止继续生成高成本视频。

---

# 11. Shot Production 决策树

```text
需要精确物理 / 精确相机 / 精确尺度？
    YES → Blender / Fusion

需要真实自然素材？
    YES → licensed/public-domain footage 优先

需要极强 impossible visual？
    YES → AI video

需要 cinematic establishing / concept plate？
    YES → AI image + controlled compositing

需要文字、数字、箭头、图解？
    YES → Fusion / vector graphics
```

禁止：

> 所有镜头都扔给 ImageGen/Flow。

---

# 12. Blender Production Standard

每一个 Blender 镜头必须可脚本化重现。

目录：

```text
shots/S005/
├── shot.yaml
├── scene.blend
├── build_scene.py
├── preview/
├── render/
└── qc/
```

`shot.yaml`：

```yaml
id: S005
renderer: eevee
camera:
  lens_mm: 35
  movement: dolly_back
simulation:
  type: rigid_body
frames:
  start: 1
  end: 72
output:
  fps: 30
```

原则：

- Shorts 优先 Eevee / viewport-friendly。
- 不为了“电影感”滥用 Cycles。
- 所有科学展示先保证 readable，再保证 cinematic。
- 先 25% preview，再 full render。

---

# 13. AI Visual Production

AI 视频输出不允许直接进剪辑。

每个生成镜头必须经过：

```text
Generation
↓
Fast QC
↓
Continuity QC
↓
Director QC
↓
Approved
```

AI 镜头必须记录：

```json
{
  "model": "...",
  "prompt": "...",
  "reference": "...",
  "seed": "...",
  "duration": 6,
  "source_hash": "...",
  "generation_date": "..."
}
```

---

# 14. DaVinci Resolve 21.1 是主后期，而不是 FFmpeg

## Edit Page

负责：

- story rhythm。
- trimming。
- J/L cut。
- pacing。
- shot order。
- speed ramp。
- music cut。
- beat alignment。

## Fusion

负责：

- arrows。
- vector lines。
- distance annotation。
- title punches。
- compositing。
- tracked graphics。
- depth separation。
- motion typography。
- controlled camera fake moves。

## Fairlight

负责：

```text
VO
↓
compression / EQ / de-ess
+
music
+
ambience
+
impact SFX
+
movement SFX
+
transition SFX
+
sub bass / tonal design
↓
master bus
```

---

# 15. Sound Design 是一等公民

每条 Shorts 至少包含：

```text
VO
Music
Ambience
3–8 个 narrative SFX
```

推荐声音类型：

- impact。
- whoosh。
- air rush。
- low boom。
- sub drop。
- texture riser。
- object movement。
- environment movement。
- silence gap。

重要原则：

> “突然静音”本身也是一种 SFX。

禁止再出现：

```text
旁白 WAV
→ denoise
→ +5 dB
→ AAC
→ final
```

---

# 16. 字幕与 Story Typography 分离

## Accessibility Subtitle

特点：

- 稳定。
- 2 行以内。
- 中下安全区。
- 不靠右。
- 不挡 Shorts UI。
- 不逐词乱跳。

## Story Typography

是镜头设计的一部分，例如：

```text
1,040 MPH
THE GROUND STOPS
YOU DON'T
465 METERS
SIDEWAYS
```

只有关键 punch 才出现。

---

# 17. 全新 Fast QC 架构

这是 V2 的核心工程要求。

## 17.1 旧方法为什么慢

禁止以下工作方式：

```text
Agent 打开图片 1
→ 看
→ 描述
Agent 打开图片 2
→ 看
→ 描述
...
Agent 打开 8 秒视频
→ 从头看
→ 再看第二个视频
```

问题：

- 图片 token 很高。
- 视频连续帧极其浪费。
- Agent context 快速膨胀。
- 同一个资产重复 QC。
- 大量正常帧根本没有检查价值。

---

# 18. Fast QC：五层漏斗

```text
Tier 0  deterministic metadata
↓
Tier 1  proxy + scene sampling
↓
Tier 2  cheap CV metrics
↓
Tier 3  batch visual/VLM QC
↓
Tier 4  human/director review
```

绝不反过来。

---

# 19. Tier 0：1–3 秒机械 QC

所有素材先跑：

```bash
ffprobe
ffmpeg decode check
blackdetect
freezedetect
silencedetect
ebur128
astats
```

检查：

- 能否完整 decode。
- 分辨率。
- FPS。
- duration。
- SAR/DAR。
- audio sample rate。
- 黑帧。
- 冻结。
- 空音频。
- clipping。
- 音量异常。
- 文件损坏。

任何 Tier 0 fail：

> 不进入 AI 视觉 QC。

---

# 20. Tier 1：只处理 Proxy

对 1080p/4K 素材绝不直接做第一轮视觉分析。

统一生成：

```text
540p
H.264
2–6 Mbps
无损时间码
```

macOS 优先尝试 FFmpeg VideoToolbox：

```bash
ffmpeg -hwaccel videotoolbox ...
```

如果硬件路径不稳定再回 CPU。

所有 scene detection / contact sheet / CV 指标默认跑 proxy。

---

# 21. Tier 1.5：Scene Detection

使用 PySceneDetect：

- `AdaptiveDetector`：主检测。
- `ContentDetector`：稳定剪辑。
- `ThresholdDetector`：fade。

官方文档表明 AdaptiveDetector 使用邻近帧 rolling average，相比固定阈值更适合存在快速运动的内容。

输出：

```json
[
  {
    "shot": "S001",
    "start": 0.0,
    "end": 1.22
  }
]
```

---

# 22. 每个 Shot 只取 3 帧

默认：

```text
10%
50%
90%
```

如 shot < 1.2 秒：

```text
25%
75%
```

只有发生以下情况才额外采样：

- 高运动。
- 可疑 morph。
- face/hand 风险。
- discontinuity。
- 模糊。
- freeze。
- artifact detector 告警。

这样 40 秒、约 20 个镜头：

```text
~60 帧
```

而不是上千帧。

---

# 23. Contact Sheet 优先

每 6–12 个镜头生成一张 contact sheet：

```text
S001_mid
S002_mid
S003_mid
...
```

Agent 首轮只看 contact sheet。

目的：

- style drift。
- brightness jump。
- color mismatch。
- composition repetition。
- continuity break。
- subject identity shift。

只有可疑镜头才打开原始关键帧。

---

# 24. Tier 2：Cheap Computer Vision

在 VLM 之前跑：

## pHash / dHash

用于：

- 重复帧。
- 近重复镜头。
- AI 视频假运动。
- 不必要重复画面。

## Laplacian variance

用于：

- 模糊异常。

## Optical flow

只在必要镜头低分辨率跑。

用于：

- 应该运动却几乎不动。
- 整个画面只有 camera zoom。
- motion direction 错误。

## Histogram / luminance

用于：

- 突然曝光跳变。
- shot continuity。

## Edge density

用于：

- 严重模糊 / texture collapse。

这些都是毫秒级到低秒级操作。

---

# 25. Tier 3：VLM 只看异常和代表帧

VLM 不看所有帧。

输入：

```text
contact_sheet
+
shot intent
+
only suspicious frames
```

每镜头输出结构化 JSON：

```json
{
  "shot_id": "S007",
  "score": 87,
  "problems": [
    {
      "type": "continuity",
      "severity": "medium",
      "detail": "screen direction reversed"
    }
  ],
  "decision": "REGENERATE"
}
```

不要让模型写 500 字审片报告。

---

# 26. Fast QC 缓存机制

每个媒体文件计算：

```text
SHA-256
```

数据库：

```text
asset_hash
qc_profile_version
result_json
timestamp
```

如果：

```text
hash unchanged
+
qc version unchanged
```

则：

> 直接复用 QC。

禁止再次打开图片、再次抽帧、再次跑 VLM。

这是必须实现的。

---

# 27. QC 并行

所有 shot-level QC：

```text
ProcessPool
or
async subprocess
```

并发限制配置：

```yaml
qc:
  workers:
    ffmpeg: 6
    cv: 8
    vlm: 2
```

原则：

> FFmpeg/CV 多并发；VLM 小批量 batch。

---

# 28. Audio QC

自动跑：

```text
ffmpeg ebur128
ffmpeg astats
faster-whisper
```

检查：

- integrated LUFS。
- true peak。
- clipping。
- silence。
- ASR transcript。
- narration missing word。
- duration mismatch。

旁白原稿和 ASR 做文本 diff。

关键数字必须单独检查：

```text
465
1000
one second
```

---

# 29. Master QC

最终成片只需要：

1. deterministic full check。
2. scene detection。
3. 1fps contact sheet。
4. subtitle OCR-free safe-zone geometry check。
5. ASR transcript compare。
6. audio loudness。
7. 关键时间点截图。
8. 人工完整播放一次。

禁止：

> Agent 通过 vision 一秒一秒读完整 40 秒视频。

---

# 30. QC CLI

目标：

```bash
uv run hajimi qc shot EP001 S005
uv run hajimi qc episode EP001
uv run hajimi qc master EP001
```

输出：

```text
episodes/EP001/qc/
├── report.json
├── report.md
├── contact_sheet.jpg
├── suspicious/
└── metrics/
```

---

# 31. Agent Skills 架构

Skills 是整个项目真正的“制作团队”。

---

## 31.1 creative-director

职责：

- 判断视频是否有 stop-scroll。
- 定义 emotional curve。
- 定义 hero shot。
- 拒绝“漂亮但无信息”的镜头。
- 决定哪些镜头值得花高成本。

不得：

- 写事实研究。
- 自己执行 Blender。
- 自己发布。

---

## 31.2 reference-deconstructor

职责：

- 分析优秀 Shorts。
- 形成 shot grammar。
- 记录 hook、cuts、sound、visual peak。
- 建立 reusable pattern。

输出：

```text
references/shot_patterns/*.yaml
```

---

## 31.3 research-editor

职责：

- 事实核验。
- 来源分类。
- fact/inference separation。
- 风险句检测。

---

## 31.4 short-script-editor

职责：

- 把研究内容变成 beat script。
- 删除冗余解释。
- 一个句子一个 punch。
- 做 hook / escalation / payoff / loop。

---

## 31.5 storyboard-director

职责：

- shot list。
- composition。
- lens。
- camera。
- screen direction。
- shot-to-shot continuity。

---

## 31.6 animatic-director

职责：

- temp VO。
- temp SFX。
- temp music。
- storyboard cut。
- 节奏 Gate。

Animatic fail：

> 禁止 Production。

---

## 31.7 shot-designer

职责：

- 根据 shot intent 决定 Blender / AI / Fusion / footage。
- 写 production brief。
- 写 negative constraint。

---

## 31.8 blender-shot

职责：

- Blender Python。
- camera。
- simulation。
- preview render。
- reusable assets。

---

## 31.9 ai-visual-producer

职责：

- image/video prompt。
- reference consistency。
- candidate generation。
- 不负责最终选镜。

---

## 31.10 resolve-editor

职责：

- Resolve 项目。
- timeline。
- trim。
- pacing。
- Fusion。
- export。

---

## 31.11 sound-designer

职责：

- BGM curve。
- ambience。
- impact。
- movement。
- silence。
- Fairlight mix。

---

## 31.12 fast-media-qc

必须严格遵守本文 Fast QC 漏斗。

禁止：

- 顺序完整查看所有媒体。
- 对 hash 未变化素材重跑 QC。
- 第一轮直接 VLM。
- 把视频原始帧塞满 Agent context。

---

## 31.13 final-master-qc

负责 master：

- technical。
- visual。
- subtitles。
- sound。
- content completeness。

不负责重新导演。

---

## 31.14 youtube-publisher

必须使用：

```text
ego-browser
```

不得自己实现：

- Playwright 登录脚本。
- Chrome cookie 抓取。
- YouTube 私有接口逆向。

---

# 32. AGENTS.md 推荐完整内容

将仓库根 `AGENTS.md` 替换为以下结构：

```markdown
# Hajimi Studio Agent Operating Manual

## Mission

Hajimi is an AI-driven visual storytelling studio.

Primary objective:
produce world-class knowledge-entertainment Shorts and long-form videos.

Optimization order:

1. audience retention
2. visual storytelling quality
3. factual correctness
4. sound and editing quality
5. repeatability
6. automation speed

Never optimize production speed by sacrificing the first four.

---

## Non-Negotiable Rules

- Do not patch the legacy V1 production system.
- Do not create new v05/v06 legacy folders.
- `episode.yaml` is the single source of truth.
- Every shot has one immutable shot ID.
- Never mix assets from different shot versions without updating the manifest.
- No production-quality shot is generated before the animatic passes.
- FFmpeg is not the creative editor.
- DaVinci Resolve is the primary picture/sound editor.
- Deterministic scientific motion should prefer Blender/Fusion.
- AI video must pass shot QC before entering the timeline.
- Never QC every frame with an LLM/VLM.
- Always run deterministic QC first.
- Reuse QC results when the asset hash is unchanged.
- Any expensive action must be incremental.
- Never publish without final-master-qc PASS.

---

## Required Workflow

topic
→ research
→ creative brief
→ reference deconstruction
→ script beats
→ storyboard
→ animatic
→ animatic gate
→ shot production
→ shot QC
→ edit
→ sound
→ master
→ master QC
→ upload private
→ YouTube checks
→ publish/schedule

Stages may not be skipped.

---

## Quality Targets

- anomaly/result inside 1.5 seconds
- meaningful visual change every 1–3 seconds
- visual/audio peak every 8–12 seconds
- at least one hero shot
- no static AI plate held > 4 seconds unless deliberately justified
- no narration-only mix
- no unresolved visual artifact in an approved shot

---

## QC Policy

Fast QC hierarchy:

1. ffprobe / decode / black / freeze / silence
2. proxy
3. scene detection
4. 3-frame-per-shot sampling
5. cheap CV metrics
6. contact sheet
7. VLM only for representative/suspicious frames
8. human review only when required

Never reverse this order.

---

## Tool Responsibilities

Blender:
deterministic 3D, simulations, controlled camera.

AI image/video:
hero visuals and impossible imagery.

Resolve:
editing, pacing, Fusion, Fairlight, delivery.

FFmpeg:
proxy, extraction, analysis, encode, QC.

ego-browser:
logged-in website interaction and YouTube Studio publishing.

---

## Agent Skill Routing

Use project skills under `.agents/skills/`.

If a task is primarily:
- creative direction → creative-director
- factual research → research-editor
- competitor/reference analysis → reference-deconstructor
- script → short-script-editor
- storyboard → storyboard-director
- animatic → animatic-director
- Blender → blender-shot
- AI generation → ai-visual-producer
- editing → resolve-editor
- sound → sound-designer
- QC → fast-media-qc / final-master-qc
- YouTube upload → youtube-publisher

Do not silently combine unrelated roles.

---

## Beads

Use `bd` for durable issue tracking.

Every production blocker must be represented as a bead.

Do not use markdown TODO files as the canonical task tracker.

---

## Destructive Operations

The user has approved removal of the V1 production architecture.

After rebuild begins:
- delete legacy production files
- do not restore them into the active tree
- Git history/tag is sufficient for rollback

Do not delete `.git`.

---

## Publish Safety

Default upload visibility is PRIVATE.

The agent may:
- upload
- fill metadata
- configure AI disclosure
- wait for processing/checks
- collect the Studio result

The agent must not make a video Public unless the current task explicitly requests publishing.

Scheduling requires an explicit date/time in the current task or episode manifest.

---

## Completion Protocol

Before marking an episode complete:

- manifest consistent
- all shots approved
- master exists
- master QC PASS
- title/description package exists
- upload result saved
- YouTube Studio checks recorded
- analytics record initialized
```

---

# 33. CLAUDE.md

不要再保留空 placeholder。

`CLAUDE.md` 只做一个轻量入口：

```markdown
# Hajimi

Read `AGENTS.md` first.

Then load the relevant project skill from `.agents/skills/`.

Key commands:

```bash
uv sync
uv run hajimi status
uv run hajimi qc episode <episode>
uv run hajimi qc master <episode>
bd ready
```

Do not modify the legacy V1 workflow.
Do not perform full-frame LLM/VLM QC.
Do not publish a video Public unless explicitly authorized.
```

---

# 34. Skill 文件标准

每个 `SKILL.md` 必须包含：

```markdown
---
name:
description:
triggers:
---

# Objective

# Inputs

# Outputs

# Required Workflow

# Quality Gate

# Failure Conditions

# Tools

# Forbidden Patterns

# Handoff
```

不要写成“知识文档”。

Skill 必须能实际约束 Agent 行为。

---

# 35. ego lite / ego-browser

截至 2026-09，ego lite 当前主要支持 macOS，并通过真实 Chromium 会话和登录态给 Agent 提供浏览器自动化。

官方 skill 安装方式：

```bash
npx skills add citrolabs/ego-lite
```

或：

```bash
npx skills add github:CitroLabs/ego-lite/skills/ego-browser
```

ego-browser 官方推荐：

```bash
ego-browser nodejs <<'EOF'
...
EOF
```

不要：

- 生成单独 `.js` 再执行。
- 自己获取 Chrome cookie。
- 复刻登录。
- 用私人 YouTube HTTP endpoint。

---

# 36. YouTube 发布流程

YouTube Studio 当前官方流程仍然是：

```text
CREATE
→ Upload videos
→ Details
→ Audience
→ Attributes / AI use
→ Video elements
→ Checks
→ Visibility
```

如果使用写实 AI 生成或显著修改了现实场景，应在 YouTube 的 **AI use / altered or synthetic content** 设置中如实披露。

官方说明同时指出：

- disclosure 本身不会限制 audience。
- disclosure 本身不影响 monetization eligibility。
- 未披露可能导致平台主动标签，持续不披露可能带来进一步处理。

---

# 37. ego-browser YouTube 发布 Skill

`youtube-publisher/SKILL.md` 要求：

## Step 1 — Preflight

必须确认：

```text
master_qc == PASS
master file exists
title exists
description exists
thumbnail exists if required
ai_disclosure resolved
audience resolved
visibility resolved
```

## Step 2 — 创建独立 Space

示意：

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('youtube-publish-EP001')
await openOrReuseTab('https://studio.youtube.com', {
  wait: true,
  timeout: 30
})
cliLog(await snapshotText())
EOF
```

## Step 3 — 上传

官方 ego-browser 提供：

```javascript
uploadFile(...)
```

示意：

```javascript
await uploadFile(
  'input[type="file"]',
  '/absolute/path/to/master.mp4'
)
```

不要把 selector 写死为长期契约。

正确方法：

1. `snapshotText()`
2. 找到 Upload 控件 ref/locator
3. 优先 ref/locator
4. selector 只作为 fallback

## Step 4 — Details

自动填写：

- Title
- Description
- Playlist
- Audience
- AI disclosure
- language
- optional thumbnail

填完立即重新：

```javascript
snapshotText()
```

做 readback。

## Step 5 — Video elements

Shorts 通常无需复杂 end screen。

长视频按 manifest 处理。

## Step 6 — Checks

YouTube 官方说明：

- Copyright Checks 可后台运行。
- 检查并非永久最终结论。
- 当前还可能运行 likeness detection。

系统策略：

```text
upload as PRIVATE
↓
wait for SD/HD processing state
↓
read Checks
↓
record result
```

不要因为网页显示“checks running”就让 Agent 长时间阻塞。

记录：

```json
{
  "copyright": "running",
  "likeness": "running",
  "upload": "complete"
}
```

然后结束本轮。

后续可以由 publish check task 再读取状态。

## Step 7 — Visibility

默认：

```text
PRIVATE
```

只有 episode manifest 或用户明确要求：

```text
PUBLIC
SCHEDULED
```

时才更改。

YouTube 官方支持从 private/scheduled 状态设定具体发布日期、时间和时区。

## Step 8 — Verify

发布后必须读回：

- video URL。
- visibility。
- title。
- processing。
- checks。
- schedule。

写入：

```text
episodes/<episode>/publish/youtube.json
```

---

# 38. 不使用 YouTube Data API 作为默认上传方式

官方 YouTube Data API 支持 `videos.insert`。

但当前存在一个实际限制：

> 2020-07-28 之后创建的未经验证 API project，API 上传的视频会被限制为 private，项目需经过审核才可解除。

因此：

## 默认方案

```text
ego-browser + YouTube Studio
```

优势：

- 复用真实登录态。
- 与人工 Studio 一致。
- 无 OAuth app 审核负担。
- 可处理 Studio 页面上的 AI disclosure / Checks / Visibility。

API 可作为后期可选通道，不是 V2 首发基础设施。

---

# 39. Publish Manifest

```yaml
youtube:
  title: "..."
  description: |
    ...
  language: en-US
  category: Education
  audience:
    made_for_kids: false
  ai_use:
    disclose: true
    reason: realistic_generated_scene
  visibility: private
  schedule:
    enabled: false
    timezone: Asia/Singapore
    datetime: null
```

---

# 40. 发布 Agent 不得做的事情

禁止：

- 上传前跳过 master QC。
- 自动选择 Public。
- 猜 AI disclosure。
- 猜 made-for-kids。
- 在不知道当前 UI 状态时坐标盲点。
- 用陈旧 selector 长期硬编码。
- bypass YouTube checks。
- 抓取 cookie 写进脚本。
- 保存账号 token 到 repo。

---

# 41. 数据闭环

每条视频除了：

```text
views
AVD
APV
comments
likes
shares
subs
```

新增：

```text
hook_type
time_to_anomaly
avg_shot_duration
shot_count
hero_shot_type
visual_peak_count
audio_peak_count
production_method_mix
ai_video_seconds
blender_seconds
static_plate_seconds
qc_fail_count
regen_count
retention_drop_1
retention_drop_2
```

只有这样才能真正回答：

> “哪种制作方式让观众留下来？”

---

# 42. 新 analytics schema

```text
video
├── metadata
├── creative
├── timeline_metrics
├── production_metrics
├── retention
└── learnings
```

例如：

```json
{
  "hook_type": "immediate_consequence",
  "time_to_anomaly": 0.38,
  "avg_shot_duration": 1.8,
  "hero_shot": "physics_mismatch",
  "production_mix": {
    "blender": 0.45,
    "ai_video": 0.25,
    "fusion": 0.20,
    "footage": 0.10
  }
}
```

---

# 43. EP001 必须重新做

不要复用 V03 成片。

只允许复用：

- 已验证事实。
- 已验证来源。

不要复用：

- 旧 script wording。
- 旧 shot list。
- 旧 Flow 片段。
- 旧 subtitle。
- 旧 render script。
- 旧 edit。

EP001 重新进入：

```text
creative direction
↓
new script
↓
new storyboard
↓
new animatic
```

---

# 44. EP001 新方向

建议 34–38 秒。

```text
0.0–1.2
地面锁死，但人/纸张继续向右
“The ground stops. You don't.”

1.2–4.0
人体横向惯性

4.0–7.0
465 m/s / 1,040 mph punch

7.0–11.0
城市尺度的 465 m 轨迹

11.0–16.0
空气相对地面高速运动

16.0–21.0
海洋惯性

21.0–27.0
land / air / water mismatch

27.0–31.0
Earth restart second impact

31.0–35.0
Gravity isn't the problem — sideways motion is

35.0–38.0
“One second. 465 meters.”
loop 回开头
```

---

# 45. Commands

目标 CLI：

```bash
uv run hajimi new EP001
uv run hajimi status EP001

uv run hajimi research EP001
uv run hajimi animatic EP001

uv run hajimi qc shot EP001 S003
uv run hajimi qc episode EP001

uv run hajimi resolve sync EP001
uv run hajimi master EP001
uv run hajimi qc master EP001

uv run hajimi publish youtube EP001 --private
uv run hajimi publish status EP001
```

---

# 46. 性能要求

Fast QC 性能目标，不是硬件基准：

## 单图

```text
metadata + hash + blur + histogram
< 300 ms typical
```

## 8 秒代理视频

```text
Tier 0 + proxy + scene sample
目标数秒级
```

## 40 秒 Shorts

```text
deterministic QC + proxy + scene detect + contact sheet
目标十几秒级，而不是数分钟
```

VLM：

```text
正常情况下只检查 1–3 张 contact sheet
+
少量异常帧
```

如果系统默认把完整视频交给 Agent vision：

> 判定架构错误。

---

# 47. 构建顺序

Codex 必须按以下顺序执行。

## Phase 1

删除 V1。

## Phase 2

建立目录、manifest、SQLite schema。

## Phase 3

实现：

```text
hash
ffprobe
proxy
scene detect
frame sampler
contact sheet
QC cache
```

先把 Fast QC 做好。

## Phase 4

创建核心 Skills：

```text
creative-director
short-script-editor
storyboard-director
animatic-director
fast-media-qc
```

## Phase 5

建立 Blender / Resolve integration。

## Phase 6

重做 EP001 Animatic。

## Phase 7

完成真实 production。

## Phase 8

ego-browser YouTube publish。

## Phase 9

analytics。

不要先做全套 UI。

---

# 48. Acceptance Criteria

系统重构完成必须满足：

### Architecture

- [ ] 旧 pipeline 已从 active tree 删除。
- [ ] episode.yaml 为单一事实源。
- [ ] shot ID 稳定。
- [ ] SQLite 状态库存在。
- [ ] assets 有 SHA-256。
- [ ] QC 有 cache。

### Production

- [ ] Animatic Gate 存在。
- [ ] Blender 是 deterministic visual backend。
- [ ] Resolve 是主编辑器。
- [ ] Fairlight 有完整 sound pipeline。
- [ ] AI visual 只是多种生产方式之一。

### QC

- [ ] 默认 QC 不逐帧调用 VLM。
- [ ] 默认先 proxy。
- [ ] 每 shot 默认最多 3 个基础 sample。
- [ ] contact sheet 支持。
- [ ] unchanged hash 不重新 QC。
- [ ] ASR diff 支持。
- [ ] master QC 可自动运行。

### Agents

- [ ] AGENTS.md 已替换。
- [ ] CLAUDE.md 已替换。
- [ ] skills 全部存在。
- [ ] skills 有明确输入/输出/禁止模式。

### Publish

- [ ] ego-browser 可使用。
- [ ] YouTube Studio 可打开。
- [ ] uploadFile 可上传 master。
- [ ] metadata readback。
- [ ] AI disclosure 可配置。
- [ ] 默认 private。
- [ ] YouTube Checks 状态入库。
- [ ] URL 入库。

### EP001

- [ ] 完全重做。
- [ ] 新 animatic PASS。
- [ ] 不复用旧 V03 timeline。
- [ ] 至少一处 Blender/Fusion deterministic visual。
- [ ] 至少一个 hero shot。
- [ ] 完整 BGM/SFX/ambience。
- [ ] master QC PASS。

---

# 49. Agent 最终执行指令

将下面内容直接交给 Codex：

```text
你现在负责彻底重构 hajimi。

不要优化现有视频生产流程。
不要继续修改 V03。
不要保留旧 pipeline 兼容性。

严格按本文件执行：

1. 给当前仓库创建 `hajimi-v1-before-rebuild` tag。
2. 删除旧内容生产结构。
3. 创建新的 studio architecture。
4. 建立 episode manifest + SQLite 状态系统。
5. 第一优先实现 Fast QC。
6. 创建本文指定的 Agent Skills。
7. 替换 AGENTS.md 和 CLAUDE.md。
8. 建立 Blender / Resolve / Fairlight / FFmpeg 分工。
9. 重做 EP001，从 Creative Brief + Animatic 开始。
10. Animatic 不通过，不进入正式生成。
11. 最终使用 Resolve 完成 picture + Fusion + sound。
12. Master 通过 Fast QC + Final QC 后，使用 ego-browser 打开 YouTube Studio。
13. 默认上传为 PRIVATE。
14. 填写 title / description / audience / AI disclosure。
15. 记录 YouTube Checks。
16. 只有明确得到 Public/Schedule 指令时才公开。
17. 所有进度使用 Beads 管理。
18. 不得重新引入旧的“大量图片/视频逐个 VLM QC”模式。
19. 不得使用 FFmpeg 代替专业剪辑和声音设计。
20. 每完成一个 Phase，运行测试和 QC，并记录结果。

最终目标不是“能生成视频”。

最终目标是：

一个 AI Agent 能持续运行的、高品质、可追踪、快速 QC、可持续提升的
AI 视觉叙事工作室。
```

---

# 50. 已核实的外部技术事实

## ego lite / ego-browser

- GitHub: https://github.com/citrolabs/ego-lite
- Docs: https://lite.ego.app/document/zh/docs/ego-browser
- 当前官方 skill 提供 `snapshotText`、`click`、`fillInput`、`uploadFile`、`captureScreenshot`、`cdp` 等能力。
- 官方推荐通过 `ego-browser nodejs <<'EOF' ... EOF` 执行完整 JS 自动化流程。
- macOS 当前为主要支持平台。

## PySceneDetect

- Docs: https://www.scenedetect.com/docs/head/api/detectors.html
- AdaptiveDetector 使用 rolling average 处理内容差异，适合运动较强的视频。
- CLI 支持 scene list + scene image 导出。

## YouTube Studio Upload

- 官方上传说明：
  https://support.google.com/youtube/answer/57407
- 定时发布：
  https://support.google.com/youtube/answer/1270709
- AI 内容披露：
  https://support.google.com/youtube/answer/14328491

YouTube 当前要求对“看起来真实但实际由 AI 生成或有意义修改”的现实人物/地点/事件进行披露。

## YouTube Data API

- `videos.insert`：
  https://developers.google.com/youtube/v3/docs/videos/insert

未经验证的较新 API project 通过 API 上传的视频存在 private 限制，因此本项目默认使用 ego-browser + Studio，而不是直接以 Data API 作为首选发布链路。

---

# Final Principle

Hajimi V2 的核心不是：

```text
AI 写稿
AI 生图
AI 生视频
FFmpeg 拼接
上传
```

而是：

```text
AI Director
+
AI Researcher
+
AI Storyboard Artist
+
Blender Technical Artist
+
AI Visual Producer
+
Resolve Editor
+
Sound Designer
+
Fast QC System
+
Browser Publishing Agent
```

目标是把单人本地工作站提升为：

> **AI 驱动的小型世界级动画 / 视觉叙事工作室。**
