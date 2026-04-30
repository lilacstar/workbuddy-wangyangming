# -*- coding: utf-8 -*-
"""
王阳明工具 - Phase 3 分析器
功能：从语料样本中提取句式统计、词汇风格、标志性表达、生成表达DNA
设计原则：量化统计 + LLM定性归类，参考女娲 extraction-framework.md 的表达DNA方法论
"""

import re
import json
from typing import Any, TypedDict
from dataclasses import dataclass, asdict
from collections import Counter


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class SentenceStats:
    """句式统计（量化层）"""
    total_chars: int
    total_sentences: int
    avg_sentence_length: float        # 平均句子长度（字符数）
    avg_word_count: float             # 平均词数（粗略）
    question_ratio: float             # 疑问句比例
    exclamation_ratio: float          # 感叹句比例
    ellipsis_ratio: float             # 省略号使用频率
    dash_ratio: float                 # 破折号使用频率
    short_sentence_ratio: float       # 短句（<10字）比例


@dataclass
class VocabularyStyle:
    """词汇风格归类"""
    formality_level: str              # 正式/口语/混合
    abstraction_level: str           # 抽象/具体/混合
    emotional_register: str          # 情感色彩：温暖/中性/冷峻/波动
    first_person_ratio: float        # 第一人称使用频率
    hedging_markers: list[str]       # 模糊词（大概/可能/也许）
    certainty_markers: list[str]    # 确定性词（一定/绝对/肯定）


@dataclass
class SignaturePhrases:
    """标志性表达提取"""
    high_freq_phrases: list[tuple[str, int]]  # 高频短语 [(phrase, count), ...]
    opening_patterns: list[str]        # 开头模式
    closing_patterns: list[str]        # 结尾模式
    personal_tropes: list[str]        # 个人修辞偏好
    hesitation_signals: list[str]     # 犹豫信号（嗯/这个/然后）
    unique_expressions: list[str]     # 独特表达（此人特有的句式）


@dataclass
class LogicalStructure:
    """逻辑结构特征"""
    organization_style: str          # 结构偏好：金字塔/漏斗/平行/自由
    conclusion_position: str         # 结论位置：先说/后说/边说边给
    evidence_preference: list[str]   # 证据偏好：数据/故事/类比/引用/经验
    causal_reasoning_style: str     # 因果推理风格：线性/跳跃/对立
    counterfactual_usage: float     # 虚拟语气使用频率


@dataclass
class ExpressionDNA:
    """表达DNA（综合输出）"""
    sentence_stats: SentenceStats
    vocabulary_style: VocabularyStyle
    signature_phrases: SignaturePhrases
    logical_structure: LogicalStructure
    composite_tags: list[str]        # 综合标签，如["短句有力型", "故事驱动型"]
    one_line_portrait: str           # 一句话表达画像


@dataclass
class Phase3Result:
    """Phase 3 完整分析结果"""
    task_count: int
    texts: list[str]                 # 原始文本列表
    sentence_stats: SentenceStats
    vocabulary_style: VocabularyStyle
    signature_phrases: SignaturePhrases
    logical_structure: LogicalStructure
    expression_dna: ExpressionDNA
    warnings: list[str]
    llm_raw_output: dict[str, Any]


# ============================================================
# 量化分析层（规则计算，无需LLM）
# ============================================================

# 句子结束标点
SENTENCE_ENDINGS = r"[。！？\.!?]+"
# 疑问词
QUESTION_MARKERS = r"[吗嘛么？没不？有没怎么怎样如何为什么]"
# 感叹标记
EXCLAMATION_MARKERS = r"[！!]"
# 省略号
ELLIPSIS_MARKERS = r"[……~]"
# 破折号
DASH_MARKERS = r"[——?-]"
# 短句阈值（字符数）
SHORT_SENTENCE_THRESHOLD = 10
# 模糊词列表
HEDGING_WORDS = [
    "大概", "可能", "也许", "似乎", "应该", "感觉",
    "有点像", "有点像", "差不多", "基本上", "一般",
    "相对", "比较", "算是", "应该说", "某种程度上"
]
# 确定性词列表
CERTAINTY_WORDS = [
    "一定", "绝对", "肯定", "必然", "毫无疑问", "确实",
    "毫无疑问", "不置可否", "板上钉钉", "毫无疑问"
]
# 第一人称
FIRST_PERSON = ["我", "我们", "我的", "我们的", "本人", "咱们"]


