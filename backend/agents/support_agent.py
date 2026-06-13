"""
TechMart LangGraph Agent.
Encapsulates the full call_model → run_tools loop.
Uses OpenAI-compatible API (gpt-4o).
"""

from __future__ import annotations
import os
import json
import logging
from datetime import datetime
from typing import Annotated, TypedDict, Literal

from openai import OpenAI, APIConnectionError, AuthenticationError, RateLimitError, APIStatusError
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from backend.tools import TOOL_SCHEMAS, dispatch
from backend.policies import POLICY_TEXT

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are an AI Customer Support Agent for TechMart India.

You have two tools:
- lookup_customer: fetch customer profile + order history by email
- evaluate_refund: apply refund policy rules and return a decision
- Sign off as "TechMart Support Team", never use "[Your Name]".
{POLICY_TEXT}

Rules:
- Always look up the customer before deciding anything.
- Be warm, professional, and empathetic.
- Always address the customer by first name.
- If you cannot identify the customer or order, ask politely for clarification.
- CRITICAL: When evaluate_refund returns a decision, follow it exactly — never override it:
  * decision=APPROVED: confirm refund approved, state 5-7 business days processing, and if keep_item=true mention the customer keeps the item (VIP goodwill policy).
  * decision=APPROVED_WITH_CONDITIONS: confirm the refund IS approved, but tell the customer they must submit photographic evidence of the defect before it can be processed (policy requirement for orders above Rs 50,000). Do NOT say escalate or mention supervisors.
  * decision=DENIED: deny firmly but politely, give the exact reason from the tool result. Do NOT apologise excessively or suggest workarounds.
  * decision=NEEDS_INFO: ask the customer for the specific missing information.
- Never use the word escalate or mention supervisors unless the tool result explicitly contains prev_refund_denied=true.
"""

# ── OpenAI tool schemas (converted from Anthropic format) ─────────────────────

def _to_openai_tools(anthropic_schemas: list[dict]) -> list[dict]:
    """Convert Anthropic tool schema format to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["input_schema"],
            },
        }
        for s in anthropic_schemas
    ]

OPENAI_TOOLS = _to_openai_tools(TOOL_SCHEMAS)

# ── State schema ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    reasoning_logs: list[dict]
    tool_calls_log: list[dict]


# ── OpenAI client (lazy) ──────────────────────────────────────────────────────

def _make_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set. "
            "Export it before starting the server."
        )
    return OpenAI(api_key=api_key)


# ── Convert internal message history → OpenAI API format ─────────────────────
#
# Our internal state stores messages as plain dicts.  Some came from LangGraph
# (role="human"/"ai"), some we wrote ourselves (role="assistant" with a list
# content that may contain "tool_use" blocks, or role="user" with a list of
# "tool_result" blocks).  OpenAI requires a very specific wire format; this
# function normalises everything correctly.
#
# OpenAI multi-turn tool-call format:
#   1. assistant message  → role="assistant", tool_calls=[{id, type, function:{name, arguments}}]
#   2. tool result        → role="tool",      tool_call_id=..., content=<string>

ROLE_MAP = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
    "tool": "tool",
    "user": "user",
    "assistant": "assistant",
}

def _build_api_messages(state_messages: list) -> list[dict]:
    """Convert internal state messages to the format OpenAI's API expects."""
    api_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    for m in state_messages:
        # Normalise to dict
        if isinstance(m, dict):
            raw_role = m.get("role", "user")
            content = m.get("content", "")
        else:
            raw_role = m.type if hasattr(m, "type") else "user"
            content = m.content if hasattr(m, "content") else str(m)

        role = ROLE_MAP.get(raw_role, "user")

        # ── Case 1: assistant message that may contain tool_use blocks ────────
        if role == "assistant" and isinstance(content, list):
            text_parts = []
            tool_calls = []

            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(block["text"])
                elif block.get("type") == "tool_use":
                    # Convert from internal Anthropic-style to OpenAI format
                    tool_calls.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    })

            msg: dict = {"role": "assistant"}
            msg["content"] = " ".join(text_parts) if text_parts else None
            if tool_calls:
                msg["tool_calls"] = tool_calls
            api_messages.append(msg)

        # ── Case 2: user message that contains tool_result blocks ─────────────
        elif role == "user" and isinstance(content, list):
            # Check if this is a tool-result message
            tool_result_blocks = [
                b for b in content
                if isinstance(b, dict) and b.get("type") == "tool_result"
            ]
            if tool_result_blocks:
                # Each tool result becomes a separate "tool" role message
                for block in tool_result_blocks:
                    api_messages.append({
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block["content"],
                    })
            else:
                # Plain list content (unlikely but handle gracefully)
                combined = " ".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                if combined:
                    api_messages.append({"role": "user", "content": combined})

        # ── Case 3: plain text message ────────────────────────────────────────
        elif isinstance(content, str) and content.strip():
            api_messages.append({"role": role, "content": content})

    return api_messages


