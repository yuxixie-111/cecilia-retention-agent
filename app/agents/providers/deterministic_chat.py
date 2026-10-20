from __future__ import annotations

import json
import re

from app.models.domain import ChatHistoryMessage, ChatResult
from app.tools.renewal_tools import RetentionToolRegistry


class DeterministicRetentionChatProvider:
    """CI-safe conversational fallback for common retention questions."""

    name = "deterministic_chat"
    model_id = "rules-chat-v1"
    generation_mode = "deterministic"
    service_available = True

    def __init__(self, tools: RetentionToolRegistry):
        self.tools = tools

    @staticmethod
    def _limit(message: str) -> int:
        patterns = (
            r"\btop\s*(\d{1,3})\b",
            r"\bhighest\s*(\d{1,3})\b",
            r"(\d{1,3})\s+highest",
            r"前\s*(\d{1,3})\s*(?:个|名)?",
            r"最高(?:的)?\s*(\d{1,3})\s*(?:个|名)?",
        )
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return min(max(int(match.group(1)), 1), 100)
        return 10

    @staticmethod
    def _clinic_id(message: str) -> str | None:
        explicit = re.search(r"\bCLN[- ]?(\d{1,4})\b", message, re.IGNORECASE)
        if explicit:
            return f"CLN-{int(explicit.group(1)):04d}"
        shorthand = re.search(
            r"(?:客户|clinic)\s*(?:id)?\s*[-:#：]?\s*0*(\d{1,4})",
            message,
            re.IGNORECASE,
        )
        if shorthand:
            return f"CLN-{int(shorthand.group(1)):04d}"
        leading = re.search(
            r"0*(\d{1,4})\s*(?:号)?(?:客户|clinic)",
            message,
            re.IGNORECASE,
        )
        if leading:
            return f"CLN-{int(leading.group(1)):04d}"
        return None

    @staticmethod
    def _markdown_table(rows: list[dict]) -> str:
        lines = [
            "| Rank | Clinic | Risk | Band | Segment | Renewal | Usage change |",
            "|---:|---|---:|---|---|---:|---:|",
        ]
        for index, row in enumerate(rows, start=1):
            lines.append(
                "| {rank} | {clinic} | {risk:.1%} | {band} | {segment} | "
                "{renewal} days | {usage:+.1f}% |".format(
                    rank=index,
                    clinic=row["clinic_id"],
                    risk=float(row["lapse_probability"]),
                    band=row["risk_band"],
                    segment=row["segment"],
                    renewal=row["days_to_term"],
                    usage=float(row["order_change_pct"]),
                )
            )
        return "\n".join(lines)

    async def chat(
        self,
        message: str,
        history: list[ChatHistoryMessage] | None = None,
    ) -> ChatResult:
        del history
        lowered = message.lower()
        ranking_tokens = (
            "top",
            "highest",
            "high-risk",
            "high risk",
            "rank",
            "ranking",
            "最高",
            "风险客户",
            "高风险",
            "排名",
            "排行",
        )
        if any(token in lowered for token in ranking_tokens) and not self._clinic_id(message):
            limit = self._limit(message)
            rows = json.loads(self.tools.list_high_risk_clinics(limit=limit))
            answer = (
                f"Here are the Top {len(rows)} accounts ranked by the current model's lapse probability. "
                "This is a priority list, not proof that they have already lapsed.\n\n"
                f"{self._markdown_table(rows)}"
            )
            return ChatResult(
                answer=answer,
                provider=self.name,
                model=self.model_id,
                generation_mode=self.generation_mode,
                tools_used=["list_high_risk_clinics"],
            )

        clinic_id = self._clinic_id(message)
        if clinic_id:
            profile = json.loads(self.tools.get_clinic_profile(clinic_id))
            prediction = json.loads(self.tools.predict_lapse(clinic_id))
            memories = json.loads(self.tools.get_clinic_memories(clinic_id))
            tools_used = ["get_clinic_profile", "predict_lapse", "get_clinic_memories"]

            if any(token in lowered for token in ("折扣", "discount", "打折")):
                knowledge = json.loads(
                    self.tools.search_renewal_playbooks(
                        "discount renewal adoption recovery value realization"
                    )
                )
                tools_used.append("search_renewal_playbooks")
                reasons: list[str] = []
                if float(profile["active_cabinet_ratio_30d"]) < 0.40:
                    reasons.append(
                        f"Active seat ratio is only {float(profile['active_cabinet_ratio_30d']):.1%}. "
                        "This looks like an adoption issue, so a price cut will not fix usage."
                    )
                if float(profile["order_change_pct"]) <= -15:
                    reasons.append(
                        f"Usage change over 30 days is {float(profile['order_change_pct']):+.1f}%. "
                        "Find the workflow or rollout blocker first."
                    )
                if int(profile["service_tickets_90d"]) >= 4:
                    reasons.append(
                        f"There were {int(profile['service_tickets_90d'])} support tickets in 90 days. "
                        "Fix the service or product issue before talking price."
                    )
                if int(profile["days_to_term"]) > 120:
                    reasons.append(
                        f"Renewal is still {int(profile['days_to_term'])} days away. "
                        "A discount now is probably too early."
                    )
                prior_discount = [
                    item["content"]
                    for item in memories
                    if "discount" in item["content"].lower() or "折扣" in item["content"]
                ]
                if prior_discount:
                    reasons.append(
                        "Memory already has a discount-related intervention. "
                        "Do not repeat it without evidence that it worked."
                    )
                if not reasons:
                    reasons.append(
                        "The current data does not show that a discount is the best next step. "
                        "Check the risk drivers and value gap first."
                    )
                evidence = "\n".join(f"- {reason}" for reason in reasons)
                source_note = (
                    f"Retrieved {len(knowledge)} approved playbook excerpts."
                    if knowledge
                    else "No matching playbook came back, so this answer uses clinic and model facts only."
                )
                answer = (
                    f"This is not a rule that **{clinic_id} can never get a discount**. "
                    "The current evidence just does not support making a discount the first move.\n\n"
                    f"Model risk: **{float(prediction['lapse_probability']):.1%} "
                    f"({prediction['risk_band']})**.\n\n{evidence}\n\n"
                    f"{source_note}\n\n"
                    "Handle adoption, support, or value-realization first. "
                    "Any commercial concession still needs an account owner."
                )
                return ChatResult(
                    answer=answer,
                    provider=self.name,
                    model=self.model_id,
                    generation_mode=self.generation_mode,
                    tools_used=tools_used,
                )

            answer = (
                f"**{clinic_id}** currently has model risk "
                f"**{float(prediction['lapse_probability']):.1%} ({prediction['risk_band']})**. "
                f"Segment is {profile['segment']}, renewal in {profile['days_to_term']} days, "
                f"usage change {float(profile['order_change_pct']):+.1f}%, "
                f"active seat ratio {float(profile['active_cabinet_ratio_30d']):.1%}. "
                f"There are {len(memories)} related memory notes."
            )
            return ChatResult(
                answer=answer,
                provider=self.name,
                model=self.model_id,
                generation_mode=self.generation_mode,
                tools_used=tools_used,
            )

        return ChatResult(
            answer=(
                "I am Cecilia's GenAI Retention Decision-Support desk. You can ask:\n\n"
                "- Who are the 10 highest-risk clinics?\n"
                "- Why shouldn't clinic 02 get a discount first?\n"
                "- What is the risk and history for CLN-0042?\n"
                "- Which retention playbook fits declining adoption?\n\n"
                "Clinic and portfolio questions go through controlled tools. I will not invent account facts."
            ),
            provider=self.name,
            model=self.model_id,
            generation_mode=self.generation_mode,
            tools_used=[],
        )
