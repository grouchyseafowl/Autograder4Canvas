"""
Unified LLM backend for the Insights Engine.

Adapted from EvalEye's llm_backend.py. Text-only (no vision tasks).

FERPA-safe local backends (recommended):
  - ollama:  Local models via Ollama REST API (localhost:11434)
  - mlx:     Apple Silicon text inference via mlx-vlm

External backends (FERPA warning — student data leaves this machine):
  - cloud:   Any OpenAI-compatible API endpoint

All backends implement: send_text(backend, prompt, system_prompt) -> str
"""

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception,
        before_sleep_log,
    )
    _TENACITY = True
except ImportError:
    _TENACITY = False

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FERPA warning
# ---------------------------------------------------------------------------

FERPA_WARNING = (
    "\u26a0\ufe0f  FERPA WARNING: The cloud backend sends student submission "
    "data to an external API at {base_url}. This may not be FERPA-compliant "
    "unless your institution has a Data Processing Agreement (DPA) with the "
    "API provider.\n\n"
    "To use FERPA-safe local processing, use Ollama or MLX — student data "
    "never leaves your machine."
)


# ---------------------------------------------------------------------------
# Backend config
# ---------------------------------------------------------------------------

@dataclass
class BackendConfig:
    """Configuration for one LLM backend."""
    name: str                  # "ollama", "mlx", "cloud"
    model: str = ""            # model name/path
    base_url: str = ""         # API base URL (ollama/cloud)
    api_key: str = ""          # API key (cloud only)
    api_format: str = "openai" # "openai" or "anthropic"
    max_tokens: int = 4096
    temperature: float = 0.1   # low temp for structured output


# ---------------------------------------------------------------------------
# Model tier mapping
# ---------------------------------------------------------------------------

DEFAULT_MODELS = {
    "lightweight": "llama3.1:8b",
    "medium": "llama3.1:70b",
    "deep_thinking": "",  # requires cloud API — user must configure
}


def get_default_model(tier: str) -> str:
    """Return the default Ollama model name for a tier."""
    return DEFAULT_MODELS.get(tier, "llama3.1:8b")


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def _is_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in ("RateLimitError", "APIStatusError", "HTTPStatusError",
                "TimeoutException", "ConnectError"):
        return True
    module = getattr(type(exc), "__module__", "") or ""
    return module.startswith("httpx")


def _with_retry(fn):
    if not _TENACITY:
        return fn
    return retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )(fn)


# ---------------------------------------------------------------------------
# Ollama availability detection (reuses reply_quality_checker pattern)
# ---------------------------------------------------------------------------

_ollama_available: Optional[bool] = None


