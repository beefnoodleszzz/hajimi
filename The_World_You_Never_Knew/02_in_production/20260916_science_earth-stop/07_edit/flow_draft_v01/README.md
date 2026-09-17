# Flow 动态版制作记录（V01）

## 固定制作流程

本项目暂定采用以下流程，后续同系列视频沿用：

1. 用内置 ImageGen 生成或整理竖屏关键帧。
2. 用 Ego 浏览器打开 Google Flow，将关键帧作为 image-to-video 输入。
3. Flow 使用低成本参数生成动态片段：`720p`、`9:16`、`8s`、`x1`。
4. Flow 片段只保留画面；剥离其自带音轨，统一使用已确定的 02 号配音。
5. 本地按配音时长剪辑、加字幕和图形镜头，输出竖屏 review 版。

## 本次项目

- 主题：`The Ground Would Stop. You Wouldn't.`
- Flow 项目：[Earth Stop — Flow Full Remake V01](https://flow.google.com/project/188dc491-a8c3-4844-80b3-52f773e55a89)
- 固定配音：候选 02，`friend_asmr_full_redo_20260917_v01/run_0001/FULL_CANDIDATES/full_candidate_02.wav`
- 配音时长：`54.910333s`
- 动态镜头：01、02、04、06、07、08、10
- 图形镜头：03、05、09

## 输出

- 成片 review：[earth_stop_flow_review_v01.mp4](./earth_stop_flow_review_v01.mp4)
- 画面锁定版：[picture_lock_flow_v01.mp4](./picture_lock_flow_v01.mp4)
- 仅字幕版：[picture_captioned_flow_v01.mp4](./picture_captioned_flow_v01.mp4)
- Flow 原始片段：`./flow_segments/`
- 本地重剪脚本：[render_flow_draft_v01.sh](./render_flow_draft_v01.sh)

## 验证结果

- 画面：`1080×1920`、`30fps`、H.264
- 音频：AAC、`48kHz`、单声道、`54.910s`
- 容器时长：`54.910s`
- Flow 自动生成音频：已移除
- 已做接触表抽检：未发现明显构图漂移、结构崩坏或镜头级伪影。

## 备注

这版先作为低成本流程验证片。若画面动态幅度、真实感或镜头控制不够，再把同一套关键帧和分镜迁移到 Kling，不改变配音、字幕和剪辑结构。
