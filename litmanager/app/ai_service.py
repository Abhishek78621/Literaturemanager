"""
ai_service.py
-------------
The ONLY module that talks to an external LLM API. Everything else in the
app (import, browse, tag, offline semantic search) works without it.

Per spec section 8/24, the provider must be swappable and never hard-coded.
Two providers are wired up: "anthropic" and "openai" (OpenAI-compatible,
so this also works with many local/hosted OpenAI-compatible servers).

If no API key is configured, classification/summary steps are skipped and
the paper is stored with domain "Unclassified" -- the user can still browse,
tag, and use offline hashing/embedding search. This keeps the app fully
usable with zero API cost, as required.
"""

"""
ai_service.py
-------------
The ONLY module that talks to an external LLM API. Everything else in the
app (import, browse, tag, offline semantic search) works without it.

Per spec section 8/24, the provider must be swappable and never hard-coded.
Providers wired up:
  - "anthropic"        Claude, via api.anthropic.com. Paid.
  - "openai"            OpenAI's own API. Paid.
  - "openai_compatible"  Any server that speaks the same request/response
                          format as OpenAI's chat completions endpoint.
                          This covers several genuinely free options:
                            * Ollama running locally (100% free, no key
                              needed, runs on your own machine, matches
                              this whole project's "local-first" idea)
                            * Groq (generous free tier, cloud-hosted)
                            * OpenRouter (some models are free)
                          You just point base_url at whichever server you
                          want; no code changes needed for a new provider
                          of this kind.

If no API key is configured (and the provider isn't a keyless local one
like Ollama), classification/summary steps are skipped and the paper is
stored with domain "Unclassified" -- the user can still browse, tag, and
use offline hashing/embedding search. This keeps the app fully usable with
zero API cost, as required.
"""

import os
import json
from app import database as db

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "openai_compatible": "llama3",  # sensible default for Ollama; override for Groq/OpenRouter
}
DEFAULT_BASE_URL = {
    "openai": "https://api.openai.com/v1/chat/completions",
    # Ollama's default local server address -- override in Settings for
    # Groq (https://api.groq.com/openai/v1/chat/completions),
    # OpenRouter (https://openrouter.ai/api/v1/chat/completions), etc.
    "openai_compatible": "http://localhost:11434/v1/chat/completions",
}


