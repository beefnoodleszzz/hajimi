# Hajimi Blender Production Stack
## Blender 5.2 LTS 世界一流视觉叙事工作站适配与自动化实施规范

> 版本：2026-09-17
> 用途：直接交给 Codex / Claude Code / 本地 AI Agent 执行。
> 目标：把 Blender 从“可用的 3D 软件”配置成 Hajimi V2 的 **deterministic cinematic backend**：可脚本化、可复现、可批量、可快速预览、可快速 QC、可与 DaVinci Resolve/Fusion/Fairlight 无缝衔接。
> 目标内容：英文科学 / What-if / Strange History / Mystery 类 9:16 Shorts，当前主时长维持约 35–40 秒。
> 原则：**不追求插件数量；只安装真正提高视觉质量、搭景速度、镜头控制或物理可信度的工具。**

---

# 0. 最终目标

配置完成后，AI Agent 必须可以做到：

```text
Episode Beat
    ↓
Shot Brief
    ↓
Blender Template
    ↓
自动搭建 Scene / Camera / Lighting / Assets / Simulation
    ↓
540p / 720p Preview
    ↓
Fast QC
    ↓
只修异常
    ↓
1080×1920 Final Image Sequence
    ↓
Resolve / Fusion
    ↓
Final Master
```

Blender 在 Hajimi 中不是独立创作工具，而是以下五个角色的集合：

```text
1. deterministic physics engine
2. deterministic camera engine
3. procedural environment engine
4. cinematic lighting / atmosphere engine
5. reusable 3D asset engine
```

它**不承担**：

```text
最终剪辑
最终字幕
最终音乐
最终声音设计
最终调色
最终发布
```

这些由 Resolve / Fusion / Fairlight / ego-browser 负责。

---

# 1. 版本锁定

## 1.1 Blender

锁定：

```text
Blender 5.2.2 LTS
```

不要自动升级到：

```text
5.3 Alpha
5.3 Beta
5.3 Release
```

除非：

1. 本文所有插件重新通过兼容性测试；
2. benchmark scene 通过；
3. 已存在项目打开无错误；
4. Headless render 通过；
5. Python API smoke test 通过。

### 当前依据

Blender 官方：

```text
Blender 5.2 LTS
Initial release: 2026-07-14
Supported until: 2028-07
Blender 5.2.2 LTS: 2026-09-15
```

因此 Hajimi 不追逐最新小版本之外的 feature release。

---

# 2. 平台与 GPU 自动检测

Agent 第一步必须识别：

```text
OS
CPU
GPU
RAM
Blender path
Blender version
```

输出：

```text
config/generated/hardware.json
```

示例：

```json
{
  "os": "macOS",
  "arch": "arm64",
  "cpu": "Apple ...",
  "ram_gb": 64,
  "gpu_vendor": "Apple",
  "gpu_backend": "METAL",
  "blender": "5.2.2"
}
```

---

# 3. Cycles GPU Backend 策略

## 3.1 Apple Silicon / macOS

使用：

```text
Cycles → Metal
```

Blender 5.2 官方文档明确支持 Apple Silicon 的 Metal GPU 加速，并支持 GPU ray tracing 与 GPU denoising。

不要设置：

```text
CUDA
OptiX
HIP
oneAPI
```

## 3.2 NVIDIA / Windows / Linux

优先：

```text
OptiX
```

Fallback：

```text
CUDA
```

## 3.3 AMD

优先：

```text
HIP
```

具体硬件 ray tracing 是否开启，以 Blender doctor 探测结果为准。

## 3.4 Intel Arc

使用：

```text
oneAPI
```

## 3.5 CPU

只作为：

```text
fallback
```

不要把 CPU + GPU 同时启用写成固定策略。

Agent 必须先跑 benchmark，再决定混合设备是否更快。

---

# 4. Viewport / Display Backend

不要混淆：

```text
Cycles compute backend
```

与：

```text
Blender viewport graphics backend
```

Physical Atmosphere² 当前官方建议 Vulkan。

但平台支持不同：

- 支持 Vulkan 的平台：优先测试 Vulkan。
- macOS / Apple Silicon：不得盲目强制 Vulkan；使用 Blender 实际支持的 graphics backend，并运行 PA² smoke test。
- 如 PA² cloud viewport 在目标平台明显不稳定：允许 PA² 只负责 atmosphere/sun，云改走 Blender volume / image plate / AI / Resolve。

原则：

> 插件不能决定整个工作站的稳定性。

---

# 5. Render Engine 分工

禁止“全部 Cycles”。

## EEVEE

默认承担：

```text
storyboard preview
animatic
most science visualization
motion graphics base
simple environment
large procedural scene
camera tests
lighting tests
most Shorts final shots
```

## Cycles

只用于：

```text
hero shot
glass
high-end reflection
complex refraction
close-up material
high-quality volumetric hero frame
physically demanding light transport
```

## Rule

每个 shot 的 `shot.yaml` 必须写：

```yaml
renderer: eevee
```

或：

```yaml
renderer: cycles
reason: "close glass refraction hero shot"
```

没有 reason，不允许默认升级 Cycles。

---

# 6. 输出格式

Blender 不直接输出最终 MP4。

## Preview

允许：

```text
H.264 proxy
```

用于：

```text
animatic / director review / QC
```

## Final

统一：

```text
image sequence
```

### 普通镜头

```text
PNG
8/16-bit
RGBA when required
```