def check_ollama(base_url: str = "http://localhost:11434") -> bool:
    """Check if Ollama is running. Auto-launches if not."""
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available

    import requests

    # Try to reach Ollama
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=5)
        if r.status_code == 200:
            _ollama_available = True
            return True
    except Exception:
        pass

    # Try to launch it
    log.info("Ollama not running — attempting to start...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(10):
            time.sleep(1)
            try:
                r = requests.get(f"{base_url}/api/tags", timeout=2)
                if r.status_code == 200:
                    log.info("Ollama started successfully")
                    _ollama_available = True
                    return True
            except Exception:
                pass
        log.warning("Ollama didn't come up in time")
    except FileNotFoundError:
        log.warning("ollama command not found")
    except Exception as e:
        log.warning("Failed to launch Ollama: %s", e)

    _ollama_available = False
    return False


def check_ollama_model(model: str, base_url: str = "http://localhost:11434") -> bool:
    """Check if a specific model is available in Ollama."""
    import requests
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return any(
                m == model or m.startswith(model.split(":")[0])
                for m in models
            )
    except Exception:
        pass
    return False


def reset_ollama_cache() -> None:
    """Reset the cached Ollama availability check."""
    global _ollama_available
    _ollama_available = None


# ---------------------------------------------------------------------------
# MLX availability
# ---------------------------------------------------------------------------

# MLX serialization lock — MLX's Metal kernel does not support concurrent calls
# from multiple threads sharing the same loaded model.  All MLX generate() calls
# must be serialized.  Orphaned threads from timed-out calls will block here until
# the previous call completes before the next one starts.
_mlx_lock = threading.Lock()

_mlx_available: Optional[bool] = None


def check_mlx() -> bool:
    """Check if MLX text inference is available.

    Tries mlx_lm (text-only) first, then mlx_vlm (vision+language).
    Either package suffices for text generation.
    """
    global _mlx_available
    if _mlx_available is not None:
        return _mlx_available
    try:
        from mlx_lm import load, generate  # noqa: F401
        _mlx_available = True
    except ImportError:
        try:
            from mlx_vlm import load, generate  # noqa: F401
            _mlx_available = True
        except ImportError:
            _mlx_available = False
    return _mlx_available


# ---------------------------------------------------------------------------
# Auto-detect best available backend
# ---------------------------------------------------------------------------

def auto_detect_backend(
    tier: str = "lightweight",
    settings: Optional[dict] = None,
) -> Optional[BackendConfig]:
    """Auto-detect the best available backend for the given tier.

    Returns None if no LLM backend is available.
    """
    s = settings or {}

    # Check for user-configured cloud API first (for medium/deep tiers)
    # Support both key names: GUI saves insights_cloud_url/key,
    # legacy code used insights_cloud_api_url/key
    cloud_url = s.get("insights_cloud_url", "") or s.get("insights_cloud_api_url", "")
    cloud_key = s.get("insights_cloud_key", "") or s.get("insights_cloud_api_key", "")
    cloud_model = s.get("insights_cloud_model", "")

    if tier == "deep_thinking" and cloud_url and cloud_key:
        return BackendConfig(
            name="cloud",
            model=cloud_model,
            base_url=cloud_url,
            api_key=cloud_key,
            api_format=s.get("insights_cloud_api_format", "openai"),
        )

    # Determine preferred backend order
    preferred = s.get("insights_llm_backend", "ollama")

    ollama_model = s.get("insights_translation_model", "")
    ollama_url = s.get("insights_ollama_url", "http://localhost:11434")
    if not ollama_model:
        ollama_model = get_default_model(tier)

    def _try_mlx():
        if check_mlx():
            return BackendConfig(
                name="mlx",
                model=s.get("insights_mlx_model",
                            "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"),
            )
        return None

    def _try_ollama():
        if check_ollama(ollama_url):
            if check_ollama_model(ollama_model, ollama_url):
                return BackendConfig(
                    name="ollama", model=ollama_model, base_url=ollama_url,
                )
            if ollama_model != "llama3.1:8b" and check_ollama_model("llama3.1:8b", ollama_url):
                log.warning("Model '%s' not found, falling back to llama3.1:8b", ollama_model)
                return BackendConfig(
                    name="ollama", model="llama3.1:8b", base_url=ollama_url,
                )
            log.warning("Ollama running but no suitable model found")
        return None

    # Try preferred backend first, then the other
    if preferred == "mlx":
        result = _try_mlx() or _try_ollama()
    else:
        result = _try_ollama() or _try_mlx()

    if result:
        return result

    # Try cloud as last resort (any tier)
    if cloud_url and cloud_key:
        return BackendConfig(
            name="cloud",
            model=cloud_model,
            base_url=cloud_url,
            api_key=cloud_key,
            api_format=s.get("insights_cloud_api_format", "openai"),
        )

    return None


# ---------------------------------------------------------------------------
# send_text — unified interface
# ---------------------------------------------------------------------------

def send_text(
    backend: BackendConfig,
    prompt: str,
    system_prompt: str = "",
    max_tokens: Optional[int] = None,
) -> str:
    """Send a text prompt to the configured backend. Returns response text.

    Parameters
    ----------
    max_tokens : int, optional
        Override backend.max_tokens for this call only.  Use this to set
        tighter limits for stages that don't need long responses (e.g.,
        theme generation: 1500 tokens, vs. coding: 4096).

    Raises RuntimeError if the backend is unavailable or fails.
    """
    # Apply per-call max_tokens override without mutating the shared config
    effective = backend
    if max_tokens is not None and max_tokens != backend.max_tokens:
        from dataclasses import replace
        effective = replace(backend, max_tokens=max_tokens)

    if effective.name == "ollama":
        return _ollama_text(effective, prompt, system_prompt)
    elif effective.name == "mlx":
        return _mlx_text(effective, prompt, system_prompt)
    elif effective.name == "cloud":
        return _cloud_text(effective, prompt, system_prompt)
    else:
        raise ValueError(f"Unknown backend: {effective.name}")


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

def _ollama_text_impl(
    backend: BackendConfig, prompt: str, system_prompt: str
) -> str:
    import requests

    base = backend.base_url or "http://localhost:11434"
    model = backend.model or "llama3.1:8b"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    r = requests.post(
        f"{base}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": backend.temperature,
                "num_predict": backend.max_tokens,
            },
        },
        timeout=600,  # 10 min — theme generation can be slow on 8B
    )
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


_ollama_text = _with_retry(_ollama_text_impl)


# ---------------------------------------------------------------------------
# MLX backend
# ---------------------------------------------------------------------------

def _mlx_text_impl(
    backend: BackendConfig, prompt: str, system_prompt: str
) -> str:
    # Serialize all MLX calls — Metal kernel doesn't support concurrent access
    # from multiple threads on the same loaded model.
    with _mlx_lock:
        return _mlx_text_inner(backend, prompt, system_prompt)


