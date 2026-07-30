"""LLM-as-judge: use any LLM provider to rate reasoning quality.

Supports: OpenAI, Anthropic, Gemini, Ollama (local), and any
OpenAI-compatible endpoint (OpenRouter, Groq, etc.).
Provider is auto-detected from environment variables or passed explicitly.
"""

import json
import os
import urllib.request
from typing import Optional


class LLMJudge:
    """Rate reasoning chain quality using any LLM provider.

    Provider auto-detection order:
    1. Explicit constructor params (provider, api_key, model)
    2. Environment variables:
       - OPENAI_API_KEY → OpenAI
       - ANTHROPIC_API_KEY → Anthropic
       - GEMINI_API_KEY → Gemini
       - OLLAMA_HOST → Ollama (local)
    """

    JUDGE_PROMPT = """You are an AI quality auditor. Rate this agent reasoning chain on 3 criteria:

1. COHERENCE (1-5): Are the steps logically connected? No jumps or contradictions?
2. GOAL ADHERENCE (1-5): Does the reasoning stay focused on the original goal?
3. COMPLETENESS (1-5): Are all necessary steps present? Nothing skipped?

Reasoning chain:
{reasoning}

Respond ONLY with JSON: {{"coherence": N, "goal_adherence": N, "completeness": N, "brief": "1 sentence summary"}}"""

    def __init__(
        self,
        sample_rate: float = 0.05,
        min_samples: int = 5,
        alert_threshold: float = 3.0,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.sample_rate = sample_rate
        self.min_samples = min_samples
        self.alert_threshold = alert_threshold
        self.provider = provider or self._detect_provider()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        if self.provider:
            self._resolve_config()

    def _detect_provider(self) -> Optional[str]:
        """Auto-detect provider from environment."""
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.environ.get("GEMINI_API_KEY"):
            return "gemini"
        if os.environ.get("OLLAMA_HOST"):
            return "ollama"
        return None

    def _resolve_config(self):
        """Resolve API key, model, and base URL for the detected provider."""
        if self.provider == "openai":
            self.api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
            self.model = self.model or "gpt-4o-mini"
            self.base_url = self.base_url or "https://api.openai.com/v1"
        elif self.provider == "anthropic":
            self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
            self.model = self.model or "claude-3-5-haiku-latest"
        elif self.provider == "gemini":
            self.api_key = self.api_key or os.environ.get("GEMINI_API_KEY")
            self.model = self.model or "gemini-2.0-flash"
        elif self.provider == "ollama":
            self.model = self.model or "llama3.2"
            self.base_url = self.base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434/v1")
        elif self.provider == "custom":
            # User must provide all params explicitly
            pass

    def rate(self, reasoning_text: str) -> dict:
        """Rate a single reasoning chain. Returns dict with scores."""
        prompt = self.JUDGE_PROMPT.format(reasoning=reasoning_text[:3000])

        if not self.provider:
            return self._no_provider_result()

        try:
            if self.provider in ("openai", "ollama", "custom"):
                return self._call_openai_compatible(prompt)
            elif self.provider == "anthropic":
                return self._call_anthropic(prompt)
            elif self.provider == "gemini":
                return self._call_gemini(prompt)
        except Exception as e:
            return {"coherence": None, "goal_adherence": None, "completeness": None, "brief": f"Error: {e}"}

    def _call_openai_compatible(self, prompt: str) -> dict:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 1000,
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key or 'ollama'}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            msg = data["choices"][0]["message"]
            text = msg.get("content")
            if text is None and msg.get("reasoning"):
                # Reasoning model: content was empty but reasoning has the
                # answer.  Skim the last paragraph for a JSON blob.
                text = msg["reasoning"]
            return self._parse_json(text)

    def _call_anthropic(self, prompt: str) -> dict:
        body = json.dumps({
            "model": self.model,
            "max_tokens": 200,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            text = data["content"][0]["text"]
            return self._parse_json(text)

    def _call_gemini(self, prompt: str) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 200},
        }).encode()

        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_json(text)

    def _parse_json(self, text: str) -> dict:
        """Extract JSON from LLM response that may contain markdown."""
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())

    def _no_provider_result(self) -> dict:
        return {
            "coherence": None,
            "goal_adherence": None,
            "completeness": None,
            "brief": "No LLM provider configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or OLLAMA_HOST.",
        }

    def rate_batch(self, reasoning_texts: list) -> dict:
        """Rate a batch. Returns aggregated scores + individual ratings."""
        import random

        sample_size = min(
            len(reasoning_texts),
            max(self.min_samples, int(len(reasoning_texts) * self.sample_rate))
        )
        sampled = random.sample(reasoning_texts, min(sample_size, len(reasoning_texts)))

        scores = []
        for text in sampled:
            rating = self.rate(text)
            scores.append(rating)

        valid_scores = [
            (s["coherence"] + s["goal_adherence"] + s["completeness"]) / 3
            for s in scores
            if s["coherence"] is not None
        ]

        return {
            "avg_score": round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else None,
            "samples_rated": len(scores),
            "valid_ratings": len(valid_scores),
            "individual_scores": scores,
            "alert": (sum(valid_scores) / len(valid_scores)) < self.alert_threshold if valid_scores else False,
        }
