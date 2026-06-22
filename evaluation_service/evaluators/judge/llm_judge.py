"""
LLM-as-a-Judge core evaluation engine for the thesis framework.

Active single-run dimensions:
  - completeness
  - accuracy
  - faithfulness
  - hallucination
  - safety
  - clinical_utility
  - conversation_quality
  - workflow, when workflow context exists
  - memory_groundedness, when memory/context exists

Scores returned by the LLM are normalized to 0.0-1.0. The orchestrator converts
the thesis scale dimensions to 1-5 in llm_judge_metrics.
"""

from __future__ import annotations

import asyncio
import json
import logging

from groq import AsyncGroq

from app.config.settings import settings
from evaluators.judge.prompts import (
    SYSTEM_JUDGE,
    accuracy_prompt,
    clinical_utility_prompt,
    completeness_prompt,
    faithfulness_prompt,
    groundedness_faithfulness_prompt,
    hallucination_judge_prompt,
    memory_groundedness_prompt,
    multilingual_consistency_prompt,
    preconsultation_quality_prompt,
    recommendation_quality_prompt,
    safety_judge_prompt,
    symptom_collection_completeness_prompt,
    thesis_conversation_quality_prompt,
    workflow_judge_prompt,
)
from schemas.eval_schemas import EvalRequest, JudgeDimension, MultilingualEvalRequest

logger = logging.getLogger(__name__)

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


async def _judge_call(prompt: str, dimension: str) -> JudgeDimension:
    raw = ""
    try:
        client = _get_client()
        resp = await client.chat.completions.create(
            model=settings.JUDGE_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_JUDGE},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        score = max(0.0, min(1.0, float(data.get("score", 0.5))))
        return JudgeDimension(score=score, explanation=str(data.get("explanation", "")))
    except json.JSONDecodeError:
        logger.warning("[LLMJudge:%s] JSON parse failed | raw=%s", dimension, raw[:200])
        return JudgeDimension(score=0.5, explanation="Judge response could not be parsed.")
    except Exception as exc:
        logger.warning("[LLMJudge:%s] Call failed: %s", dimension, exc)
        return JudgeDimension(score=0.5, explanation=f"Evaluation unavailable ({type(exc).__name__}).")


class LLMJudge:
    """Orchestrates parallel LLM-as-a-Judge evaluation."""

    async def evaluate(self, req: EvalRequest) -> dict[str, JudgeDimension]:
        tasks: dict[str, asyncio.Task] = {
            "safety": asyncio.create_task(_judge_call(
                safety_judge_prompt(req.user_message, req.agent_response),
                "safety",
            )),
            "hallucination": asyncio.create_task(_judge_call(
                hallucination_judge_prompt(req.user_message, req.agent_response, req.context),
                "hallucination",
            )),
            "completeness": asyncio.create_task(_judge_call(
                completeness_prompt(req.user_message, req.agent_response, req.symptom_data, req.context),
                "completeness",
            )),
            "accuracy": asyncio.create_task(_judge_call(
                accuracy_prompt(req.user_message, req.agent_response, req.reference_response, req.context),
                "accuracy",
            )),
            "faithfulness": asyncio.create_task(_judge_call(
                faithfulness_prompt(req.user_message, req.agent_response, req.context, req.retrieved_memories or []),
                "faithfulness",
            )),
            "groundedness": asyncio.create_task(_judge_call(
                groundedness_faithfulness_prompt(
                    req.user_message,
                    req.agent_response,
                    req.context,
                    req.retrieved_memories or [],
                ),
                "groundedness",
            )),
            "clinical_utility": asyncio.create_task(_judge_call(
                clinical_utility_prompt(req.user_message, req.agent_response),
                "clinical_utility",
            )),
            "conversation_quality": asyncio.create_task(_judge_call(
                thesis_conversation_quality_prompt(req.user_message, req.agent_response, req.language),
                "conversation_quality",
            )),
        }

        if req.retrieved_memories or req.context:
            tasks["memory_groundedness"] = asyncio.create_task(_judge_call(
                memory_groundedness_prompt(req.user_message, req.agent_response, req.retrieved_memories or []),
                "memory_groundedness",
            ))

        if req.workflow:
            tasks["workflow"] = asyncio.create_task(_judge_call(
                workflow_judge_prompt(
                    req.user_message,
                    req.agent_response,
                    req.workflow.expected_tool,
                    req.workflow.expected_action,
                    req.workflow.workflow_state,
                    req.workflow.ui_action,
                ),
                "workflow",
            ))

        if req.include_preconsultation:
            wf_state = (req.workflow.workflow_state if req.workflow else {}) or {}
            tasks["symptom_collection"] = asyncio.create_task(_judge_call(
                symptom_collection_completeness_prompt(req.user_message, req.agent_response, wf_state),
                "symptom_collection",
            ))
            symptom_data = req.symptom_data or {}
            if symptom_data.get("chief_complaint") and symptom_data.get("duration"):
                tasks["preconsultation_quality"] = asyncio.create_task(_judge_call(
                    preconsultation_quality_prompt(
                        req.user_message,
                        req.agent_response,
                        symptom_data.get("chief_complaint", ""),
                        symptom_data.get("duration", ""),
                        int(symptom_data.get("severity", 5)),
                        symptom_data.get("associated_symptoms", []),
                    ),
                    "preconsultation_quality",
                ))

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        dimensions: dict[str, JudgeDimension] = {}
        for key, result in zip(tasks.keys(), results):
            if isinstance(result, BaseException):
                logger.warning("[LLMJudge] Dimension '%s' raised: %s", key, result)
                dimensions[key] = JudgeDimension(score=0.5, explanation="Evaluation failed.")
            else:
                dimensions[key] = result
        return dimensions

    async def evaluate_multilingual(self, req: MultilingualEvalRequest) -> JudgeDimension:
        return await _judge_call(
            multilingual_consistency_prompt(req.intent_description, req.messages, req.responses),
            "multilingual_consistency",
        )

    async def evaluate_recommendation(
        self,
        user_message: str,
        agent_response: str,
        recommendations: list[dict],
        context: str | None,
    ) -> JudgeDimension:
        return await _judge_call(
            recommendation_quality_prompt(user_message, agent_response, recommendations, context),
            "recommendation",
        )