def calculate_sentence_stats(texts: list[str]) -> SentenceStats:
    """计算句式统计"""
    combined = "\n".join(texts)
    total_chars = len(combined)

    # 切分句子
    sentences = re.split(SENTENCE_ENDINGS, combined)
    sentences = [s.strip() for s in sentences if s.strip()]
    total_sentences = len(sentences)

    if total_sentences == 0:
        return SentenceStats(
            total_chars=0, total_sentences=0,
            avg_sentence_length=0.0, avg_word_count=0.0,
            question_ratio=0.0, exclamation_ratio=0.0,
            ellipsis_ratio=0.0, dash_ratio=0.0,
            short_sentence_ratio=0.0
        )

    # 平均句子长度
    avg_length = total_chars / total_sentences

    # 粗略词数（按空格+标点切分）
    words = re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", combined)
    avg_word_count = len(words) / total_sentences

    # 疑问句比例
    question_count = len(re.findall(QUESTION_MARKERS, combined))
    question_ratio = question_count / total_sentences

    # 感叹句比例
    exclamation_count = len(re.findall(EXCLAMATION_MARKERS, combined))
    exclamation_ratio = exclamation_count / total_sentences

    # 省略号比例
    ellipsis_count = len(re.findall(ELLIPSIS_MARKERS, combined))
    ellipsis_ratio = ellipsis_count / total_sentences

    # 破折号比例
    dash_count = len(re.findall(DASH_MARKERS, combined))
    dash_ratio = dash_count / total_sentences

    # 短句比例
    short_count = sum(1 for s in sentences if len(s) < SHORT_SENTENCE_THRESHOLD)
    short_sentence_ratio = short_count / total_sentences

    return SentenceStats(
        total_chars=total_chars,
        total_sentences=total_sentences,
        avg_sentence_length=round(avg_length, 1),
        avg_word_count=round(avg_word_count, 1),
        question_ratio=round(question_ratio, 3),
        exclamation_ratio=round(exclamation_ratio, 3),
        ellipsis_ratio=round(ellipsis_ratio, 3),
        dash_ratio=round(dash_ratio, 3),
        short_sentence_ratio=round(short_sentence_ratio, 3)
    )


def calculate_vocabulary_style(texts: list[str]) -> VocabularyStyle:
    """计算词汇风格指标"""
    combined = "\n".join(texts)
    total_chars = max(len(combined), 1)

    # 正式/口语判断（简化版）
    formal_markers = ["因此", "然而", "综上所述", "基于此", "由此可见", "故", "故而"]
    casual_markers = ["其实", "我觉得", "大概", "然后", "那个", "就是", "嗯"]
    formal_count = sum(combined.count(m) for m in formal_markers)
    casual_count = sum(combined.count(m) for m in casual_markers)

    if formal_count > casual_count * 2:
        formality_level = "偏正式"
    elif casual_count > formal_count * 2:
        formality_level = "偏口语"
    else:
        formality_level = "混合"

    # 抽象/具体判断
    abstract_markers = ["意义", "价值", "本质", "规律", "逻辑", "概念", "理论", "思想", "哲学"]
    concrete_markers = ["具体", "数字", "名字", "时间", "地点", "做了", "说了", "发生"]
    abstract_count = sum(combined.count(m) for m in abstract_markers)
    concrete_count = sum(combined.count(m) for m in concrete_markers)

    if abstract_count > concrete_count * 2:
        abstraction_level = "偏抽象"
    elif concrete_count > abstract_count * 2:
        abstraction_level = "偏具体"
    else:
        abstraction_level = "混合"

    # 情感色彩
    emotional_positive = ["开心", "高兴", "喜欢", "感恩", "温暖", "幸福", "棒", "赞", "好"]
    emotional_negative = ["痛苦", "难受", "难过", "失望", "糟糕", "无奈", "焦虑", "担心"]
    positive_count = sum(combined.count(m) for m in emotional_positive)
    negative_count = sum(combined.count(m) for m in emotional_negative)

    if positive_count > negative_count * 2:
        emotional_register = "温暖积极"
    elif negative_count > positive_count * 2:
        emotional_register = "冷峻克制"
    elif positive_count + negative_count > 0:
        emotional_register = "中性波动"
    else:
        emotional_register = "中性"

    # 第一人称比例
    first_person_count = sum(combined.count(p) for p in FIRST_PERSON)
    first_person_ratio = first_person_count / total_chars * 1000  # 每千字符

    # 模糊词
    hedging_found = [w for w in HEDGING_WORDS if w in combined]
    certainty_found = [w for w in CERTAINTY_WORDS if w in combined]

    return VocabularyStyle(
        formality_level=formality_level,
        abstraction_level=abstraction_level,
        emotional_register=emotional_register,
        first_person_ratio=round(first_person_ratio, 1),
        hedging_markers=hedging_found,
        certainty_markers=certainty_found
    )