### 合成型 Hero Shot

```text
OpenEXR
half float
selected passes
```

不要每个镜头都输出 20 个 pass。

只启用实际需要：

```text
Combined
Depth
Normal
Vector
Mist
Cryptomatte
```

---

# 7. Shorts Resolution Profile

Hajimi 当前最终画面：

```text
1080 × 1920
30 fps
9:16
```

建立四档：

## P0 — BLOCKING

```yaml
width: 270
height: 480
fps: 15
```

只看：

```text
composition
timing
camera
```

## P1 — PREVIEW

```yaml
width: 540
height: 960
fps: 30
```

默认 Shot QC 使用。

## P2 — ANIMATIC

```yaml
width: 720
height: 1280
fps: 30
```

## P3 — FINAL

```yaml
width: 1080
height: 1920
fps: 30
```

Hero Shot 如果需要超采样：

```text
1440 × 2560
↓
Resolve downsample
```

不得默认所有镜头超采样。

---

# 8. Camera System

Hajimi 必须建立统一 Camera Rig。

目录：

```text
assets/blender/camera/
├── hajimi_camera_rig.blend
├── presets/
│   ├── 18mm_epic.yaml
│   ├── 24mm_environment.yaml
│   ├── 35mm_action.yaml
│   ├── 50mm_documentary.yaml
│   └── 85mm_detail.yaml
└── scripts/
```

---

# 9. Camera Rig 必须支持

```text
Camera
└── CameraRoot
    ├── Dolly
    ├── PanTilt
    ├── Shake
    └── Target
```

Agent 操作：

```text
Root → world placement
Dolly → push / pull
PanTilt → rotation
Target → controlled focus
Shake → procedural shake
```

禁止直接给 Camera Object 同时堆几十个动画通道。

---

# 10. Camera Grammar

默认镜头语言：

## Hook

```text
24–35mm
low / eye-level
clear foreground action
0–1.5 sec anomaly
```

## Scale Reveal

```text
18–28mm
crane / dolly / aerial pull-back
```

## Mechanism

```text
35–50mm
clean lateral movement
high readability
```

## Detail

```text
50–85mm
short duration
single subject
```

禁止：

```text
每个 shot 都 zoom in
每个 shot 都 dolly forward
每个 shot 都 handheld
```

---

# 11. Camera Motion

优先：

```text
dolly
truck
crane
orbit
controlled handheld
```

慎用：

```text
digital zoom
```

完全禁止：

```text
为了“有运动”而做无意义 Ken Burns
```

---

# 12. 摄影机安全区

建立：

```text
9:16 mobile safe guides
```

必须显示：

- YouTube Shorts right interaction UI reserve
- bottom title/description reserve
- subtitle safe region
- story typography safe region

所有 Camera Preview 默认打开 overlay。

---

# 13. Photographer 5

## Status

推荐：

```text
P0
```

当前官方页面声明支持 Blender 3 / 4 / 5.x，EEVEE + Cycles。

主要使用：

```text
physical camera
shutter
ISO
bokeh
light mixer
world mixer
gobo
IES
lens effects
render queue
```

## Hajimi 使用规则

Photographer 不是“特效包”。

默认：

```text
lens distortion: subtle
chromatic aberration: off or extremely subtle
film grain: off in Blender
bloom: shot dependent
fringing: off
```

最终 grain / bloom 主要留给 Resolve。

真正高价值：

```text
physical exposure
IES
gobo
light placement
camera controls
```

## 安装

如果 Agent 能找到合法 ZIP：

```text
Install from Disk
```

安装后：

```text
enable
restart Blender
run smoke test
```

如未找到：

```text
BLOCKED_LICENSE_PACKAGE
```

不要阻塞其他配置。

---

# 14. Physical Atmosphere²

## Status

推荐：

```text
P0
```

当前官方要求：

```text
Blender 5.2.0+
```

用途：

```text
atmosphere
sun
moon
stars
volumetric clouds
real place/date/time lighting
live viewport sky
```

## 什么时候用

```text
epic environment
planetary atmosphere
late afternoon
sunrise/sunset
cloud reveal
history reconstruction
large exterior
```

## 什么时候不用

```text
studio cutaway
diagram
indoor scene
abstract science graphic
```

## Performance

Cloud 必须分档：

```text
preview_cloud_quality
final_cloud_quality
```

不要在 blocking 阶段开高质量 cloud。

---

# 15. Geo-Scatter

## Status

推荐：

```text
P0
```

锁定兼容版本：

```text
Geo-Scatter 5.6.4
```

其官方 changelog 明确：

```text
Blender 5.2 LTS compatibility
```

用途：

```text
grass
rocks
debris
street dressing
forest
ground details
environment complexity
```

## 规则

永远优先：

```text
collection instance
low preview density
distance-based detail
camera-aware scatter
```

不要把百万级真实 mesh 展开成独立 object。

## Preview

```text
density: 10–25%
```

Final：

```text
density: shot-dependent
```

---

# 16. botaniq / engon

## Status

推荐：

```text
P1
```

当前 engon 1.10.0 changelog 已包含 Blender 5.2 fixes，并包含 botaniq 相关能力。

作用：

```text
tree
grass
shrubs
forest dressing
background environment
```

不负责：

```text
hero close-up botanical asset
```

只在自然环境占比高时启用。

---

# 17. FLIP Fluids

## Status

```text
ON DEMAND
```

