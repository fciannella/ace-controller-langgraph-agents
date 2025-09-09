"""Simple client to talk to a LangGraph agent running locally.

Usage examples:
  - Single message:
      python talk_to_agent.py -m "Hello there"

  - Interactive chat (type /exit to quit, /reset to start a new thread):
      python talk_to_agent.py -i

Environment variables (optional):
  - LANGGRAPH_BASE_URL (default: http://127.0.0.1:2024)
  - LANGGRAPH_ASSISTANT (default: ace-base-agent)
  - USER_EMAIL (default: test@example.com)
"""

import argparse
import asyncio
import os
import datetime
from pathlib import Path
import json
import sys
from typing import Optional, Union, Any, Dict
from dotenv import load_dotenv

from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage

load_dotenv(override=True)

DEFAULT_BASE_URL = os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024")
DEFAULT_ASSISTANT = os.getenv("LANGGRAPH_ASSISTANT", "ace-base-agent")
DEFAULT_THREAD_FILE = os.path.join(os.path.dirname(__file__), "saved_thread_id.txt")



def load_thread_id(thread_file_path: str) -> Optional[str]:
    if not os.path.exists(thread_file_path):
        return None
    try:
        with open(thread_file_path, "r", encoding="utf-8") as f:
            value = f.read().strip()
            return value or None
    except Exception:
        return None


def save_thread_id(thread_file_path: str, thread_id: str) -> None:
    try:
        with open(thread_file_path, "w", encoding="utf-8") as f:
            f.write(thread_id)
    except Exception as exc:
        print(f"Warning: failed to persist thread id to {thread_file_path}: {exc}")


def extract_message_content(message: Any) -> str:
    """Best-effort extraction of text content from a message object or dict."""
    # Access attribute or dict key
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")

    if isinstance(content, str):
        return content

    # Sometimes content can be a list of parts
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if "text" in part and isinstance(part["text"], str):
                    parts.append(part["text"])
                elif "content" in part and isinstance(part["content"], str):
                    parts.append(part["content"])
        if parts:
            return "\n".join(parts)
        return str(content)

    # Fallback stringification
    return "" if content is None else str(content)


def _collect_messages_recursively(node: Any) -> list:
    """Recursively collect message-like entries from nested update payloads.

    Looks for any dict with a 'messages' key that is a list, and returns a flat list of those messages.
    """
    collected = []
    try:
        if isinstance(node, dict):
            # Direct messages
            msgs = node.get("messages")
            if isinstance(msgs, list):
                collected.extend(msgs)
            # Recurse into nested dicts
            for v in node.values():
                collected.extend(_collect_messages_recursively(v))
        elif isinstance(node, list):
            for item in node:
                collected.extend(_collect_messages_recursively(item))
    except Exception:
        pass
    return collected


def _collect_assistant_texts_recursively(node: Any) -> list[str]:
    """Find any assistant-like messages (type/role ai|assistant) and return their text content."""
    texts: list[str] = []
    def visit(x: Any) -> None:
        try:
            if isinstance(x, dict):
                content = x.get("content")
                role = x.get("type") or x.get("role")
                if isinstance(content, str) and role in ("ai", "assistant"):
                    texts.append(content)
                for v in x.values():
                    visit(v)
            elif isinstance(x, list):
                for e in x:
                    visit(e)
            else:
                # object-like
                role_obj = getattr(x, "type", None) or getattr(x, "role", None)
                content_obj = getattr(x, "content", None)
                if isinstance(content_obj, str) and role_obj in ("ai", "assistant"):
                    texts.append(content_obj)
        except Exception:
            pass
    visit(node)
    return texts


def _collect_metadata_recursively(node: Any) -> list[Dict[str, Any]]:
    """Collect all response_metadata dicts found anywhere in the payload."""
    found: list[Dict[str, Any]] = []
    def visit(x: Any) -> None:
        try:
            if isinstance(x, dict):
                rm = x.get("response_metadata")
                if isinstance(rm, dict):
                    found.append(rm)
                for v in x.values():
                    visit(v)
            elif isinstance(x, list):
                for e in x:
                    visit(e)
            else:
                if hasattr(x, "response_metadata"):
                    rm = getattr(x, "response_metadata")
                    if isinstance(rm, dict):
                        found.append(rm)
        except Exception:
            pass
    visit(node)
    return found