def extract_signature_phrases(texts: list[str]) -> SignaturePhrases:
    """提取标志性表达"""
    combined = "\n".join(texts)

    # 高频短语（2-5字词组，按N-gram）
    def get_ngrams(text: str, n: int) -> list[str]:
        chars = [c for c in text if '\u4e00' <= c <= '\u9fa5']
        return ["".join(chars[i:i+n]) for i in range(len(chars) - n + 1)]

    ngrams = []
    for n in [2, 3, 4]:
        ngrams.extend(get_ngrams(combined, n))

    # 过滤停用词（简化处理）
    stopwords = {"的", "了", "在", "是", "我", "你", "他", "她", "它", "们", "和", "与", "或", "也", "都", "而", "但", "就", "这", "那", "有", "没", "很", "会", "能", "要", "可以", "一个", "一种", "一些", "这个", "那个", "什么", "怎么", "如何", "为什"}
    filtered = [ng for ng in ngrams if ng not in stopwords and len(ng) >= 2]
    freq = Counter(filtered)
    high_freq = freq.most_common(15)

    # 开头模式（每段首句前10字）
    opening_patterns = []
    paragraphs = [p.strip() for p in combined.split("\n") if p.strip()]
    for para in paragraphs[:5]:
        first_sent = re.split(SENTENCE_ENDINGS, para)[0]
        opening_patterns.append(first_sent[:15] if len(first_sent) > 15 else first_sent)

    # 结尾模式
    closing_patterns = []
    for para in paragraphs[:5]:
        sentences = re.split(SENTENCE_ENDINGS, para)
        if sentences:
            last = sentences[-1].strip()
            closing_patterns.append(last[-15:] if len(last) > 15 else last)

    # 犹豫信号
    hesitation_signals = []
    for sig in ["嗯", "呃", "这个", "就是", "然后", "其实", "不过"]:
        if sig in combined:
            hesitation_signals.append(sig)

    return SignaturePhrases(
        high_freq_phrases=high_freq,
        opening_patterns=opening_patterns[:3],
        closing_patterns=closing_patterns[:3],
        personal_tropes=[],  # LLM补充
        hesitation_signals=hesitation_signals,
        unique_expressions=[]  # LLM补充
    )


def extract_logical_structure(texts: list[str]) -> LogicalStructure:
    """提取逻辑结构特征（简化版，更多依赖LLM）"""
    combined = "\n".join(texts)
    sentences = re.split(SENTENCE_ENDINGS, combined)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return LogicalStructure(
            organization_style="unknown",
            conclusion_position="unknown",
            evidence_preference=[],
            causal_reasoning_style="unknown",
            counterfactual_usage=0.0
        )

    # 结论位置判断
    first_sent = sentences[0]
    conclusion_position = _judge_conclusion_position(first_sent, sentences[-1])

    # 证据偏好（关键词检测）
    evidence_prefs = []
    if any(w in combined for w in ["数据", "统计", "研究", "表明", "显示", "根据"]):
        evidence_prefs.append("数据/研究引用")
    if any(w in combined for w in ["我曾经", "有一次", "那时候", "后来", "结果"]):
        evidence_prefs.append("个人故事")
    if any(w in combined for w in ["就像", "比如说", "打个比方", "比如"]):
        evidence_prefs.append("类比")
    if any(w in combined for w in ["有人说", "常说", "不是有句话", "鲁迅说"]):
        evidence_prefs.append("引用/名言")
    if not evidence_prefs:
        evidence_prefs.append("经验直觉")

    # 虚拟语气使用
    counterfactual_count = len(re.findall(r"如果|假如|要是|倘若|要是说", combined))
    counterfactual_usage = counterfactual_count / len(sentences)

    # 组织风格（句子长度分布）
    lengths = [len(s) for s in sentences]
    if lengths:
        variance = sum((l - sum(lengths)/len(lengths))**2 for l in lengths) / len(lengths)
        if variance < 100:
            organization_style = "结构规整"
        elif variance > 400:
            organization_style = "自由散漫"
        else:
            organization_style = "自然流畅"
    else:
        organization_style = "unknown"

    return LogicalStructure(
        organization_style=organization_style,
        conclusion_position=conclusion_position,
        evidence_preference=evidence_prefs,
        causal_reasoning_style="unknown",  # LLM判断
        counterfactual_usage=round(counterfactual_usage, 3)
    )