当前：

```text
FLIP Fluids 1.8.8
Blender 4.5–5.2
```

官方 1.8.7/1.8.8 对 Blender 5.2 LTS 有明确支持。

用途：

```text
hero liquid
water collision
fluid displacement
foam
spray
whitewater
```

不要用于：

```text
普通远景海面
普通湖面
普通波纹
```

这些使用：

```text
shader
geometry nodes
normal animation
displacement
```

---

# 18. Poliigon

## Status

```text
P1
```

当前：

```text
Poliigon Blender Addon 1.16.3
tested Blender 5.2
```

用途：

```text
PBR materials
models
HDRIs
```

Hajimi 原则：

```text
Poly Haven first
Local curated library second
Poliigon when quality/asset gap remains
```

不要每次 shot 都在线搜索。

Agent 应先查本地 Asset Browser。

---

# 19. Poly Haven

不是强制插件。

作为：

```text
P0 source library
```

把常用资产提前下载、整理、进入本地资产库。

目标：

```text
HDRI
rock
concrete
road
metal
wood
ground
surface
```

优先做：

```text
curated local pack
```

不要每次联网重新下载。

---

# 20. BlenderKit / Blendkit

作为：

```text
P2 fallback
```

适合：

```text
快速找低重要度 prop
背景资产
临时 blocking asset
```

不允许 Agent 自动把随机社区资产用于 Hero Shot。

进入 final 前必须：

```text
license check
quality check
topology/material check
```

---

# 21. 插件清单

## 必装

```text
Photographer 5
Geo-Scatter 5.6.4
Physical Atmosphere²
```

前提：

```text
用户已有合法安装包 / license
```

## 推荐

```text
Poliigon Addon 1.16.3
botaniq via current engon
```

## 按项目启用

```text
FLIP Fluids 1.8.8
```

## 不需要首批安装

```text
HardOps
Boxcutter
Auto-Rig Pro
Rigify-heavy toolchains
Octane
Redshift
K-Cycles
大量视觉滤镜 add-on
```

---

# 22. 不引入第三方 Renderer

V1 Blender Stack：

```text
Eevee
+
Cycles
```

原因：

```text
稳定
Python API 原生
headless 好控制
资产兼容好
license 简单
AI Agent 容易自动化
```

不要为了 benchmark 单帧质量引入：

```text
Octane
Redshift
Arnold
```

除非未来某一类内容证明 Cycles 是实际瓶颈。

---

# 23. Asset Library 架构

不要让插件各自把东西散落在用户目录。

统一：

```text
$HAJIMI_ASSETS/
├── blender/
│   ├── curated/
│   ├── vendor/
│   │   ├── geoscatter/
│   │   ├── botaniq/
│   │   ├── poliigon/
│   │   └── flipfluids/
│   ├── hdri/
│   ├── materials/
│   ├── models/
│   ├── environments/
│   ├── cameras/
│   ├── lights/
│   ├── geometry_nodes/
│   └── fx/
└── licenses/
```

---

# 24. Curated Library

`curated/` 是 AI Agent 第一资产源。

只有人工/Director 认可的资产才进入。

例如：

```text
road/
city/
coast/
planet/
atmosphere/
industrial/
history/
science/
```

一个资产必须附：

```yaml
asset_id:
type:
source:
license:
poly_count:
texture_resolution:
approved:
tags:
```

---

# 25. Asset Browser

Blender 5.2 原生支持：

```text
local asset library
online asset library
local cache
```

Hajimi 必须创建：

```text
Hajimi Curated
Hajimi Cameras
Hajimi Materials
Hajimi Environments
Hajimi FX
```

不要直接让几十个 Vendor Library 全部出现在默认 Asset Browser。

---

# 26. Asset Cache

Blender 官方会缓存 online asset。

Hajimi 还要自己记录：

```text
source URL
source version
local path
hash
license
```

这样重建 shot 不依赖远端变化。

---

# 27. Lighting System

建立：

```text
assets/blender/lights/
```

核心 rig：

```text
sun_environment
soft_studio
hard_science
night_city
emergency
rim_hero
overcast
```

---

# 28. Lighting Rules

高级感首先来自：

```text
direction
contrast
depth
material response
atmosphere
```

不是：

```text
更多灯
更多 bloom
更多 saturation
```

每个 shot 最少定义：

```yaml
key_direction:
key_quality:
fill_ratio:
rim:
atmosphere:
color_temperature:
```

---

# 29. HDRI 规则

HDRI 用于：

```text
reflection
natural fill
world context
```

不要让 HDRI 决定所有 lighting。

大部分 Hero Shot：

```text
HDRI
+
controlled key
+
rim/accent
```

---

# 30. Color Management

不要在 Blender 中追最终“网红调色”。

Blender：

```text
neutral cinematic baseline
```

Resolve：

```text
final look
```

原则：

```text
do not bake destructive look too early
```

Hero EXR 保留动态范围。

---

# 31. Materials

统一使用：

```text
Principled BSDF
```

除非明确理由。

每个 material 检查：

```text
base color
roughness
normal
displacement
IOR
transmission
metallic
scale
```

禁止：

```text
8K texture on background pebble
```

---

# 32. Texture Resolution

按 screen space：

```text
Hero close-up: 4K–8K
Mid-ground: 2K–4K
Background: 1K–2K
Tiny prop: 512–1K
```

不是按“能下载多大”。

---

# 33. Geometry Nodes

