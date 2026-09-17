from __future__ import annotations

from app.constants import OUTCOME_STATUSES, READING_CATEGORIES
from app.services.card_loader import get_card, get_spread
from app.services.interpreter import interpret_spread
from app.services.reading_store import get_clarifier_readings, get_reading


def export_reading_markdown(reading_id: int) -> str | None:
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

    lines: list[str] = [
        "# 星谕 · 塔罗解读报告",
        "",
        f"**问题：** {record.question}",
        f"**时间：** {record.created_at}",
        f"**牌阵：** {spread.name_zh}",
        f"**分类：** {READING_CATEGORIES.get(record.category, record.category or '未分类')}",
        f"**应验状态：** {OUTCOME_STATUSES.get(record.outcome_status, record.outcome_status)}",
        "",
        "---",
        "",
        "## 牌阵解读",
        "",
    ]

    for pos in analysis.positions:
        orient = "逆位" if pos.is_reversed else "正位"
        lines.append(f"### {pos.position_label} · {pos.card_name_zh}（{orient}）")
        lines.append("")
        lines.append(f"> {pos.meaning}")
        lines.append("")
        lines.append(f"关键词：{' · '.join(pos.keywords)}")
        lines.append("")
        lines.append("```")
        lines.append(pos.interpretation)
        lines.append("```")
        lines.append("")

        pos_clarifiers = [c for c in clarifiers if c.clarifies_position == pos.position_index]
        for cr in pos_clarifiers:
            clar_orient = "逆位" if cr.clarifier_is_reversed else "正位"
            lines.append(
                f"#### 澄清牌 · {cr.clarifier_card_name_zh}（{clar_orient}）"
            )
            lines.append("")
            lines.append("```")
            lines.append(cr.interpretation)
            lines.append("```")
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

    if record.notes:
        lines.extend(["## 占卜笔记", "", record.notes, ""])

    if record.outcome_notes:
        lines.extend(["## 应验回顾", ""])
        if record.reviewed_at:
            lines.append(f"**回顾时间：** {record.reviewed_at}")
            lines.append("")
        lines.append(record.outcome_notes)
        lines.append("")

    lines.append("---")
    lines.append("*由星谕塔罗解牌助手导出*")
    return "\n".join(lines)
