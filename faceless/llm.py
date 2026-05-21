"""Thin wrapper around LM Studio's OpenAI-compatible local endpoint."""
from __future__ import annotations

from openai import OpenAI

from .common import die


class LLM:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])

    def chat(self, system: str, user: str) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.cfg["model"],
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self.cfg["temperature"],
                max_tokens=self.cfg["max_tokens"],
            )
        except Exception as e:  # noqa: BLE001
            die(
                f"Couldn't reach the local LLM at {self.cfg['base_url']}.\n"
                f"   Is LM Studio running with a model loaded and the server started?\n"
                f"   (LM Studio → Developer tab → Start Server)\n"
                f"   Original error: {e}"
            )
        return resp.choices[0].message.content.strip()
