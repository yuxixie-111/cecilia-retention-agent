from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from agent_framework import SkillsProvider
from agent_framework_ollama import OllamaChatClient

from app.core.config import PROJECT_ROOT
from app.core.exceptions import AgentProviderError
from app.models.domain import (
    ActionItem,
    ClinicProfile,
    KnowledgeHit,
    MemoryItem,
    PredictionResult,
    Recommendation,
    ReviewResult,
)
from app.services.action_catalog import approved_interventions
from app.services.agent_skill_router import recommended_agent_skills
from app.services.specialist_catalog import available_specialists, recommended_specialist_focus
from app.tools.renewal_tools import RetentionToolRegistry


class MicrosoftOllamaRecommendationProvider:
    """Ollama-backed local provider that uses structured JSON responses for recommendations."""

    name = "microsoft_ollama"
    generation_mode = "ollama"

    def __init__(
        self,
        host: str,
        model_id: str,
        tools: RetentionToolRegistry | None,
        settings: Any | None = None,
        skills_dir: Path | None = None,
    ):
        self.host = host.rstrip("/")
        self.model_id = model_id
        self.tools = tools
        self.settings = settings
        self.skills_dir = (skills_dir or PROJECT_ROOT / "skills").resolve()
        max_resource_bytes = int(getattr(settings, "skill_max_resource_bytes", 100_000))

        def trusted_resource_filter(skill_name: str, relative_path: str) -> bool:
            relative = Path(relative_path)
            skill_dir = (self.skills_dir / skill_name).resolve()
            resource = (skill_dir / relative).resolve()
            return (
                not relative.is_absolute()
                and ".." not in relative.parts
                and "agents" not in relative.parts
                and resource.is_relative_to(skill_dir)
                and resource.is_file()
                and resource.stat().st_size <= max_resource_bytes
            )

        self.skills_provider = SkillsProvider.from_paths(
            self.skills_dir,
            script_runner=None,
            resource_filter=trusted_resource_filter,
            disable_load_skill_approval=True,
            disable_read_skill_resource_approval=True,
        )
        self.chat_client = OllamaChatClient(host=self.host, model=self.model_id)
        self.agent = self.chat_client.as_agent(
            name="cecilia-clinic-renewal",
            instructions=(
                "You are a careful enterprise retention planner. Use formal Agent Skills by loading "
                "only the skills relevant to the supplied account. Treat profile facts and model outputs "
                "as authoritative, never invent clinic details, and return valid JSON only."
            ),
            tools=self.tools.as_functions() if self.tools else None,
            context_providers=[self.skills_provider],
        )
        self.ollama_available = self._probe_ollama()
        self.last_latency_ms: float | None = None
        self.last_successful_llm_call: str | None = None
        self.last_error: str | None = None
        self.last_prompt: str | None = None

    def _probe_ollama(self) -> bool:
        try:
            response = httpx.get(f"{self.host}/api/tags", timeout=2.0)
            return response.status_code == 200
        except (httpx.HTTPError, httpx.TimeoutException, OSError):
            return False

    @staticmethod
    def _extract_json(text: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fenced:
            return fenced.group(1)
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return text[start : end + 1]
        raise AgentProviderError("The local model did not return a JSON object")

    def _build_context(
        self,
        profile: ClinicProfile,
        prediction: PredictionResult,
        benchmark: dict,
        knowledge: list[KnowledgeHit],
        memories: list[MemoryItem],
    ) -> dict[str, Any]:
        intervention_history = [
            {
                "type": memory.memory_type,
                "content": memory.content,
                "importance": memory.importance,
            }
            for memory in memories
            if memory.memory_type.startswith("intervention_")
        ]
        return {
            "clinic_id": profile.clinic_id,
            "clinic_profile": profile.model_dump(),
            "prediction": prediction.model_dump(),
            "risk_drivers": [driver.model_dump() for driver in prediction.top_drivers],
            "segment_benchmark": benchmark,
            "retrieved_playbooks": [hit.model_dump() for hit in knowledge],
            "long_term_memory": [memory.model_dump() for memory in memories],
            "prior_interventions": [memory.content for memory in memories if memory.memory_type.startswith("intervention_")],
            "intervention_history": intervention_history,
            "available_interventions": approved_interventions(),
            "recommended_agent_skills": recommended_agent_skills(profile, prediction, memories),
            "available_specialists": available_specialists(),
            "recommended_specialist_focus": recommended_specialist_focus(profile, prediction),
            "business_constraints": [
                "Use only retrieved clinic facts and model outputs.",
                "Do not invent clinic facts or model metrics.",
                "Use clinic_profile.clinic_notes only when present to personalize communication and interventions.",
                "Prefer the approved available_interventions list and only adapt it when the clinic context clearly requires it.",
                "Load only relevant formal Agent Skills, starting with recommended_agent_skills.",
                "Use available_specialists and recommended_specialist_focus to assign internal ownership.",
                "Do not repeat a prior intervention already noted in memory, especially ones marked ineffective.",
                "The evidence array must include an item that starts with 'Model risk:' and cites lapse probability and risk band.",
                "Human approval is required before creating tickets, issuing discounts, or changing clinic records.",
            ],
        }

    def _build_prompt(self, context: dict[str, Any]) -> str:
        return (
            "You are the retention recommendation agent for an enterprise clinic-success workflow. "
            "Return only valid JSON. Use the supplied facts and do not invent clinic details. "
            "Include executive_summary, risk_assessment, recommended_actions, rationale, evidence, "
            "do_not_do, confidence, and requires_human_approval. The evidence array must include "
            "an item starting with 'Model risk:' that cites lapse probability and risk band.\n"
            f"Context:\n{json.dumps(context, default=str, indent=2)}"
        )

    def _build_repair_prompt(self, raw_text: str) -> str:
        return (
            "The previous response was not valid JSON. Return one JSON object only and use this schema: "
            "{\"executive_summary\": string, \"risk_assessment\": string, \"recommended_actions\": [string], "
            "\"rationale\": string, \"evidence\": [string], \"do_not_do\": [string], \"confidence\": number, "
            "\"requires_human_approval\": boolean}. Previous response: "
            f"{raw_text}"
        )

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5

        # Some local models emit confidence as a percentage (e.g., 98 for 98%).
        if confidence > 1.0 and confidence <= 100.0:
            confidence = confidence / 100.0

        if confidence < 0.0:
            return 0.0
        if confidence > 1.0:
            return 1.0
        return confidence

    def _normalize_payload(self, payload: dict[str, Any]) -> Recommendation:
        actions: list[ActionItem] = []
        recommended_actions = payload.get("recommended_actions") or []
        if isinstance(recommended_actions, list) and recommended_actions:
            for index, action in enumerate(recommended_actions, start=1):
                action_text = action if isinstance(action, str) else str(action)
                actions.append(
                    ActionItem(
                        priority=index,
                        action=action_text,
                        owner="Clinic Success",
                        rationale=payload.get("rationale", "Generated by local LLM"),
                        expected_impact="Address the lapse risk using evidence-backed next steps.",
                        approval_required=bool(payload.get("requires_human_approval", False)),
                    )
                )
        elif payload.get("actions"):
            actions = [
                ActionItem.model_validate(action) if isinstance(action, dict) else ActionItem(
                    priority=1,
                    action=str(action),
                    owner="Clinic Success",
                    rationale=payload.get("rationale", "Generated by local LLM"),
                    expected_impact="Address the lapse risk using evidence-backed next steps.",
                    approval_required=bool(payload.get("requires_human_approval", False)),
                )
                for action in payload["actions"]
            ]
        if not actions:
            actions.append(
                ActionItem(
                    priority=1,
                    action="Schedule an evidence-based retention review with the account owner.",
                    owner="Clinic Success",
                    rationale=payload.get("rationale", "Generated by local LLM"),
                    expected_impact="Address the lapse risk using evidence-backed next steps.",
                    approval_required=bool(payload.get("requires_human_approval", False)),
                )
            )
        evidence = payload.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        do_not_do = payload.get("do_not_do") or []
        if not isinstance(do_not_do, list):
            do_not_do = [str(do_not_do)]
        confidence = self._normalize_confidence(payload.get("confidence", 0.5))
        return Recommendation(
            executive_summary=str(payload.get("executive_summary", "")),
            risk_assessment=str(payload.get("risk_assessment", "")),
            recommended_actions=[str(item) for item in recommended_actions] if isinstance(recommended_actions, list) else [],
            rationale=str(payload.get("rationale", "")),
            actions=actions,
            do_not_do=[str(item) for item in do_not_do],
            evidence=[str(item) for item in evidence],
            confidence=confidence,
            generated_by=self.name,
            requires_human_approval=bool(payload.get("requires_human_approval", False)),
        )

    async def _chat(self, prompt: str, *, retry: bool = False) -> str:
        if not self.ollama_available:
            raise AgentProviderError(
                "Ollama is unavailable. Start the local service and ensure the configured model is installed."
            )
        start = time.perf_counter()
        timeout_seconds = float(getattr(self.settings, "llm_timeout_seconds", 120))
        try:
            response = await asyncio.wait_for(
                self.agent.run(
                    prompt,
                    options={
                        "temperature": float(getattr(self.settings, "llm_temperature", 0.2)),
                        "num_predict": int(getattr(self.settings, "llm_max_tokens", 1500)),
                    },
                ),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            message = (
                "Microsoft/Ollama agent execution timed out after "
                f"{timeout_seconds:g} seconds"
            )
            self.last_error = message
            raise AgentProviderError(message) from exc
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            raise AgentProviderError(f"Microsoft/Ollama agent execution failed: {exc}") from exc

        self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
        text = response.text
        if not text:
            raise AgentProviderError("Ollama returned an empty response")
        self.last_successful_llm_call = datetime.now(UTC).isoformat()
        if retry:
            self.last_error = None
        return text

    async def generate(
        self,
        profile: ClinicProfile,
        prediction: PredictionResult,
        benchmark: dict,
        knowledge: list[KnowledgeHit],
        memories: list[MemoryItem],
    ) -> Recommendation:
        context = self._build_context(profile, prediction, benchmark, knowledge, memories)
        prompt = self._build_prompt(context)
        self.last_prompt = prompt
        raw_text = ""
        try:
            raw_text = await self._chat(prompt)
        except AgentProviderError as exc:
            self.last_error = str(exc)
            raise

        try:
            parsed = json.loads(self._extract_json(raw_text))
            return self._normalize_payload(parsed)
        except (json.JSONDecodeError, AgentProviderError):
            try:
                repaired_text = await self._chat(self._build_repair_prompt(raw_text), retry=True)
                parsed = json.loads(self._extract_json(repaired_text))
                return self._normalize_payload(parsed)
            except (json.JSONDecodeError, AgentProviderError) as repair_exc:
                raise AgentProviderError(
                    "The local Ollama model returned invalid JSON after a repair attempt"
                ) from repair_exc
        except Exception as exc:
            self.last_error = str(exc)
            raise AgentProviderError(f"Microsoft/Ollama agent execution failed: {exc}") from exc

    async def review_recommendation(
        self,
        profile: ClinicProfile,
        prediction: PredictionResult,
        recommendation: Recommendation,
    ) -> ReviewResult:
        review_prompt = (
            "You are the reviewer agent for a retention recommendation. Verify that the plan only uses "
            "retrieved clinic facts, cites the retrieved playbooks, does not repeat prior interventions, "
            "and requires human approval for external actions. Return valid JSON: "
            "{\"passed\": boolean, \"score\": number, \"issues\": [string], \"required_changes\": [string]}. "
            f"Clinic profile: {profile.model_dump_json()}\nPrediction: {prediction.model_dump_json()}\n"
            f"Recommendation: {recommendation.model_dump_json()}"
        )
        try:
            raw_text = await self._chat(review_prompt)
            parsed = json.loads(self._extract_json(raw_text))
            return ReviewResult.model_validate(parsed)
        except Exception as exc:
            raise AgentProviderError(f"Ollama reviewer execution failed: {exc}") from exc
