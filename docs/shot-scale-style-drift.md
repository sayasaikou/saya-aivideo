# 景别画风漂移调研（特写变赛璐璐）· 2026-10-16

> **服务场景**：MiniMax H3（WanGP/mmgp，Ref2VA pruned 20B，1344×768，40 步，两阶段）＋ 单张 2D 半写实立绘参考图（`video_prompt_type: "I"`）＋ 一条超长六段式英文提示词。
> **现象**：同一短片里远景/中景是半写实绘画感，特写/近景变赛璐璐（平色块、均匀描边、无渐变）。
> **已试无效**：提示词里加整段 `RENDER STYLE (highest priority): ... NOT flat cel-shaded ...`。
> **可信度分级**：`①官方`（模型方/前端方的规范与代码）｜`②厂商内容站`（Hailuo 自家知识库，营销向，非技术规范）｜`③第三方教程`｜`④社区帖`｜`⑤学术`。
> **纪律**：每条结论带 URL；查不到的直接写"没查到"。

---

## 一句话结论（社区到底怎么说这个现象）

**没有一个公认的名字或定论**；但有两条被独立重复的说法共同指向我们的场景：

1. **「画风漂移」是普遍故障，社区明确点名它高发于「近景 / 手部近景 / 变焦 / 转身」这些时刻**（ArcLoop 手册，③）。
2. **官方（MiniMax 自家 Hailuo 知识库）明确说：景别决定模型分配多少"细节预算"，景别不对时相关指令会被直接忽略**（②）。

⇒ 合起来就是：**「景别会改变模型渲染什么」有官方表述；「漂移发生在近景」有社区共识；但「特写会被渲染成赛璐璐」这个具体形态，没查到任何权威解释。**

---

## 现象是否有公认解释

**部分有，但都不是针对"赛璐璐"这个词的。**

| # | 说法 | 出处 | 级别 |
| --- | --- | --- | --- |
| A | 景别（相机"感知距离"）决定细节预算；远景里提示"毛孔"会被忽略 | Hailuo 知识库 §04 | ② |
| B | 画风跳变集中在**近景、手部近景、变焦、转身、特效**时刻 | ArcLoop《画风乱跳怎么锁住》 | ③ |
| C | 同一片段内"厚涂写实 → 赛璐璐卡通脸"是图生视频最常见的坑 | 太平洋科技 | ③ |
| D | 风格词太泛/互相打架 ⇒ 模型在不同渲染语言之间跳；**修法是删冲突词，不是加形容词** | ArcLoop | ③ |
| E | 模型默认走"平均化"审美（训练数据里优质照片都修过图） | Hailuo 知识库 §01 | ② |
| F | 为了保动态流畅，模型会牺牲风格细节，**用"最常见的默认画风"脑补缺失部分** | 太平洋科技 | ③ |

**没查到的**：任何官方文档、论文或高赞社区帖直接说"特写/近景会被渲染成平涂或赛璐璐"。搜过的关键词见文末。

---

## 每个候选成因的可行性（结合我们的场景）

