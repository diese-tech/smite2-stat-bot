from services import evidence_service


def test_json_fingerprint_is_stable_for_key_order():
    left = {"draft_id": "GF-0001", "games": [{"game_number": 1}]}
    right = {"games": [{"game_number": 1}], "draft_id": "GF-0001"}

    assert evidence_service.fingerprint_json(left) == evidence_service.fingerprint_json(right)


def test_fuzzy_match_returns_candidate_above_cutoff():
    candidate = {
        "Discord Message ID": "123",
        "Parsed Player Names": "Alpha, Bravo, Charlie, Delta, Echo",
    }

    assert evidence_service.best_fuzzy_match(["Alpha", "Bravo", "Charlie"], [candidate]) == "123"


def test_fuzzy_match_returns_empty_below_cutoff():
    candidate = {
        "Discord Message ID": "123",
        "Parsed Player Names": "One, Two, Three",
    }

    assert evidence_service.best_fuzzy_match(["Alpha", "Bravo", "Charlie"], [candidate]) == ""

