# H3 官方提示词规范（实测验证版）

> **2026-10-09 立** ｜ 来源：MiniMax 官方 [VIDEO_PROMPT_WRITING_GUIDE_base_en.md](https://hf-mirror.com/MiniMaxAI/MiniMax-H3/raw/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)（HF 被墙，走 hf-mirror 镜像拿到）
> **实测结论：按官方格式写的提示词，动作完整性/到位率/连贯性全面优于我们原来的简略写法**（A/B 对比，同首尾帧、同参数）

---

## 一、提示词结构（FL2VA 首尾帧模式）

```
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with
the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 4.00-second
mark of the target video.
                                                       ← 必须空一行
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

**第一行的对齐指令是硬要求**，格式随任务类型变：

| 模式 | 第一行 |
| --- | --- |
| **T2VA**（纯文） | **无**对齐指令，直接三字段 |
| **I2VA**（首帧） | `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` |
| **FL2VA**（首尾帧） | `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` |
| **L2VA**（尾帧） | `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.` |

`S.SS` = 实际时长，**两位小数**（如 4.00）。

---

## 二、三个核心字段怎么写

| 字段 | 内容 | 约束 |
| --- | --- | --- |
| `integrated_multimodal_description` | 画面、动作、镜头、说话人、对白、diegetic 音效，**按时间线** | `[Shot 1]` 开头先写**风格 + 初始构图**（风格词：Cinematic / live-action / 2D-animated / 3D CG / claymation / watercolor / vintage film）；后续镜头 `[Shot 2] At 00:03.500, the camera cuts to...`（**首个镜头不加时间戳**，切割时间严格递增） |
| `overall_soundscape` | 环境音 + 动作音 + 非语言人声 | **1–4 句英文一段**；**不要重复对白/歌声/diegetic 音乐**（那些已在上一段）；全片静音才写 `N/A` |
| `non_diegetic_music` | 观众能听到、角色听不到的音乐 | **1–3 句**；写**配器/速度/节奏/动态**，**不要写抽象情绪词**；没有就写 `N/A` |

### FL2VA 正文的关键要求（我们之前全错了）

> 两张图**只是锚点** —— 正文**不要重复描述两张静态图**，而要写**连通它们的运动路径**。

推荐结构：**首帧状态 → 可观察的中间变化 → 差异逐步收窄 → 尾帧状态**
且**尾帧必须在最后一个 `[Shot N]` 的结尾达成**。FL2VA **默认单镜头**（便于连续插值），要多镜头必须显式写明。

### 镜头运动 = 类型 + 幅度 + 速度

| 维度 | 写法 |
| --- | --- |
| 类型 | `Zoom In/Out` `Push In/Pull Out` `Pan Left/Right` `Truck Left/Right` `Tilt Up/Down` `Pedestal Up/Down` `Arc Shot` `Tracking Shot` `Static Shot` `Shake Slightly/Strongly` `POV` `Roll Clockwise/Counterclockwise` |
| 幅度 | `with small amplitude` / `with large amplitude` |
| 速度 | `at slow speed` / `at fast speed` |

写成**句内自然英文**，别在句尾堆标签：
```
The camera pushes in with small amplitude at slow speed toward the folded letter in her hands.
```

### 对白格式

```
The young woman with a quiet, breathy voice (S1) says: <d>[English] I get off at the next station.</d>
```
- 说话人用稳定 ID `(S1)`；合唱 `(S1,S2)`；**不出声的角色不给 ID**
- **`<d>` 内只放语言标签 + 原始台词**（逐字保留、不翻译）；身份描述/动作/语气放 `<d>` **外面**
- 画外音用固定短语 `says in an off-screen voiceover`，且紧跟一句"嘴唇完全闭合"
- 台词跨剪切用 `<scenetrans>`；被片尾截断用 `<cutoff>`

### 画面上的文字

实际可见的招牌/字幕/霓虹：用英文双引号包裹、**原样保留**：
```
A red neon sign reading "营业中" glows above the doorway.
```

---

## 三、A/B 实测（2026-10-09，同首尾帧同参数）

| 版本 | 提示词 | 动作完整性 | 到达尾帧姿态 | 连贯性 | 耗时 |
| --- | --- | --- | --- | --- | --- |
| **A** | **官方格式**（含对齐指令＋运动三要素） | ✅ 完整（站→闭眼→抬手→挥手） | ✅ **到位** | ✅ 更好 | 269 秒 |
| B | 我们的旧写法（无对齐指令） | ⚠️ 幅度小 | ❌ 抬手不到位 | 一般（第 3–6 帧近乎停滞） | 252 秒 |

清晰度/细节两者无显著差异 —— **差别全在"动作是否正确执行"**。

---

## 四、落地时的坑

1. 🔴 **WanGP 必须设 `multi_prompts_gen_type: "FG"`**
   官方格式的提示词**天然多行**，WanGP 默认 `PG` 会**按换行把一条 prompt 拆成 4 个请求**，直接报错：
   `parses this prompt into 4 separate generation requests... use 'FG' if the line breaks belong to one prompt`
2. HF 直连不通 ⇒ 走 `hf-mirror.com`（`https://hf-mirror.com/<repo>/raw/main/<path>`）
3. 官方文档还提到：H3 原生 24fps，**帧数向上取整到 `17k+5`**（5 秒 → 124 帧 ≈ 5.167 秒）—— 与实测 97 帧≈4.04 秒一致

---

## 五、可复制的完整模板（FL2VA，4 秒）

```
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 4.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] 2D semi-realistic anime, cinematic golden-hour light, a medium shot frames <角色> exactly as established by Picture 1, with <场景> behind. She begins from the still pose of Picture 1, then gradually <中间动作>; at the same moment <次要动态>. Her head tips slightly and <表情变化> as the motion settles into the pose, spacing, and composition established by Picture 2 at the end of the shot. The camera holds a static shot with small amplitude, keeping the character and <场景锚点> in the same framing from beginning to end.

overall_soundscape: <环境音 1–2 句> <动作音 1 句>

non_diegetic_music: <配器+速度+动态，或 N/A>
```