| 候选原因 | 有没有出处 | 能不能在我们这儿试 | 怎么试（具体参数/命令） |
| --- | --- | --- | --- |
| **1. 一条超长提示词跨景别，自己跟自己打架** | ✅ ③：Seedance"H3 一条提示词只写一个镜头"；④：H3 用户"短而直白的提示词更管用，模型对花哨措辞会发神经"；②：prompt stuffing 会"confuse the model" | 能，最高优先 | 拆镜：远/中/特写各出一条 prompt，只携带不变量（身份/皮肤质感/服装/光位/调色）。见做法清单 1 |
| **2. 风格句写的位置/形式不合官方规范** | ✅ ①：Ref2VA 的风格是"`[Shot 1]` **之前** 1–2 句英文"；我们那整段 `RENDER STYLE (highest priority)` 是元指令，规范里没有这种写法 | 能 | 把风格句挪到 `detailed_description:` 之后、`[Shot 1]` 之前，压到 2 句；删掉"highest priority / 冲突以它为准"这类元指令 |
| **3. 风格没被当成"被追踪的引用项"** | ✅ ①：官方明确 `<Subject N>` 覆盖 **Styles**；只定义风格的图要写进 Subject 定义里，不单列 `<Picture N>` | 能 | 新增 `<Subject 2>` = 参考图里的画风（笔触/次表面散射/织纹），`retention_analysis` 写 `fully_preserved`，并逐镜点名它在场 |
| **4. 文本编码器量化把长提示词里的风格段吃掉了** | ✅ ①（WanGP 自己的 H3 文档）："More aggressive quantization can slightly affect prompt interpretation."（NVFP4 AWQ 就在这条链上） | 能，且便宜 | Misc. → Text Encoder 从 `NVFP4 AWQ` 换 `Quanto INT8`（或 BF16 试一次），同 seed 同 prompt 对拉 |
| **5. 参考图内部像素预算不够 → 细节/风格线索被压掉** | ✅ ①（WanGP）：`image_refs_relative_size` 50–400（默认 100），"Higher values can preserve more reference detail and improve fidelity" | 能 | Hidden/Advanced 里把它从 100 拉到 200→400 试一次。⚠️ 它调的是**细节保真**，不是画风强度，别期待它单独解决 |
| **6. 特写镜头"细节预算"不足（景别太小/太快/动作太多）** | ✅ ②：景别不足时"模型会忽略该指令"；③：Seedance 升级阶梯第 3 条就是"change the shot scale" | 能 | 特写单独出；单镜只留一个动作；必要时给特写段更高像素（或单独跑一次 2K 再生） |
| **7. 两阶段的第二相（Turbo LoRA 精修）** | ✅ ①（WanGP）：第二相是"fixed three-step refinement … using the LightX2V Turbo LoRA"；④：turbo LoRA 掉遵循度 | 能，但解释力弱 | 它作用于整片，解释不了"只有特写变"。要验就关掉 Two Phases 跑同 seed 对比 |
| **8. 采样器/solver 影响画风倾向** | ✅ ④（Reddit 一条）："euler simple … when i go for anime style the style is more distinctive" | 能 | 只作为备选：`euler` ↔ `res_multistep` 同 seed 对拉。⚠️ 会动到全局观感，一次只改一个变量 |
| **9. 模型自带的"anime 特写=平涂"先验** | ❌ 没查到出处。只查到泛论"训练数据平均化"（②） | 只能硬锚，不能证实 | 用风格 LoRA（做法 6）或把风格写成 `<Subject>` + 逐镜重申，把先验压下去 |
| **10. 参考图反过来吃掉提示词的风格描述** | ⚠️ 间接：③ ArcLoop"强视觉风格会想重塑整帧"；③ Seedance"参考图要和景别匹配" | 能 | 参考图换成与目标画风更一致的（半写实厚涂）那张；Ref2VA 支持 ≤9 张图，可加一张**纯风格参考图**并在 prompt 里定义为 `<Subject 2>` |

---

## 可抄的做法清单（按性价比排序）

1. **拆镜：一个镜头一条提示词。** 只携带不变量，动作/镜头/景别逐镜改。
   来源：③ Seedance——"Make one prompt per shot. Reusing a long master prompt across a close-up, wide shot, and product macro can create contradictions. Carry only the true invariants: identity, skin finish, wardrobe, product, light direction, and color palette."
   落地：WanGP 的 `multi_prompts_gen_type` 设成 `G`／`PG`（每行/每段一条独立请求），一条 prompt 只写一个景别。

2. **把"画风"升级成一个被追踪的引用项 `<Subject 2>`，并在每一镜点名它。**
   来源：① 官方 Ref 指南 §2.1（`<Subject N>` 覆盖 Styles）、§2.2（只定义风格的图写进 Subject）、§4（`fully_preserved`／`weak_reference` 标记）。
   落地：`subject_definitions` 里加 `<Subject 2> is the rendering style of <Picture 1>: painterly semi-realistic, visible brushwork, subsurface-scattering skin, woven fabric texture, no flat colour fills and no uniform outlines.`；`retention_analysis` 加 `<Subject 2> (appears in [Shot 1], [Shot 2]...): fully_preserved - ...`。