必须建立 Hajimi 自己的 Node Asset Library。

首批：

```text
HJ_DebrisScatter
HJ_DustTrail
HJ_VectorTrail
HJ_ImpactWave
HJ_CityRepeater
HJ_CloudLayerGuide
HJ_OceanSurface
HJ_ProceduralRoad
HJ_ArrowVector
HJ_ScaleMarkers
HJ_ParticleBurst
HJ_AtmosphericDust
```

这些比继续安装插件更重要。

---

# 34. Geometry Nodes 要求

每个 Node Group：

```text
输入清晰
默认安全
可动画
可脚本设置
有 Preview mode
有 Final mode
```

不要设计成只适合鼠标手调。

---

# 35. Physics

## Rigid Body

用于：

```text
objects retain inertia
debris
impact
structural pieces
```

## Geometry Nodes Simulation

用于：

```text
procedural motion
trails
particles
simple secondary motion
```

## FLIP

用于：

```text
hero liquid only
```

## Volume

用于：

```text
fog
dust
cloud
atmosphere
```

---

# 36. Simulation Cache

每个 shot：

```text
shots/S005/cache/
```

禁止全局 cache。

目录：

```text
cache/
├── sim/
├── geo/
├── volume/
└── preview/
```

shot hash 改变才失效。

---

# 37. Simulation Quality Profile

## PREVIEW

```text
low resolution
low particles
short cache
```

## FINAL

只在 Director approve 后 bake。

绝不：

```text
先高质量 bake
再看镜头好不好
```

---

# 38. Blender 文件结构

每 shot：

```text
shots/S005/
├── shot.yaml
├── scene.blend
├── build_scene.py
├── render_preview.py
├── render_final.py
├── cache/
├── preview/
├── render/
├── qc/
└── logs/
```

---

# 39. `shot.yaml`

```yaml
id: S005
episode: EP001
role: hero
duration_sec: 4.2

renderer: eevee

camera:
  preset: 24mm_environment
  movement: crane_pullback

environment:
  atmosphere: physical_atmosphere
  scatter: geoscatter

assets:
  - city_block_A
  - road_master
  - debris_pack_A

simulation:
  rigid_body: true
  flip: false

render:
  preview_profile: P1
  final_profile: P3

qc:
  motion_direction: right
  identity_lock: false
  expected_visual_change: high
```

---

# 40. Blender Python 是第一等接口

所有可重复 scene setup 必须脚本化。

禁止：

```text
Agent 用鼠标手动点击 50 个面板
```

优先：

```text
bpy
```

GUI 只用于：

```text
visual inspection
creative adjustment
plugin actions without stable API
```

---

# 41. Background Mode

Blender 官方支持：

```bash
blender --background file.blend --python script.py
```

Hajimi 所有：

```text
preview render
final render
doctor
asset indexing
scene build
benchmark
```

优先 headless。

Blender 5.2 还加入了 background GPU initialization 相关 API 能力，因此 5.2 是当前自动化的合理基线。

---

# 42. CLI Wrapper

实现：

```bash
uv run hajimi blender doctor
uv run hajimi blender bootstrap
uv run hajimi blender benchmark
uv run hajimi blender build EP001 S005
uv run hajimi blender preview EP001 S005
uv run hajimi blender render EP001 S005
uv run hajimi blender qc EP001 S005
```

---

# 43. `blender doctor`

必须检查：

```text
Blender exists
version == 5.2.2
Python works
GPU backend available
Cycles device available
Eevee render works
Cycles render works
plugins load
asset libraries resolve
temp directory writable
cache directory writable
headless render works
```

输出：

```text
artifacts/blender_doctor.json
```

---

# 44. 插件 Doctor

每个插件：

```json
{
  "name": "Geo-Scatter",
  "required": true,
  "installed": true,
  "enabled": true,
  "version": "5.6.4",
  "blender_compat": true,
  "smoke_test": "PASS"
}
```

不是仅检查“目录存在”。

---

# 45. 商业插件安装策略

Agent 不负责购买。

逻辑：

```text
if licensed zip/package exists:
    install
    enable
    validate
else:
    mark BLOCKED
    continue
```

例如：

```text
$HAJIMI_INSTALLERS/
├── geoscatter.zip
├── photographer.zip
├── physical_atmosphere.zip
├── flipfluids.zip
└── engon.zip
```

不得：

```text
搜索破解
下载非官方包
绕 license
```

---

# 46. Blender Extension Installation

Blender 5.2 官方支持：

```text
Get Extensions
Install from Disk
Local Repository
```

Agent 应优先使用 Blender Extension 机制。

Legacy add-on 仅在插件官方仍要求时使用。

---

# 47. Studio-managed Extension Repository

建议创建：

```text
$HAJIMI_BLENDER_EXTENSIONS/
```

通过：

```text
BLENDER_SYSTEM_EXTENSIONS
```

或用户 Local Repository 管理。

目标：

```text
可复现
不污染系统默认目录
升级可控
```

---

# 48. Studio Scripts

设置：

```text
BLENDER_USER_SCRIPTS
```

指向：

```text
repo/blender/scripts
```

目录：

```text
blender/scripts/
├── startup/
├── addons/
├── modules/
└── presets/
```

---

# 49. Startup Script

`startup/hajimi_bootstrap.py`

职责：

```text
register asset libraries
set studio paths
load camera presets
load render profiles
set cache paths
register custom operators
```

