from __future__ import annotations

from backend.app.schemas.common import HumanVerificationQueueItem


JANE_SOCIAL_HEAT_CHECK = HumanVerificationQueueItem(
    item="jane_social_heat_check",
    question="Have non-investor friends or family recently asked you about this stock or theme unprompted?",
    jane_reference="Research handbook: widespread non-investor discussion is a late-cycle overheat signal",
    action="If yes, treat as additional overheat evidence. Not a scoring input — human judgment required.",
    needs_human_verification=True,
)


def append_jane_social_heat_check(queue: list, overheat_score: float) -> None:
    if overheat_score < 60:
        return
    if any(isinstance(item, HumanVerificationQueueItem) and item.item == JANE_SOCIAL_HEAT_CHECK.item for item in queue):
        return
    if any(isinstance(item, dict) and item.get("item") == JANE_SOCIAL_HEAT_CHECK.item for item in queue):
        return
    queue.append(JANE_SOCIAL_HEAT_CHECK)