def _prefer_irbot_metadata(current: Optional[Dict[str, Any]], new_md: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Choose the metadata to keep, preferring one that contains 'irbot'."""
    if new_md is None:
        return current
    if current is None:
        return new_md
    try:
        new_has_irbot = isinstance(new_md, dict) and "irbot" in new_md
        cur_has_irbot = isinstance(current, dict) and "irbot" in current
        if new_has_irbot and not cur_has_irbot:
            return new_md
        # Otherwise keep existing (avoid overwriting an irbot md with generic md)
        if cur_has_irbot:
            return current
        # Neither has irbot, keep the latest
        return new_md
    except Exception:
        return new_md or current


def _to_jsonable(obj: Any) -> Any:
    """Best-effort conversion of arbitrary objects to JSON-serializable structures."""
    try:
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {str(k): _to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_to_jsonable(v) for v in obj]
        # Handle message-like objects
        role = getattr(obj, "type", None) or getattr(obj, "role", None)
        content = getattr(obj, "content", None)
        if role is not None or content is not None:
            rm = getattr(obj, "response_metadata", None)
            ak = getattr(obj, "additional_kwargs", None)
            return {
                "type": role,
                "content": content if isinstance(content, (str, int, float, bool)) else str(content),
                "response_metadata": _to_jsonable(rm) if isinstance(rm, dict) else None,
                "additional_kwargs": _to_jsonable(ak) if isinstance(ak, dict) else None,
            }
        if hasattr(obj, "__dict__"):
            return _to_jsonable(vars(obj))
        return str(obj)
    except Exception:
        return str(obj)


def _append_stream_log(log_path: Optional[str], event: str, data: Any) -> None:
    if not log_path:
        return
    try:
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "event": event,
            "data": _to_jsonable(data),
        }
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Do not fail streaming due to logging issues
        pass


async def ensure_thread_id(client: Any, thread_file_path: str, reset: bool = False) -> Optional[str]:
    if not reset:
        existing = load_thread_id(thread_file_path)
        if existing:
            return existing

    try:
        thread = await client.threads.create()
    except Exception as exc:
        print(f"Warning: failed to create thread, falling back to threadless runs: {exc}")
        return None

    # Try multiple ways to obtain ID
    thread_id = getattr(thread, "thread_id", None)
    if thread_id is None and isinstance(thread, dict):
        thread_id = thread.get("thread_id") or thread.get("id")
    if thread_id is None:
        thread_id = getattr(thread, "id", None)
    if thread_id is None and isinstance(thread, str):
        thread_id = thread

    if isinstance(thread_id, str) and thread_id:
        save_thread_id(thread_file_path, thread_id)
        return thread_id

    print("Warning: could not determine thread id from create() result; using threadless runs.")
    return None


async def send_message(
    client: Any,
    assistant: str,
    message_text: str,
    *,
    thread_id: Optional[str] = None,
    user_email: str = "test@example.com",
    thread_file_path: Optional[str] = None,
    _attempt: int = 0,
    stream_mode: str = "values",
    debug_stream: bool = False,
    stream_log: Optional[str] = None,
) -> tuple[str, Optional[str], Optional[Dict[str, Any]], bool]:
    """Send one message and stream updates.

    Returns (final_text, effective_thread_id_if_changed)
    where effective_thread_id_if_changed is not None only if we created a new thread to recover from 404.
    """
    config: Dict[str, Any] = {"configurable": {"user_email": user_email}}
    # Surface thread_id to agent via configurable for agents that use it as session_id
    if thread_id:
        config["configurable"]["thread_id"] = thread_id
        config["configurable"]["session_id"] = thread_id
    last_text = ""
    assembled_text: list[str] = []
    updated_thread_id: Optional[str] = None
    last_metadata: Optional[Dict[str, Any]] = None
    printed_any: bool = False

    try:
        # Include session_id in message additional_kwargs as a fallback path for agents
        msg = HumanMessage(
            content=message_text,
            additional_kwargs={"session_id": thread_id} if thread_id else {},
        )
        async for chunk in client.runs.stream(
            thread_id,
            assistant,
            input=[msg],
            stream_mode=stream_mode,
            config=config,
        ):
            # Attempt to stream partial tokens and capture final messages
            data = getattr(chunk, "data", None)

            # Handle token streaming events (e.g., on_chat_model_stream)
            evt = getattr(chunk, "event", "") or ""
            # Deduplicate prints within a single event
            seen_texts_this_event: set[str] = set()
            if debug_stream:
                # Print event and a compact preview of data for debugging
                try:
                    preview: str
                    if isinstance(data, dict):
                        keys = ",".join(list(data.keys())[:6])
                        preview = f"dict keys=[{keys}]"
                    else:
                        dtype = type(data).__name__
                        # Try to extract short content
                        sample = extract_message_content(data)
                        if sample:
                            sample = (sample[:120] + "…") if len(sample) > 120 else sample
                            preview = f"{dtype} content=\"{sample}\""
                        else:
                            preview = dtype
                except Exception:
                    preview = str(type(data))
                print(f"[stream] event={evt} data={preview}")
            # Always append raw event to log if enabled
            _append_stream_log(stream_log, evt, data)
            # Additionally, surface backchannel AI messages promptly
            # If data is already a list of messages (messages mode completion), print them
            if isinstance(data, list):
                for m in data:
                    txt = extract_message_content(m)
                    if txt:
                        last_text = txt
                        if txt not in seen_texts_this_event:
                            seen_texts_this_event.add(txt)
                            sys.stdout.write("\n" + txt)
                            sys.stdout.flush()
                            printed_any = True
                    try:
                        if isinstance(m, dict) and isinstance(m.get("response_metadata"), dict):
                            last_metadata = m.get("response_metadata")
                        elif hasattr(m, "response_metadata") and isinstance(getattr(m, "response_metadata"), dict):
                            last_metadata = getattr(m, "response_metadata")
                    except Exception:
                        pass

            # Some runtimes nest messages under node keys; search recursively
            if evt and data and isinstance(data, dict):
                msgs = []
                # Prefer direct messages array when present
                direct = data.get("messages")
                if isinstance(direct, list):
                    msgs = direct
                else:
                    # Some servers send {node_name: {messages: [...]}}
                    for v in data.values():
                        if isinstance(v, dict) and isinstance(v.get("messages"), list):
                            msgs.extend(v.get("messages"))
                    if not msgs:
                        # Last resort recursive search
                        msgs = _collect_messages_recursively(data)
                for m in msgs:
                    role = getattr(m, "type", None) or (m.get("type") if isinstance(m, dict) else None) or (m.get("role") if isinstance(m, dict) else None)
                    if role in ("ai", "assistant"):
                        txt = extract_message_content(m)
                        if txt:
                            if txt not in seen_texts_this_event:
                                seen_texts_this_event.add(txt)
                                sys.stdout.write("\n" + txt)
                                sys.stdout.flush()
                                printed_any = True
                    # pull metadata if any on this message
                    try:
                        if isinstance(m, dict) and isinstance(m.get("response_metadata"), dict):
                            last_metadata = _prefer_irbot_metadata(last_metadata, m.get("response_metadata"))
                        elif hasattr(m, "response_metadata") and isinstance(getattr(m, "response_metadata"), dict):
                            last_metadata = _prefer_irbot_metadata(last_metadata, getattr(m, "response_metadata"))
                    except Exception:
                        pass

            # Handle final value events (values mode typically returns a single AIMessage-like dict)
            if evt == "values":
                # Many dev servers emit an AIMessage-like payload with top-level 'content'
                candidate_text = extract_message_content(data)
                if candidate_text:
                    last_text = candidate_text
                # Avoid printing here to prevent duplicate output; we'll print once at the end
                # Capture response metadata if present (dict or object)
                try:
                    if isinstance(data, dict) and isinstance(data.get("response_metadata"), dict):
                        last_metadata = data.get("response_metadata")
                    elif hasattr(data, "response_metadata") and isinstance(getattr(data, "response_metadata"), dict):
                        last_metadata = getattr(data, "response_metadata")
                except Exception:
                    pass
            if "on_chat_model_stream" in evt:
                # Try multiple shapes
                part_text = ""
                if isinstance(data, dict):
                    if "chunk" in data:
                        ch = data["chunk"]
                        part_text = extract_message_content(ch)
                    elif "delta" in data:
                        part_text = extract_message_content(data["delta"])
                    elif "content" in data and isinstance(data["content"], str):
                        part_text = data["content"]
                else:
                    # Fallback: direct attribute
                    part_text = extract_message_content(data)

                if part_text:
                    assembled_text.append(part_text)
                    sys.stdout.write(part_text)
                    sys.stdout.flush()

            # Handle updates that include whole messages array (dict or object)
            messages_obj: Optional[Union[list, Any]] = None
            if isinstance(data, dict) and data.get("messages"):
                messages_obj = data.get("messages")
            elif hasattr(data, "messages"):
                messages_obj = getattr(data, "messages")

            if messages_obj is not None:
                messages = messages_obj or []
                if isinstance(messages, list) and messages:
                    # Print each AI/human content inline for updates
                    for m in messages:
                        text = extract_message_content(m)
                        if text:
                            last_text = text
                            if text not in seen_texts_this_event:
                                seen_texts_this_event.add(text)
                                sys.stdout.write("\n" + text)
                                sys.stdout.flush()
                                printed_any = True
                        # capture response_metadata if present on any message
                        try:
                            if isinstance(m, dict) and isinstance(m.get("response_metadata"), dict):
                                last_metadata = m.get("response_metadata")
                            elif hasattr(m, "response_metadata") and isinstance(getattr(m, "response_metadata"), dict):
                                last_metadata = getattr(m, "response_metadata")
                        except Exception:
                            pass
            else:
                # If the data itself looks like a message with content, print it
                if hasattr(data, "content"):
                    maybe_text = extract_message_content(data)
                    if maybe_text:
                        assembled_text.append(maybe_text)
                        if maybe_text not in seen_texts_this_event:
                            seen_texts_this_event.add(maybe_text)
                            sys.stdout.write(maybe_text)
                            sys.stdout.flush()
                            printed_any = True

            # For updates mode, also scan recursively for assistant-like texts anywhere in payload
            if evt.startswith("updates") and isinstance(data, (dict, list)):
                texts = _collect_assistant_texts_recursively(data)
                for t in texts:
                    if t not in seen_texts_this_event:
                        seen_texts_this_event.add(t)
                        sys.stdout.write("\n" + t)
                        sys.stdout.flush()
                        printed_any = True
                # Collect any response metadata present and prefer irbot content if found
                mets = _collect_metadata_recursively(data)
                for md in mets:
                    if isinstance(md, dict):
                        last_metadata = _prefer_irbot_metadata(last_metadata, md)
                # If we have IRBot metadata now, print it immediately in updates mode
                try:
                    if isinstance(last_metadata, dict) and isinstance(last_metadata.get("irbot"), (dict, list)):
                        print("\nMetadata (irbot):")
                        print(json.dumps(last_metadata.get("irbot"), indent=2))
                except Exception:
                    pass

            # Fallback: look for common result containers in update payloads (dict-like)
            if isinstance(data, dict):
                for key in ("result", "output", "final_output", "value", "response"):
                    if key in data and data[key] is not None:
                        candidate_text = extract_message_content(data[key])
                        if candidate_text:
                            last_text = candidate_text
                            sys.stdout.write("\n" + candidate_text)
                            sys.stdout.flush()
                            printed_any = True

            # Attribute-based containers (object-like)
            for attr in ("value", "output", "result", "final_output", "response"):
                if hasattr(data, attr):
                    candidate = getattr(data, attr)
                    if candidate is not None:
                        candidate_text = extract_message_content(candidate)
                        if candidate_text:
                            last_text = candidate_text
                            sys.stdout.write("\n" + candidate_text)
                            sys.stdout.flush()
                            printed_any = True
        # Newline after streaming loop to tidy stdout
        if last_text:
            print()
        # Prefer final snapshot; otherwise fall back to assembled tokens
        if not last_text and assembled_text:
            last_text = "".join(assembled_text)
            print()  # ensure newline after token stream
        return last_text, updated_thread_id, last_metadata, printed_any
    except Exception as exc:
        # Auto-recover from missing/expired thread (common after local dev restart)
        text_exc = str(exc)
        if thread_id and ("404" in text_exc or "Not Found" in text_exc):
            try:
                if _attempt == 0:
                    new_thread_id = await ensure_thread_id(
                        client,
                        thread_file_path or DEFAULT_THREAD_FILE,
                        reset=True,
                    )
                    print("Previous thread not found; created a new thread and retrying...")
                    # Track updated thread id so caller can reuse it next time
                    updated_thread_id = new_thread_id
                    text, _, md, printed = await send_message(
                        client,
                        assistant,
                        message_text,
                        thread_id=new_thread_id,
                        user_email=user_email,
                        thread_file_path=thread_file_path,
                        _attempt=1,
                        stream_mode=stream_mode,
                    )
                    return text, updated_thread_id, md, printed
                else:
                    # Second failure using threads → fall back to threadless
                    print("Threads unavailable in this dev session; switching to threadless runs.")
                    text, _, md, printed = await send_message(
                        client,
                        assistant,
                        message_text,
                        thread_id=None,
                        user_email=user_email,
                        thread_file_path=thread_file_path,
                        _attempt=2,
                        stream_mode=stream_mode,
                    )
                    return text, None, md, printed
            except Exception as inner_exc:
                print(f"Error creating new thread after 404: {inner_exc}")
        print(f"Error during streaming: {exc}")
        return "", None, None, False


async def interactive_chat(
    client: Any,
    assistant: str,
    thread_file_path: str,
    *,
    user_email: str,
    stream_mode: str,
    debug_stream: bool,
    stream_log: Optional[str],
) -> None:
    print("Type your message and press Enter.")
    print("Commands: /exit to quit, /reset to start a new thread")

    thread_id = await ensure_thread_id(client, thread_file_path, reset=False)
    if thread_id:
        print(f"Thread: {thread_id}")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if not user_input:
            continue
        if user_input.lower() in {"/exit", ":q", "quit", "exit"}:
            print("Goodbye!")
            return
        if user_input.lower() in {"/reset", "/new"}:
            thread_id = await ensure_thread_id(client, thread_file_path, reset=True)
            print(f"Started a new thread. Thread: {thread_id}")
            continue

        # Use 'values' mode first; dev server reliably returns final value
        response_text, new_thread, metadata, printed_any = await send_message(
            client,
            assistant,
            user_input,
            thread_id=thread_id,
            user_email=user_email,
            thread_file_path=thread_file_path,
            stream_mode=stream_mode,
            debug_stream=debug_stream,
            stream_log=stream_log,
        )
        if new_thread:
            thread_id = new_thread
            print(f"(Thread switched) Thread: {thread_id}")
        if response_text:
            print(f"Agent: {response_text}")
            # Print IRBot metadata if present
            try:
                if isinstance(metadata, dict) and isinstance(metadata.get("irbot"), (dict, list)):
                    print("Metadata (irbot):")
                    print(json.dumps(metadata.get("irbot"), indent=2))
            except Exception:
                pass
        else:
            # In updates mode, we may have printed inline chunks; avoid spurious <no response>
            if stream_mode == "updates" and printed_any:
                continue
            print("Agent: <no response>")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Talk to a local LangGraph agent.")
    parser.add_argument(
        "-u",
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"LangGraph API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "-a",
        "--assistant",
        default=DEFAULT_ASSISTANT,
        help=f"Assistant name or id (default: {DEFAULT_ASSISTANT})",
    )
    parser.add_argument(
        "-m",
        "--message",
        nargs="*",
        help="Send a single message (omit to start interactive mode)",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start an interactive chat session",
    )
    parser.add_argument(
        "--reset-thread",
        action="store_true",
        help="Create a new thread and overwrite saved thread id",
    )
    parser.add_argument(
        "--thread-file",
        default=DEFAULT_THREAD_FILE,
        help=f"File to persist thread id (default: {DEFAULT_THREAD_FILE})",
    )
    parser.add_argument(
        "--user-email",
        default=os.getenv("USER_EMAIL", "test@example.com"),
        help="Value for configurable.user_email",
    )
    parser.add_argument(
        "--stream-mode",
        default=os.getenv("STREAM_MODE", "values"),
        choices=["updates", "values", "messages", "events"],
        help="Streaming mode used by the SDK (default: values)",
    )
    parser.add_argument(
        "--debug-stream",
        action="store_true",
        help="Print raw stream events for debugging parsing",
    )
    parser.add_argument(
        "--stream-log",
        default=None,
        help="Path to a JSONL log file to write every stream event (debugging)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    client = get_client(url=args.base_url)

    async def _run() -> None:
        # If a message is provided and not interactive, send once and exit
        if args.message and not args.interactive:
            thread_id = await ensure_thread_id(client, args.thread_file, reset=args.reset_thread)
            text = " ".join(args.message)
            print(f"Sending to {args.assistant} @ {args.base_url} (thread={thread_id or 'threadless'})\n")
            reply, _, _, _ = await send_message(
                client,
                args.assistant,
                text,
                thread_id=thread_id,
                user_email=args.user_email,
                thread_file_path=args.thread_file,
                stream_mode=args.stream_mode,
                debug_stream=args.debug_stream,
                stream_log=args.stream_log,
            )
            if reply:
                print(f"\nAgent: {reply}")
            return

        # Otherwise start interactive mode
        print(f"Connecting to {args.base_url}")
        print(f"Assistant: {args.assistant}")
        if args.reset_thread:
            # Force new thread at the start of interactive session
            _ = await ensure_thread_id(client, args.thread_file, reset=True)
        await interactive_chat(
            client,
            assistant=args.assistant,
            thread_file_path=args.thread_file,
            user_email=args.user_email,
            stream_mode=args.stream_mode,
            debug_stream=args.debug_stream,
            stream_log=args.stream_log,
        )

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()


