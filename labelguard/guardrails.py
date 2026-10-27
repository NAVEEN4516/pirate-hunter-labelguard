"""Conservative local detectors. Not a claim of comprehensive jailbreak or toxicity detection."""

import re
import unicodedata

INJECTION = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|system)|"
    r"(?:system|assistant|developer)\s*(?:prompt|message|:)|"
    r"(?:reveal|print|show|exfiltrate)\s+(?:the\s+)?(?:secret|api.?key|system prompt)|"
    r"(?:bypass|disable)\s+(?:the\s+)?(?:guardrail|verification|safety)|"
    r"(?:call|invoke|execute)\s+(?:the\s+)?(?:tool|shell|command)|"
    r"<\|(?:im_start|system)|\[INST\]|approve\s+(?:this|all)\s+labels?\s+regardless",
    re.IGNORECASE,
)
TOXIC = re.compile(r"\b(?:idiot|moron|kill yourself|fuck|shithead)\b", re.IGNORECASE)


def texts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from texts(v)
    elif isinstance(value, list):
        for v in value:
            yield from texts(v)


def inspect_input(value) -> list[str]:
    errors = []
    for original in texts(value):
        text = unicodedata.normalize("NFKC", original)
        text = "".join(c for c in text if unicodedata.category(c) != "Cf")
        if INJECTION.search(text):
            errors.append(
                "Potential prompt injection in free text; remove instructions directed at the system."
            )
        if TOXIC.search(text):
            errors.append("Toxic text detected by the local input filter.")
    return sorted(set(errors))


def safe_output(result: dict) -> bool:
    if result.get("print_authorized") is not False or not result.get("verified"):
        return False
    text = " ".join(
        [result.get("summary", "")] + [f.get("explanation", "") for f in result.get("findings", [])]
    )
    if TOXIC.search(text):
        return False
    return not re.search(
        r"\b(?:approved for print|authorised for print|authorized for print|legally approved)\b", text, re.I
    )
