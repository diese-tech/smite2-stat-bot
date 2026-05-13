import hashlib
import json
from difflib import SequenceMatcher


def fingerprint_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fingerprint_json(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return fingerprint_bytes(payload)


def best_fuzzy_match(player_names: list[str], candidates: list[dict], cutoff: float = 0.72) -> str:
    names = _normalize_names(player_names)
    if not names:
        return ""

    best_score = 0.0
    best_candidate = ""
    for candidate in candidates:
        candidate_names = _normalize_names(
            (candidate.get("Parsed Player Names") or candidate.get("parsed_player_names") or "").split(",")
        )
        if not candidate_names:
            continue
        score = _name_overlap_score(names, candidate_names)
        if score > best_score:
            best_score = score
            best_candidate = candidate.get("Discord Message ID") or candidate.get("message_id") or ""

    return best_candidate if best_score >= cutoff else ""


def _normalize_names(names: list[str]) -> list[str]:
    return sorted({name.strip().lower() for name in names if name and name.strip()})


def _name_overlap_score(left: list[str], right: list[str]) -> float:
    exact = len(set(left) & set(right))
    if exact:
        return exact / min(len(set(left)), len(set(right)))

    scores = []
    for name in left:
        scores.append(max(SequenceMatcher(None, name, other).ratio() for other in right))
    return sum(scores) / len(scores)
