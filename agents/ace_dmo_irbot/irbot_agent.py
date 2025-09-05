import os
from typing import Any, Dict, List, Optional

import requests
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.func import entrypoint


IRBOT_BASE_URL = os.getenv("IRBOT_BASE_URL", "https://api-prod.nvidia.com")
IRBOT_API_KEY = os.getenv("IRBOT_API_KEY", "")
IRBOT_TIMEOUT = int(os.getenv("IRBOT_TIMEOUT", "20"))


def _post_userquery(query: str, session_id: str) -> Dict[str, Any]:
    if not IRBOT_API_KEY:
        raise RuntimeError("IRBOT_API_KEY is not set")
    url = f"{IRBOT_BASE_URL.rstrip('/')}/chatbot/irbot-app/userquery"
    headers = {"x-irbot-secure": IRBOT_API_KEY}
    payload = {"query": query, "session_id": session_id}
    resp = requests.post(url, json=payload, headers=headers, timeout=IRBOT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _extract_text_from_response(data: Dict[str, Any]) -> str:
    # Try common fields where backend may place the textual response
    for key in ("answer", "message", "text", "content", "response"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    # Fallback to stringify
    return str(data)


@entrypoint()
async def agent(messages: List[Any], previous: Optional[List[Any]], config: Optional[Dict[str, Any]] = None):
    # No accumulation: just proxy the latest human message to IRBot using thread_id as session_id
    if not messages:
        return entrypoint.final(value=AIMessage(content=""), save=previous or [])

    # Find the last HumanMessage; if none, just echo empty
    last_user: Optional[HumanMessage] = None
    for m in reversed(messages):
        if isinstance(m, HumanMessage) or getattr(m, "type", None) == "human":
            last_user = m
            break

    if last_user is None:
        return entrypoint.final(value=AIMessage(content=""), save=previous or [])

    # Determine session id from config thread_id
    cfg = config or {}
    cfg_conf = cfg.get("configurable", {}) if isinstance(cfg, dict) else {}
    session_id = cfg_conf.get("thread_id") or cfg_conf.get("session_id") or "unknown"

    # Call backend
    try:
        backend = _post_userquery(query=last_user.content, session_id=session_id)
        text = _extract_text_from_response(backend)
        ai = AIMessage(content=text)
        # Do not accumulate; return only the AIMessage as value, and do not save growing history
        return entrypoint.final(value=ai, save=None)
    except Exception as exc:
        err = AIMessage(content=f"Backend error: {exc}")
        return entrypoint.final(value=err, save=None)