def _judge_conclusion_position(first_sent: str, last_sent: str) -> str:
    """判断结论位置"""
    first_keywords = ["我觉得", "我认为", "我的看法", "结论是", "总之", "简单说"]
    last_keywords = ["所以", "因此", "总之", "最后", "最终", "关键是"]

    first_has_conclusion = any(k in first_sent for k in first_keywords)
    last_has_conclusion = any(k in last_sent for k in last_keywords)

    if first_has_conclusion and not last_has_conclusion:
        return "结论先行"
    elif not first_has_conclusion and last_has_conclusion:
        return "结论后置"
    elif first_has_conclusion and last_has_conclusion:
        return "首尾呼应"
    else:
        return "边说边给"


# ============================================================
# LLM 驱动：风格归类与表达DNA生成
# ============================================================

def build_style_classification_prompt(
    sentence_stats: SentenceStats,
    vocabulary_style: VocabularyStyle,
    signature_phrases: SignaturePhrases,
    logical_structure: LogicalStructure,
    texts: list[str]
) -> str:
    """
    构建风格归类LLM prompt
    参考女娲 expression-dna.md 的量化+定性方法论
    """
    top_phrases = signature_phrases.high_freq_phrases[:10]
    phrases_text = "\n".join(f"- {p}: {c}次" for p, c in top_phrases)

    return f"""## 任务：分析以下写作样本的表达风格，生成表达DNA

### 量化统计结果
- 总字数：{sentence_stats.total_chars}
- 总句数：{sentence_stats.total_sentences}
- 平均句长：{sentence_stats.avg_sentence_length}字符
- 疑问句比例：{sentence_stats.question_ratio:.1%}
- 感叹句比例：{sentence_stats.exclamation_ratio:.1%}
- 省略号使用：{sentence_stats.ellipsis_ratio:.1%}
- 短句（<10字）比例：{sentence_stats.short_sentence_ratio:.1%}
- 第一人称频率：{vocabulary_style.first_person_ratio:.1%}

### 词汇风格
- 正式程度：{vocabulary_style.formality_level}
- 抽象程度：{vocabulary_style.abstraction_level}
- 情感色彩：{vocabulary_style.emotional_register}
- 模糊词使用：{vocabulary_style.hedging_markers or '无'}
- 确定性词使用：{vocabulary_style.certainty_markers or '无'}

### 高频词组
{phrases_text}

### 结构特征
- 组织风格：{logical_structure.organization_style}
- 结论位置：{logical_structure.conclusion_position}
- 证据偏好：{', '.join(logical_structure.evidence_preference)}
- 虚拟语气使用：{logical_structure.counterfactual_usage:.1%}

### 用户原文样本（供交叉验证）
{chr(10).join(f"[样本{i+1}] {t[:300]}..." for i, t in enumerate(texts))}

---

### 风格归类维度（参考女娲表达DNA方法论）

**句式偏好**：
- 短句有力型：平均句长<15字，短句比例>40%
- 长句缠绕型：平均句长>25字，长句多
- 长短交错型：长短句混合，有节奏感

**词汇风格**：
- 学术型：抽象词多，引用研究数据
- 口语型：短句多，语气词多，"我觉得"频繁
- 文学型：修辞丰富，情感词多，描写细腻
- 务实型：具体词多，数据支撑，案例导向

**逻辑结构**：
- 金字塔型：结论先行，后分层论证
- 漏斗型：宽泛引入，逐步收窄到核心
- 平行型：多角度并列，无明显主次
- 叙事型：以时间/故事线串联

**情感温度**：
- 热：积极情感词密集，感情外露
- 冷：克制，少用情感词，理性分析
- 温差型：整体克制但在关键处爆发

---

### 你的任务

1. 综合以上量化数据和原文样本，给出综合标签（1-3个）
2. 提取3-5个标志性表达（该用户特有的、高频出现的句式或词汇组合）
3. 识别1-2个表达上的潜在弱点（如过度使用某个词/句式）
4. 生成一句话表达画像
5. 如发现与Phase 1/2心理画像存在矛盾，标注预警

### 输出格式

```json
{{
  "composite_tags": ["标签1", "标签2"],
  "signature_phrases": ["标志性表达1", "标志性表达2", "标志性表达3"],
  "style_weaknesses": ["弱点1", "弱点2"],
  "one_line_portrait": "一句话表达画像",
  "phase_coherence_check": "与Phase 1/2的一致性评估，如有矛盾则标注",
  "style_evolution_suggestion": "如有明显套路化倾向，建议如何突破"
}}
```"""


