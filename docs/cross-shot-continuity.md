# 跨镜连续性 · 社区做法调研

> **调研范围**：开源视频生成模型（MiniMax H3 / Wan 2.x / LTX-2.x）＋ ComfyUI / WanGP 工作流里，多镜头拼装时如何保持角色姿态、道具位置、手持物连续。
> **检索日期**：2026-10-15（所有链接当日实读；平台/仓库行为会漂移，参数请以自己环境复测为准）
> **可信度图例**：①**官方**（厂商/项目官方文档、官方 PR、论文）｜②**实测**（作者给出了可复现做法或量化数据）｜③**推测/低可信**（无可复核证据、营销或 SEO 内容）
> **方法说明**：GitHub 正文通过 ghproxy 镜像读取，HuggingFace 通过 hf-mirror 读取（本机网络直连 github.com / huggingface.co 失败）。**Reddit、B站、知乎正文未读到**（fetch 被拦），详见第五节。

---

## 一、结论（可直接执行的清单，按推荐顺序）

**先立账，再拍片；能用 latent 就别走像素；硬锚点要防"冻住"，软引导要防"漂走"。**

1. **建连续性台账（每镜一行）**：入口状态 → 变化事件 → 出口状态。字段至少含「人物空间 / **持物与手部** / 造型 / 环境 / 摄影 / 声音」六类。跨镜靠记录，不靠记忆。〔②〕[ADC1920/continuity-log.md](https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/continuity-log.md)
2. **每镜先出关键帧图，再出视频**：构图问题在静态图上改，成本约为视频段的 1/15–1/20。〔②〕[ADC1920/SKILL.md](https://github.com/ADC1920/AI-short-play-video-creation/blob/main/SKILL.md)
3. **上一镜结尾 → 下一镜开头，第一选择是"尾帧接首帧"**：抽上一段尾帧当下一段的首帧/start_image；同一序列内**只用一种**衔接方式，不同时混用"分镜图首帧"和"尾帧接力"。〔②〕[fxi-frame-chain](https://github.com/fueledximagination/comfyui-fxi-frame-chain)、[ADC1920/SKILL.md](https://github.com/ADC1920/AI-short-play-video-creation/blob/main/SKILL.md)
4. **不要用"字面上的最后一帧"**：模型末帧常发糊/发暗/冻结。抽尾帧时往前偏（`offset_from_end`）或按窗口丢弃末段帧；首尾帧接续时也要裁掉被冻结的落地帧。〔②〕[fxi-frame-chain](https://github.com/fueledximagination/comfyui-fxi-frame-chain)、〔①〕[WanGP PROCESSING.md](https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/PROCESSING.md)、〔②〕[Herrgotts-H3-Infinite-Continuation-Suite](https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite)
5. **能用 latent 接续，就不要每段都解码成 MP4 再编码**：像素往返会累积掉细节/对比/纹理/身份；H3 系已有多个 latent 级接续实现；WanGP 也有对应插件。〔②〕[SatoDive](https://github.com/SatoDive/Minimax-H3-Latent-Continuation)、[HerrgottMargott](https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite)、[g3n3rativ3/wan2gp-h3-latent-continue](https://github.com/g3n3rativ3/wan2gp-h3-latent-continue)
6. **提示词里把"跨镜不变的事实"逐字带进每一镜正文**（锁面＝最小可辨识名词短语，如 `pale blue chunky knit wool sweater`），**状态（姿势、左右手、持有人、破损进度）不要上锁**。〔②〕[zenstory-ai/drama-skills/continuity-lock.md](https://github.com/zenstory-ai/drama-skills/blob/main/skills/short-drama-assets/references/continuity-lock.md)
7. **每段末尾写"具体末帧画面"**（谁＋在哪＋什么姿态＋关键道具状态），不要写"严格继承上一段"这类套话。〔②〕[ADC1920/continuity-log.md](https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/continuity-log.md)
8. **接缝位置要选，不要随机**：放场景切换处、人物换气/视线转开瞬间、重音之后；**绝不放**句子中间、连续运镜中途、大幅动作中段。〔②〕[God-minmax-H3/stitching.md](https://github.com/LIUFelix2004/God-minmax-H3/blob/main/references/stitching.md)
9. **接缝做帧级对齐**：每段裁掉生成余量、对齐整拍网格；裁掉上一段末尾数帧＋下一段开头 1 帧（fxi 的 `drop_seam_frames` 就是干这个）。〔②〕[ADC1920/transition-editing.md](https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/transition-editing.md)
10. **参考密集的镜头别开蒸馏加速**：H3 官方明确写「4 步时参考几乎不生效，主体姿态/脸角度会随片段漂走」，参考要紧就关掉 Lightning LoRA 跑 20 步（必要时 25 步）。〔①〕[docs.comfy.org MiniMax H3](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
11. **长链要设"重新锚定"上限**：同一来源链最多连续 2 段（硬上限 3 段），到上限／跨场景／发现漂移 → 从长期母版重新锚定。〔②〕[xixihhhh/ai-short-drama-skill](https://github.com/xixihhhh/ai-short-drama-skill/blob/v0.3.2/skills/dramake/references/project-state.md)
12. **重生有预算**：单集重生段数控制在 ~10% 以内，超了先停下查系统性原因（素材/提示词），别硬刷；同一镜失败 3 次 → 简化镜头契约或拆成两条。〔②〕[ADC1920/SKILL.md](https://github.com/ADC1920/AI-short-play-video-creation/blob/main/SKILL.md)、[Emily2040/seedance-2.0](https://github.com/Emily2040/seedance-2.0/blob/main/references/shot-list-continuity.md)

---

## 二、手法逐条

### 2.1 连续性台账 / 交接单（所有手法的地基）

- **做法**：每镜记「入口状态 → 变化事件 → 出口状态」，并按**连续性分级**决定处理强度——**硬连续**（身份、空间方向、**关键道具**、动作因果、伤势阶段、台词事实）冲突＝P0 必修；**表演连续**（目标、注意对象、呼吸、动作相位）通常 P0/P1；**软连续**（衣褶、细小背景、轻微手位）优先用剪辑/遮挡处理；**有意断裂**（越轴、跳切）必须写清意图。附带「接镜检查」：比较**上一镜最后可用帧**与本镜第一可用帧，写差异表（字段/上一状态/本镜状态/严重级/是否有意/首选修法/验收条件）。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/continuity-log.md>
- **另一个版本（英文侧）**：Shot List 增加 Continuity anchors 字段（wardrobe / prop / screen direction / light state / background layout），并维护 Continuity Ledger 九类锚点；进阶做法是把"松散台账"换成 **clip lineage**：`parent_clip_id` + 计划的起止状态 + **复核后观测到的起止状态** + 连续性锁与允许的变化 + 转场与开放运动矢量。**只把当前未定的那一条镜头提示词定稿，后面的镜头卡保持临时态。**〔②〕<https://github.com/Emily2040/seedance-2.0/blob/main/references/shot-list-continuity.md>
- **父子段依赖（把"上一镜结尾"结构化的写法）**：依赖段记录 `scene_id`、`parent_block_id`、**父段 `observed_exit_state`**、自身 `entry_state`、未完成运动与转场方式；**已完成节拍不得重演，未来节拍不得提前泄漏**；验收素材的实际状态优先于计划。〔②〕<https://github.com/xixihhhh/ai-short-drama-skill/blob/v0.3.2/skills/dramake/references/project-state.md>
- **适用场景**：多集/多镜、一个镜头多次重生成、交接给他人或未来的自己。
- **可信度**：②（这些是工程化规则文档，不是模型行为声明；其内部数字/阈值多为作者自定）

### 2.2 尾帧接力 / Frame Chaining（像素级，最通用的做法）

- **做法**：clip N 生成完 → 抽出它的最后一帧 → 作为 clip N+1 的起始图（I2V 的 start_image / first_frame）。ComfyUI 有现成节点：`Last Frame Extract (FXI)`、`Frame Chain Step (FXI)`、`Stitch Clips (FXI)`；后者的 `drop_seam_frames` 默认开启，用来删掉"重复的那一帧"（clip N+1 的首帧＝clip N 的尾帧，不删会顿一下）。同包还提供 `offset_from_end`（跳过糊/虚的末帧）与速度斜坡（`ramp_fast/ramp_hold/ramp_split`）。〔②〕<https://github.com/fueledximagination/comfyui-fxi-frame-chain>
- **中文实操版（更完整的一套）**：抽尾帧 `ffmpeg -sseof -0.1 -i segA.mp4 -frames:v 1 -q:v 1 segA_last.jpg` 作下一段 `role=first_frame`；并提醒"图生视频模式下 `ratio` 恒为 adaptive，**第一段的画幅就定死了全片画幅**"。〔②〕<https://github.com/LIUFelix2004/God-minmax-H3/blob/main/references/stitching.md>
- **已知坑（重要）**：
  - 模型末帧常糊/暗/冻结 → 抽帧要往前挑，或按窗口丢弃末帧。〔①〕[WanGP PROCESSING.md](https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/PROCESSING.md)「Discard Last Frames: remove weak final frames from each window when a model tends to blur at the end」
  - Wan 2.2 的尾帧问题有用户实测报告：用 Kijai wrapper 做 FLF 时「2.2 质量严重下降、最后一帧噪声极大」，2.1 则「到不了最后一帧，会提前结束」。〔②〕<https://huggingface.co/Kijai/WanVideo_comfy/discussions/77>
  - **接力帧不能当硬引导滥用**：LTX-2.3 上把上一段"解码后的尾帧"当作 shot 2 的 guide，会因为该帧是"像素可续的"，采样器选择直接复制它而不去动——表现为"旁白配一张几乎不动的脸"，作者称其为**结构性问题，任何参数都救不回来**；改法是把上一段最后约 3 秒的**视频＋音频 latent** 当上下文做真正的 extension，实测"联动镜头"的音画相关性从 ~0.1–0.4 提到 **0.64**。〔②〕<https://huggingface.co/joeygambino/ltx23-multishot-lite>
- **适用场景**：I2V 模型的连续动作、长镜头推轨、无剪辑的"一镜到底"。
- **可信度**：②（节点包与命令均是公开可复现做法）；其中"末帧糊/冻结"由多个独立项目复现（①＋②）

### 2.3 首尾帧驱动（FLF2V / FL2VA，模型内置能力）

- **做法**：给模型**同时**喂首帧和尾帧，让它在两者之间插值运动。ComfyUI 官方 Wan2.2 模板即 `WanFirstLastFrameToVideo` 节点（两个 `LoadImage`：start / end），官方建议「按你的首尾帧写提示词」、显存够就上 720P。〔①〕<https://docs.comfy.org/tutorials/video/wan/wan2_2>、<https://blog.comfy.org/p/wan22-flf2v-comfyui-native-support>
- **MiniMax H3 的对应能力叫 FL2VA**，官方支持 `first_frame` / `last_frame` 可选输入；H3 还有官方 partner-node 版 FLF2V 工作流。〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>、<https://comfy.org/workflows/ef37c26c9bbf-ef37c26c9bbf/>
- **什么时候用 FL2VA、什么时候用 Ref2VA（有实测数字）**：社区量化对比给的是 fl2va 落到目标帧 **26.35 dB**，而 ref2va+keyframe 只有 **16.15 dB（turbo 6 步）/ 16.81 dB（标准 20 步）**；作者的判据是「**ref2va：脸或声音要跨镜延续时用；fl2va：这一镜必须精确地从上一镜结束的地方开始时用**」。"一段一段推进、渲染→看→把尾帧喂给下一段"正是 fl2va 的设计场景。〔②〕<https://huggingface.co/joeygambino/MiniMax-H3-comfy-native-fl2va>
- **坑**：FL2VA 的落地帧常是"冻结/不稳定"的，社区做接续时要先检测并绕开它（见 2.5、2.6）。〔②〕<https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite>
- **可信度**：①官方能力＋②社区量化

### 2.4 时间轴多关键帧锚定（一条生成里放多个锚点）

- **做法 A（H3 原生）**：`MiniMaxH3AddGuide` 节点把任意张静图（或短视频片段）钉在时间轴的**任意帧**上，`frame_idx` 支持负数（从末尾算）；多张就串联多个 Add Guide。官方给的用例即：「把已有视频的前 22 帧＋音频钉在 frame 0，模型续写两路流」，或「在 124 帧视频的 frame 60 放一张静图，强制视频经过那一帧」。**关键限制：Add Guide 是 conditioning，不是 video-to-video，`denoise` 不会像 v2v 那样缩放引导强度**；它存在的每一步都在 conditioning 里。〔①〕[docs.comfy.org H3 native](https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native)（PR #15439）
- **做法 B（多镜头模板）**：官方 H3 Multiframe Reference 模板就是"一图一镜"的拼装法：`<Picture 1>` = 身份锁＋Shot 1 首帧，`<Picture 2>` 锚在 1.5s（Shot 2），`<Picture 3>` 锚在 3.0s，`<Picture 4>` 锚在 5.0s；**"在明确的时间戳上切镜"**，提示词按官方 full-reference 指南写（定义每个 subject、把 `<Picture N>` 映射到各镜首帧/关键帧）。注意两点：(a) 只接到 Add Guide 的图**文本编码器看不到**，想让提示词引用它必须同时插进 `ref_images`；(b) `frame_idx`＋guide 长度必须落在生成时长内。〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-multiframe>
- **做法 C（LTX 侧，多关键帧是原生 API 形状）**：`KeyframeInterpolationPipeline.interpolate(keyframe_images=[...], keyframe_indices=[...])` 本身就是**列表**；把 Shot N 的尾帧当 Shot N+1 的 keyframe-0，两段就共享一个精确边界帧，"切点隐形"。作者对"多镜头角色漂移"的实测是：**同一提示词、不同角度、不同 seed 跑三个镜头 → 得到三个不同的女人**；多关键帧的价值就是"构图变成输入，而不是提示词"。〔②〕<https://github.com/mrbizarro/Phosphene/blob/main/docs/SDK_KEYFRAME_INTERPOLATION.md>
- **做法 D（LoRA/节点级）**：社区有直接把 50 张关键帧按帧号排进 LTX 的节点（`(Deno) LTX Sequencer`，每个关键帧带 0.0–1.0 强度）；官方 LTX 工作流用的 guide strength 是 **0.7**，因为 `LTXVAddGuide` 在 strength=1.0 时会跳过 attention mask、把引导当成"同时间戳的竞争 token"追加。〔②〕<https://github.com/mrbizarro/Phosphene/blob/main/docs/SDK_KEYFRAME_INTERPOLATION.md>、<https://huggingface.co/joeygambino/ltx23-multishot-lite>
- **可信度**：①（H3/LTX 官方）＋②（社区实测细节）

### 2.5 Latent 级接续（保前缀、噪声掩码；目前"最不掉质"的一档）

- **ComfyUI 官方原语**：PR #15375 给 H3 加了**逐 token 噪声掩码**（视频与音频各自独立）：掩码 `0` = 保留该 latent 区域，`1` = 重新生成；视频掩码吸附到 2×2 latent patch 网格，音频吸附到整个 latent 帧。用途明确写着"局部重绘、去物体，或**在保持已有内容稳定的前提下延长片段**"。〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>
- **社区把它用成"精确续接"**：`ComfyUI-H3-Continuum-Plus` 默认 `Continuation Method = Native Masked — exact continuation`：chunk 2 起，**把上一段被接受的 H3 视频 latent 尾巴直接拷进下一段目标 latent 的开头**，用 core 掩码把拷贝前缀标 `0=preserve`、新区标 `1=generate`；开音频连续性时还会拷**对齐的上一段音频 latent 尾巴**。24fps 视频 + 40Hz 音频下，当前精确 AV 档案是 **39 视频帧 = 65 音频 latent 步**。作者自陈局限：Native Masked 需要含 PR #15375 的 Core 版本；Guide 路线"仍然是模型 conditioning，不冻结精确目标前缀"。〔②〕<https://github.com/xmarre/ComfyUI-H3-Continuum-Plus>
- **另一套（自动找安全切换点 + 裁头）**：`ComfyUI-H3-Latent-Relay` 走"latent 逐位拷贝（管运动）＋ conditioning 钉帧（管取景）"并联的复合桥，并给出可量化的取舍：
  - latent 拷贝：**不发糊**，但色档/亮度阶跃大（实测 **0.040 ≈ 硬切级**）；conditioning 钉帧：阶跃小（**0.004**），但**会发糊**（复现沉降）。
  - "必须裁头"：钉住区前 22 帧不是新内容，而是模型对上一段尾部的**重生成**（实测逐帧 MAE ≈ 6/255）；证据是"段 B 首帧最相似的帧是段 A 的倒数第 22 帧（MAE 3.09），次优候选 MAE 17.5"。不裁＝接缝处约 **0.92 秒画面重播**。
  - "裁多少不该由人填、要当场量"：73 帧的段，切换点落在原第 22→23 帧之间（MAE **6.52 → 102.27**），固定裁 22 帧不够；107 帧的段则干净。
  - **默认反而"不裁沉降"**：实测裁 0 帧→缝处跳 **0.020**、裁 8 帧→0.044、裁 16 帧→0.055；作者结论「**裁沉降才是跳帧的源头**，留下的几帧只是清晰度渐变，人眼对渐变容忍度极高」。段首糊改用 `settle_sharpen`（画质域 unsharp，强度从缝端线性衰减），实测相对锐度 0.873 → **1.008**（amount=1.0），并诚实标注"锐化只能恢复对比度，救不回已丢失的细节"。
  - `seam_ghost`（缝帧重影）虽然把跳帧 0.055 降到 0.029，但**观感更差（一跳变两跳）**，作者把默认设为关。〔②〕<https://github.com/ZenHG/ComfyUI-H3-Latent-Relay/blob/main/docs/01-mechanism.md>
- **音频与时长口径（Herrgott 套件）**：精确 AV 上下文长度是 **39 / 90 / 141 / 192 …（39+51k）帧**；默认 39 帧 ≈ 1.625s ≈ 65 个音频 latent tick。它把"画面切换点"和"音频保护点"解耦：视频端点吸附到最近的精确 AV 边界（这一步可能比理想视觉切点**再早最多 16 帧**，作者说这是有意保守），音频可以独立延长保护到上一段真实尾音。`Duration Mode = Net New Content` 时 5s 请求 → 158 总帧 − 39 保护 = **119 新帧（~4.96s）**。〔②〕<https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite>
- **为什么值得走 latent（两处独立说明）**：
  - 社区版：「导出 MP4 再喂回去，中间的反覆**像素解码/重编码**会造成纹理发糊、压缩代际损失、对比变暗、色彩漂移、角色严重不一致与房间布局漂移」；latent 直传则"零质量损失"，并额外用 `Seed Ref Video` 传**宏观语境**（例如更早的广角主镜）来防"换机位就把环境搞坏"。〔②〕<https://github.com/SatoDive/Minimax-H3-Latent-Continuation>
  - WanGP 插件版：「WanGP 标准 Continue Video 会把给的 MP4 再经视频 VAE 编码一次；反复做会渐进损坏细节、对比、纹理与身份」，所以它保存**推理时的原始 latent** 复用；并有三种 join 模式（Reference 最少 18 帧上下文 / 更长视频音频上下文 18·35·52 帧 / **冻结音频前缀**），推荐先用「冻结音频前缀 + 35 帧 + 1 秒 + No Skipping」。限制：模型变体、VAE、分辨率、FPS 必须与检查点一致，MP4 字节哈希必须匹配（**改过/重封装/裁剪过就不认**），只支持单窗口单相位，且作者明确"**仍然可能看到接缝，因为新段是生成出来的、不是从连续原片里拷的**"。〔②〕<https://github.com/g3n3rativ3/wan2gp-h3-latent-continue>
- **背景原理**：FramePack 论文把这类问题叫 **drift / observation bias（误差累积）**，给出的抗漂手段是 **early-established endpoints（早立端点）、adjusted sampling orders（调整采样顺序）、discrete history representation（离散历史表示）**——"提前钉好端点"正是首尾帧/关键帧锚定的理论根据。〔①〕<https://arxiv.org/abs/2504.12626>
- **可信度**：①（官方掩码原语、论文）＋②（各实现的量化与取舍）

### 2.6 引导式接续（Guide / Motion Context，比"钉死"软一档）

- **做法**：不拷 latent，而是把上一段的 latent 片段作为**时间引导/keyframe conditioning**注入。Continuum 把它保留为 `Guide / Motion Context` 模式，用于"较软的情境影响与镜头转场"；官方也提醒这条路线"不冻结精确目标前缀"。Herrgott 说明了为什么要从 guide 换成 masked：老 guide 路径下"**H3 仍要负责生成新片段开头**，于是未来 Last Frame、别的视觉条件或常驻运行时状态有时会比预期更强烈地影响开头"；v1.4 的分工变成：**上一段 AV latent＝被保护的起始上下文；Last Frame＝可选的未来端点/画质重置；Qwen References＝人物/服装/物体描述**。〔②〕<https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite>
- **适用场景**：镜头间有明确转变（换机位/换景）时的"软接"；或作为 A/B 对照。
- **可信度**：②

### 2.7 滑动窗口 / 长视频（WanGP 官方文档，直接可抄的参数）

- **做法**：设窗口大小、重叠帧、丢弃末帧，多窗口合并成一条长视频。生成帧数公式：`Generated Frames = (Nb Windows − 1) × (Window Size − Overlap − Discard) + Window Size`。〔①〕<https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/PROCESSING.md>
- **抗漂建议（原文）**：「**提前用图像生成模型准备好几张"结束帧"图，分配给后续各个窗口**，这些视觉锚点会把后面的窗口拉回目标人物、构图与外观」；并且「**每次都从主图（master image）分支去编辑，不要顺着上一张关键帧链式编辑——链式编辑会在视频生成之前就累积视觉漂移**」；H3 与 VACE 还能在窗口之间**重新注入参考图/帧**。〔①〕同上
- **换镜头的官方开关**：多行提示词 = 每行/每段一个窗口的提示词；窗口提示词可带 `[/overlap=9]`、`[/new_shot]`（＝`[/overlap=0]`，**阻止前一个窗口条件化新窗口，形成硬切**）、`[/duration=4s]`。音画同步方面：LTX-2/H3/Ovi 会把每个窗口的音频对齐到视频时间轴，并**替换前一段音轨的一小段结尾为新生重叠**，防止累计时间漂移；"keep the model's default overlap；如果 WanGP 报 overlap 太短无法修音频，就加大"。〔①〕同上
- **排障口径（原文）**：窗口不一致 → 加大 overlap、保持提示词一致、少丢有用帧；发糊 → 减少过量 overlap、**加大丢弃末帧数**、换更干净的参考/控制视频。〔①〕同上
- **可信度**：①（WanGP 项目官方文档）

### 2.8 参考注入（角色 / 道具 / 场景资产）

- **H3 R2V 官方写法**：参考按连接顺序用 `<Picture 1>`、`<Video 1>`、`<Audio 1>` 引用；**给每个参考分配职责**（身份/风格/运动/相机/音色），"明确指派往往效果好得多"；上限 9 图 + 3 视频 + 3 音频；`ref_image_size=max` 保留到 2048 短边换更强身份保真（速度换质量）。**一张参考图可以放多视图或分镜面板**，让每个镜头点名要哪个 panel。〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>、<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-prompt-guide>
- **"身份锁放最前、配件锁排在面部锁之前"**：AniGuide 的"五道一致性防线"里写：(a) 连续性锁＝登记的英文短语**原样写进**相关每一帧提示词（管服装、道具、场地固定物）；(b) 角色形象图（全身多视图 + 头部特写**分开出**，因为全身图里的脸只有几十像素）；(c) 本镜首帧（锁机位/景别/光线方向）；(d) **上一镜尾帧只在"承接"型转场才用**——「**跳切时绝不用上一镜尾帧，那会把两个不该相连的镜头强行焊在一起**」；(e) 场景参考板。并写明「**顺序有意义**：身份锁放提示词最前（放末尾会被后面的场景描述冲掉），而且**配件类锁排在面部类锁之前——实测配饰比脸更容易丢**」；「**有外观锚点时，文字不再重描角色**（重描＝让模型按文字重画一个，再拿参考图修色）」。〔②〕<https://github.com/exiell/ai-video>
- **场景/空间锚定**：场景九宫格（9 个机位一次锁死空间）、720° 全景取景（注意广角畸变，提示词加"50mm 以上中焦"）；这两条来自中文自媒体整理，附了来源"创作者 仙人甲"。〔③低可信，未找到一手出处〕<https://www.hxsd.com/content/59442/>
- **静止背景锁（拉链式）**：`comfyui-h3-pullforward` 把"没在动的像素"的锚值**贴回后续帧的 latent**，只动静止格子，运动主体不动；实测"单机位场景、10 段链条，背景漂移/亮度/饱和度贴着第一段走而不是逐段走远"。注意它只适用**固定机位**，且 `block_latents` 必须保持 5，否则出现"每 17 帧一次的亮度脉冲"。〔②〕<https://github.com/roycho87/comfyui-h3-pullforward>
- **可信度**：①（H3 官方）＋②（两个社区项目）＋③（九宫格那条）

### 2.9 提示词层（跨镜锁死的可执行写法）

- **锁面（verbatim lock）规范**〔②〕<https://github.com/zenstory-ai/drama-skills/blob/main/skills/short-drama-assets/references/continuity-lock.md>：
  - 只有**三条同时成立**才值得上锁：① 该可见事实出现在两个以上镜头（或一镜＋一张资产板）；② 观众能直接看出前后不一致；③ **它不随剧情改变**。典型可锁：服装主色与形制、**道具主色与材质**、发型长度、伤口位置与形状、招牌/界面形制配色。
  - **锁面＝要被逐字带进提示词正文的最小可辨识名词短语**，通常是「颜色＋材质/形制＋物体」；不含句号、动作、状态、数量、镜头信息、剧情；不写 `in her hands`、`half-finished`、`on the sofa` 这类随镜头变化的词。
  - **校验细节（很实用）**：大小写不敏感、换行按空格；**粘在词上的匹配不算**（`chipped white enamel mug` 不被 `unchipped white enamel mug` 满足）；**负面提示词里的匹配不算**（写在 `no/not/without/不要` 之后的锁面说的是"不要出现它"）；**不允许以"参考帧已经交代过"为由删掉锁面**。
  - **反例**：`锁面：蓝色毛衣`（英文正文永远匹配不上）；含剧情/时态的锁面；`high quality, detailed` 这种不是可辨识事实的词。
  - **规模建议**：一集的锁通常是个位数；把每条识别锚点都升级成锁，会把每条提示词撑满、反而挤掉本镜真正要执行的动作。
- **"末态法则"**：多事件提示词必须为**每个阶段写可见末态**——「她感到释然」不算，「肩膀松下、皱眉消失」才算；**最贵的锁定位在提示词末尾重述一次**。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/SKILL.md>
- **工作流词不进投喂正文**：「末态继承」「段缝」「拼接节点」这类制作流程词写进提示词，模型会当画面词处理。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/continuity-log.md>
- **H3 特有的两条**（官方）〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-prompt-guide>：
  - **否定句无效**：模板走 `BasicGuider`，只有一路 conditioning、cfg=1，没有负向分支；写 `no subtitles and no on-screen text` 等于**把"字幕"当内容喂进去**。要"没有"就写正面状态，例如 `the sign above the door is blank`。
  - **说话人 ID 要跨镜稳定**：每个出声的角色给 `(S1)/(S2)`，每镜重复；「音频参考被发给错误说话人」是已知问题，缓解办法是"每镜只保留该镜需要的参考"、把台词**绑到可见事件**（"当电话贴到耳边时，穿大衣的男人说"）而不是绝对时间码。
- **反向做法（对话类"角色说了什么"要实测）**：写负面词的场景也有社区反例——ADC1920 的"否定失效三改法"（词根零出现 / 主体优先句式 / 移除触发器）说明**否定在部分平台上确实会失效**，与 H3 官方的解释互相印证（两处讲的是不同平台，结论方向一致）。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/prompt-craft.md>

### 2.10 后期的缝处理（生成之后的最后一道）

- **帧级裁剪＋无损拼接**：抽尾帧、去尾数帧、去头 1 帧（快档 `-c copy` 精度受关键帧边界限制、误差 <0.1s；准档 `trim` 滤镜帧精确），再 `ffmpeg -f concat -c copy` 拼接；并给了成片机检三查（`ffprobe` 参数对账 / `blackdetect` 黑帧 / `volumedetect` 电平）。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/transition-editing.md>
- **切点对齐整拍网格**：拍长＝60÷BPM，每拍帧数＝拍长×帧率；先把每段裁到整拍时长再顺序拼接，否则"每段多 0.09 秒，拼到第十段切点偏出半拍"。〔②〕同上
- **接缝处的画面修正**：Continuum 的 `Video Seam = Auto 3 (Sustained Tone)` 用静止背景区域估计一个**有界的逐帧 RGB 仿射校正**，**只改新生成的解码帧**，不动权威前缀/音频/几何；作者实测"减少了一个 chunk 边界处的持续变暗"，并明确它**不能**修正几何漂移、累积变焦、背景细节丢失或不完整的语音。〔②〕<https://github.com/xmarre/ComfyUI-H3-Continuum-Plus>
- **音频缝**：段间硬切音频会有"啪"声 → 音频交叉淡化；Herrgott 默认 4 帧视频交叉淡化 + 15ms 音频 de-click。〔②〕<https://github.com/LIUFelix2004/God-minmax-H3/blob/main/references/stitching.md>、<https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite>
- **可信度**：②（命令与阈值都是公开可复现的）

### 2.11 一次生成里直接出多镜（模型原生，省掉拼接）

- **Kling 3.0（官方 partner node 文档）**：官方列的能力就是 **multi-shot generation（单次生成里出多个镜头并控时长）＋ locked subject consistency（在镜头运动与场景演变中保持角色与**物体**身份）**。〔①〕<https://docs.comfy.org/tutorials/partner-nodes/kling/kling-3-0>
- **MiniMax H3（官方）**：提示词按"整体场景 → 分时段镜头"写，镜头之间**在明确时间戳切**；Multiframe Reference 模板就是多镜头模板。〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>、<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-multiframe>
- **LTX-2（官方）**：把 "Keyframe-driven generation: interpolate between keyframe images" 列为模型能力之一。〔①〕<https://docs.comfy.org/tutorials/video/ltx/ltx-2>
- **可信度**：①（官方文档）；注意这些是**厂商声明**，不代表在所有题材上都成立

---

## 三、手持道具 / 细节连续性的专项做法

> 先说结论：**"哪只手拿、拿没拿"这类细节，社区通行的处理是"当状态逐镜记录＋在末态里写死"，而不是"当成锁逐字锁死"**；而且专业规则文档明确把"左右手/持有人"划到**不该上锁**的一侧。

1. **规则层：持物属于"状态"，不属于"锁"**。连续性锁的规范明确列出**不典型/不该上锁**的项：情绪、姿势、**左右手**、镜头角度、时段光线、破损进度、**持有人**——理由这些是"状态或镜头瞬态"，分别归 `本集状态` 与分镜；同时给出正确的分法示范：**毛衣"越织越长"写状态，颜色与针法写锁面**。〔②〕<https://github.com/zenstory-ai/drama-skills/blob/main/skills/short-drama-assets/references/continuity-lock.md>
2. **台账层：持物必须逐镜记**。连续性账要求记录「**持物与手部：左右手占用、数量、开合、完整/损坏**」；接镜检查（上一镜最后可用帧 vs 本镜第一可用帧）里，**关键道具**属于"硬连续"，冲突破坏理解、P0 必修。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/continuity-log.md>
3. **提示词层：道具写"最小可辨识名词短语"（颜色＋材质＋形制），逐字进每一镜正文**；道具的**主色与材质**可上锁，**"在她手里""织到一半"不可**。〔②〕同上
4. **顺序层（少见的实测经验）**：**配件类锁要排在面部类锁之前，因为实测配饰比脸更容易丢**；身份锁放提示词最前。〔②〕<https://github.com/exiell/ai-video>
5. **参考图层：道具可以走参考图而不是文字**。H3 的 Qwen/VLM 参考（`<Picture N>`）官方定位就是"描述人物、服装、**物体**或其他视觉细节"，比文字描述更稳；Herrgott 的 picture_map 说明也把 Qwen References 归为"人物/服装/物体"类描述。〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-prompt-guide>、〔②〕<https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite>
6. **接力层：道具最容易在"尾帧→首帧"这一跳丢**。既然道具/手部是最常被模型重画的部分，接力时必须把它写进"接续状态的末帧画面"（谁＋在哪＋什么姿态＋**关键道具/互动状态**），并在下一镜提示词里重申（见第一节第 7 条）。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/continuity-log.md>
7. **镜头设计层：避开"手-物精细交互"的特写**。营销向指南给的两条做法是：专注**大肌群动作**（走、转身），手-物细节用**分切镜头**处理（先给人物在桌前的全景，再单独给屏幕特写）。〔③低可信：该页含"[Your Brand]"占位符与无法核实的"内部数据"，只当思路参考〕<https://hailuoai.video/pages/knowledge/ai-b-roll-subject-consistency-workflow>
8. **工具层（道具画错时的定点修复）**：
   - H3 的**逐 token 噪声掩码**可以只重画局部（`0` 保留 / `1` 重生成），官方点名"局部重绘、去物体"；Fun ControlNet Union 页另有 mask 路线的 inpainting。〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>
   - WanGP 的遮罩体系（黑＝保留、白＝处理；`Mask Expansion / Shrinking` 调整可编辑区大小；Matanyone 做视频遮罩）——官方提醒"**对人物/物体替换来说，跨帧稳定的遮罩通常比某一帧的完美遮罩更重要**"。〔①〕<https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/PROCESSING.md>
   - 背景/静止物漂移用 latent 层的 pull-forward 锁回参考段。〔②〕<https://github.com/roycho87/comfyui-h3-pullforward>
9. **互相矛盾之处（两边都保留）**：
   - zenstory 的锁规范说**左右手/持有人不该上锁**；而 ADC1920 的台账要求**逐镜记录左右手占用**并写进末态。两者其实分工不同（一个管"逐字锁死的短语"，一个管"逐镜记录的状态"），但**"能不能用一句提示词锁死某只手"这一点，没有找到可靠来源支持**。

---

## 四、已出错时的补救手段

按"代价从低到高"排：

1. **先量化定位，再决定修哪**（不要整体重做）：
   - 接缝量化检测：对相邻分镜"上一段尾帧 vs 下一段首帧"算 **SSIM／亮度差／色相差／饱和差** 四维指标＋综合偏差排序（阈值经人工判定样本校准）。〔②〕`scripts/check_seams.py`，索引见 <https://github.com/ADC1920/AI-short-play-video-creation/blob/main/SKILL.md>
   - 接缝自检：窗口紧贴钉住区，基线取钉住区内部相邻帧差中位数，**帧差 > 4×max(基线,1.0) 即认定为切换点**（纯 CPU，每段约 40ms）。〔②〕<https://github.com/ZenHG/ComfyUI-H3-Latent-Relay/blob/main/docs/01-mechanism.md>
   - 成片机检三查：参数对账 / 黑帧 / 音频电平。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/transition-editing.md>
   - ⚠️ **反例（别用错尺子）**：AniGuide 曾用"字面重合度"判断首尾差距，在示例项目上报 6 条**全是误报**，该规则被整条撤掉。〔②〕<https://github.com/exiell/ai-video>
2. **只重生成坏的那一段**（不是整片）：
   - 分块工作流保留"Run Storage"，`Regenerate From` 指定从第几段起重跑，**前面兼容的块原样复用**；用固定 seed 才能复现。〔②〕<https://github.com/xmarre/ComfyUI-H3-Continuum-Plus>
   - H3 中文导演台走的是"六段独立编辑/执行/SUCCESS、指定起始段、失败后续跑"。〔②〕<https://github.com/asd454314633-byte/H3-Chinese-Director>（注：仓库地址见文末链接表）
3. **局部重绘而不是重拍整镜**：
   - H3 逐 token 噪声掩码（保留/重生）；〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>
   - WanGP 的 Inpainting / Temporal Inpainting（填补既有帧之间的缺失帧）/ Frames To Keep（保留选定控制帧、只重生成其余帧）；〔①〕<https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/PROCESSING.md>
   - 官方一句提醒：**要"重绘一部分片段"走 mask 路线，要"换风格/改风格"才走参考视频路线**，两者别混。〔①〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>
4. **接缝的"补一帧/纠一帧"**：
   - 单帧 Guide：H3 官方 Add Guide 明确支持"在 124 帧视频的 frame 60 放一张静图，强制视频经过那一帧"；中文导演台记录里有"**Clean Rebase + 官方单帧 Guide**，六段第 4 段 Guide frame0 与五处接缝通过"的验收记录（2026-10-09）。〔①〕＋〔②〕<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>、<https://github.com/asd454314633-byte/H3-Chinese-Director>
   - 缝处重影 `seam_ghost`：数值上把跳帧从 0.055 降到 0.029，**但作者实测观感更差（一跳变两跳），默认关闭** —— 数值改善 ≠ 观感改善。〔②〕<https://github.com/ZenHG/ComfyUI-H3-Latent-Relay/blob/main/docs/01-mechanism.md>
   - 缝处糊：`settle_sharpen` 在画质域做渐变锐化（不动时间轴，避免裁帧引入跳帧）。〔②〕同上
5. **接缝亮度/色调不一致**：Video Seam 类光度校正（只改新生成帧）；或后期在 NLE 里用统一 LUT 做色彩匹配。〔②〕<https://github.com/xmarre/ComfyUI-H3-Continuum-Plus>、〔③低可信〕<https://hailuoai.video/pages/knowledge/ai-b-roll-subject-consistency-workflow>
6. **"改已有视频"而不是重生成**（编辑四件套）：写明 ① @video1 是**唯一编辑母版**；② **范围写两遍**（改什么＋保留什么）；③ 目标数量（"全片只有一盏白色台灯"，防复制）；④ **时间轴继承**（替换物继承原物的一切出现、运动、遮挡与离场）。另给了"向前延长"与"向后延长"两套模板——**向后延长是把源片首帧写成你正在生成这一段的明确末态**，否则会翻车。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/transition-editing.md>
7. **重生成仍然不行时的"降级决策"**（社区显式写下的止损线）：
   - 一个镜头**失败 3 次 → 简化镜头契约，或把动作拆成两条**。〔②〕<https://github.com/Emily2040/seedance-2.0/blob/main/references/shot-list-continuity.md>
   - **重生预算 ~10%**：单集重生段数超过就停下，查素材与提示词的系统性问题。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/SKILL.md>
   - **到达"来源链上限"或发现漂移 → 从长期母版重新锚定**（允许同一来源链最多连续 2 段，硬上限 3 段）。〔②〕<https://github.com/xixihhhh/ai-short-drama-skill/blob/v0.3.2/skills/dramake/references/project-state.md>
   - **单变量迭代**：一次只改一项；必须同时改多项时标"组合改动，无法单独归因"，不得据此宣称某个词必然有效。〔②〕<https://github.com/ADC1920/AI-short-play-video-creation/blob/main/references/continuity-log.md>
8. **画质层面的补救（不是连续性，但常一起做）**：低分辨率结构复用 + 高分辨率重建（Flow-Aligned Regenerate：捕获低分辨率去噪轨迹去引导第二次高分辨率 pass；"**轻微接续变暗仍是已知问题**"，且作者强调"用**解码后的画面**而不是结构指标来验收新工作流变体"）。〔②〕<https://github.com/xmarre/MiniMax-H3-Flow-Aligned-Regenerate>

---

## 五、未找到可靠来源的部分（不编）

1. **Reddit（r/comfyui、r/StableDiffusion）正文未读到**：本机环境对 `reddit.com` / `old.reddit.com` 的抓取全部失败（fetch error），只能从搜索层拿到**标题**。因此**任何"Reddit 网友说……"的复述都不在本文中**。
2. **B站 / 知乎正文未读到**：B站视频页返回验证码页，知乎返回 403。中文社区的具体参数与工作流文件**本文没有引用**。
3. **"把手持物锁死到某一只手/某个持有人"——未找到可靠来源**。找得到的只有：规则文档明确说这属于"状态、不该上锁"（②），以及台账要求逐镜记录左右手占用（②）。**没有**任何可复核来源声称某段提示词/某个节点能稳定锁定"哪只手"。
4. **没有单一的"跨镜一致性权威检查清单/参数表"**。社区只有若干各自成文的清单（连续性账、锁规范、缝类型、机检三查、拍摄前 checklist），**参数散落在各工作流文档里**（如 H3 的 39 帧 AV 上下文、WanGP 的 overlap/discard、LTX 的 guide strength 0.7、H3 的步数建议），彼此不可直接换算。本次未找到把跨模型参数统一成一张表的一手来源。
5. **未核实正文、只见到标题的**（列出但不作结论依据）：
   - `kijai/ComfyUI-WanVideoWrapper` issue #1837 "Why remove last frame with FLF2V?"（标题级）<https://github.com/kijai/ComfyUI-WanVideoWrapper/issues/1837>
   - `Kijai/WanVideo_comfy` discussion #31（标题级："Wan 2.2 Animate darkening/artifacts on last 4 frames (last latent)"）<https://huggingface.co/Kijai/WanVideo_comfy/discussions/31>
6. **低可信来源（收录但不当证据用）**：
   - 阿里云开发者社区两篇：一篇声称"IPAdapter+FaceID+LineArt 保角色一致、8GB 显存部署"，另一篇声称"全局特征池＋双锚点时序同步＋重叠帧缝合，实测一致性提升至 94.7%"——**正文未渲染出来、无复现步骤与样本**，标 ③。<https://developer.aliyun.com/article/1768305>、<https://developer.aliyun.com/article/1764366>
   - 火星时代那篇"6 个画面一致性方法"（方法 1 提示词锚定、2 参考图驱动 I2V、3 场景九宫格、4 720° 全景取景、5 LoRA）**未署一手出处、第 6 条本次未读到**，标 ③；其中"方法 3/4"提到来自创作者"仙人甲"，也未找到一手来源。<https://www.hxsd.com/content/59442/>
   - Hailuo/Seele 等厂商 SEO 页：含 `[Your Brand]` 占位符与无法核实的"内部数据"（如"100 条片段""12%→48% 可用率"），标 ③，只在"思路"层面参考。<https://hailuoai.video/pages/knowledge/ai-b-roll-subject-consistency-workflow>、<https://www.seeles.ai/resources/blogs/ai-video-continuity-bible-workflow>
7. **互相矛盾、两边都写进正文的说法**（本文均已并列保留）：
   - **尾帧像素接力 vs latent 接续**：前者是最广用的做法（fxi/`God-minmax-H3`/ADC1920 都这么干），后者有多个项目声称能免掉像素往返带来的掉质（SatoDive/Herrgott/WanGP 插件）。两者适用条件不同（单机位连续动作 vs 长链跨镜），**没有任何一方给出"在同等条件下 A 一定优于 B"的对照实验**。
   - **硬钉死 vs 软引导**：硬钉（拷贝 latent / strength 1.0 引导）能防漂但可能"冻住"（LTX v1 的 lip sync 崩坏是结构性证据），软引导会动但会漂。WanGP 的 `[/new_shot]`（硬切）与 Continuum 的 `Guide / Motion Context`（软接）是同一取舍的两种官方/半官方答案。
   - **`seam_ghost`**：数值指标改善、作者实测观感更差——**指标与观感冲突时的处置（以观感为准）本身就是一个社区结论**。
8. **本次未查的**：Wan 2.2 官方提示词指南（指向阿里钉钉文档，未抓取）、各模型的中文 LoRA 生态与训练侧做法、音频跨镜一致性（除 H3 的音频掩码与 WanGP 的 overlap 音频重建外，未系统检索）。

---

## 附：本文引用来源速查

**官方 ①**
- ComfyUI 官方文档 · Wan2.2（含 FLF2V 工作流）：<https://docs.comfy.org/tutorials/video/wan/wan2_2>
- ComfyUI 官方博客 · Wan2.2 FLF2V 原生支持：<https://blog.comfy.org/p/wan22-flf2v-comfyui-native-support>
- ComfyUI 官方文档 · MiniMax H3 总览（步数/参考漂移/续接模板）：<https://docs.comfy.org/tutorials/video/minimax/minimax-h3>
- ComfyUI 官方文档 · H3 原生工作流（Add Guide、latent 噪声掩码）：<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native>
- ComfyUI 官方文档 · H3 Multiframe Reference（多镜头模板）：<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-multiframe>
- ComfyUI 官方文档 · H3 提示词指南（否定失效、说话人 ID、参考面板）：<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-prompt-guide>
- ComfyUI 官方文档 · Kling 3.0（原生多镜头＋主体/物体一致性）：<https://docs.comfy.org/tutorials/partner-nodes/kling/kling-3-0>
- ComfyUI 官方文档 · LTX-2（关键帧驱动生成）：<https://docs.comfy.org/tutorials/video/ltx/ltx-2>
- ComfyUI 工作流库 · MiniMax H3 FLF2V：<https://comfy.org/workflows/ef37c26c9bbf-ef37c26c9bbf/>
- WanGP 官方文档 · Processing（滑动窗口/结束帧/overlap）：<https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/PROCESSING.md>
- FramePack 论文（drift 与抗漂手段）：<https://arxiv.org/abs/2504.12626>

**社区实测 ②**
- FXI Frame Chain（尾帧接力三节点）：<https://github.com/fueledximagination/comfyui-fxi-frame-chain>
- H3 Continuum-Plus（Native Masked 精确续接、Seam 校正）：<https://github.com/xmarre/ComfyUI-H3-Continuum-Plus>
- Herrgott H3 Infinite Continuation（39/90/141/192 帧 AV 上下文、Auto Handover）：<https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite>
- H3 中文导演台（六段连续、AV latent 接续、单帧 Guide 修复）：<https://github.com/asd454314633-byte/H3-Chinese-Director>
- SatoDive H3 Latent Continuation（latent 直传＋双参考）：<https://github.com/SatoDive/Minimax-H3-Latent-Continuation>
- ZenHG H3 Latent Relay（裁头/沉降/锐化/重影的量化取舍）：<https://github.com/ZenHG/ComfyUI-H3-Latent-Relay/blob/main/docs/01-mechanism.md>
- H3 Pull-Forward（静止背景锁回）：<https://github.com/roycho87/comfyui-h3-pullforward>
- Flow-Aligned Regenerate（低分辨率结构复用/高分辨率重建）：<https://github.com/xmarre/MiniMax-H3-Flow-Aligned-Regenerate>
- WanGP H3 Latent Continue 插件（三种 join 模式、检查点绑定）：<https://github.com/g3n3rativ3/wan2gp-h3-latent-continue>
- LTX-2.3 Multishot Lite（v1 结构性失败 → v2 latent 扩展、0.64 相关性）：<https://huggingface.co/joeygambino/ltx23-multishot-lite>
- MiniMax-H3 fl2va 量化对比（26.35dB vs 16.15/16.81dB）：<https://huggingface.co/joeygambino/MiniMax-H3-comfy-native-fl2va>
- Phosphene · 多关键帧插值（构图变成输入）：<https://github.com/mrbizarro/Phosphene/blob/main/docs/SDK_KEYFRAME_INTERPOLATION.md>
- ADC1920 · AI 短剧创作工作流（SKILL / 连续性台账 / 衔接与后期）：<https://github.com/ADC1920/AI-short-play-video-creation>
- zenstory-ai · 跨镜一致性锁：<https://github.com/zenstory-ai/drama-skills/blob/main/skills/short-drama-assets/references/continuity-lock.md>
- Emily2040 · Shot List and Continuity：<https://github.com/Emily2040/seedance-2.0/blob/main/references/shot-list-continuity.md>
- AniGuide（五道一致性防线、配件锁顺序、22 条穿帮规则）：<https://github.com/exiell/ai-video>
- novel-storyboard（18 道质量门）：<https://github.com/yzsp-studio/novel-storyboard>
- God-minmax-H3 · 分段生成与拼接（接缝位置、接力三件套、检查清单）：<https://github.com/LIUFelix2004/God-minmax-H3/blob/main/references/stitching.md>
- ai-short-drama-skill · 项目状态（父子段依赖、来源链上限）：<https://github.com/xixihhhh/ai-short-drama-skill/blob/v0.3.2/skills/dramake/references/project-state.md>
- Kijai/WanVideo_comfy 讨论 #77（Wan FLF 尾帧问题）：<https://huggingface.co/Kijai/WanVideo_comfy/discussions/77>

**低可信 ③（仅作线索，不作证据）**
- 火星时代 · 6 个画面一致性方法：<https://www.hxsd.com/content/59442/>
- 阿里云开发者社区（角色一致性工程 / 无限画布自动拆镜）：<https://developer.aliyun.com/article/1768305>、<https://developer.aliyun.com/article/1764366>
- Hailuo 知识库（B-roll 主体一致性）：<https://hailuoai.video/pages/knowledge/ai-b-roll-subject-consistency-workflow>
- SEELE AI（Continuity Bible）：<https://www.seeles.ai/resources/blogs/ai-video-continuity-bible-workflow>
