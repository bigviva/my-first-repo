"""Common escape rating / escalation matrix.

Rating = severity x likelihood on a 4x4 matrix. The score drives the
escalation level so every escape is rated and escalated the same way,
replacing the ad-hoc judgment calls made in spreadsheets today.
"""

SEVERITY_LABELS = {1: "Minor", 2: "Moderate", 3: "Major", 4: "Critical"}
LIKELIHOOD_LABELS = {1: "Rare", 2: "Occasional", 3: "Likely", 4: "Frequent"}


def rating_score(severity: int, likelihood: int) -> int:
    return severity * likelihood


def escalation_level(score: int) -> str:
    if score >= 12:
        return "Executive"
    if score >= 8:
        return "Level 2"
    if score >= 4:
        return "Level 1"
    return "None"


def rate(severity: int, likelihood: int) -> tuple[int, str]:
    score = rating_score(severity, likelihood)
    return score, escalation_level(score)