def _mlx_text_inner(
    backend: BackendConfig, prompt: str, system_prompt: str
) -> str:
    # Try mlx_lm first (text-only, simpler API), fall back to mlx_vlm
    try:
        from mlx_lm import load as mlx_load, generate as mlx_generate
        _use_vlm = False
    except ImportError:
        from mlx_vlm import load as mlx_load, generate as mlx_generate  # type: ignore[no-redef]
        _use_vlm = True

    model_name = backend.model or "mlx-community/Qwen2.5-7B-Instruct-4bit"

    # Module-level cache (attached to the inner function, not the dispatcher)
    if not hasattr(_mlx_text_inner, "_cache"):
        _mlx_text_inner._cache = {}

    if model_name not in _mlx_text_inner._cache:
        model, tokenizer = mlx_load(model_name)
        _mlx_text_inner._cache[model_name] = (model, tokenizer)

    model, tokenizer = _mlx_text_inner._cache[model_name]

    # Build chat-formatted prompt
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    if _use_vlm:
        # mlx_vlm path (vision-language models)
        from mlx_vlm.prompt_utils import apply_chat_template  # type: ignore[import]
        from mlx_vlm.utils import load_config  # type: ignore[import]
        config = load_config(model_name)
        formatted = apply_chat_template(tokenizer, config, full_prompt, num_images=0)
        result = mlx_generate(model, tokenizer, formatted, max_tokens=backend.max_tokens, verbose=False)
        return result.text if hasattr(result, "text") else str(result)
    else:
        # mlx_lm path — apply chat template via tokenizer if available
        if hasattr(tokenizer, "apply_chat_template"):
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            formatted = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False
            )
        else:
            formatted = full_prompt
        return mlx_generate(
            model, tokenizer, prompt=formatted,
            max_tokens=backend.max_tokens, verbose=False,
        )


_mlx_text = _mlx_text_impl  # no retry needed for local


# ---------------------------------------------------------------------------
# Cloud backend (OpenAI-compatible or Anthropic)
# ---------------------------------------------------------------------------

def _cloud_text_impl(
    backend: BackendConfig, prompt: str, system_prompt: str
) -> str:
    if backend.api_format == "anthropic":
        return _anthropic_text(backend, prompt, system_prompt)
    return _openai_text(backend, prompt, system_prompt)


def _openai_text(backend: BackendConfig, prompt: str, system_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=backend.api_key, base_url=backend.base_url)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=backend.model,
        max_tokens=backend.max_tokens,
        temperature=backend.temperature,
        messages=messages,
    )
    return response.choices[0].message.content or ""


def _anthropic_text(backend: BackendConfig, prompt: str, system_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(
        api_key=backend.api_key,
        base_url=backend.base_url or None,
    )
    kwargs = {
        "model": backend.model,
        "max_tokens": backend.max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    response = client.messages.create(**kwargs)
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


_cloud_text = _with_retry(_cloud_text_impl)


# ---------------------------------------------------------------------------
# JSON parsing utility
# ---------------------------------------------------------------------------

def _clean_llm_json(text: str) -> str:
    """Pre-process LLM output to fix common JSON generation artifacts.

    Handles two predictable 8B model failure modes:

    1. Double-brace artifact: model outputs {{ }} instead of { }
       (Python f-string template confusion from training data).
       In JSON, {{ is never valid, so collapsing is always safe.

    2. Invalid escape sequences: model writes \\s, \\c, \\d etc. inside
       string values.  Only \\", \\\\, \\/, \\b, \\f, \\n, \\r, \\t,
       and \\uNNNN are valid JSON escapes.  Stray backslashes are doubled
       so they parse as literal backslashes in the string value.
    """
    import re

    # 1. Collapse Python-style double braces to single JSON braces
    #    Do this before escape-fixing so {{ doesn't confuse the regex.
    text = text.replace("{{", "{").replace("}}", "}")

    # 2. Fix invalid escape sequences inside JSON string values.
    #    Replace \X where X is not a valid JSON escape character with \\X.
    #    Valid single-char escapes: " \ / b f n r t
    #    Valid unicode escape: u followed by 4 hex digits (lookahead keeps 'u')
    text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)

    return text


def parse_json_response(text: str) -> dict:
    """Parse JSON from an LLM response, handling markdown code fences
    and common 8B model generation artifacts (double-braces, bad escapes).
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try to find JSON object/array boundaries
    start = -1
    for i, c in enumerate(text):
        if c in "{[":
            start = i
            break
    if start > 0:
        text = text[start:]

    # Find matching end
    if text.startswith("{"):
        depth = 0
        for i, c in enumerate(text):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    text = text[: i + 1]
                    break
    elif text.startswith("["):
        depth = 0
        for i, c in enumerate(text):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    text = text[: i + 1]
                    break

    # First attempt: parse as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Second attempt: apply artifact cleanup and retry before logging failure
    cleaned = _clean_llm_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.warning("JSON parse error: %s — raw: %.200s", e, text)
        return {"_parse_error": str(e), "_raw": text[:1000]}
