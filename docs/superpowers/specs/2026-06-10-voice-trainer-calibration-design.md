# Voice Trainer — 个人标定(阶段二·第一块)设计文档

**日期**: 2026-06-10
**状态**: 设计已确认,待生成实现计划
**前置**: 阶段一 MVP 已上线(实时音高+共鸣双轨,内置通用元音模板)。

## 1. 目标与范围

让用户录自己的元音,建**个人元音模板**,替换内置通用模板。此后:
- `classify_vowel` 用用户自己的元音空间 → 分类更准。
- `normalized_resonance` 基准 = 用户自己的元音 → 共鸣数 = "相对你自己起点抬升了多少",真正个人化。
- 目标带暂仍用"基线 + X 八度"默认(resonance 0.15–0.7、f0 165–220),目标带编辑 UI 留后续 cycle。

**标定对象**:用户**当前/中性**放松说话的声音(基线),不是目标声。
**元音覆盖**:全 5 个 a/e/i/o/u,每个拉长发 ~2–3 秒。

### 诚实边界
- 个人模板让基线/分类更准,但 Task 4 记录的"翻格"是最近邻分类的**结构性**问题(整体抬升越过 Voronoi 边界),换个人模板只能**缓解不能根治**;真正根治(分类对整体抬升不变)是独立的后续修法,本 cycle 不夸大。

### YAGNI 边界
- **本 cycle 内**:5 元音标定流、个人模板、JSON 持久化、实时反馈用上个人模板、calibrate/profile 端点、标定 UI。
- **留后**:单元音 F1×F2 定位图、目标带编辑 UI、目标声录制、多命名 profile、录制复盘(阶段三)、翻格根治修法。

## 2. 方法选型:个人模板如何进入分析

现状:`classify_vowel` / `normalized_resonance` 用模块级常量 `VOWEL_TEMPLATES`。

**选定方案 A + 轻量 C**:模板作为**参数穿过纯函数**(默认参数 = 内置 `VOWEL_TEMPLATES`,老调用/测试不动);用 `Profile` 对象(模板 + 目标带)承载,WS 连接时 `load_active()` 后把 templates 透传进纯函数、band 给 `contains()`。

**不选**:模块级"当前模板"可变全局(引入全局可变状态,毁掉纯函数可测性)。

## 3. 模块边界(扩展现有,不另起炉灶)

- `analysis/vowel.py`:为 `classify_vowel` / `normalized_resonance` 增加 `templates` 参数,默认 `VOWEL_TEMPLATES`。
- `analysis/frame.py`:`analyze_frame(samples, sr, templates=VOWEL_TEMPLATES)`,透传给 vowel 函数。
- `analysis/calibrate.py`(新):`analyze_vowel_recording(samples, sr) -> Optional[Tuple[float,float]]`——整段 clip 滑窗复用 `estimate_f0`+`estimate_formants`,收 voiced 且 F1/F2 有效的窗,取 F1、F2 中位数;有效窗太少返回 None(触发重录)。
- `profiles.py`(新):`Profile` 数据模型 + 本地 JSON 存取(`load_active()` / `save(profile)`)。
- `app.py`:新增 `POST /api/calibrate`、`PUT /api/profile`、`GET /api/profile`;WS 连接时 `load_active()`,把 templates 透传给 `analyze_frame`、band 给 `contains`。
- 前端 `src/calibrate.ts`(新):引导式标定流;`src/main.ts`:加 Calibrate 入口按钮。复用麦克风采集,但走"录一段 clip 再 HTTP POST",不走 WS 流。

## 4. 数据模型

```
Profile {
  vowel_templates: { "a":[f1,f2], "e":[f1,f2], "i":[f1,f2], "o":[f1,f2], "u":[f1,f2] },
  target: TargetProfile,          # 复用现有:band 字段 + contains()
  source: "builtin" | "calibrated"
}
```

- 持久化到 `backend/data/profile.json`(gitignore,单激活 profile)。
- 路径走 env `PROFILE_PATH`,默认 `backend/data/profile.json`;测试指向临时文件做隔离。
- `load_active()`:有文件→解析(source="calibrated");无文件→内置 `VOWEL_TEMPLATES` + `builtin_default()` 带(source="builtin")。
- `save(profile)`:原子写 JSON(先写临时文件再 rename)。
- 复用 `targets.py` 的 `TargetProfile.contains()`,不重写判定逻辑。