3. **风格句按官方位置写：`detailed_description` 开头、`[Shot 1]` 之前，1–2 句，逐字固定不变。**
   来源：① 官方 Ref 指南 §5.2 对照表；③ 腾讯云工程文"风格词必须固定"；HF 风格 LoRA 作者"Freeze a character description word-for-word and repeat it verbatim in every prompt"。
   落地：删掉 `RENDER STYLE (highest priority)` 这种元指令块（规范里没有，且属"互相打架的指令"）。风格规则写成五部分：**线稿 / 阴影 / 调色 / 材质 / 合成**（ArcLoop 给的形式），每条一句。

4. **风格边界写进正文，别指望负面提示词。**
   来源：① H3 权重是 CFG-distilled（官方 README）；① WanGP H3 两处写死 `no_negative_prompt: True`；③ Seedance"H3 stock graph 没有正负 conditioning 对"。
   落地：在正文末尾加 1–2 句可观察的排除句（Seedance 的写法）：`No flat colour blocks on skin or cloth; no uniform outline around the face; no posterised shading; no cel-shaded simplification at any point in the shot.`

5. **首帧/中间帧回锚，压住漂移。**
   来源：① WanGP `docs/PROCESSING.md`——"can re-inject reference images or frames between windows … can restore character identity, appearance, or composition before drift becomes too noticeable"；① WanGP CHANGELOG——Ref2VA"preserves its selected reference memories across every Sliding Window"。
   落地：Ref2VA 用 `FI` 模式 + `frames_positions`，在窗口边界注入参考帧；或用 `image_start`（上一镜末帧）＋ 目标 `image_end`；滑窗模式可加 `[/new_shot]` 控制硬切。

6. **上风格 LoRA（H3 生态已有），rank/scale 直接控制"厚涂 ↔ 平涂"。**
   来源：HF `lovis93/studio-1939-old-animation-lora-minimax-h3`（H3 专用风格 LoRA，82 likes）——"studio1939-light (r16) — painterly … studio1939-strong (r64) — full cel. Bold flat-shaded characters with clean outlines over painted backgrounds… **Same prompt, same seed — only the LoRA rank changes.**"；配方原文："Prompt expansion: off — write the full art direction yourself"、"Scale: 1.0 for the full look; 0.4–0.8 to blend it under a modern art direction"。
   落地：WanGP 的 LoRA 是多阶段感知的（`loras_slists` 带 `phase2`），非 turbo 的 LoRA 在第二相保留倍数 ⇒ 风格 LoRA 会作用于两个阶段；`[/loras_mult=1;3]` 可按窗口单独调。

7. **特写单独出 + 提高该段的像素/细节投入。**
   来源：② Hailuo §04（景别不足则指令被忽略）；③ Seedance 升级阶梯第 3 条"change the shot scale"。
   落地：把特写单独跑一次，单独给更高像素或缩减同镜动作数；不要指望同一段里"远推近"兼顾两种景别的渲染。

8. **换文本编码器量化档做对照实验（我们这条链路上唯一"可能吃掉长提示词"的硬件旋钮）。**
   来源：① WanGP H3 文档——"More aggressive quantization can slightly affect prompt interpretation."
   落地：`NVFP4 AWQ` → `Quanto INT8`（再试一次 BF16），同 seed / 同 prompt，只看特写那一段。

---

## 依据清单（URL + 原文摘录）

### ① 官方（模型方 / 前端方）

1. **MiniMax-H3 模型卡（HF 官方）** — <https://huggingface.co/MiniMaxAI/MiniMax-H3>
   > "The released checkpoints are CFG-distilled Omni Transformer model weights."
   > "H3-Context-IR … may also supplement missing or underspecified semantic details where appropriate." / "it is not included in this open-source release"
   ⇒ ① 本地没有负向 conditioning 通道；② 官方那套"补全欠描述细节"的预处理我们本地**没有**。

