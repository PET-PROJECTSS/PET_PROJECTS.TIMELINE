from __future__ import annotations

from typing import Any

from app.config import SCHEMA_VERSION


def default_payload() -> dict[str, Any]:
    return {
        "uid": 4,
        "schema_version": SCHEMA_VERSION,
        "nodes": [
            {"id": "node-1", "x": 80, "y": 200, "width": 320, "height": 200,
             "title": "Увеличить доход", "type": "Path",
             "note": "Рост зарплаты, переход в более сильную команду, поиск доп. источников.",
             "due": "2026–2027", "duration": "8 месяцев"},
            {"id": "node-2", "x": 460, "y": 50, "width": 320, "height": 200,
             "title": "Подготовить первый взнос", "type": "Path",
             "note": "Резерв, подушка, расчёт ежемесячного накопления.",
             "due": "до марта 2027", "duration": "10 месяцев"},
            {"id": "node-3", "x": 470, "y": 340, "width": 320, "height": 200,
             "title": "Выбрать район и объект", "type": "Path",
             "note": "Сравнить ЖК, транспорт, платежи, сроки сдачи.",
             "due": "лето 2027", "duration": "3 месяца",
             "substeps": [
                 {"id": "step-1", "title": "Сравнить жилые комплексы", "done": True},
                 {"id": "step-2", "title": "Проверить транспорт и инфраструктуру", "done": False},
                 {"id": "step-3", "title": "Рассчитать ежемесячный платёж", "done": False},
             ]},
            {"id": "node-4", "x": 900, "y": 195, "width": 320, "height": 200,
             "title": "Купить квартиру", "type": "Goal",
             "note": "Главная цель. Выход на сделку, оформление ипотеки, переезд.",
             "due": "до декабря 2028", "duration": "6 месяцев"},
        ],
        "links": [
            {"id": "link-1", "from": "node-1", "to": "node-3", "label": "4 месяца"},
            {"id": "link-2", "from": "node-2", "to": "node-3", "label": "6 месяцев"},
            {"id": "link-3", "from": "node-3", "to": "node-4", "label": "2 месяца"},
        ],
        "viewport": {"panX": 0, "panY": 0, "scale": 1},
    }


def _migrate_substeps(node: dict[str, Any]) -> list[dict[str, Any]]:
    substeps = node.get("substeps")
    if not isinstance(substeps, list):
        return []
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in substeps:
        if not isinstance(step, dict):
            continue
        sid = str(step.get("id") or "")
        if not sid:
            sid = f"step-{len(clean) + 1}"
        if sid in seen:
            continue
        seen.add(sid)
        clean.append({
            "id": sid,
            "title": str(step.get("title") or ""),
            "done": bool(step.get("done")),
        })
    return clean


def migrate_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    current = int(payload.get("schema_version", 0))
    if current >= SCHEMA_VERSION:
        return payload, False
    changed = current < SCHEMA_VERSION
    out = dict(payload)
    if current < 2:
        nodes: list[dict[str, Any]] = []
        for node in payload.get("nodes", []):
            if not isinstance(node, dict):
                continue
            migrated_node: dict[str, Any] = dict(node)
            if "note" not in migrated_node or not isinstance(migrated_node.get("note"), str):
                migrated_node["note"] = migrated_node.pop("desc", "") or ""
            migrated_node.pop("desc", None)
            if "duration" not in migrated_node or not isinstance(migrated_node.get("duration"), str):
                migrated_node["duration"] = str(migrated_node.pop("months", "") or "")
            migrated_node.pop("months", None)
            migrated_node["type"] = "Goal" if str(migrated_node.get("type", "Path")).lower() == "goal" else "Path"
            migrated_node.setdefault("done", False)
            migrated_node.setdefault("due", "")
            migrated_node.setdefault("width", 320)
            migrated_node.setdefault("height", 200)
            nodes.append(migrated_node)
        out["nodes"] = nodes
        if "links" not in out and isinstance(payload.get("edges"), list):
            links: list[dict[str, Any]] = []
            for edge in payload.get("edges", []):
                if not isinstance(edge, dict):
                    continue
                src, dst = edge.get("from"), edge.get("to")
                if not src or not dst:
                    continue
                links.append({
                    "id": edge.get("id") or f"link-{src}-{dst}",
                    "from": src,
                    "to": dst,
                    "label": str(edge.get("label") or edge.get("months") or "переход"),
                })
            out["links"] = links
        viewport = payload.get("viewport")
        if not isinstance(viewport, dict):
            viewport = {}
        out["viewport"] = {
            "panX": viewport.get("panX", viewport.get("x", 0)),
            "panY": viewport.get("panY", viewport.get("y", 0)),
            "scale": viewport.get("scale", 1),
        }
        out.setdefault("uid", 0)
    if current < 3:
        nodes: list[dict[str, Any]] = []
        for node in out.get("nodes", []):
            if not isinstance(node, dict):
                continue
            migrated_node: dict[str, Any] = dict(node)
            if str(migrated_node.get("type", "Path")).lower() == "goal":
                migrated_node["substeps"] = []
            else:
                migrated_node["substeps"] = _migrate_substeps(migrated_node)
            nodes.append(migrated_node)
        out["nodes"] = nodes
    out["schema_version"] = SCHEMA_VERSION
    return out, changed
