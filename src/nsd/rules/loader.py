"""Muat aturan dari JSON lokal. Hanya berkas lokal; tidak ada sumber jarak jauh."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nsd.rules.schema import validate_rule


@dataclass
class RuleSet:
    rules: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    digest: str = ""


def default_rules_dir() -> Path:
    env = os.environ.get("NSD_RULES_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "rules"
    return Path(__file__).resolve().parents[3] / "rules"


def load_rules(directory: Path | None = None) -> RuleSet:
    directory = Path(directory) if directory else default_rules_dir()
    rs = RuleSet()
    h = hashlib.sha256()
    seen: dict[str, str] = {}
    for path in sorted(directory.glob("*.json")):
        raw = path.read_bytes()
        h.update(path.name.encode()); h.update(raw)
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            rs.errors.append(f"{path.name}: JSON tidak valid ({exc.__class__.__name__})")
            continue
        items = doc.get("rules") if isinstance(doc, dict) else None
        if not isinstance(items, list):
            rs.errors.append(f"{path.name}: harus berisi objek dengan kunci 'rules' (list)")
            continue
        for rule in items:
            errs = validate_rule(rule)
            rid = rule.get("id", "?") if isinstance(rule, dict) else "?"
            if rid in seen:
                errs.append(f"id duplikat (sudah ada di {seen[rid]})")
            if errs:
                rs.errors.extend(f"{path.name}:{rid}: {e}" for e in errs)
                continue
            seen[rid] = path.name
            rs.rules.append(rule)
    rs.digest = h.hexdigest()
    return rs