# ── Graph nodes ───────────────────────────────────────────────────────────────

def call_model(state: AgentState) -> AgentState:
    """Send current message history to GPT-4o and capture the response."""
    client = _make_client()
    api_messages = _build_api_messages(state["messages"])

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            tools=OPENAI_TOOLS,
            messages=api_messages,
        )
    except APIConnectionError as exc:
        logger.error("OpenAI API connection error: %s", exc)
        raise RuntimeError("Unable to reach OpenAI API. Check your internet connection.") from exc
    except AuthenticationError as exc:
        logger.error("OpenAI API authentication error: %s", exc)
        raise RuntimeError("Invalid OPENAI_API_KEY. Please check your environment variable.") from exc
    except RateLimitError as exc:
        logger.warning("OpenAI API rate limit hit: %s", exc)
        raise RuntimeError("Rate limit reached. Please wait a moment and try again.") from exc
    except APIStatusError as exc:
        logger.error("OpenAI API error %s: %s", exc.status_code, exc.message)
        raise RuntimeError(f"OpenAI API returned status {exc.status_code}: {exc.message}") from exc

    choice = response.choices[0]
    msg = choice.message

    logs = list(state.get("reasoning_logs", []))
    logs.append({
        "type": "llm_call",
        "text": (
            f"GPT-4o called | finish_reason={choice.finish_reason} | "
            f"input_tokens={response.usage.prompt_tokens} "
            f"output_tokens={response.usage.completion_tokens}"
        ),
        "ts": datetime.now().isoformat(),
    })

    # Serialise assistant message in our internal portable dict form
    assistant_content: list[dict] = []
    if msg.content:
        assistant_content.append({"type": "text", "text": msg.content})
    if msg.tool_calls:
        for tc in msg.tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments),
            })

    new_messages = list(state["messages"]) + [{"role": "assistant", "content": assistant_content}]
    return {
        "messages": new_messages,
        "reasoning_logs": logs,
        "tool_calls_log": state.get("tool_calls_log", []),
    }


def run_tools(state: AgentState) -> AgentState:
    """Execute all tool calls from the latest assistant message."""
    last = state["messages"][-1]
    content = last["content"] if isinstance(last, dict) else last.content

    tool_results: list[dict] = []
    logs = list(state.get("reasoning_logs", []))
    tool_log = list(state.get("tool_calls_log", []))

    for block in content:
        if not (isinstance(block, dict) and block.get("type") == "tool_use"):
            continue

        tool_name = block["name"]
        tool_input = block["input"]
        tool_id = block["id"]

        logs.append({
            "type": "tool_call",
            "text": f"Calling {tool_name}({json.dumps(tool_input)})",
            "ts": datetime.now().isoformat(),
        })
        tool_log.append({"name": tool_name, "input": tool_input, "ts": datetime.now().isoformat()})

        result = dispatch(tool_name, tool_input)

        for pl in result.get("policy_logs", []):
            logs.append({"type": "policy_check", "text": pl, "ts": datetime.now().isoformat()})

        logs.append({
            "type": "tool_result",
            "text": f"{tool_name} → {json.dumps(result)[:300]}",
            "ts": datetime.now().isoformat(),
        })

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tool_id,
            "content": json.dumps(result),
        })

    new_messages = list(state["messages"]) + [{"role": "user", "content": tool_results}]
    return {"messages": new_messages, "reasoning_logs": logs, "tool_calls_log": tool_log}


def should_continue(state: AgentState) -> Literal["run_tools", "__end__"]:
    last = state["messages"][-1]
    content = last["content"] if isinstance(last, dict) else last.content
    if isinstance(content, list) and any(
        b.get("type") == "tool_use" for b in content if isinstance(b, dict)
    ):
        return "run_tools"
    return "__end__"


# ── Build & compile graph ─────────────────────────────────────────────────────

def build_agent():
    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("run_tools", run_tools)
    graph.set_entry_point("call_model")
    graph.add_conditional_edges("call_model", should_continue)
    graph.add_edge("run_tools", "call_model")
    return graph.compile()


agent = build_agent()