2. **官方提示词规范 base（T2VA/I2VA/FL2VA/L2VA）** — <https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md>
   > §4.1 "At the beginning of `[Shot 1]`, state the overall style and initial composition. Common styles include `Cinematic`, `live-action`, `2D-animated`, `3D CG`, `claymation`, `watercolor`, and `vintage film`. For keyframe tasks, derive the style from the reference image; for T2VA, select it from the user's text."
   > §4.2 "A cut should introduce new information about the subject, space, state, viewpoint, or time. **If only the distance or a slight angle needs to change, prefer camera motion.**"
   ⇒ 官方**没有**任何"景别 ↔ 画风"的说明；风格词表里也没有"半写实/赛璐璐"这类细分。

3. **官方提示词规范 Ref（Ref2VA 六段式，正是我们在用的模式）** — <https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md>
   > §5.2 对照表："Style opening | Written after `[Shot 1]`（T2VA）| **Established in one or two English sentences before `[Shot 1]`**（full-reference mode）"
   > §2.1 "`<Subject N>` is used for reusable visible content, including: People…; Scenes…; Clothing, props, interfaces, or visual effects; **Styles, actions, expressions, or poses**"
   > §2.2 "If an image is used only to define a character, scene, costume, **or style**, do not create a standalone picture entry. Instead, cite the image source inside the corresponding `<Subject N>` definition."
   > §4 "`weak_reference`: Only broad similarity in style, category, composition, or atmosphere is retained."
   > §5.2 "For generation tasks, `detailed_description` is normally 350-500 English words."

4. **WanGP `docs/PROCESSING.md`** — 本机 `$env:DSH_AI\Wan2GP\docs\PROCESSING.md`
   > "Some uncommon models, including MiniMax H3 and VACE, can also re-inject reference images or frames between windows. Supplying suitable intermediate references gives the model recurring visual anchors and **can restore character identity, appearance, or composition before drift becomes too noticeable**."

5. **WanGP `docs/CHANGELOG.md`（H3 段）** — 本机 `$env:DSH_AI\Wan2GP\docs\CHANGELOG.md`
   > "You can now choose the **reference-image pixel budget from 50% to 400%**: lower is faster, 100% matches the output, and higher favors fidelity."
   > "Ref2VA preserves its selected reference memories across every Sliding Window"
   > 两阶段原文："H3 first generates at half the target width and height, upscales the latent, and then performs a **fixed three-step refinement at the target resolution using the LightX2V Turbo LoRA**."
   > "LoRA multiplier (default is 0.5 as 1.0 seems too strong)"

6. **WanGP H3 模型定义/文档（本机代码）** — `$env:DSH_AI\Wan2GP\models\minimax_h3\minimax_h3_handler.py`
   > L162–164："**Rescale Internaly Image Ref (% in relation to Output Video) to change Output Composition** controls each reference image's internal pixel budget… Higher values can preserve more reference detail and improve fidelity, but generation is slower; lower values are faster but can lose fine details."
   > L283："**Text Encoder:** … **NVFP4 AWQ**, **GGUF Q4_K_M**, and especially **GGUF Q2_K** reduce it further. **More aggressive quantization can slightly affect prompt interpretation.**"
   > L360 / L638：`"no_negative_prompt": True`；L725–726：`"image_refs_relative_size": {"min": 50, "max": 400, "step": 1}`；L1216–1218：`"guidance_phases": 1, "guidance_scale": 1.0`
   > `prompt_enhancer.py` L292（WanGP 自己的 H3 写作规则）："Establish the global visual treatment, then begin [Shot 1] without a timestamp." / "Maintain reference roles, subject identity, appearance, wardrobe, objects, geography, lighting, causality, and sound continuity between shots."

7. **WanGP `docs/SETTINGS.md`** — 本机
   > "`negative_prompt` | string | Negative prompt when the model supports it. **Ignored or removed for models with `no_negative_prompt`.**"

### ② 厂商内容站（Hailuo AI 知识库，营销向，慎用）

