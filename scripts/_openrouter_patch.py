"""
_openrouter_patch.py — 멀티 프로바이더 monkey-patch (공통 헬퍼)

지원 프로바이더:
  - openrouter: OpenRouter API (OpenAI 호환)
  - glm:        ZAI API (Anthropic SDK 호환, api.z.ai)
  - minimax:    MiniMax API (OpenAI 호환)

사용법:
    from scripts._openrouter_patch import patch_providers, make_provider
    patch_providers(LLMProvider, PromptBuilder)
    provider = make_provider(LLMProvider, "openrouter", "Claude-3.7-Sonnet",
                             "anthropic/claude-3.7-sonnet")
"""
from __future__ import annotations
import os, re
import openai

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_patched = False


def _strip_think(text: str) -> str:
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return stripped if stripped else text


def patch_providers(LLMProvider, PromptBuilder):
    """LLMProvider.call을 openrouter/glm/minimax 지원으로 monkey-patch."""
    global _patched
    if _patched:
        return
    _patched = True

    _orig_call = LLMProvider.call

    def _patched_call(self, prompt: str, max_tokens: int, system: str = "") -> str:
        if self.provider == "openrouter":
            return _call_openrouter(self, prompt, max_tokens, system, PromptBuilder)
        if self.provider == "glm":
            return _call_glm(self, prompt, max_tokens, system, PromptBuilder)
        if self.provider == "minimax":
            return _call_minimax(self, prompt, max_tokens, system, PromptBuilder)
        return _orig_call(self, prompt, max_tokens, system)

    LLMProvider.call = _patched_call


def _call_openrouter(self, prompt, max_tokens, system, PromptBuilder):
    api_key = os.environ.get("OPENROUTER_API_KEY", self.api_key or "")
    client = openai.OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE,
        default_headers={
            "HTTP-Referer": "https://github.com/jaytoone/HalluMaze",
            "X-Title": "HalluMaze Benchmark",
        },
    )
    effective_tokens = max(max_tokens, 6000) if "thinking" in self.model else max_tokens
    temperature = getattr(self, "_temperature", 0.7)
    resp = client.chat.completions.create(
        model=self.model,
        max_tokens=effective_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system or PromptBuilder.SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )
    return _strip_think(resp.choices[0].message.content or "")


def _call_glm(self, prompt, max_tokens, system, PromptBuilder):
    import anthropic
    api_key = os.environ.get("GLM_API_KEY", self.api_key or "")
    base_url = os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
    # ZAI Anthropic SDK: temperature via extra_body (non-standard extension)
    temperature = getattr(self, "_temperature", 0.7)
    msg = client.messages.create(
        model=self.model,
        max_tokens=max_tokens,
        system=system or PromptBuilder.SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"temperature": temperature},
    )
    return msg.content[0].text


def _call_minimax(self, prompt, max_tokens, system, PromptBuilder):
    api_key = os.environ.get("MINIMAX_API_KEY", self.api_key or "")
    base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    effective_tokens = max(max_tokens, 8000)
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=self.model,
        max_tokens=effective_tokens,
        messages=[
            {"role": "system", "content": system or PromptBuilder.SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )
    return _strip_think(resp.choices[0].message.content or "")


def make_provider(LLMProvider, provider_type: str, display: str, model_id: str,
                  temperature: float = 0.7):
    """프로바이더 인스턴스 생성. temperature는 call() 시 사용됨."""
    key_map = {
        "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
        "glm":        os.environ.get("GLM_API_KEY", ""),
        "minimax":    os.environ.get("MINIMAX_API_KEY", ""),
    }
    api_key = key_map.get(provider_type, "")
    p = LLMProvider(provider=provider_type, api_key=api_key, model=model_id)
    p._display = display
    p._temperature = temperature  # patch가 이 값을 사용
    return p
