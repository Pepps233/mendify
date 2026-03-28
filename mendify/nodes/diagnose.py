from __future__ import annotations

import json
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from mendify.config import AgentConfig
from mendify.state import AgentState

SYSTEM_PROMPT = """\
You are an expert DevOps engineer performing automated CI failure diagnosis.
Analyze the provided build logs and return a JSON object with exactly these keys:
  - diagnosis: string — root cause of the failure
  - patch: object — map of file paths to their complete new content (only files that need changing)
  - confidence: number between 0 and 1
  - explanation: string — what the patch does and why it fixes the issue

Return ONLY the JSON object, no markdown fences or extra text.
"""

RETRY_SUFFIX = """
IMPORTANT: A previous patch attempt failed. You MUST try a DIFFERENT approach.
Do not repeat the same changes. Previous errors are listed below for context.
"""


def _parse_llm_response(content: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned.strip())


def diagnose(state: AgentState) -> dict:
    """Use Claude to diagnose the build failure and propose a patch."""
    build_logs = state.get("build_logs", "")
    error_history: list[str] = state.get("error_history", [])
    iteration: int = state.get("iteration", 0)
    config = AgentConfig()

    # Build prompt
    user_content = f"Build logs:\n\n{build_logs}"
    if error_history:
        history_text = "\n\n".join(
            f"Attempt {i + 1} error:\n{err}" for i, err in enumerate(error_history)
        )
        user_content += f"\n\n{RETRY_SUFFIX}\n\n{history_text}"

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    logger.info("Sending diagnosis request to Claude iteration={}", iteration)
    llm = ChatAnthropic(model=config.model, temperature=config.temperature)
    response = llm.invoke(messages)
    raw = response.content if hasattr(response, "content") else str(response)

    try:
        parsed = _parse_llm_response(str(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse LLM JSON ({}), retrying with extraction", exc)
        # Second attempt: ask model to output clean JSON
        retry_msg = HumanMessage(
            content="Your response was not valid JSON. Return ONLY the JSON object, no other text."
        )
        response2 = llm.invoke(messages + [response, retry_msg])
        raw2 = response2.content if hasattr(response2, "content") else str(response2)
        parsed = _parse_llm_response(str(raw2))

    logger.info(
        "Diagnosis complete confidence={} files_patched={}",
        parsed.get("confidence"),
        len(parsed.get("patch", {})),
    )

    return {
        "diagnosis": parsed.get("diagnosis", ""),
        "patch": parsed.get("patch", {}),
        "confidence": parsed.get("confidence", 0.0),
        "explanation": parsed.get("explanation", ""),
    }
