from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

import numpy as np

from src.config.settings import DESTINATIONS


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = " ".join(text.split())
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.upper()


def normalize_id(value: Any) -> str:
    return normalize_text(value).replace(" ", "")


def _canonical_origin_id(value: Any) -> str:
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return ""
    # caso clássico de cast float: 12345.0 -> 12345
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    # chave de origem é numérica: manter apenas dígitos
    s = re.sub(r"\D+", "", s)
    return s


def as_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (float, int, np.integer, np.floating)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".") if "," in text else text
    try:
        return float(text)
    except ValueError:
        return None


def get_dest_key_by_departamento(departamento: str) -> Optional[str]:
    departamento_norm = normalize_text(departamento)
    if not departamento_norm:
        return None
    for dest_key, cfg in DESTINATIONS.items():
        for kw in cfg.get("dept_keywords", []):
            if normalize_text(kw) and normalize_text(kw) in departamento_norm:
                return dest_key
    return None


def has_motivo_desligamento(raw_value: Any) -> bool:
    if raw_value is None:
        return False
    if isinstance(raw_value, str):
        return bool(raw_value.strip())
    if isinstance(raw_value, dict):
        labels = raw_value.get("labels")
        if isinstance(labels, list) and any(str(x).strip() for x in labels):
            return True
        label = raw_value.get("label")
        if isinstance(label, str) and label.strip():
            return True
    return bool(str(raw_value).strip())


def get_target_group_id(
    dest_cfg: Dict[str, Any],
    motivo_desligamento_raw: Any,
    tipo_desligamento_raw: Any,
) -> str:
    if has_motivo_desligamento(motivo_desligamento_raw) or has_motivo_desligamento(tipo_desligamento_raw):
        return dest_cfg["grupo_desligados_id"]
    return dest_cfg["grupo_base_id"]


def get_dest_key_by_contrato(contrato: str) -> Optional[str]:
    return get_dest_key_by_departamento(contrato)