def build_expression_dna(
    sentence_stats: SentenceStats,
    vocabulary_style: VocabularyStyle,
    signature_phrases: SignaturePhrases,
    logical_structure: LogicalStructure,
    texts: list[str],
    llm_provider: callable | None = None
) -> ExpressionDNA:
    """
    生成表达DNA
    如果提供LLM provider，执行完整生成；否则返回量化数据
    """
    if llm_provider:
        prompt = build_style_classification_prompt(
            sentence_stats, vocabulary_style, signature_phrases,
            logical_structure, texts
        )
        raw_output = llm_provider(prompt, "default")
        parsed = _parse_dna_output(raw_output)
        return ExpressionDNA(
            sentence_stats=sentence_stats,
            vocabulary_style=vocabulary_style,
            signature_phrases=signature_phrases,
            logical_structure=logical_structure,
            composite_tags=parsed.get("composite_tags", []),
            one_line_portrait=parsed.get("one_line_portrait", "待分析")
        )
    else:
        # 无LLM时，用量化规则做简单归类
        composite_tags = _rule_based_tags(sentence_stats, vocabulary_style)
        return ExpressionDNA(
            sentence_stats=sentence_stats,
            vocabulary_style=vocabulary_style,
            signature_phrases=signature_phrases,
            logical_structure=logical_structure,
            composite_tags=composite_tags,
            one_line_portrait=f"{composite_tags[0] if composite_tags else '待分析'}风格"
        )


def _rule_based_tags(ss: SentenceStats, vs: VocabularyStyle) -> list[str]:
    """基于规则的简单风格归类（无LLM时的降级方案）"""
    tags = []

    # 句式偏好
    if ss.avg_sentence_length < 15 and ss.short_sentence_ratio > 0.4:
        tags.append("短句有力型")
    elif ss.avg_sentence_length > 25:
        tags.append("长句缠绕型")
    else:
        tags.append("长短交错型")

    # 词汇风格
    if vs.formality_level == "偏正式":
        tags.append("偏学术型")
    elif vs.formality_level == "偏口语":
        tags.append("口语表达型")

    # 情感
    if vs.emotional_register == "温暖积极":
        tags.append("情感外露型")
    elif vs.emotional_register == "冷峻克制":
        tags.append("理性克制型")

    return tags


def _parse_dna_output(raw_output: str) -> dict[str, Any]:
    """解析LLM输出的表达DNA"""
    # 简单正则提取JSON块
    import ast
    match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {}


# ============================================================
# 主入口
# ============================================================

def analyze_phase3(
    texts: list[str],
    llm_provider: callable | None = None,
    llm_model: str = "default"
) -> Phase3Result:
    """
    Phase 3 分析主入口

    参数:
        texts: 用户写作样本列表（2-3个写作任务的输出）
        llm_provider: LLM调用函数
        llm_model: 模型标识
    """
    if not texts:
        return Phase3Result(
            task_count=0,
            texts=[],
            sentence_stats=SentenceStats(0,0,0.0,0.0,0.0,0.0,0.0,0.0,0.0),
            vocabulary_style=VocabularyStyle("unknown","unknown","unknown",0.0,[],[]),
            signature_phrases=SignaturePhrases([],[],[],[],[],[]),
            logical_structure=LogicalStructure("unknown","unknown",[], "unknown",0.0),
            expression_dna=None,
            warnings=["无语料数据"],
            llm_raw_output={}
        )

    # 量化分析层
    sentence_stats = calculate_sentence_stats(texts)
    vocabulary_style = calculate_vocabulary_style(texts)
    signature_phrases = extract_signature_phrases(texts)
    logical_structure = extract_logical_structure(texts)

    # LLM风格归类
    expression_dna = build_expression_dna(
        sentence_stats, vocabulary_style, signature_phrases,
        logical_structure, texts, llm_provider
    )

    # 预警信号
    warnings = []
    if sentence_stats.short_sentence_ratio > 0.7 and sentence_stats.avg_sentence_length < 10:
        warnings.append("短句比例过高，可能过于碎片化")
    if vocabulary_style.first_person_ratio > 100:  # 每千字符>100次
        warnings.append("第一人称使用过于频繁，可能主观色彩过重")
    if not signature_phrases.high_freq_phrases:
        warnings.append("缺乏高频标志性表达，可能风格尚未形成")

    return Phase3Result(
        task_count=len(texts),
        texts=texts,
        sentence_stats=sentence_stats,
        vocabulary_style=vocabulary_style,
        signature_phrases=signature_phrases,
        logical_structure=logical_structure,
        expression_dna=expression_dna,
        warnings=warnings,
        llm_raw_output={}
    )


