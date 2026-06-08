"""Deep-research trigger for MUSE.

The user asked: "do deep research if it doesn't fully understand a
topic or code". This module implements the trigger: when reasoning
confidence is too low OR the topic is unfamiliar (no recollection
hits, no matching rule), JARVIS opens a structured research brief
INSTEAD of answering at low confidence.

The actual research is delegated to:

- ``aos-enterprise-council/specialists/research-evidence-bureau.md``
  for owner-approved external lookups.
- The ``model_router`` ``browser-research`` worker when
  ``needs_external_docs=True``.
- The repo's own files (read_file / search_files) for code questions
  about the current repo.

This module produces the ``ResearchBrief`` envelope, not the result.
The runtime hands the brief to the appropriate worker and awaits
return.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence


class ResearchScope(Enum):
    LOCAL_REPO = "local_repo"
    LOCAL_DOCS = "local_docs"
    LOCAL_MEMORY = "local_memory"
    EXTERNAL_WEB = "external_web"
    COUNCIL_SPECIALIST = "council_specialist"


@dataclass(frozen=True)
class ResearchQuestion:
    text: str
    why_it_matters: str
    must_cite: bool = True


@dataclass(frozen=True)
class ResearchBrief:
    topic: str
    triggered_by: str  # "low_confidence" | "no_recollection" | "unfamiliar_topic" | "code_unknown"
    scopes: tuple[ResearchScope, ...]
    questions: tuple[ResearchQuestion, ...]
    minimum_sources: int
    forbid_speculation: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "triggered_by": self.triggered_by,
            "scopes": [s.value for s in self.scopes],
            "questions": [
                {"text": q.text, "why_it_matters": q.why_it_matters, "must_cite": q.must_cite}
                for q in self.questions
            ],
            "minimum_sources": self.minimum_sources,
            "forbid_speculation": self.forbid_speculation,
            "created_at": self.created_at.isoformat(),
        }


def open_brief(
    topic: str,
    triggered_by: str,
    questions: Sequence[ResearchQuestion],
    scopes: Optional[Sequence[ResearchScope]] = None,
    minimum_sources: int = 2,
) -> ResearchBrief:
    """Construct a ResearchBrief envelope.

    Default scopes start LOCAL (repo + docs + memory) and only add
    EXTERNAL_WEB when the trigger is "unfamiliar_topic" or the caller
    explicitly requests it. This matches Hermes's local-first
    principle.
    """

    if scopes is None:
        scope_list: list[ResearchScope] = [
            ResearchScope.LOCAL_MEMORY,
            ResearchScope.LOCAL_DOCS,
            ResearchScope.LOCAL_REPO,
        ]
        if triggered_by == "unfamiliar_topic":
            scope_list.append(ResearchScope.EXTERNAL_WEB)
        scopes = tuple(scope_list)

    return ResearchBrief(
        topic=topic,
        triggered_by=triggered_by,
        scopes=tuple(scopes),
        questions=tuple(questions),
        minimum_sources=minimum_sources,
    )


def needs_research(
    *,
    confidence: float,
    recollection_hits: int,
    has_matching_rule: bool,
    is_code_question: bool = False,
    confidence_floor: float = 0.65,
) -> Optional[str]:
    """Return the trigger reason if research is required, else None.

    Trigger categories:
    - ``low_confidence``: reasoning landed below the floor.
    - ``no_recollection``: query has no memory hits AND no rule fits.
    - ``unfamiliar_topic``: topic outside any known category.
    - ``code_unknown``: question is about code we haven't read yet.
    """

    if confidence < confidence_floor and not has_matching_rule:
        if recollection_hits == 0:
            return "no_recollection"
        return "low_confidence"
    if is_code_question and recollection_hits == 0 and not has_matching_rule:
        return "code_unknown"
    if recollection_hits == 0 and not has_matching_rule and confidence < 0.5:
        return "unfamiliar_topic"
    return None


_CITATION_REQUIRED_INSTRUCTION = """\
Cite every factual claim. If you cannot cite a claim, prefix it with
"I'm not certain — " or replace it with "I don't know yet". Do not
guess. Do not fabricate file paths, line numbers, URLs, API names,
function signatures, version numbers, dates, or quotations. When
unsure, return the ResearchBrief instead of an answer.
"""


def epistemic_instruction() -> str:
    """The 'never hallucinates' rule prefix added to JARVIS's prompts."""

    return _CITATION_REQUIRED_INSTRUCTION
