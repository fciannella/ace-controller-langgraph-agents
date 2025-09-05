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
) -> tuple[str, Optional[str], Optional[Dict[str, Any]]]:
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
                    last = messages[-1]
                    text = extract_message_content(last)
                    if text:
                        last_text = text
                        # Overwrite-friendly printing for a streaming feel
                        # Show latest snapshot on its own line if differs from token stream
                        if not assembled_text or last_text != "".join(assembled_text):
                            sys.stdout.write("\n" + last_text)
                            sys.stdout.flush()
                    # Try to capture response metadata from the last message
                    try:
                        if isinstance(last, dict) and isinstance(last.get("response_metadata"), dict):
                            last_metadata = last.get("response_metadata")
                        elif hasattr(last, "response_metadata") and isinstance(getattr(last, "response_metadata"), dict):
                            last_metadata = getattr(last, "response_metadata")
                    except Exception:
                        pass
            else:
                # If the data itself looks like a message with content, print it
                if hasattr(data, "content"):
                    maybe_text = extract_message_content(data)
                    if maybe_text:
                        assembled_text.append(maybe_text)
                        sys.stdout.write(maybe_text)
                        sys.stdout.flush()

            # Fallback: look for common result containers in update payloads (dict-like)
            if isinstance(data, dict):
                for key in ("result", "output", "final_output", "value", "response"):
                    if key in data and data[key] is not None:
                        candidate_text = extract_message_content(data[key])
                        if candidate_text:
                            last_text = candidate_text
                            sys.stdout.write("\n" + candidate_text)
                            sys.stdout.flush()

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
        # Newline after streaming loop to tidy stdout
        if last_text:
            print()
        # Prefer final snapshot; otherwise fall back to assembled tokens
        if not last_text and assembled_text:
            last_text = "".join(assembled_text)
            print()  # ensure newline after token stream
        return last_text, updated_thread_id, last_metadata
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
                    text, _, md = await send_message(
                        client,
                        assistant,
                        message_text,
                        thread_id=new_thread_id,
                        user_email=user_email,
                        thread_file_path=thread_file_path,
                        _attempt=1,
                        stream_mode=stream_mode,
                    )
                    return text, updated_thread_id, md
                else:
                    # Second failure using threads → fall back to threadless
                    print("Threads unavailable in this dev session; switching to threadless runs.")
                    text, _, md = await send_message(
                        client,
                        assistant,
                        message_text,
                        thread_id=None,
                        user_email=user_email,
                        thread_file_path=thread_file_path,
                        _attempt=2,
                        stream_mode=stream_mode,
                    )
                    return text, None, md
            except Exception as inner_exc:
                print(f"Error creating new thread after 404: {inner_exc}")
        print(f"Error during streaming: {exc}")
        return "", None, None


async def interactive_chat(
    client: Any,
    assistant: str,
    thread_file_path: str,
    *,
    user_email: str,
    stream_mode: str,
    debug_stream: bool,
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
        response_text, new_thread, metadata = await send_message(
            client,
            assistant,
            user_input,
            thread_id=thread_id,
            user_email=user_email,
            thread_file_path=thread_file_path,
            stream_mode=stream_mode,
            debug_stream=debug_stream,
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
            reply, _ = await send_message(
                client,
                args.assistant,
                text,
                thread_id=thread_id,
                user_email=args.user_email,
                thread_file_path=args.thread_file,
                stream_mode=args.stream_mode,
                debug_stream=args.debug_stream,
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
        )

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()