8. **《Mastering Micro-Texture: Prompting Skin Pores and Blemishes…》** — <https://hailuoai.video/pages/knowledge/ai-video-skin-realism-pores-blemishes-guide>
   > §04 "Spatial Control and Shot Scale"："The model's ability to render micro-texture is heavily dependent on the 'perceived' distance of the camera. **If you prompt for 'pores' in a wide shot, the model will likely ignore the instruction because those details are smaller than a single pixel at that scale.** To trigger pore-level detail, you must explicitly state the shot scale."
   > §01："Most generative models are trained on vast datasets where high-quality photography often includes post-processing and skin retouching. Consequently, the model's 'average' human face leans toward an idealized, smooth texture."
   > §02："A common mistake is 'prompt stuffing'—loading a prompt with contradictory style modifiers like 'cinematic,' 'hyperrealistic,' and 'detailed skin' all at once. This often confuses the model, resulting in washed-out textures or inconsistent features."

9. **《Matching Light Sources Across Complex Multi-Angle AI Shots》** — <https://hailuoai.video/pages/knowledge/ai-video-lighting-consistency>
   > §03："When you switch from a wide shot to a tight close-up, the perspective of the background and the subject changes (parallax). **If you also change the description of the light, the AI will likely 're-render' the entire lighting environment, causing the subject's face or surface to look completely different.**"
   > "…that exact phrase must appear in your prompts for the wide shot, the medium shot, and the extreme close-up." / "Create a 'lighting block' … **Append this exact block to every camera angle prompt.**"

### ③ 第三方教程 / 博客

10. **ArcLoop《AI动漫画风乱跳怎么修》** — <https://arcloop.ai/handbook/zh-CN/fix-style-switching>
    > "风格乱跳会让一个片段像两个项目硬缝在一起。**前几秒是干净的 2D 赛璐璐动画，转个脸就变成半写实。**"
    > "原因通常是风格要求太松…会让它在不同渲染语言之间跳来跳去…**目标不是堆更多风格词，而是删掉互相打架的指令。**"
    > "**风格乱跳常发生在转身、变焦、手部近景或强特效时刻。**" / "先生成低成本草稿，**检查转身、近景和特效时刻，这些地方最容易跑偏**。"
    > "风格修复需要一套规则：线条粗细、上色方式、材质限制、调色规则、背景处理和负向风格边界。"

11. **ArcLoop《风格压过了角色，怎么办》** — <https://arcloop.ai/handbook/zh-CN/style-character-consistency-conflict>
    > "**强视觉风格会想重塑整帧画面。**" / "如果提示词不说谁优先，模型就会替你决定"
    > "五个通常是多数提示词的实用上限：脸型、发型、服装剪影、一组色彩关系，以及一个标志性道具或标记。**远景可以更少，只有在细节确实可见的特写里才更多。**"
    > "**风格用词写在镜头描述里，不要写进资产里。**"
    > "不要用否定提示词解决所有冲突。'不要漂移'不是规则。"
    > "创作者也常让风格参考承担太多职责。除非你有意分配，**否则风格参考不该决定服装、姿势、年龄或性格**。"（← 反例：风格参考会"顺带把设计也改了"）

12. **Seedance《MiniMax H3 Negative Prompt in ComfyUI: What Actually Works》** — <https://www.seedance.tv/blog/minimax-h3-negative-prompt-comfyui>
    > "The stock released H3 checkpoints are **CFG-distilled**, so the standard graph does not use the familiar positive-versus-negative conditioning pair."
    > "A custom node may store negative text **without connecting it to active guidance**… a visible widget is not proof that the model receives it."
    > 升级阶梯第 3 步："**Strengthen the reference or change the shot scale.**"
    > "A close or medium shot gives the model more pixels for fingers than a wide shot with fast motion."

13. **Seedance《MiniMax H3 Plastic Skin Fix for Video Ads》** — <https://www.seedance.tv/blog/minimax-h3-plastic-skin-fix-for-video-ads>
    > "The fourth is **scale**: if the face occupies too few pixels, no instruction can recover fine skin information."
    > "**Match the reference to the planned shot size.** A tight speaking shot needs a tight reference; a wide running shot should not be expected to reproduce pore-level detail."
    > "**Make one prompt per shot. Reusing a long master prompt across a close-up, wide shot, and product macro can create contradictions. Carry only the true invariants: identity, skin finish, wardrobe, product, light direction, and color palette.** Change action, lens, framing, and camera movement shot by shot."
    > "Can a negative prompt remove waxy skin? It can reduce unwanted styling, but it **cannot restore texture missing from the reference** or pixels missing from a distant face."

