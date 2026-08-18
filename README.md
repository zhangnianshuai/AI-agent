# AI 智能面试官与人才评估系统

面向校园招聘、求职训练与岗位能力评估场景的 AI 面试系统。系统围绕候选人简历、岗位画像与企业题库完成结构化面试，支持文字/语音交互、动态追问、回答评分、面试报告和 HR 后台管理。

## 核心设计

### 1. 有状态面试 Workflow

面试流程采用 **Deterministic Workflow + Agentic Node** 的混合设计：

- LangGraph StateGraph 管理自我介绍、项目深挖、专业能力、行为面试和反问等主阶段；
- LLM 负责问题生成、语义理解和结构化评分，程序负责阶段迁移、追问上限与结束条件；
- 回答评分拆分为完整性、相关性、技术深度、事实/案例支撑等维度；
- 当回答存在明显信息缺口时触发一次受限追问，避免纯 ReAct 模式下的无界循环；
- 文字和语音面试共用同一套 Workflow，WebSocket 仅承担不同传输层职责。

### 2. Hybrid RAG 题库检索

题库使用 Milvus 构建混合检索：

- Dense Vector：语义向量召回；
- Sparse Vector：Milvus BM25；
- RRF：融合 Dense / Sparse 两路结果；
- 企业/岗位题库通过 partition 进行检索范围约束；
- Embedding 使用 TTL + 容量限制缓存，降低重复向量化请求。

专业能力出题可通过 `search_question_bank` 工具检索题库依据；单轮评分同时检索参考答案和评分标准，作为独立 evaluator 的参考上下文。

### 3. 结构化评估与 Transcript

单轮评分使用独立非流式 evaluator，不污染面试 Agent 对话历史。评分结果包含：

- score
- completeness
- relevance
- technical_depth
- evidence_strength
- follow_up_required / follow_up_reason

每轮真实问题、候选人回答和评分结果会写入结构化 transcript。最终 HR 报告直接基于完整 transcript 生成，避免将简历信息误当作候选人在面试中的真实表现。

### 4. 流式语音面试

语音链路采用：

`WebSocket -> faster-whisper STT -> Streaming LLM -> 文本切句 -> bounded concurrent TTS -> ordered playback`

TTS 采用受限并发和顺序缓冲，兼顾首段语音响应时间与播放顺序；连续 STT 失败、TTS 超时和报告生成异常均有明确兜底路径。

### 5. SQL Guard 与 Agent 可观测性

管理员自然语言查询在执行前进入只读 SQL Guard：仅允许单条 SELECT，解析全部 FROM/JOIN 表并进行白名单校验，禁止 UNION、CTE、子查询、危险函数和锁定读取，拒绝 `SELECT *` 与 `password_hash` 等敏感字段，并自动限制最大返回行数。复杂查询采用 fail-closed 策略，要求 Agent 改写为更容易授权的显式 JOIN。

Agent 调用同时写入轻量 Trace：记录组件、模型、总耗时、检索耗时、工具名称、输出长度和运行状态，不落完整 Prompt 或候选人回答。管理员可通过 `/admin/agent/traces` 查看最近运行轨迹。

### 6. 后台与 Agent 工具

系统包含候选人端与 HR / Admin 后台，覆盖：

- 简历上传与解析
- 企业/岗位管理
- 岗位画像与题库管理
- 文字/语音面试
- 面试记录与报告
- SQL Agent / Milvus / MCP 工具调用
- JWT + 角色及资源归属权限控制
- Agent 会话复用与空闲回收

## 项目结构

```text
server/
├── agent/
│   ├── base_agent.py
│   ├── interview_agent.py
│   ├── interview_workflow.py
│   ├── sql_agent.py
│   ├── agent_tools/
│   └── agent_skills/
├── api/
├── service/
├── dao/
├── models/
├── constant/
└── utils/

webui/webui/
└── src/

tests/
└── test_interview_workflow.py
```

## 本地运行

1. 创建虚拟环境并安装依赖：

```bash
pip install -r requirements.txt
```

2. 复制 `.env-example` 为 `.env`，配置 MySQL、Milvus、模型和 Embedding 参数。

3. 初始化数据库表，并确保 Milvus 服务及题库数据可用。

4. 启动后端：

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

5. 启动前端：

```bash
cd webui/webui
npm install
npm run dev
```

## 测试

```bash
pip install -r requirements-dev.txt
pytest -q tests
```

当前测试覆盖 SQL Guard 的 SELECT-only、JOIN 表白名单、危险结构拦截与 LIMIT 边界；在安装 LangGraph 的完整运行环境中还会执行面试阶段规划、弱维度追问、追问次数边界和结束条件测试。后续可继续补充检索离线评测与端到端面试流程测试。