def get_config():
    provider = db.get_setting("ai_provider") or os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER)
    api_key = (
        db.get_setting("ai_api_key")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    model = db.get_setting("ai_model") or DEFAULT_MODEL.get(provider, "")
    base_url = db.get_setting("ai_base_url") or DEFAULT_BASE_URL.get(provider, "")
    return {"provider": provider, "api_key": api_key, "model": model, "base_url": base_url}


def is_configured() -> bool:
    """
    Local OpenAI-compatible servers (Ollama) typically don't need a real
    API key, so that provider counts as configured as long as a base_url
    is set. Every other provider needs an actual key.
    """
    cfg = get_config()
    if cfg["provider"] == "openai_compatible":
        return bool(cfg["base_url"])
    return bool(cfg["api_key"])


def _call_llm(system: str, user: str, max_tokens=800) -> str:
    cfg = get_config()

    if cfg["provider"] == "anthropic":
        if not cfg["api_key"]:
            raise RuntimeError("No AI API key configured. Set it in Settings to enable AI features.")
        import anthropic
        client = anthropic.Anthropic(api_key=cfg["api_key"])
        resp = client.messages.create(
            model=cfg["model"],
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if not text.strip():
            stop = getattr(resp, "stop_reason", "unknown")
            raise RuntimeError(
                f"Anthropic returned an empty response (stop_reason={stop!r}). "
                "This usually means the model hit max_tokens or refused the request."
            )
        return text

    elif cfg["provider"] in ("openai", "openai_compatible"):
        if cfg["provider"] == "openai" and not cfg["api_key"]:
            raise RuntimeError("No AI API key configured. Set it in Settings to enable AI features.")
        import requests
        url = cfg["base_url"] or DEFAULT_BASE_URL.get(cfg["provider"], "")
        headers = {}
        # Ollama typically ignores the Authorization header entirely; Groq/
        # OpenRouter/OpenAI all require a real bearer key. Sending a
        # placeholder key when none is set keeps this one code path working
        # for both cases without branching further.
        headers["Authorization"] = f"Bearer {cfg['api_key'] or 'not-needed'}"
        r = requests.post(
            url,
            headers=headers,
            json={
                "model": cfg["model"],
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120,  # local models on modest hardware can be slow
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        if not content or not content.strip():
            finish = r.json()["choices"][0].get("finish_reason", "unknown")
            raise RuntimeError(
                f"AI returned an empty response (finish_reason={finish!r}). "
                "The model may have hit its token limit or refused the request."
            )
        return content

    else:
        raise ValueError(f"Unknown AI provider: {cfg['provider']}")


def classify_and_summarize(paper_text: str, title: str, existing_domains: list) -> dict:
    """
    Single API call that returns domain classification, technical summary,
    and a plain-language explanation. Combined into one call to minimize
    API cost per the spec's cost-control principle.
    """
    system = (
        "You are a research-paper classification assistant for a personal literature "
        "library. Respond with ONLY a JSON object, no markdown fences, no preamble."
    )
    user = f"""Existing domains in the user's library: {json.dumps(existing_domains)}

Paper title: {title}

Paper text (excerpt):
{paper_text[:2000]}

Return a JSON object with exactly these keys:
- "document_type": string. The broad type of document, e.g., "Research_Papers", "Books", "Reports". Use "Research_Papers" as the default for standard academic papers.
- "primary_domain": string. Prefer an existing domain if the paper genuinely fits one.
  Only propose a new domain if the paper doesn't reasonably fit any existing one.
- "subdomains": array of EXACTLY 1 short string (more specific than primary_domain). Do not return more than 1 subdomain.
- "is_new_domain": boolean, true only if primary_domain is not in the existing domains list.
- "keywords": array of up to 6 short keyword strings.
- "technical_summary": 2-4 sentences, written for a researcher, precise and technical.
- "simple_explanation": 2-3 sentences, plain language, no jargon, as if reminding a
  busy person what the paper is about.
"""
    raw = _call_llm(system, user, max_tokens=1200)
    return _parse_json(raw)


def answer_complex_query(query: str, papers: list) -> str:
    """
    Multi-paper reasoning (comparison, synthesis, etc). `papers` is a list of
    dicts with at least title/abstract/technical_summary. This is the only
    other place that calls the API -- ordinary "find my paper" search never
    reaches this function (see embeddings.py for that offline path).
    """
    system = (
        "You are a research assistant answering questions about papers already "
        "in the user's personal library. Base your answer only on the provided "
        "paper summaries. If the summaries are insufficient, say so plainly."
    )
    context = "\n\n".join(
        f"[{i+1}] {p['title']}\nSummary: {p.get('technical_summary') or p.get('abstract') or '(no summary)'}"
        for i, p in enumerate(papers)
    )
    user = f"Papers:\n{context}\n\nQuestion: {query}"
    return _call_llm(system, user, max_tokens=1000)


def _parse_json(raw: str) -> dict:
    """Parse a JSON string returned by the LLM.

    Handles three common model output styles:
      1. Bare JSON object   : {"key": "value"}
      2. Fenced code block  : ```json\n{...}\n```
      3. JSON buried in text: some prose ... {"key": "value"} ... more prose
    """
    raw = raw.strip()
    if not raw:
        raise ValueError(
            "AI returned an empty string. Check that your API key is valid, "
            "the model name is correct, and the request didn't exceed the token limit."
        )

    # Strip markdown code fences (``` or ```json) without corrupting content.
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Drop first line (the fence opener e.g. "```json") and last line if it's a fence closer
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        raw = "\n".join(inner).strip()

    # Attempt 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract the first {...} block (handles prose before/after JSON)
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not parse AI response as JSON.\n"
        f"Raw response was:\n{raw[:500]!r}"
    )