14. **太平洋科技《AI图生视频常见坑：参考图风格不一致怎么解决》** — <https://www.pconline.com.cn/ai/article/1647853.html>
    > "角色上一秒还是厚涂写实风，**下一秒就变成了赛璐璐卡通脸**。"（← 与我们的现象同型，但他们的场景是同一镜头内）
    > "模型容易为了维持动态流畅，**牺牲风格细节，转而用最常见的默认画风去'脑补'缺失部分**。" / "时间步长累积误差"
    > "这些风格词最好放在提示词的最前面。" / "避免厚涂变平涂" / "不要频繁换参考图" / "相似度…合理区间在 0.4~0.7"

15. **腾讯云开发者社区《AI 短剧/漫剧生成工程化实践》** — <https://cloud.tencent.cn/developer/article/2754003>
    > 系统分层："分镜层：场景、镜头、**景别**、运镜、时长"；"视觉层：角色卡、场景卡、**风格卡**、首尾帧"
    > "关键点：角色名、场景名、**风格词必须固定**；**单镜头只写一个动作**"

16. **阿里云开发者社区《面向连载内容的 AI 漫剧工程化实现》** — <https://developer.aliyun.com/article/1755304>
    > 摘要（正文未读到）："解决角色漂移、色彩闪烁、**线条软化**、流程割裂四大痛点"（⚠️ 只拿到摘要，不算硬依据）

### ④ 社区讨论 / 模型仓

17. **r/StableDiffusion《Minimax H3 - Best settings and practices for non-turbo generations》** — <https://www.reddit.com/r/StableDiffusion/comments/1wxy7zd/>（镜像可读）
    > u/SwitchDangerous8686："**Shorter, more literal prompts also seem to matter more here than on H2, the model gets twitchy with flowery language.**"
    > u/MastMaithun："Turbo works for simple thing but **when you involve multiple things, turbo loses its mind.**"
    > u/apostrophefee："the only good thing about euler simple is when i go for anime style **the style is more distinctive**."

18. **r/StableDiffusion《Which prompt to use to correctly use a character sheet in minimax H3?》** — <https://www.reddit.com/r/StableDiffusion/comments/1wygxoa/>
    > u/Sad_Berry_4621："In the summary section of the prompt, use **[Reference Generation], not [Keyframe Completion]**."
    > u/yeah-i-shouldnt-have："**The reason I describe the woman in the character sheet is that it then allows me to reference those in the prompt**… If I just rely on MiniMax picking them up from the image it can be a bit more hit and miss."

19. **HF `lovis93/studio-1939-old-animation-lora-minimax-h3`（H3 专用风格 LoRA）** — <https://huggingface.co/lovis93/studio-1939-old-animation-lora-minimax-h3>
    > "**studio1939-light (r16) — painterly.** … **studio1939-strong (r64) — full cel.** Bold flat-shaded characters with clean outlines over painted backgrounds… **Same prompt, same seed — only the LoRA rank changes.**"
    > Recipe："**Prompt expansion: off — write the full art direction yourself**"；"Scale: `1.0` for the full look; `0.4–0.8` to blend it under a modern art direction"；"Best results with **exhaustive prompts: name every color, every element, and end with what must not appear**"
    > "Freeze a character description **word-for-word** and repeat it verbatim in every prompt"
    > 规模证据："87 scenes; all 261 shots generated in 28 minutes"（同一套冻结人设 + 穷举美术指令）

20. **HF `WarmBloodAban/Minimax-h3_Singularity` 提示词规范（社区整理，739 likes）** — <https://huggingface.co/WarmBloodAban/Minimax-h3_Singularity>
    > §1："Composition — framing, **shot size**, subject placement, foreground/background relationships."
    > §4："If a picture only supplies appearance, identity, clothing, environment, **or style**, place that relationship inside the Subject definition."
    > §11："Words such as 'cinematic,' 'epic,' 'high quality,' and 'dynamic' … **should never replace observable visual instructions.**"

