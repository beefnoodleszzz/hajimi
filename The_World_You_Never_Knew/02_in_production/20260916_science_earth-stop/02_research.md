# Research Pack

> 选题：What If Earth Stopped Spinning for One Second?  
> 研究日期：2026-09-16（Asia/Shanghai）  
> 研究范围：只支持首条 45–55 秒 Shorts 的关键事实；不是完整地球物理模拟。

## 1. 情景定义

这是一个明确的思想实验：假设地球自转在瞬间被外力“冻结”一秒，然后恢复。这个机制在现实中不可行；视频只讨论瞬间停止后的一阶相对运动，不把假设包装成真实预言。

## 2. 已确认事实

### F1 — 地球自转周期约为一天

NASA 说明地球相对太阳每 24 小时自转一周；相对恒星的自转周期约为 23 小时 56 分钟。[S1]

### F2 — 赤道表面速度约为 465 m/s

NASA GSFC 给出赤道周长约 40,074 km、自转周期 86,164 s，并计算得到约 0.4651 km/s，即 465.1 m/s。[S2]

### F3 — 停止自转时，未固定物体会向东保持运动，速度随纬度变化

NASA Cosmicopia 的问答直接说明：如果地球停止自转，未附着的物体会向东、平行于地表飞出；速度取决于纬度，极点附近几乎不受这一切向速度影响。[S3]

### F4 — 不会因为这一个速度直接飞入太空

同一 NASA 问答说明：即使在赤道约 1000 mph 的最大速度下，重力仍然存在，速度不足以克服地球引力使人飞入太空。[S3]

### F5 — 地球自转会影响风和海洋运动的方向

NOAA 说明，科里奥利效应来自地球自转，会使北半球运动中的空气向右偏、南半球向左偏；海洋表层流也受到全球风系和科里奥利效应影响。[S4][S5]

### F6 — 现实中的“突然停转”没有可行机制

NASA 的科普问答指出，地球具有巨大的角动量和能量，突然停止需要吸收巨大的能量与角动量；一个足够大的碰撞本身会造成灾难。[S6] 这条作为脚本的限定语，不进入主 Hook。

## 3. 推导与合理推演

### D1 — 一秒内的简化相对位移

以赤道为例：

```text
v ≈ 465 m/s
t = 1 s
d ≈ v × t ≈ 465 m
```

这是基于 NASA 赤道速度的简化推导，不是对真实地形、空气阻力、人体姿态和结构破坏的精确模拟。脚本使用“roughly 465 meters relative to the ground”，并保留 `under this simplified model` 的限定。

### D2 — 纬度差异

在球形地球近似下，某纬度的自转切向速度可写成：

```text
v(latitude) ≈ 465 × cos(latitude) m/s
```

因此不能把赤道的 465 m/s 或约 1000 mph 说成全地球统一速度；两极的切向速度接近 0。这个关系是几何推导，视频只用“the speed depends on latitude”表达，避免堆公式。

### D3 — “地面停下、物体继续动”

这是惯性导致的相对运动推演：如果地表被假定瞬间停止，而未被刚性固定的物体没有同时获得相反冲量，它会在惯性参考系中暂时保持原有切向速度。NASA 的 F3 对该思想实验给出同方向结论；视频不声称已经完成真实灾害数值模拟。

### D4 — 停止后恢复会有额外冲击

如果一秒后地球表面又瞬间恢复原来的自转速度，地面、空气、海水和物体之间的速度差会造成极端的相对运动。这里使用 `catastrophic mismatch` 作为物理推演的概括，不量化具体伤亡、海啸高度或全球地貌变化。

## 4. Claim Map：脚本逐句回指

| 脚本段落 | 类型 | 依据 |
|---|---|---|
| “Assume a magical, instantaneous halt...” | 情景假设 | 片头主动限定，不冒充事实 |
| “The ground would stop—but you wouldn’t.” | 合理推演 / Hook | F3、D3 |
| “At the equator... about 465 meters per second...” | 已确认事实 | F2 / S2 |
| “Your body, the air, and the oceans would keep that sideways motion.” | 合理推演 | D3；不做精细流体模拟 |
| “In one second, roughly 465 meters relative to the ground.” | 计算推演 | D1 |
| “The poles are different...” | 已确认事实 + 简化解释 | F3、D2 |
| “Gravity would still hold you to Earth.” | 已确认事实 | F4 / S3 |
| “Restart... catastrophic mismatch...” | 合理推演 | D4；不量化结果 |
| “Spin helps bend global winds and ocean currents...” | 已确认事实的简化表达 | F5 / S4 / S5 |

## 5. 明确不使用的说法

- `Everyone would be thrown at 1,000 mph.` —— 速度随纬度变化，且 NASA 只给出赤道最大值。
- `Everyone would fly into space.` —— 与 NASA 的重力说明相冲突。
- `The atmosphere would disappear instantly.` —— 本条没有足够来源支持，也不是一秒 Shorts 必须回答的内容。
- `Mile-high tsunamis would sweep the planet.` —— 使用夸张且未经本条研究包量化的说法。
- `Earth would explode.` —— 把灾难性相对运动偷换成行星爆炸，删掉。

## 6. 来源

- [S1 — NASA Science, Chapter 2: Reference Systems](https://science.nasa.gov/learn/basics-of-space-flight/chapter2-1/)，访问日期 2026-09-16。
- [S2 — NASA GSFC, The Rotating Earth](https://pwg.gsfc.nasa.gov/stargaze/Srotfram1.htm)，访问日期 2026-09-16。
- [S3 — NASA Cosmicopia, Earth and Moon Q&A（What Happens if Earth Stops Rotating?）](https://cosmicopia.gsfc.nasa.gov/qa_earth.html)，访问日期 2026-09-16。
- [S4 — NOAA JetStream, Origin of Wind](https://www.noaa.gov/jetstream/synoptic/origin-of-wind)，访问日期 2026-09-16。
- [S5 — NOAA National Ocean Service, The Coriolis Effect — Currents](https://oceanservice.noaa.gov/education/tutorial_currents/04currents1.html)，访问日期 2026-09-16。
- [S6 — NASA GSFC, Get a Straight Answer — If Earth's Rotation Would Stop](https://pwg.gsfc.nasa.gov/stargaze/StarFAQ10.htm)，访问日期 2026-09-16。

## 7. 事实复核结果

- [x] 关键数字有 NASA 来源。
- [x] 一秒位移明确标为简化推导。
- [x] 纬度差异已写入脚本与镜头说明。
- [x] 未把“停转”与“停止绕太阳公转”混淆。
- [x] 已删除无来源的海啸高度、全球灭绝和大气消失断言。
