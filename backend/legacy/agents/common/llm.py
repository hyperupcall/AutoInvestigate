"""litellm call helper: low temperature, JSON out, validated with retries."""
import json
import os
import re

import litellm

MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-5-5")
# Current Claude models only accept temperature=1, so it is optional: set
# LLM_TEMPERATURE only for providers that allow lower values.
_T = os.getenv("LLM_TEMPERATURE", "").strip()
EXTRA = {"temperature": float(_T)} if _T else {}


async def ask_json(system: str, user: str, validate, retries: int = 2) -> dict:
    """Call the LLM until `validate(obj)` returns None (ok) or an error string."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last = "no attempt"
    for _ in range(retries + 1):
        resp = await litellm.acompletion(
            model=MODEL, messages=messages, max_tokens=3000, **EXTRA)
        text = resp.choices[0].message.content or ""
        m = re.search(r"\{.*\}", text, re.S)
        try:
            obj = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            obj = None
        err = "reply was not valid JSON" if obj is None else validate(obj)
        if err is None:
            return obj
        last = err
        import logging; logging.getLogger("council.llm").error("bad LLM output (%s): %r", err, text[:400])
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": f"Invalid: {err}. Reply with JSON only."}]
    raise ValueError(f"LLM output failed validation: {last}")
