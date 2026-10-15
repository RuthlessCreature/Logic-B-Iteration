"""Permanent security identifier is exchange plus six-digit code, never name or ST."""
from __future__ import annotations
import re

def canonical_code(value: str) -> str:
    code = str(value).strip().upper()
    if re.fullmatch(r"(SH|SZ|BJ)\.\d{6}", code):
        market, digits = code.split(".")
        return f"{digits}.{market}"
    if re.fullmatch(r"\d{6}\.(SH|SS|SZ|BJ)", code):
        return code[:-2] + "SH" if code.endswith(".SS") else code
    if re.fullmatch(r"\d{6}\.(?:XSHG|XSHE)", code):
        return code[:6] + (".SH" if code.endswith("XSHG") else ".SZ")
    if re.fullmatch(r"\d{6}", code):
        raise ValueError("exchange missing: bare six-digit code is ambiguous")
    raise ValueError(f"unsupported stock symbol: {value!r}")