## 5. 标定提取细节 `analyze_vowel_recording`

- 输入:某元音的整段 clip(~2–3s PCM)+ sample_rate。
- 处理:按 ~75ms 窗滑动,逐窗复用 `estimate_f0` + `estimate_formants`,只收"voiced 且 F1/F2 都有"的窗;取 F1、F2 各自的**中位数**(持续元音下最稳)。
- 拒收(返 None → 前端重录):有效窗 < 总窗 30% 或 < 5 个——挡掉静音/纯气声/录太短。

## 6. 数据流(标定)

1. 点 **Calibrate** → 进入引导流。
2. 对每个元音(a→e→i→o→u):显示提示("拉长发 啊 …")→ 录 ~2–3s clip → `POST /api/calibrate {vowel, clip}` → 后端 `analyze_vowel_recording` → 返回 `{f1,f2}` 或 `{retake:true}`。
3. 重录直到 5 个都拿到 → `PUT /api/profile {vowel_templates}` → 后端 `save(Profile(templates, builtin_default() 带, "calibrated"))`。
4. 回实时视图;WS 重连时 `load_active()` 拿到个人模板,实时反馈即用个人模板。

## 7. 后端端点

- `POST /api/calibrate?vowel=<a|e|i|o|u>&sampleRate=<n>`:body = 原始 Int16 小端 PCM clip(同实时的字节约定,raw body 不做 JSON 包裹);resp = `{"f1":.., "f2":..}` 或 `{"retake": true}`。无状态(不在后端存 pending,客户端自己攒 5 个)。
- `PUT /api/profile`:body = JSON `{"vowel_templates": {"a":[f1,f2], ...5 个...}}`;校验 5 个齐全(缺 → 400);保存为 calibrated profile;resp = 保存后的 profile。
- `GET /api/profile`:返回激活 profile(templates + band + source);未标定返回 builtin。
- 既有 `GET /api/target` **改为**从 `load_active().target` 取,使其反映激活 profile(本 cycle band 仍是默认,但口径统一,后续带编辑自然生效)。

## 8. 实时链路改动

WS 连接时 `profile = load_active()`;循环里 `analyze_frame(buf, sr, templates=profile.vowel_templates)`,`profile.target.contains(...)`。其余不变。标定后重连即生效(前端标定完成后重连 WS 或刷新)。

## 9. 错误处理(都退化成有意义状态,不崩)

- 单元音录不到稳定共振峰 → `/api/calibrate` 返回 `retake`,前端"没录到稳定的 X,再来一次"。
- `PUT /api/profile` 缺元音 → 400 + 明确信息。
- `GET /api/profile` 未标定 → 返回 builtin(前端显示"用通用模板/未标定")。
- `profile.json` 损坏/读不了 → 回退 builtin + 记日志,不崩;WS 加载失败同样回退 builtin。

## 10. 测试

- `analyze_vowel_recording`:合成持续元音(复用源-滤波器 `_vowel`)→ (f1,f2) 贴近合成值;静音/太短 → None。
- `vowel.py` 带 `templates` 参数:在传入的个人模板上 `normalized_resonance==0`;`classify_vowel` 用传入模板。
- `frame.py`:`analyze_frame(..., templates=...)` 透传生效(resonance 对传入模板计算)。
- `profiles.py`:save→load 往返;无文件→builtin;损坏文件→builtin。
- 端点:`POST /api/calibrate` 出 f1/f2(喂合成元音 clip);`PUT`+`GET /api/profile` 往返;WS 用上激活 profile(in_target 反映加载的模板/带)。测试用临时 `PROFILE_PATH` 隔离,不碰真 profile。
- 前端采音/UI 无单测,`tsc` 类型检查 + 标定流手动冒烟。

## 11. 落地顺序(实现计划将据此展开)

1. 分析层加 `templates` 参数(vowel → frame),默认内置,老测试全绿。
2. `analyze_vowel_recording`(TDD)。
3. `profiles.py`:Profile 模型 + JSON 存取 + load_active 回退(TDD)。
4. 端点 `GET/PUT /api/profile`、`POST /api/calibrate`;WS 接 `load_active` 透传(TDD,临时 PROFILE_PATH)。
5. 前端 `calibrate.ts` 引导流 + main.ts 入口;手动冒烟。