不做：

```text
网络访问
重型扫描
simulation
render
```

---

# 50. Performance

## Principle

Viewport FPS 比最终画质重要。

在镜头未锁定之前：

```text
quality is temporary
camera is permanent
```

---

# 51. Heavy Object Strategy

远景：

```text
instance
proxy
LOD
bounding box
```

不要：

```text
full geometry
```

Geo-Scatter / vegetation：

```text
viewport density reduction
```

Volume：

```text
preview steps reduced
```

---

# 52. Texture Memory

实现预检查：

```text
total texture bytes
largest textures
estimated VRAM pressure
```

如果背景物体使用 8K：

```text
WARN_TEXTURE_OVERSPEC
```

---

# 53. Render Profiles

配置：

```text
config/blender/render_profiles.yaml
```

示意：

```yaml
blocking:
  engine: EEVEE
  resolution: [270, 480]
  fps: 15

preview:
  engine: EEVEE
  resolution: [540, 960]
  fps: 30

animatic:
  engine: EEVEE
  resolution: [720, 1280]
  fps: 30

final_eevee:
  engine: EEVEE
  resolution: [1080, 1920]
  fps: 30

final_cycles:
  engine: CYCLES
  resolution: [1080, 1920]
  fps: 30
  adaptive_sampling: true
  denoise: true
```

Samples 不写死为全局神奇数字。

benchmark 后生成：

```text
config/generated/render_tuning.yaml
```

---

# 54. Cycles Quality

初始建议：

```text
Preview:
32–64 max samples

Final:
64–256 max samples
adaptive sampling
GPU denoise
```

实际由 benchmark 选择。

不要为了“专业”默认 1024/4096 samples。

---

# 55. Eevee Quality

重点：

```text
shadow quality
volumetric quality
screen-space effects
TAA
material correctness
```

不要为 preview 打开所有 final-quality effect。

---

# 56. Motion Blur

只在需要时开启。

科学解释镜头：

```text
可读性 > motion blur
```

Hero action：

```text
允许 controlled motion blur
```

不要让运动信息被糊掉。

---

# 57. Depth of Field

同理：

```text
story focus > shallow DOF
```

科学 diagram：

```text
DOF off
```

Hero close-up：

```text
DOF on
```

---

# 58. Atmosphere

高级感的推荐顺序：

```text
light direction
↓
atmospheric perspective
↓
foreground/mid/background separation
↓
controlled haze
↓
volumetric accents
```

不是：

```text
全场加厚雾
```

---

# 59. World-Class Look Checklist

每个 cinematic shot：

```text
[ ] foreground exists
[ ] midground readable
[ ] background depth exists
[ ] light direction clear
[ ] subject silhouette readable
[ ] material scale believable
[ ] atmospheric perspective present when appropriate
[ ] camera has purpose
[ ] motion has purpose
[ ] one focal hierarchy
```

---

# 60. AI 与 Blender 混合

Blender 不需要承担所有纹理/背景。

可用：

```text
AI matte painting
↓
projection / card
↓
Blender camera / foreground / physics
```

或者：

```text
Blender deterministic render
↓
AI visual enhancement
↓
Resolve composite
```

但任何 AI pass 都必须保持：

```text
camera
physics
screen direction
identity
```

---

# 61. 科学镜头优先级

Earth Stop 这类内容：

```text
S001 Ground Lock
Blender

S002 Human inertia
Blender + AI/character insert

S003 465m scale
Blender/Fusion

S004 atmosphere
Blender + Physical Atmosphere

S005 ocean inertia
shader / FLIP only if hero

S006 land-air-water mismatch
Blender deterministic cutaway

S007 gravity vector
Fusion
```

这样比：

```text
7 个 Flow clips
```

更可靠。

---

# 62. Blender Fast QC

Blender QC 不直接检查 Final 4K/1080 全帧。

流程：

```text
render 540p proxy
↓
first/mid/last frames
↓
contact sheet
↓
motion metrics
↓
only suspicious full frame
```

---

# 63. Pre-render QC

正式 render 前：

```text
camera active
resolution correct
fps correct
frame range correct
missing texture check
missing linked library check
NaN object transform check
hidden hero object check
plugin dependency check
cache ready
output writable
```

任一失败：

```text
do not render
```

---

# 64. Preview QC

Agent 默认只看：

```text
3 representative frames
+
4–8 sec 540p proxy
```

不要打开所有 rendered frames。

---

# 65. Render Fail Recovery

必须使用 image sequence，因此：

```text
frame 1–70 complete
frame 71 crash
```

恢复：

```text
start frame 71
```

不要重新渲染 1–70。

---

# 66. Hash-Based Cache

计算：

```text
scene config hash
asset hash
script hash
plugin profile hash
```

未变化：

```text
reuse preview
reuse simulation
reuse QC
```

---

# 67. Benchmark Scene

创建：

```text
benchmarks/hajimi_blender_benchmark.blend
```

包含：

```text
PBR road
glass
metal
volumetric haze
scatter grass/rock
moving camera
simple rigid body
sun + HDRI
```

---

# 68. Benchmark Tasks

自动：

```text
10 sec viewport benchmark
10 preview frames Eevee
1 Cycles frame
headless render
GPU denoise
plugin smoke test
```

记录：

```json
{
  "eevee_preview_fps": 0,
  "eevee_frame_sec": 0,
  "cycles_frame_sec": 0,
  "gpu": "...",
  "backend": "...",
  "date": "..."
}
```

