from __future__ import annotations

LAYOUT_PRESETS: dict[str, dict] = {
    "line": {
        "name": "一字横排",
        "desc": "经典时间流、三牌阵，从左到右依次阅读",
        "min_cards": 1,
        "max_cards": 10,
    },
    "grid": {
        "name": "网格排列",
        "desc": "多牌通用，自动换行，适合主题矩阵",
        "min_cards": 2,
        "max_cards": 12,
    },
    "cross": {
        "name": "十字形",
        "desc": "中心为处境，上下左右为挑战/基础/建议/结果（需 5 张）",
        "min_cards": 5,
        "max_cards": 5,
    },
    "pyramid": {
        "name": "金字塔",
        "desc": "底层为基础，逐层向上，顶端为结论",
        "min_cards": 3,
        "max_cards": 10,
    },
    "columns": {
        "name": "双列对照",
        "desc": "左右两列对比，适合自我与他人、选择与结果",
        "min_cards": 2,
        "max_cards": 10,
    },
    "horseshoe": {
        "name": "马蹄形",
        "desc": "弧形展开，经典七张马蹄（7 张时效果最佳）",
        "min_cards": 5,
        "max_cards": 9,
    },
}


def build_layout(preset: str, count: int) -> dict:
    count = max(count, 1)
    if preset == "line":
        return {
            "type": "grid",
            "preset": preset,
            "cols": count,
            "rows": 1,
            "coords": [[i, 0] for i in range(count)],
        }
    if preset == "cross" and count == 5:
        return {
            "type": "grid",
            "preset": preset,
            "cols": 3,
            "rows": 3,
            "coords": [[1, 0], [0, 1], [1, 1], [2, 1], [1, 2]],
        }
    if preset == "pyramid":
        return _pyramid_layout(count)
    if preset == "columns":
        return _columns_layout(count)
    if preset == "horseshoe":
        return _horseshoe_layout(count)
    return _grid_layout(count, preset)


def _grid_layout(count: int, preset: str = "grid") -> dict:
    cols = min(max(count, 1), 4)
    rows = (count + cols - 1) // cols
    return {
        "type": "grid",
        "preset": preset,
        "cols": cols,
        "rows": rows,
        "coords": [[i % cols, i // cols] for i in range(count)],
    }


def _columns_layout(count: int) -> dict:
    left_count = (count + 1) // 2
    coords = []
    for i in range(count):
        col = 0 if i < left_count else 1
        row = i if i < left_count else i - left_count
        coords.append([col, row])
    rows = max(left_count, count - left_count)
    return {"type": "grid", "preset": "columns", "cols": 2, "rows": rows, "coords": coords}


def _pyramid_layout(count: int) -> dict:
    coords: list[list[int]] = []
    row = 0
    remaining = count
    col_offset = 0
    while remaining > 0:
        row_width = min(row + 1, remaining)
        start_col = col_offset
        for c in range(row_width):
            coords.append([start_col + c, row])
        col_offset += 0
        remaining -= row_width
        row += 1
    max_col = max(c[0] for c in coords) + 1 if coords else 1
    return {
        "type": "grid",
        "preset": "pyramid",
        "cols": max_col,
        "rows": row,
        "coords": coords,
    }


def _horseshoe_layout(count: int) -> dict:
    if count == 7:
        coords = [[0, 1], [0, 0], [1, 0], [2, 0], [3, 0], [3, 1], [3, 2]]
        return {"type": "grid", "preset": "horseshoe", "cols": 4, "rows": 3, "coords": coords}
    return _grid_layout(count, "horseshoe")
