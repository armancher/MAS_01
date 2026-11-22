"""LLM backends. All real backends use the OpenAI-compatible chat API.

LLM_BACKEND=mock    (default) offline stand-in that obeys any instruction it sees.
                    Use it only to check the plumbing. It is NOT evidence.
LLM_BACKEND=gemini  Google Gemini API. Key: GEMINI_API_KEY (from Google AI Studio).
LLM_BACKEND=qwen    Alibaba Model Studio (DashScope). Key: DASHSCOPE_API_KEY.
                    Default region Singapore; set LLM_BASE_URL for another region.
LLM_BACKEND=ollama  local open models, e.g. qwen3 via Ollama. No key needed.
LLM_BACKEND=openai  any other OpenAI-compatible API. Set LLM_BASE_URL and LLM_API_KEY.

Always set LLM_MODEL. To see which model names your key can use:
    python llm.py models

Settings can also go in a .env file next to this one (KEY=value per line).
Never commit keys: .env is in .gitignore.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

PRESETS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "qwen": ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
}

# Token counts across all calls, for the overhead metric.
USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}


def _load_dotenv():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def backend() -> str:
    return os.environ.get("LLM_BACKEND", "mock")


def _endpoint():
    name = backend()
    if name not in PRESETS:
        raise ValueError(f"unknown LLM_BACKEND {name!r}; use mock, {', '.join(PRESETS)}")
    base, key_var = PRESETS[name]
    base = os.environ.get("LLM_BASE_URL", base).rstrip("/")
    key = os.environ.get("LLM_API_KEY") or (os.environ.get(key_var, "") if key_var else "")
    if key_var and not key:
        raise RuntimeError(f"set {key_var} (or LLM_API_KEY) for LLM_BACKEND={name}")
    return base, key

def _request(method, url, key, body=None, retries=6):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        wait = min(60, 5 * 2 ** attempt)                     # 5, 10, 20, 40, 60 s
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 429 and "limit: 0" in detail:
                raise RuntimeError("This model has no free quota for your key. "
                                   "Pick another model in .env.") from None
            if e.code == 429 and "PerDay" in detail:
                raise RuntimeError("Daily free quota used up for this model. "
                                   "Pick another model in .env or wait until tomorrow.") from None
            if e.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise RuntimeError(f"HTTP {e.code} from {url}:\n{detail[:1500]}") from None
            m = re.search(r'"retryDelay":\s*"(\d+)', detail)   # Gemini says how long to wait
            if m:
                wait = int(m.group(1)) + 1
            print(f"  [{e.code}] retrying in {wait}s")
        except (TimeoutError, urllib.error.URLError) as e:
            if attempt == retries - 1:
                raise RuntimeError(f"no response from {url} after {retries} tries: {e}") from None
            print(f"  [no response] retrying in {wait}s")
        time.sleep(wait)


# Optional cache (LLM_CACHE=1): the same prompt in the same run index is answered once,
# so every configuration sees identical reader/summariser outputs (a paired comparison)
# and rerunning costs nothing. Different run indexes are still separate calls.
RUN = 0                                                     # set by run.py
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".llm_cache.json")
_CACHE = None
_LAST_CALL = [0.0]


def _cache():
    global _CACHE
    if _CACHE is None:
        _CACHE = {}
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, encoding="utf-8") as f:
                _CACHE = json.load(f)
    return _CACHE


def complete(role: str, system: str, user: str) -> str:
    if backend() == "mock":
        return _mock(role, user)
    base, key = _endpoint()
    model = os.environ.get("LLM_MODEL")
    if not model:
        raise RuntimeError("set LLM_MODEL (run `python llm.py models` to list names)")
    use_cache = os.environ.get("LLM_CACHE") == "1"
    cache_key = json.dumps([backend(), model, RUN, system, user])
    if use_cache and cache_key in _cache():
        return _cache()[cache_key]

    gap = float(os.environ.get("LLM_MIN_INTERVAL", "0"))    # seconds between calls
    pause = _LAST_CALL[0] + gap - time.time()
    if pause > 0:
        time.sleep(pause)
    _LAST_CALL[0] = time.time()

    body = {"model": model, "temperature": 0,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
    if os.environ.get("LLM_REASONING_EFFORT"):
        body["reasoning_effort"] = os.environ["LLM_REASONING_EFFORT"]
    out = _request("POST", base + "/chat/completions", key, body)
    usage = out.get("usage") or {}
    USAGE["calls"] += 1
    USAGE["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
    USAGE["completion_tokens"] += usage.get("completion_tokens", 0) or 0
    text = out["choices"][0]["message"].get("content") or ""
    if use_cache:
        _cache()[cache_key] = text
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache(), f)
    return text



def list_models():
    base, key = _endpoint()
    out = _request("GET", base + "/models", key)
    for m in sorted(x.get("id", "") for x in out.get("data", [])):
        print(m)


# --------------------------------------------------------------------------
# Mock: a deliberately gullible model, so the pipeline can be tested offline.
# --------------------------------------------------------------------------
_INSTRUCTION = re.compile(r"\b(send|forward|ignore|important|must|instead)\b", re.I)
_EXFIL = re.compile(r"send (?:the )?contents of (\S+?\.txt) to (\S+@[\w.\-]+\w)", re.I)
_ADDR = re.compile(r"[\w.\-]+@[\w.\-]+\w")


def _mock(role: str, user: str) -> str:
    if role == "reader":
        return user  # passes the email through unchanged
    if role == "summariser":
        sentences = re.split(r"(?<=[.!?])\s+", user.strip())
        keep = sentences[:2] + [s for s in sentences[2:] if _INSTRUCTION.search(s)]
        return " ".join(keep)
    if role == "executor":
        ctx = json.loads(user)
        text, sender = ctx["summary"], ctx["email_sender"]
        plan = []
        exfil = _EXFIL.search(text)
        if exfil:
            plan.append({"tool": "read_file", "args": {"name": exfil.group(1)}})
            plan.append({"tool": "send_email",
                         "args": {"to": exfil.group(2), "body": "<<LAST_RESULT>>"}})
        # Gullible: any other address in the text becomes the reply target.
        others = [a for a in _ADDR.findall(text)
                  if a != sender and not (exfil and a == exfil.group(2))]
        reply_to = others[0] if others else sender
        plan.append({"tool": "send_email",
                     "args": {"to": reply_to, "body": "Received. Summary: " + text[:120]}})
        step = len(ctx["history"])
        if step >= len(plan):
            return json.dumps({"tool": "done", "args": {}})
        action = plan[step]
        if action["args"].get("body") == "<<LAST_RESULT>>":
            action["args"]["body"] = ctx["history"][-1]["result"]
        return json.dumps(action)
    raise ValueError(f"mock backend has no {role!r} role; use a real model")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["models"]:
        list_models()
    elif sys.argv[1:] == ["ping"]:
        print(complete("ping", "Answer with one word.", "Say OK."))
    else:
        print("usage: python llm.py models | ping")