不规定全球统一“必须几秒”。

只用于：

```text
本机 regression baseline
```

---

# 69. Plugin Smoke Scene

Geo-Scatter：

```text
plane + 100 instances
```

PA²：

```text
sun + atmosphere
```

Photographer：

```text
camera exposure + physical light
```

FLIP：

```text
small domain preview
```

botaniq：

```text
spawn one plant
```

只有 smoke test 成功：

```text
READY
```

---

# 70. Blender Skill

新增：

```text
.agents/skills/blender-production/SKILL.md
```

建议完整内容：

```markdown
---
name: blender-production
description: Build deterministic cinematic Blender shots for Hajimi.
triggers:
  - Blender shot
  - deterministic 3D
  - simulation
  - scientific visualization
  - cinematic 3D environment
---

# Objective

Create reproducible, cinematic, physically legible Blender shots for Hajimi.

Blender is a deterministic visual backend, not the final editor.

# Inputs

- episode.yaml
- shot.yaml
- creative brief
- storyboard frame
- reference images
- approved asset library

# Required Workflow

1. Read shot intent.
2. Decide if Blender is actually the correct production method.
3. Load the Hajimi camera rig.
4. Build blocking at P0.
5. Validate composition.
6. Build environment and materials.
7. Add lighting / atmosphere.
8. Add simulation only if required.
9. Render P1 proxy.
10. Run Fast QC.
11. Fix only QC failures.
12. Render P3 image sequence.
13. Write render manifest.
14. Handoff to Resolve.

# Production Method Rules

Use Geometry Nodes for procedural/repeated structures.

Use Geo-Scatter for large environment dressing.

Use Physical Atmosphere² for exterior atmospheric lighting when appropriate.

Use Photographer for camera/exposure/IES/gobo workflow.

Use FLIP only for hero liquid simulations.

Use local curated assets before online search.

# Renderer

Default: Eevee.

Use Cycles only when the shot demonstrates a real visual requirement.

# Camera

Every shot must use the Hajimi camera rig.

No arbitrary zoom animation.

Preserve storyboard screen direction.

# Performance

Blocking before detail.

Proxy before final.

Instance before duplicate.

Low-density scatter before final density.

Never bake high-quality simulations before camera approval.

# QC

Never ask an LLM/VLM to inspect all rendered frames.

Use P1 proxy and representative frames.

Reuse QC by content hash.

# Forbidden

- No direct MP4 final from Blender.
- No static image slow zoom masquerading as a 3D shot.
- No plugin effect added only to look "cinematic".
- No global high-quality Cycles default.
- No 8K textures on invisible/background assets.
- No untracked online asset.
- No render before preflight passes.
- No old cached simulation after scene hash changes.

# Output

shots/<shot_id>/
  scene.blend
  shot.yaml
  build_scene.py
  preview/
  render/
  qc/
  logs/

# Handoff

Return:
- render status
- frame range
- renderer
- dependencies
- QC status
- output path
```

---

# 71. Blender Bootstrap Skill

新增：

```text
.agents/skills/blender-bootstrap/SKILL.md
```

职责：

```text
install/configure/verify Blender production environment
```

它不生成创意镜头。

---

# 72. 配置文件

创建：

```text
config/blender.yaml
```

示例：

```yaml
version:
  required: "5.2.2"

paths:
  assets_env: HAJIMI_ASSETS
  installers_env: HAJIMI_INSTALLERS
  extensions_env: HAJIMI_BLENDER_EXTENSIONS

render:
  default_engine: EEVEE
  final_width: 1080
  final_height: 1920
  final_fps: 30

cycles:
  auto_detect_device: true

assets:
  prefer_local: true
  allow_online_fallback: true

plugins:
  photographer:
    required: true
  geoscatter:
    required: true
    expected_version: "5.6.4"
  physical_atmosphere:
    required: true
  poliigon:
    required: false
    expected_version: "1.16.3"
  flip_fluids:
    required: false
    expected_version: "1.8.8"
  botaniq_engon:
    required: false

qc:
  proxy_width: 540
  proxy_height: 960
  sample_frames: 3
  use_cache: true
```

---

# 73. 目录

在 Hajimi V2 仓库增加：

```text
blender/
├── scripts/
│   ├── startup/
│   │   └── hajimi_bootstrap.py
│   ├── doctor.py
│   ├── configure_gpu.py
│   ├── configure_assets.py
│   ├── configure_render.py
│   ├── benchmark.py
│   └── render_shot.py
├── templates/
│   ├── short_9x16.blend
│   ├── science_cutaway.blend
│   ├── cinematic_exterior.blend
│   └── studio_diagram.blend
└── presets/
```

---

# 74. Template — `short_9x16.blend`

必须已有：

```text
Camera Rig
Safe Guides
World
Collections:
  ENV
  SUBJECT
  FX
  LIGHTS
  HELPERS
  RENDER_ONLY
  QC
```

默认：

```text
1080×1920
30fps
Eevee
```

---

# 75. Collections 规则

```text
ENV
SUBJECT
PROPS
FX
LIGHTS
HELPERS
CAMERA
RENDER_ONLY
```

禁止：

```text
Collection
Collection.001
Cube.031
```

---

# 76. Naming

```text
CAM_Main
LGT_Key
LGT_Rim
ENV_Road
ENV_City
SUB_Person
FX_Dust
GEO_VectorTrail
```

