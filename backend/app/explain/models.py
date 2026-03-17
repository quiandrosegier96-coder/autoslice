"""
AutoSlice — Explanation data models.

Each generated setting gets one SettingExplanation with:
  - setting:  human name of the setting group
  - value:    the actual chosen value(s), as a display string
  - reason:   one plain-English sentence explaining why
  - icon:     hint for the frontend ("check" / "warning" / "info")

ExplanationReport groups all items plus a one-sentence overall summary.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SettingExplanation(BaseModel):
    setting: str
    value:   str
    reason:  str
    icon:    Literal["check", "warning", "info"] = "info"


class ExplanationReport(BaseModel):
    summary: str
    items:   list[SettingExplanation]
