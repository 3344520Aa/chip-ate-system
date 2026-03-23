import re
import os


# ── 测试阶段关键字映射 ────────────────────────────────────────────
# key   : 标准阶段名
# value : 文件名 token 中可能出现的所有变体
# 匹配规则：token 完全等于变体，或变体开头 + 1~2 位数字后缀（如 RT1、EQC1）
# 数字后缀限制 ≤2 位，防止 FT20260304009 这类 LOT 编号误匹配
STAGE_TOKENS: dict[str, list[str]] = {
    'QA': ['QA'],
    'FT': ['FT', 'FTH', 'FTL', 'FTC', 'EQC'],   # EQC 也归入 FT 类
    'RT': ['RT'],
    'CP': ['CP', 'WT'],
}

# 优先判断顺序（QA > RT > FT > CP）
_STAGE_ORDER = ['QA', 'RT', 'FT', 'CP']

# ── ATE 机台识别关键字 ────────────────────────────────────────────
# 读取文件前 5 行，按顺序匹配；先精确后宽泛
_TESTER_PATTERNS: list[tuple[str, str]] = [
    ('ETS364',  'ETS364'),
    ('STS8300', 'STS8300'),
    ('STS8200', 'STS8200'),
    ('T2K',     '[Tester],T2K'),
    ('TMT',     '[Tester],TMT'),
    ('STS8200',     'sLotsetupinfo'),       # LBS log2csv 转换格式
]


def detect_tester(filepath: str) -> str:
    """
    识别 ATE 机台类型。
    读取文件前 5 行内容，按优先级逐一匹配关键字。

    返回值：'STS8200' | 'STS8300' | 'ETS364B' | 'T2K' | 'TMT' | 'LBS' | 'UNKNOWN'
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            head = [f.readline() for _ in range(5)]
    except Exception:
        return 'UNKNOWN'

    content = ''.join(head)

    for tester_name, keyword in _TESTER_PATTERNS:
        if keyword in content:
            return tester_name

    return 'UNKNOWN'


def detect_test_stage(filename: str, has_coords: bool) -> str:
    """
    识别测试阶段，返回 'CP' | 'FT' | 'RT' | 'QA'。

    策略：
    1. 将文件名（去扩展名）按 _ - 空格 切分为 token 列表
    2. 对每个 token 做 token 级别匹配，避免 LOT 编号中含 FT/RT 字样的误判
       - token 完全等于关键字变体（如 FT、FTH、QA）
       - 或关键字变体开头 + 1~2 位纯数字后缀（如 RT1、EQC1、R1）
    3. 按 QA > RT > FT > CP 优先级返回，有多个命中时取优先级最高的
    4. 文件名无任何命中时，用坐标兜底：有坐标 → CP，否则 → FT
    """
    name = os.path.splitext(os.path.basename(filename))[0].upper()
    tokens = re.split(r'[_\-\s]+', name)

    matched_stages: set[str] = set()

    for token in tokens:
        for stage, keywords in STAGE_TOKENS.items():
            for kw in keywords:
                # 完全匹配，或 关键字 + 1~2 位数字后缀
                if token == kw or re.fullmatch(rf'{kw}\d{{1,2}}', token):
                    matched_stages.add(stage)

    # 按优先级返回第一个命中的阶段
    for stage in _STAGE_ORDER:
        if stage in matched_stages:
            return stage

    # 兜底：有坐标数据 → CP；否则 → FT
    return 'CP' if has_coords else 'FT'
