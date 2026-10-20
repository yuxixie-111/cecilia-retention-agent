# Architecture

## Runtime request path

```text
Historical labeled clinic data ----> Training pipeline ----> sklearn artifact
Current clinic snapshot -----------> Current clinic table --+
                                                            |
Streamlit / Client
        |
      FastAPI
        |
ClinicRetentionWorkflow
        |
  +-----+-------------------+
  |                         |
SQL Agent                ML Agent
  |                         |
ClinicRepository       MLService
  |                         |
SQLite current/history tables  sklearn artifact
  +------------+------------+
               |
        Knowledge Agent ---- Chroma / playbook index
               |
          Memory Service --- SQLite session + long-term memory
               |
      Recommendation Agent
        |             |
Deterministic policy   Microsoft Agent Framework + Ollama
        +-------------+
               |
          Reviewer Agent
               |
           Report Agent
               |
   Prediction / feedback / approval ticket storage
```

## Design decisions

### Provider isolation
Microsoft Agent Framework is intentionally restricted to `app/agents/providers`. ETL, ML, services, repositories, evaluation, and API code do not import the framework. This reduces migration cost when provider APIs change.

Formal Agent Skills live in `skills/` as self-contained `SKILL.md` packages. The Microsoft
provider attaches them through `SkillsProvider`, which advertises metadata first and loads
instructions or references only when needed. `AgentSkillService` provides the same safe,
read-only discovery boundary to non-Microsoft adapters. Specialist roles are business ownership
metadata and intentionally live in `specialist_catalog.py`, not in the Agent Skills namespace.

### Deterministic core, probabilistic edge
Database facts, model outputs, business rules, and safety checks are deterministic. The LLM can synthesize and prioritize but cannot silently replace authoritative facts.

### Tools versus services
Agent tools are narrow, documented interfaces. Services contain reusable business logic. Repositories own persistence. This prevents agents from receiving unrestricted database or filesystem access.

### Memory
Session messages support continuity during one analysis session. Long-term memory stores compact, high-value summaries, not full raw conversations. Memory is retrieved with limits and included as evidence rather than treated as unquestionable truth.

### Human approval
Creating a ticket is an explicit request parameter. Sending email, issuing discounts, or changing clinic records should follow the same approval boundary in later versions.