AI Agent 操作场景时必须使用可预测名字。

---

# 77. Scene State

脚本执行必须幂等。

即：

```text
build_scene.py
run twice
```

不能生成：

```text
CAM_Main.001
CAM_Main.002
```

必须：

```text
create or update
```

---

# 78. Logging

每次 background job：

```text
logs/<timestamp>.jsonl
```

记录：

```text
operation
duration
frame
GPU
renderer
error
output
```

---

# 79. Crash Policy

如果 Blender crash：

1. 不立即重跑三次。
2. 检查 last log。
3. 检查 frame。
4. 检查 plugin。
5. 若 plugin-related，disable optional plugin。
6. 从失败 frame 恢复。

---

# 80. Resolve Handoff

Blender Final：

```text
shots/S005/render/final/####.png
```

输出 sidecar：

```text
render_manifest.json
```

```json
{
  "fps": 30,
  "start": 1,
  "end": 126,
  "alpha": true,
  "color_space": "...",
  "passes": ["combined"]
}
```

Resolve ingest 只读 manifest。

---

# 81. Alpha

只有需要合成：

```text
transparent background
```

才开 alpha。

不要所有镜头都 RGBA。

---

# 82. EXR

只有：

```text
real compositing need
```

才用 EXR。

一般 Shorts：

```text
PNG
```

足够快。

---

# 83. Blender → Fusion

适合输出：

```text
depth
normal
vector
cryptomatte
```

用于：

```text
fog
tracked graphic
depth composite
motion graphics
localized grade
```

---

# 84. Blender 不做最终字幕

严格禁止：

```text
Text Object = subtitles
```

除非文字是真实世界场景的一部分。

字幕：

```text
Resolve
```

Story Typography：

```text
Fusion
```

---

# 85. Blender 不做最终音乐/音效

Blender Audio：

```text
temporary timing only
```

最终：

```text
Fairlight
```

---

# 86. 安装顺序

AI Agent 必须：

## Phase 1

```text
detect Blender
lock 5.2.2
doctor
```

## Phase 2

```text
configure GPU
configure paths
configure Asset Browser
```

## Phase 3

```text
install/validate P0 plugins
```

顺序：

```text
Photographer
Physical Atmosphere²
Geo-Scatter
```

## Phase 4

```text
optional asset tools
Poliigon
engon/botaniq
```

## Phase 5

```text
FLIP if license exists
```

## Phase 6

```text
create templates
create Geometry Nodes library
```

## Phase 7

```text
benchmark
```

## Phase 8

```text
build EP001 test shot
```

---

# 87. EP001 Validation Shot

不要一上来做完整 EP001。

先做：

```text
EP001_TEST_01
```

画面：

```text
9:16
city road
one person proxy
red loose paper
late-afternoon light
dust
ground locks
paper continues screen-right
camera subtle pull-back
```

必须验证：

```text
camera
lighting
atmosphere
motion
screen direction
render
QC
Resolve handoff
```

---

# 88. Acceptance Criteria

## Core

- [ ] Blender 5.2.2 LTS installed / detected.
- [ ] Headless command works.
- [ ] Python bpy works.
- [ ] Eevee works.
- [ ] Cycles GPU works.
- [ ] 1080×1920 / 30fps template exists.

## GPU

- [ ] Correct compute backend selected.
- [ ] GPU render smoke test passes.
- [ ] GPU denoise smoke test passes when supported.

## Plugins

- [ ] Photographer installed or correctly BLOCKED.
- [ ] Geo-Scatter 5.6.4 installed or correctly BLOCKED.
- [ ] PA² installed or correctly BLOCKED.
- [ ] Every installed plugin passes smoke test.
- [ ] Optional plugin failure does not break Blender startup.

## Assets

- [ ] Hajimi Curated registered.
- [ ] Cameras library registered.
- [ ] Materials library registered.
- [ ] Environments library registered.
- [ ] FX library registered.
- [ ] Asset source/license metadata stored.

## Automation

- [ ] `hajimi blender doctor` works.
- [ ] `hajimi blender benchmark` works.
- [ ] `hajimi blender build` works.
- [ ] `hajimi blender preview` works.
- [ ] `hajimi blender render` works.

## Performance

- [ ] P0 blocking render works.
- [ ] P1 proxy render works.
- [ ] Final image sequence resumes from partial render.
- [ ] Scatter uses preview density.
- [ ] Heavy simulation has preview/final modes.

## QC

- [ ] Pre-render check exists.
- [ ] Proxy QC exists.
- [ ] Representative-frame QC exists.
- [ ] Hash cache exists.
- [ ] Full-frame VLM scanning is not default.

## Resolve

- [ ] Final image sequence imports correctly.
- [ ] FPS matches.
- [ ] color/alpha verified.
- [ ] sidecar manifest exists.

---

# 89. AI Agent 执行总指令

把以下内容作为 Codex 当前任务：

