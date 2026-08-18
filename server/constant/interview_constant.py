"""面试相关常量 — Prompt 模板 / 超时配置 / WS 标记"""

from server.models.result import Result

# ═══════════════════════════════════════════════════════
# WebSocket 消息标记
# ═══════════════════════════════════════════════════════

STREAM_START = Result.ws_msg(data={"type": "stream_start"})
STREAM_END = Result.ws_msg(data={"type": "stream_end"})
KEEPALIVE = Result.ws_msg(data={"type": "ping"})

# ═══════════════════════════════════════════════════════
# Prompt 模板
# ═══════════════════════════════════════════════════════

WELCOME = (
    "👋 你好！欢迎参加 {title} 岗位面试。"
    "本次计划进行 {total} 道主问题，系统会根据回答质量在必要时追加一次针对性追问。"
    "准备好了吗？输入任意内容开始..."
)

# 保留兼容导出。实际出题阶段由 InterviewWorkflow 生成更精确的阶段指令。
FIRST_Q = (
    "【重要】你是面试官，只能提问和追问，禁止替候选人说话或生成候选人的回答。"
    "请开始面试，先让候选人做自我介绍。只提问，等待回答。"
)
NEXT_Q = (
    "【重要】你是面试官，禁止替候选人说话或补全回答。"
    "请根据系统提供的当前面试阶段和已有上下文生成下一道问题。"
    "只需提问，不要评价、打分或重复候选人的回答。"
)

# ── 非流式评分 prompt（独立 evaluator LLM，不污染面试 Agent 历史）──
SCORE_PROMPT = """你是面试评分引擎。请根据题目、候选人回答和题库参考进行结构化评价。

当前面试环节：{expected_question_type}
面试题：{question}
候选人回答：{answer}

## 参考标准答案（来自题库，可能为空）
{reference}

总体分数区间：
- 90~100：理解深入，有明确原理、权衡或实际落地经验
- 75~89：核心结论正确，但深度、案例或边界条件不足
- 60~74：基本方向正确，但存在明显遗漏
- 60以下：答非所问、关键概念错误或缺乏有效信息

请同时给出 0~1 的四个维度分数：
- completeness：回答完整性
- relevance：与问题的相关性
- technical_depth：技术/分析深度；非技术问题可按论证深度评估
- evidence_strength：事实、项目细节、数据或具体案例支撑程度

follow_up_required 只表示你是否建议追问，最终是否追问由程序规则决定。
question_type 必须返回当前面试环节 {expected_question_type}，不要自行改成其他类型。

返回格式（直接输出 JSON，不要 markdown 包裹）：
{{
  "feedback":"10~30字自然反馈，不出现评分/打分字样",
  "score":75,
  "question_type":"{expected_question_type}",
  "comment":"给HR看的评分备注（20~80字）",
  "completeness":0.75,
  "relevance":0.90,
  "technical_depth":0.62,
  "evidence_strength":0.55,
  "follow_up_required":true,
  "follow_up_reason":"缺少关键技术细节或具体案例"
}}"""

FINAL_EVAL_PROMPT = (
    "面试已全部结束。请基于下方完整面试记录生成最终评价。"
    "不得遗漏候选人的真实回答，也不要根据简历内容替候选人补充未回答的信息。"
    "返回纯 JSON（不要 markdown 代码块包裹）：\n"
    '{{"total_score":85,"is_pass":true,"summary":"综合评价（100-200字，面向HR）",'
    '"strengths":"优势","weaknesses":"不足","suggestion":"建议"}}'
)
EARLY_EXIT_PROMPT = (
    "候选人主动结束了面试。请仅基于已经完成的真实问答生成评价，并在 summary 中说明面试提前结束。"
    "返回纯 JSON（不要 markdown 代码块包裹）：\n"
    '{{"total_score":70,"is_pass":false,"summary":"综合评价（100-200字，面向HR）",'
    '"strengths":"优势","weaknesses":"不足","suggestion":"建议"}}'
)

# ═══════════════════════════════════════════════════════
# 面试配置
# ═══════════════════════════════════════════════════════

EXIT_KW = ("结束面试", "退出", "quit")
RECV_TO = 600
CONFIRM_TO = 120
REPORT_TO = 120
ANSWER_MAX = 2000
QNS_MAX = 50