# ============================================================
# 快速入口：生成阶段3报告（供 skill_generator 调用）
# ============================================================

def summarize_for_generator(result: Phase3Result) -> str:
    """生成Phase 3的摘要文本，供 skill_generator 注入到prompt中"""
    if not result.expression_dna:
        return "Phase 3数据缺失"

    dna = result.expression_dna
    stats = dna.sentence_stats
    vs = dna.vocabulary_style
    sp = dna.signature_phrases
    ls = dna.logical_structure

    lines = [
        f"## Phase 3 表达风格分析",
        f"",
        f"### 句式统计",
        f"- 总字数：{stats.total_chars} | 总句数：{stats.total_sentences} | 平均句长：{stats.avg_sentence_length}字符",
        f"- 短句比例：{stats.short_sentence_ratio:.0%} | 疑问句：{stats.question_ratio:.0%} | 感叹句：{stats.exclamation_ratio:.0%}",
        f"",
        f"### 词汇风格",
        f"- 正式程度：{vs.formality_level} | 抽象程度：{vs.abstraction_level} | 情感色彩：{vs.emotional_register}",
        f"- 第一人称密度：{vs.first_person_ratio:.1%} | 模糊词：{', '.join(vs.hedging_markers[:5]) or '无'}",
        f"",
        f"### 标志性表达（Top 5）",
    ]

    for phrase, count in sp.high_freq_phrases[:5]:
        lines.append(f"- \"{phrase}\"（{count}次）")

    lines.extend([
        f"",
        f"### 结构与逻辑",
        f"- 组织风格：{ls.organization_style} | 结论位置：{ls.conclusion_position}",
        f"- 证据偏好：{', '.join(ls.evidence_preference)}",
        f"",
        f"### 表达DNA",
        f"- 综合标签：{' / '.join(dna.composite_tags)}",
        f"- 一句话画像：{dna.one_line_portrait}",
    ])

    if dna.sentence_stats.short_sentence_ratio > 0.5:
        lines.append(f"- ⚠️ 短句过多，注意节奏控制")

    return "\n".join(lines)


if __name__ == "__main__":
    # 测试
    test_texts = [
        "我觉得这个事吧，要从两个角度看。一个是短期，一个是长期。短期来看，可能会有一些波动，但长期来看，方向是对的。",
        "我遇到过很多次类似的情况。每次我都会先想，这件事对我意味着什么？如果只是表面上的利益，我会更关注内在的成长。如果是真正重要的事，我会全力以赴。",
        "比如说，有一次我做了一个决定。所有人都说不对，但我坚持了。后来证明我是对的。关键不是听谁的，而是看这件事本身值不值得。"
    ]
    result = analyze_phase3(test_texts)
    print("Phase 3 分析结果:")
    print(f"字数: {result.sentence_stats.total_chars}, 句数: {result.sentence_stats.total_sentences}")
    print(f"平均句长: {result.sentence_stats.avg_sentence_length}字符")
    print(f"高频词组: {result.signature_phrases.high_freq_phrases[:5]}")
    print(f"组织风格: {result.logical_structure.organization_style}")
    print(f"结论位置: {result.logical_structure.conclusion_position}")
    print(f"综合标签: {result.expression_dna.composite_tags}")
    print(f"\n摘要输出:")
    print(summarize_for_generator(result))