```text
你现在负责把本机 Blender 配置为 Hajimi V2 的正式 Production Backend。

不要只安装插件。
不要追求插件数量。
不要修改 Hajimi 的最终视频时长策略。
不要把 Blender 变成最终剪辑器。

严格执行《Hajimi Blender Production Stack》：

1. 检测当前 Blender 与硬件。
2. 将 Production baseline 锁定为 Blender 5.2.2 LTS。
3. 自动识别正确的 GPU / Cycles backend。
4. 创建 Blender doctor。
5. 创建独立的 Hajimi Blender config / cache / assets / extensions 目录。
6. 配置 Asset Browser。
7. 如果合法安装包已经存在，安装并验证：
   - Photographer 5
   - Geo-Scatter 5.6.4
   - Physical Atmosphere²
8. 如果存在对应包，再安装验证：
   - Poliigon 1.16.3
   - current engon / botaniq
   - FLIP Fluids 1.8.8
9. 不允许从非官方来源搜索付费插件。
10. 插件缺失要标记 BLOCKED，不得阻塞核心 Blender pipeline。
11. 创建 Hajimi Camera Rig。
12. 创建 9:16 Shorts template。
13. 创建 render profiles。
14. 创建本项目 Geometry Nodes reusable library。
15. 创建 headless scene-build/render scripts。
16. 创建 Fast Blender QC。
17. 创建 benchmark scene。
18. 跑 benchmark 并保存 baseline。
19. 创建 blender-production Skill。
20. 创建 blender-bootstrap Skill。
21. 用 EP001_TEST_01 验证完整流程：
    scene build
    → preview
    → QC
    → final image sequence
    → Resolve handoff manifest。
22. 不允许高质量 simulation 在 camera lock 前 bake。
23. 不允许默认 Cycles。
24. 不允许 Blender 直接输出 final MP4。
25. 不允许所有帧进入 LLM/VLM QC。
26. 不允许把商业插件的 license/token 写入 Git。
27. 所有变更、测试结果、blocked dependency 使用 Beads 跟踪。

完成后必须输出：

- Blender Doctor report
- hardware profile
- plugin matrix
- asset library matrix
- benchmark result
- generated templates
- Geometry Nodes library inventory
- EP001_TEST_01 preview
- EP001_TEST_01 QC report
- Resolve handoff manifest
- remaining BLOCKED items
```

---

# 90. Agent 不得做的事情

```text
❌ 自动升级到 Blender 非 LTS
❌ 安装几十个随机插件
❌ 破解付费插件
❌ 把最终视频交给 Blender VSE 完成
❌ 全程 Cycles
❌ 每镜头 4K
❌ 所有纹理 8K
❌ 动画未确认就 bake 高成本 simulation
❌ 直接 MP4 final render
❌ 全帧 VLM QC
❌ 把 Vendor Assets 直接当 Curated Assets
❌ 把 PA² / Geo-Scatter / Photographer 当作“一键电影感”
❌ 让插件决定 Camera / Story / Shot Design
```

---

# 91. 优化优先级

如果资源有限，按：

```text
Camera
>
Lighting
>
Composition
>
Materials
>
Atmosphere
>
Environment detail
>
Simulation
>
Post effects
```

永远不要倒过来。

---

# 92. 最重要的原则

Blender 最终看起来“世界一流”，不是因为装了插件。

正确关系：

```text
Shot Design
×
Camera
×
Lighting
×
Material
×
Atmosphere
×
Motion
×
Sound
```

插件只是把其中某些步骤变快。

Hajimi 的 Blender Stack 必须做到：

> **Agent 能稳定、快速、可复现地构建高质量镜头，而不是每次临时手搓一个 Blender 项目。**

---

# 93. 当前已核实版本与依据

截至 2026-09-17：

## Blender

```text
5.2.2 LTS
2026-09-15
5.2 LTS support until 2028-07
```

官方：
https://www.blender.org/releases/5-2/

## Blender GPU

Apple Silicon：

```text
Metal
GPU ray tracing
GPU denoising
```

官方：
https://docs.blender.org/manual/en/5.2/render/cycles/gpu_rendering.html

## Geo-Scatter

```text
5.6.4
Blender 5.2 LTS
2026-07-17
```

官方：
https://www.geoscatter.com/docs-changelogs.html

## Physical Atmosphere²

```text
requires Blender 5.2.0+
Vulkan recommended where supported
```

官方：
https://www.physicaladdons.com/physical-atmosphere/getting-started/

## Poliigon

```text
Addon 1.16.3
tested Blender 5.2
```

官方：
https://help.poliigon.com/en/articles/11657058-poliigon-blender-addon-changelogs

## FLIP Fluids

```text
1.8.8
official Blender 4.5–5.2 support
```

官方：
https://flipfluids.com/category/development/

## Photographer 5

当前官方说明：

```text
Blender 3 / 4 / 5.x
EEVEE
Cycles
```

官方：
https://chafouin.gumroad.com/l/photographer5
https://sites.google.com/view/photographer-5-documentation

## engon / botaniq

engon 1.10.0（2026-08-28）包含 Blender 5.2 修复和 botaniq 相关更新。

官方：
https://docs.polygoniq.com/engon/1.10.0/endnotes/release_log/

---

# 94. 最终交付形态

重构完成后，Blender 子系统应该像这样工作：

```text
Codex
│
├── blender doctor
│
├── blender asset search
│
├── blender build shot
│       ├── camera
│       ├── environment
│       ├── lighting
│       ├── assets
│       └── simulation
│
├── render P0
├── director review
├── render P1
├── fast QC
│
├── render final image sequence
│
└── Resolve ingest
```

而不是：

```text
AI 打开 Blender
→ 随便摆东西
→ 装很多插件
→ Cycles 拉满
→ 等几十分钟
→ 成片还是普通
```

这就是 Hajimi Blender Production Stack 的最终标准。
