"""One model client behind one interface. Provider is config, not code.

MAYOR_PROVIDER=openai|anthropic|mock, MAYOR_MODEL=<id>. The mock provider is a
scripted policy so the whole pipeline runs with no keys (checkpoint fallback).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import weave


@dataclass
class LLMConfig:
    provider: str = os.getenv("MAYOR_PROVIDER", "mock")
    model: str = os.getenv("MAYOR_MODEL", "gpt-5.6-luna")
    max_tokens: int = 1200
    temperature: float = 0.2


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


class LLM:
    def __init__(self, cfg: LLMConfig | None = None):
        self.cfg = cfg or LLMConfig()
        self._client: Any = None
        if self.cfg.provider == "openai":
            from openai import OpenAI

            self._client = OpenAI()
        elif self.cfg.provider == "anthropic":
            from anthropic import Anthropic

            self._client = Anthropic()
        elif self.cfg.provider != "mock":
            raise ValueError(f"unknown provider {self.cfg.provider!r}")

    @weave.op()
    def complete_json(self, system: str, user: str, *, purpose: str = "") -> dict[str, Any]:
        """Return a JSON object. `purpose` is for the trace only."""
        if self.cfg.provider == "mock":
            return _mock_policy(user)
        if self.cfg.provider == "openai":
            resp = self._client.chat.completions.create(
                model=self.cfg.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                max_completion_tokens=self.cfg.max_tokens,
            )
            return _extract_json(resp.choices[0].message.content or "{}")
        # anthropic
        resp = self._client.messages.create(
            model=self.cfg.model,
            max_tokens=self.cfg.max_tokens,
            system=system + "\nRespond with a single JSON object and nothing else.",
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content)
        return _extract_json(text)


# ---------------------------------------------------------------------------
# Mock policy: a deterministic, slightly-sensible mayor for keyless runs.
# It reads the state block out of the prompt and reacts to it.
# ---------------------------------------------------------------------------


def _mock_policy(user: str) -> dict[str, Any]:
    m = re.search(r"CURRENT STATE \(json\):\s*(\{.*?\})\s*\n", user, flags=re.S)
    if "POST-MORTEM" in user:
        return {
            "lessons": [
                {"when": "pollution above 50", "did": "built factories", "outcome": "happiness fell",
                 "rule": "build a park for every factory", "confidence": 0.6}
            ]
        }
    if not m:
        return {"actions": [], "reasoning": "mock: no state found"}
    s = json.loads(m.group(1))
    actions: list[dict[str, Any]] = []
    if s.get("services", 50) < 30 and s.get("treasury", 0) > 200:
        actions.append({"name": "fund_services", "args": {"level": 1}})
    if s.get("unemployment", 0) > 0.1 and s.get("treasury", 0) > 300:
        actions.append({"name": "build_factory", "args": {"count": 1}})
    if s.get("pollution", 0) > 50 and s.get("treasury", 0) > 120:
        actions.append({"name": "build_park", "args": {"count": 1}})
    if s.get("housing_ratio", 1.1) < 1.0:
        actions.append({"name": "build_housing", "args": {"units": 100}})
    return {"actions": actions[:3], "reasoning": "mock: react to state"}
