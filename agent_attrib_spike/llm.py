"""Shared LLM access for the spike: env loading, OpenAI client, on-disk cache.

The cache is load-bearing, not just a cost saver: keying responses on
(model, messages, temperature) makes the testbed and replay **deterministic** —
identical agent-turn inputs return byte-identical outputs — which is exactly the
reproducibility the pre-registration's temp-0 replay contract requires. A
counterfactual substitution changes a step's output and therefore all downstream
inputs, so those turns are genuine cache misses (fresh calls); unchanged prefixes
are cache hits.
"""
import hashlib
import json
import os
import pathlib

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_CACHE_DIR = pathlib.Path(__file__).resolve().parent / ".cache_llm"

AGENT_MODEL = "gpt-4o-mini"          # cheap: drives the testbed agents + replay
ALT_MODEL = "gpt-4o"                 # capable: blind alternative-generation
EMBED_MODEL = "text-embedding-3-small"

_client = None


def load_env(path=None):
    """Load KEY=VALUE lines from the repo-root .env into os.environ (no override)."""
    p = pathlib.Path(path) if path else _REPO_ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get_client():
    global _client
    if _client is None:
        load_env()
        from openai import OpenAI
        _client = OpenAI()
    return _client


def _cache_get(key):
    f = _CACHE_DIR / (key + ".json")
    if f.exists():
        return json.loads(f.read_text())
    return None


def _cache_put(key, value):
    _CACHE_DIR.mkdir(exist_ok=True)
    (_CACHE_DIR / (key + ".json")).write_text(json.dumps(value))


def chat(messages, model=AGENT_MODEL, temperature=0.0, max_tokens=400):
    """Cached chat completion -> assistant text. Deterministic for fixed inputs."""
    key = hashlib.sha256(
        json.dumps([model, messages, temperature, max_tokens], sort_keys=True).encode()
    ).hexdigest()[:40]
    hit = _cache_get(key)
    if hit is not None:
        return hit["text"]
    r = _get_client().chat.completions.create(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
    )
    text = r.choices[0].message.content
    _cache_put(key, {"text": text})
    return text


def embed(text, model=EMBED_MODEL):
    """Cached embedding vector for `text`."""
    key = "emb_" + hashlib.sha256(
        json.dumps([model, text], sort_keys=True).encode()
    ).hexdigest()[:40]
    hit = _cache_get(key)
    if hit is not None:
        return hit["vec"]
    r = _get_client().embeddings.create(model=model, input=text)
    vec = r.data[0].embedding
    _cache_put(key, {"vec": vec})
    return vec
