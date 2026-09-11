# 原模型与多模态真实推理验收

这是 Windows 本地工程验收，不是专家标注研究集的准确率认证。输入为提前冻结答案的合成图片、PDF、语音、视频及已有领域包测试记录；答案不进入模型请求。实际调用、模型身份、结果、失败尝试和源代码摘要分别留证。

## 最终工程验收结果

- 同一代码摘要 `f8158afc0dc52441461cf759ed427de4d557f2939339eaabbfdc4e7cc90a9252` 上，Qwen3 的 HR、林业工单/反馈/回滚、新本体修复三条真实链路均通过；本地 BGE-M3、FAISS、重排及 tokenizer 实测通过。
- 七个多模态文件、十一条观察完成独立精确比对：八次视觉推理、两次 ASR、一次文本 PDF 解析。
- 后端完整执行 1932 项：1923 PASS、9 SKIP、0 FAIL；其中可选 PDF 用例在模型环境补测通过，独立覆盖合计 1924 PASS、8 项 Windows 平台限制跳过。前端 39 项、lint、类型检查和生产构建通过。
- 完整浏览器首跑保留 7 PASS、1 FAIL、2 个条件 SKIP；混合资料的 503 用例在原代码、原限时下独立重验通过，两个条件读取用例也分别通过，十个用例全部有通过覆盖。没有把首次失败重写为 PASS。
- Wheel/源码包重建一致、两套全新安装通过；全新 Git 检出后的 169 个 schema 标识、契约目录和 7 项身份/契约测试通过。

机器可读总表见 [当前验收记录](original-models-validation.json)。主流程仍是预发布工程实现，不将分支合并等同于科研准确率认证或生产上线。

## 执行边界

- Qwen2.5 通过 SiliconFlow 实际推理；响应模型名会校验，但托管服务没有提供权重摘要或 vLLM 运行时证明，因此不宣称自部署 vLLM 已实测。
- BGE-M3、bge-reranker-v2-m3 和 Qwen2.5 tokenizer 从固定 Hugging Face revision 下载到忽略目录 `runtime/models/`。验收前逐文件校验 SHA-256。检索实际调用 FlagEmbedding 和 FAISS IndexFlatIP，没有 LLM 排序替代。
- Qwen2-VL-2B 从已有本地快照加载，Transformers CPU 实际推理，不下载或执行远程模型代码。
- 语音明确授权后上传 SiliconFlow 的指定 ASR 模型。模型请求名不等同于托管权重证明。音频定位是整段音轨，不伪造逐字时间戳。
- 视频实际解码帧并提取音轨。默认最多四帧，保存帧序号和该帧的时间范围；本轮夹具为恒定帧率，时间按帧序号/报告帧率计算，变帧率输入未验收，不应用于精确时间关联。不宣称对任意长视频穷尽理解，也不将单帧文字扩展成整个时间段的事实。
- 图片保留整图区域定位；扫描 PDF 保留页定位。扫描夹具经 pypdf 确认没有文本层，再经 Poppler 渲染和人工可视检查。带文本层的 PDF 使用原解析器，收据明确记为解析而非 OCR。

## 独立执行

新接口 `zhigou_toolchain.ingestion.multimodal.infer` 返回 `ZHIGOU_MULTIMODAL_OBSERVATIONS`，含原文件摘要、定位、模型输出和推理收据。`verify_receipt` 要求外部冻结的收据摘要和原文件重新核验。

这些结果始终是 `NOT_GRANTED` 待审核观察，不冒充从原文件可确定性重提取的 EvidenceRecord 文本；原来的 `ingestion.plan/run` 和元数据解析器保持原有行为。此轮新增的是独立 Python/CLI 推理入口，**没有声称工作台已自动将 OCR/ASR 结果入正式本体**。正式候选仍须现有映射/审核/校验流程，不允许模型绕过授权。

```powershell
# 独立环境；不要修改其他项目的全局 Torch/Transformers。
python -m venv .venv-models
.venv-models/Scripts/python -m pip install -e '.[dev,ingestion-multimodal,modeling-models]'
.venv-models/Scripts/python -m pip install -r requirements-model-validation.txt

# 这一步显式下载固定快照；应用启动和正常接入不会自行下载模型。
.venv-models/Scripts/python tools/prepare_original_models.py
.venv-models/Scripts/python tools/verify_original_multimodal.py prepare --output runtime_reports/my-model-run
.venv-models/Scripts/python tools/verify_original_multimodal.py original --output runtime_reports/my-model-run
.venv-models/Scripts/python tools/verify_original_multimodal.py multimodal --output runtime_reports/my-model-run --vision-path <已有Qwen2-VL-2B快照绝对路径>

# 对明确授权的实际音频单独生成观察收据；不会覆盖现存收据。
.venv-models/Scripts/python tools/infer_multimodal.py <音频.wav> --media-type audio/wav --authorize-network --output runtime_reports/audio-observation.json
```

`SILICONFLOW_API_KEY` 只从进程环境读取，不写入项目或日志。模型依赖安装清单是测试环境版本约束，不是完整传递依赖锁。准备夹具使用 Windows System.Speech，PDF/视频的生产推理接口不依赖该语音合成工具。

原模型全业务链路使用显式 Qwen 托管配置运行 `tools/verify_live_assistance.py --original-models --pack hr`，以及 `--pack forestry-workorders`；新本体修复运行 `--pack repair`。这些测试仍通过真实 Worker、同一控制面和精确答案检查。

已通过配置可在当前终端显式设置（不输出或永久保存密钥）：

```powershell
$env:OPENAI_BASE_URL = 'https://api.siliconflow.cn/v1'
$env:OPENAI_TEXT_MODEL = 'Qwen/Qwen3-30B-A3B-Instruct-2507'
$env:OPENAI_API_KEY = $env:SILICONFLOW_API_KEY
$env:OPENAI_RESPONSE_FORMAT = 'json_object'
.venv-models/Scripts/python tools/verify_live_assistance.py --original-models --pack hr
```

## 已发现并保留的差异

7B Qwen 的一次建模输出没有满足闭合 JSON 契约，系统拒绝输出，没有将错误候选通过审核。Qwen2.5-72B 已通过 HR 整链，但复杂林业与修复尝试分别出现契约不符、HTTP 400、对已声明 IRI 规则仍报告未决的问题。保留这些失败，并使用同为 Qwen 系列的 Qwen3-30B-A3B-Instruct-2507 做对照验收；不把 Qwen3 的结果冒充 Qwen2.5 的结果。

SenseVoiceSmall 将英文 “Tree” 误识别为数字，未通过冻结答案；同一音频由 Qwen3-ASR-1.7B 实际转写，未修改答案来迁就模型。

PDF 渲染资源释放的兼容问题已修复并加入独立回归测试。所有失败尝试与后续重验分开记录，不将首次失败改写成通过。

17 次实测尝试的脱敏收据见 [原模型运行证据](evidence/original-model-runs.json)，固定输入保存在 `evidence/model-inputs/`。原始运行文件的摘要同时保留，没有将脱敏副本冒充原始字节。

独立严格比对见 [逐观察精确核验](evidence/multimodal-exact-audit.json)：七个文件、十一条观察逐条匹配，不只检查关键词是否出现。视频编码在切换点保留了一帧前画面，因此用实际解码帧与预先冻结的两张原图的像素距离确定每帧金标准，不根据 OCR 预测选择答案。

最终机器可读结果与合并记录见同目录验收记录；历史证据副本中六份报告的本机绝对路径已规范化，结果、跳过原因和既有校验摘要没有改变，原始运行文件仍保留在本机运行目录。
