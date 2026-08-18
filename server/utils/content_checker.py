"""统一违禁内容检测（纯正则匹配）"""

import re
import string

from server.models.job import Job

# ═══════════════════════════════════════════════════════════
# 违禁规则（全部正则，一个入口）
# ═══════════════════════════════════════════════════════════

_VIOLATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # ── 诈骗 / 违规招聘 ──
    (re.compile(r'(刷单|刷榜|刷信誉|刷好评)'),                  '涉嫌刷单诈骗'),
    (re.compile(r'(兼职.*日结|日入|日赚|时薪\d{3,})'),          '涉嫌虚假高薪招聘'),
    (re.compile(r'(无需.*经验.*月入|轻松.*过万|躺着.*赚钱)'),    '涉嫌虚假招聘'),
    (re.compile(r'(微商|直销|发展下线|拉人头)'),                '涉嫌传销'),
    (re.compile(r'(陪聊|陪玩|情感陪护|特殊服务)'),              '涉嫌违规服务'),
    (re.compile(r'(代考|代写|代做|枪手)'),                      '涉嫌作弊服务'),
    (re.compile(r'(出售|买卖).*(账号|个人信息|数据)'),          '涉嫌非法交易'),
    (re.compile(r'(赌博|博彩|彩票|时时彩)'),                    '涉嫌赌博'),
    (re.compile(r'(网贷|贷款|放款|套现)'),                      '涉嫌非法金融'),
    # ── 违禁词（原 illegal_words.txt 合并到这里）──
    (re.compile(r'(色情|seqing|毒品|贩毒|恐怖主义|反动|dubo)'), '包含违法词汇'),
]

# 预编译一个合并版，contains_illegal_word 用
_COMBINED = re.compile(
    "|".join(f"({p.pattern})" for p, _ in _VIOLATION_PATTERNS),
    re.IGNORECASE,
)

_ALLOWED_PASSWORD_CHARS = frozenset(string.ascii_letters + string.digits + string.punctuation)


# ═══════════════════════════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════════════════════════

def check_content(text: str) -> bool:
    """检测文本是否违规。True = 安全，False = 违规"""
    if not text:
        return True
    return not _COMBINED.search(text)


def check_job_content(job: Job) -> bool:
    """检测 Job 模型的文本内容是否违规"""
    parts = [
        p for p in (
            job.title, job.description, job.location,
            job.category, job.education_requirement, job.experience_requirement,
        ) if p
    ]
    return check_content(" ".join(parts))


def contains_illegal_word(value: str) -> bool:
    """检测单个值是否包含违禁词"""
    return bool(_COMBINED.search(value))


def validate_registration(username: str, password: str) -> str | None:
    """校验注册信息；合法返回 None，否则返回错误提示"""
    if not 5 <= len(username) <= 12:
        return "用户名长度必须为5到12个字符"

    if any(c.isspace() for c in username):
        return "用户名不能包含空格"

    if not 6 <= len(password) <= 20:
        return "密码长度必须为6到20个字符"

    if contains_illegal_word(username):
        return "用户名包含违法词汇"

    if contains_illegal_word(password):
        return "密码包含违法词汇"

    if any(c not in _ALLOWED_PASSWORD_CHARS for c in password):
        return "密码只能包含英文字母、数字和符号"

    has_letter = any(c in string.ascii_letters for c in password)
    has_digit = any(c in string.digits for c in password)
    has_symbol = any(c in string.punctuation for c in password)
    if not (has_letter and has_digit and has_symbol):
        return "密码必须同时包含英文字母、数字和符号"

    return None