### ⑤ 学术（只作背景，不是本问题的直接证据）

21. **CRAFT-LoRA: Content-Style Personalization via Rank-Constrained Adaptation**（CVPR 2026） — <https://openaccess.thecvf.com/content/CVPR2026/papers/Li_CRAFT-LoRA_Content-Style_Personalization_via_Rank-Constrained_Adaptation_and_Training-Free_Fusion_CVPR_2026_paper.pdf>
    ⇒ LoRA 的 rank 约束同时决定"内容 / 风格"的取舍——与 19 号"rank16=厚涂、rank64=全平涂"的实证对得上。**未读全文，只作旁证。**

---

## 没查到的（不许编）

1. **"特写/近景 ⇒ 平涂/赛璐璐"的权威因果解释**：没查到。没有官方说明、没有论文、没有高赞社区帖直接说这件事。
   搜过的关键词：`style drift shot scale` / `anime cel shading close up AI video` / `close-up flat shading` / `style consistency across shot sizes` / `特写 画风 崩` / `近景 平涂` / `景别 画风 不一致` / `AI漫剧 风格漂移` / `\"close-up\" \"cel shaded\" inconsistency` / `shot size style drift`。
2. **MiniMax 官方文档里关于 shot size 与画风/细节/渲染的任何说明**：没查到。官方 base/ref 指南只把"风格"定义为开篇 1–2 句；`shot size` 只在示例里作为构图词出现（`medium-wide shot`、`close-up`、`close shot`）。
3. **H3 用户报告"同一短片里特写变平涂"**：没查到。HF MiniMax-H3 的 116 条 discussions 列表页抓取两次都只返回空白框架；Reddit 搜到的 H3 讨论集中在 settings/LoRA/角色表，没有这条。
4. **WanGP / mmgp 里给 H3 的"风格强度"或"负向提示词"参数**：确认**不存在**（`no_negative_prompt: True`；参考图旋钮只有 `image_refs_relative_size`，且它调细节保真不是画风强度）。也没查到 H3 走 IP-Adapter 的路子。
5. **"靠统一景别避免跳变"的直接说法**：没查到。反而查到相反立场——ArcLoop 说"近景、远景和动作切镜可以有不同构图，但可以共享同一套线稿、调色逻辑和材质限制"（即靠**统一规则**，不是靠统一景别）。
6. **invideo.io 的 FAQ（"Why Wide Shots Look More Realistic…"等三篇）**：抓取 4 次全部失败，只拿到标题，**正文没读到 ⇒ 不作为依据**。
7. **MiniMax 开放平台 API 文档的完整参数表**：页面两次都在参数表之前被截断，**没有核到 API 侧是否有 negative 类字段**；"没有负向通道"这条结论只建立在**官方权重是 CFG-distilled** ＋ **WanGP 本地实现 `no_negative_prompt: True`** 之上。

---

## 附：下一步验证建议（A/B，同 seed）

| 组 | 变量 | 判据 |
| --- | --- | --- |
| A（基线） | 现状：一条长 prompt 跨景别 | 记录特写段是否赛璐璐 |
| B | 拆成"远景一条 / 特写一条"，只带不变量 | 特写段是否保住半写实 |
| C | 在 B 基础上：风格写成 `<Subject 2>` + `retention_analysis: fully_preserved`，风格句挪到 `[Shot 1]` 之前 2 句 | 同上，且角色身份没掉 |
| D | 在 C 基础上：Text Encoder `NVFP4 AWQ` → `Quanto INT8` | 判断是不是量化吃掉风格段 |
| E | 在 C 基础上：`image_refs_relative_size` 100 → 400 | 判断是不是参考图细节预算 |
| F（贵） | 上风格 LoRA（painterly 档），scale 0.4–0.8 | 是否彻底压住平涂 |

> ⚠️ 一次只改一个变量；每次都固定 seed、分辨率、步数、两阶段开关。
