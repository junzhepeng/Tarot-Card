from __future__ import annotations

from app.constants import OUTCOME_STATUSES, READING_CATEGORIES, READING_TAGS
from app.models.reading import ReadingRecord
from app.models.spread import Spread
from app.services.card_loader import get_spread
from app.services.clarifier import ClarifierReading
from app.services.interpreter import SpreadAnalysis, interpret_spread
from app.services.reading_store import get_clarifier_readings, get_reading


def export_reading_markdown(reading_id: int, mode: str = "full") -> str | None:
    record = get_reading(reading_id)
    if not record:
        return None

    spread = get_spread(record.spread_id)
    if not spread:
        return None

    drawn = [
        (c.position_index, c.card_id, c.is_reversed) for c in record.spread_cards
    ]
    analysis = interpret_spread(spread, drawn)
    clarifiers = get_clarifier_readings(record)

    if mode == "client":
        return _build_client_markdown(record, spread, analysis, clarifiers)
    return _build_full_markdown(record, spread, analysis, clarifiers)


def _append_positions(
    lines: list[str],
    analysis: SpreadAnalysis,
    clarifiers: list[ClarifierReading],
    *,
    include_interpretation_block: bool = True,
) -> None:
    for pos in analysis.positions:
        orient = "逆位" if pos.is_reversed else "正位"
        lines.append(f"### {pos.position_label} · {pos.card_name_zh}（{orient}）")
        lines.append("")
        lines.append(f"> {pos.meaning}")
        lines.append("")
        lines.append(f"关键词：{' · '.join(pos.keywords)}")
        lines.append("")
        if include_interpretation_block:
            lines.append("```")
            lines.append(pos.interpretation)
            lines.append("```")
            lines.append("")

        pos_clarifiers = [c for c in clarifiers if c.clarifies_position == pos.position_index]
        for cr in pos_clarifiers:
            clar_orient = "逆位" if cr.clarifier_is_reversed else "正位"
            lines.append(f"#### 澄清 · {cr.clarifier_card_name_zh}（{clar_orient}）")
            lines.append("")
            lines.append(cr.interpretation)
            lines.append("")

    lines.extend(["## 整阵叙事", ""])
    lines.append(f"**解读技巧：** {analysis.spread_tips}")
    lines.append("")
    for line in analysis.narrative:
        if line == "---":
            lines.append("---")
        else:
            lines.append(f"- {line}")
    lines.append("")


def _build_client_markdown(
    record: ReadingRecord,
    spread: Spread,
    analysis: SpreadAnalysis,
    clarifiers: list[ClarifierReading],
) -> str:
    lines: list[str] = [
        "# 星谕 · 塔罗解读",
        "",
        f"**问题：** {record.question}",
        f"**时间：** {record.created_at}",
        f"**牌阵：** {spread.name_zh}",
        "",
        "---",
        "",
        "## 牌面解读",
        "",
    ]
    _append_positions(lines, analysis, clarifiers, include_interpretation_block=False)

    if record.final_summary:
        lines.extend(["## 解读总结", "", record.final_summary, ""])

    if record.ai_summary:
        lines.extend(["## 深度解读", "", record.ai_summary, ""])

    lines.append("---")
    lines.append("*由星谕塔罗解牌助手生成*")
    return "\n".join(lines)


def _build_full_markdown(
    record: ReadingRecord,
    spread: Spread,
    analysis: SpreadAnalysis,
    clarifiers: list[ClarifierReading],
) -> str:
    lines: list[str] = [
        "# 星谕 · 塔罗解读报告",
        "",
        f"**问题：** {record.question}",
        f"**时间：** {record.created_at}",
        f"**牌阵：** {spread.name_zh}",
        f"**案主：** {record.querent or '未填写'}",
        f"**主题：** {' / '.join(READING_TAGS.get(t, t) for t in record.tags) or '无'}",
        f"**分类：** {READING_CATEGORIES.get(record.category, record.category or '未分类')}",
        f"**应验状态：** {OUTCOME_STATUSES.get(record.outcome_status, record.outcome_status)}",
        "",
        "---",
        "",
        "## 牌阵解读",
        "",
    ]
    _append_positions(lines, analysis, clarifiers, include_interpretation_block=True)

    lines.extend(["## 模式分析", ""])
    patterns = analysis.patterns
    lines.append(
        f"- 大阿卡纳 {patterns['major_count']} · 小阿卡纳 {patterns['minor_count']}"
    )
    lines.append(
        f"- 正位 {patterns['upright_count']} · 逆位 {patterns['reversed_count']}"
    )
    if patterns.get("elements"):
        elem_parts = [f"{k} {v}" for k, v in patterns["elements"].items()]
        lines.append(f"- 元素分布：{' · '.join(elem_parts)}")
    lines.append("")

    if record.ai_summary:
        lines.extend(["## AI 深度解读", "", record.ai_summary, ""])

    if record.first_impression or record.notes or record.final_summary:
        lines.extend(["## 分层笔记", ""])
        if record.first_impression:
            lines.extend(["### 第一印象", "", record.first_impression, ""])
        if record.notes:
            lines.extend(["### 过程笔记", "", record.notes, ""])
        if record.final_summary:
            lines.extend(["### 最终总结", "", record.final_summary, ""])

    if record.outcome_notes or record.review_due_at:
        lines.extend(["## 应验回顾", ""])
        if record.review_due_at:
            lines.append(f"**计划回访：** {record.review_due_at}")
            lines.append("")
        if record.reviewed_at:
            lines.append(f"**回顾时间：** {record.reviewed_at}")
            lines.append("")
        if record.outcome_notes:
            lines.append(record.outcome_notes)
            lines.append("")

    lines.append("---")
    lines.append("*由星谕塔罗解牌助手导出*")
    return "\n".join(lines)
