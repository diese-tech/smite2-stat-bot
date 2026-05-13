import json
import os
import tempfile
import time
from pathlib import Path

import config
from services import guild_config_service, match_service, sheets_service


ECONOMY_FILE = "forgelens_economy.json"
LINE_STATUSES = {"created", "open", "closed", "locked", "settled", "voided", "archived"}
WAGER_STATUSES = {"placed", "settled", "voided"}
TRANSACTION_KINDS = {
    "wallet_seed",
    "wallet_adjust",
    "wager_debit",
    "wager_payout",
    "wager_refund",
}


class EconomyError(ValueError):
    pass


def _now() -> int:
    return int(time.time())


def _empty_store() -> dict:
    return {"guilds": {}}


def _empty_guild(guild_id: int | str) -> dict:
    return {
        "guild_id": str(guild_id),
        "wallets": {},
        "lines": {},
        "wagers": {},
        "transactions": [],
        "audit": [],
        "ledger_posts": [],
        "counters": {"line": 0, "wager": 0, "transaction": 0, "audit": 0},
    }


def economy_path() -> Path:
    return Path(config.FORGELENS_ECONOMY_PATH or ECONOMY_FILE)


def _load_store() -> dict:
    path = economy_path()
    if not path.exists():
        return _empty_store()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("guilds", {})
    return data


def _save_store(data: dict) -> None:
    path = economy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent if str(path.parent) != "." else None,
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
        ) as tmp:
            json.dump(data, tmp, indent=2, sort_keys=True)
            tmp.flush()
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def _guild(data: dict, guild_id: int | str) -> dict:
    key = str(guild_id)
    if key not in data["guilds"]:
        data["guilds"][key] = _empty_guild(key)
    guild = data["guilds"][key]
    guild.setdefault("wallets", {})
    guild.setdefault("lines", {})
    guild.setdefault("wagers", {})
    guild.setdefault("transactions", [])
    guild.setdefault("audit", [])
    guild.setdefault("ledger_posts", [])
    guild.setdefault("counters", {"line": 0, "wager": 0, "transaction": 0, "audit": 0})
    return guild


def _next_id(guild: dict, kind: str, prefix: str) -> str:
    guild["counters"][kind] = int(guild["counters"].get(kind, 0)) + 1
    return f"{prefix}-{guild['counters'][kind]:04d}"


def _starting_balance(guild_id: int | str) -> int:
    cfg = guild_config_service.get_guild_config(guild_id)
    return int(cfg.get("starting_balance") or 500)


def _append_audit(guild: dict, action: str, actor_id: int | str, target: str, metadata: dict | None = None) -> None:
    audit_id = _next_id(guild, "audit", "AUDIT")
    guild["audit"].append({
        "audit_id": audit_id,
        "guild_id": guild["guild_id"],
        "action": action,
        "actor_id": str(actor_id),
        "target": target,
        "metadata": metadata or {},
        "created_at": _now(),
    })


def _append_transaction(
    guild: dict,
    user_id: int | str,
    display_name: str,
    kind: str,
    amount: int,
    balance_after: int,
    reference_type: str,
    reference_id: str,
    reason: str,
    created_by: int | str,
) -> dict:
    if kind not in TRANSACTION_KINDS:
        raise EconomyError(f"Unknown transaction kind: {kind}")
    tx = {
        "transaction_id": _next_id(guild, "transaction", "TX"),
        "guild_id": guild["guild_id"],
        "user_id": str(user_id),
        "display_name": display_name,
        "kind": kind,
        "amount": int(amount),
        "balance_after": int(balance_after),
        "reference_type": reference_type,
        "reference_id": reference_id,
        "reason": reason,
        "created_by": str(created_by),
        "created_at": _now(),
    }
    guild["transactions"].append(tx)
    return tx


def get_wallet(guild_id: int | str, user_id: int | str) -> dict | None:
    data = _load_store()
    guild = _guild(data, guild_id)
    return guild["wallets"].get(str(user_id))


def ensure_wallet(
    guild_id: int | str,
    user_id: int | str,
    display_name: str,
    created_by: int | str | None = None,
) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    uid = str(user_id)
    wallet = guild["wallets"].get(uid)
    if wallet is None:
        balance = _starting_balance(guild_id)
        wallet = {
            "guild_id": str(guild_id),
            "user_id": uid,
            "display_name": display_name,
            "balance": balance,
            "created_at": _now(),
            "updated_at": _now(),
        }
        guild["wallets"][uid] = wallet
        _append_transaction(
            guild,
            uid,
            display_name,
            "wallet_seed",
            balance,
            balance,
            "wallet",
            uid,
            "Starting community points balance",
            created_by or uid,
        )
        _append_audit(guild, "wallet.seed", created_by or uid, uid, {"amount": balance})
    else:
        wallet["display_name"] = display_name or wallet.get("display_name", "")
        wallet["updated_at"] = _now()
    _save_store(data)
    return wallet


def adjust_wallet(
    guild_id: int | str,
    user_id: int | str,
    display_name: str,
    amount: int,
    reason: str,
    created_by: int | str,
) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    wallet = ensure_wallet(guild_id, user_id, display_name, created_by)
    data = _load_store()
    guild = _guild(data, guild_id)
    wallet = guild["wallets"][str(user_id)]
    wallet["balance"] = int(wallet["balance"]) + int(amount)
    wallet["display_name"] = display_name or wallet.get("display_name", "")
    wallet["updated_at"] = _now()
    tx = _append_transaction(
        guild,
        user_id,
        wallet["display_name"],
        "wallet_adjust",
        amount,
        wallet["balance"],
        "wallet",
        str(user_id),
        reason,
        created_by,
    )
    _append_audit(guild, "wallet.adjust", created_by, str(user_id), {"amount": amount, "reason": reason})
    _save_store(data)
    return {"wallet": wallet, "transaction": tx}


def list_wallets(guild_id: int | str) -> list[dict]:
    data = _load_store()
    guild = _guild(data, guild_id)
    return sorted(guild["wallets"].values(), key=lambda w: (-int(w.get("balance", 0)), w.get("display_name", "")))


def create_line(
    guild_id: int | str,
    match_id: str,
    title: str,
    option_a: str,
    option_b: str,
    max_wager: int,
    close_condition: str,
    created_by: int | str,
    payout_model: str = "pool",
) -> dict:
    if payout_model != "pool":
        raise EconomyError("Only the pool payout model is supported in this MVP.")
    if max_wager <= 0:
        raise EconomyError("max_wager must be greater than zero.")
    data = _load_store()
    guild = _guild(data, guild_id)
    normalized_match_id = match_id.upper().strip()
    for existing in guild["lines"].values():
        if (
            existing.get("match_id") == normalized_match_id
            and existing.get("status") not in {"settled", "voided", "archived"}
        ):
            raise EconomyError(f"An active wager line already exists for match {normalized_match_id}.")
    line_id = _next_id(guild, "line", "WL")
    line = {
        "line_id": line_id,
        "guild_id": str(guild_id),
        "match_id": normalized_match_id,
        "title": title.strip() or normalized_match_id,
        "options": [option_a.strip(), option_b.strip()],
        "payout_model": payout_model,
        "max_wager": int(max_wager),
        "close_condition": close_condition.strip() or "manual close",
        "status": "created",
        "winning_option": "",
        "created_by": str(created_by),
        "created_at": _now(),
        "updated_at": _now(),
    }
    if not all(line["options"]):
        raise EconomyError("Both line options are required.")
    if line["options"][0].lower() == line["options"][1].lower():
        raise EconomyError("Line options must be different.")
    guild["lines"][line_id] = line
    _append_audit(guild, "line.create", created_by, line_id, {"match_id": line["match_id"]})
    _save_store(data)
    return line


def get_line(guild_id: int | str, line_id: str) -> dict | None:
    data = _load_store()
    guild = _guild(data, guild_id)
    return guild["lines"].get(line_id.upper().strip())


def list_lines(guild_id: int | str, include_archived: bool = False) -> list[dict]:
    data = _load_store()
    guild = _guild(data, guild_id)
    lines = list(guild["lines"].values())
    if not include_archived:
        lines = [line for line in lines if line.get("status") != "archived"]
    return sorted(lines, key=lambda line: line.get("created_at", 0), reverse=True)


def set_line_status(guild_id: int | str, line_id: str, status: str, actor_id: int | str) -> dict:
    if status not in LINE_STATUSES:
        raise EconomyError(f"Unknown line status: {status}")
    data = _load_store()
    guild = _guild(data, guild_id)
    line = guild["lines"].get(line_id.upper().strip())
    if not line:
        raise EconomyError(f"Line {line_id} not found.")
    if line["status"] in {"settled", "voided"} and status not in {"archived"}:
        raise EconomyError(f"Line {line_id} is already {line['status']}.")
    line["status"] = status
    line["updated_at"] = _now()
    _append_audit(guild, f"line.{status}", actor_id, line["line_id"], {"match_id": line["match_id"]})
    _save_store(data)
    return line


def open_line(guild_id: int | str, line_id: str, actor_id: int | str) -> dict:
    return set_line_status(guild_id, line_id, "open", actor_id)


def close_line(guild_id: int | str, line_id: str, actor_id: int | str) -> dict:
    return set_line_status(guild_id, line_id, "closed", actor_id)


def lock_line(guild_id: int | str, line_id: str, actor_id: int | str) -> dict:
    return set_line_status(guild_id, line_id, "locked", actor_id)


def _normalize_option(line: dict, option: str) -> str:
    wanted = option.strip().lower()
    for item in line["options"]:
        if item.lower() == wanted:
            return item
    raise EconomyError(f"Option must be one of: {', '.join(line['options'])}.")


def place_wager(
    guild_id: int | str,
    line_id: str,
    user_id: int | str,
    display_name: str,
    option: str,
    amount: int,
) -> dict:
    if amount <= 0:
        raise EconomyError("Wager amount must be greater than zero.")
    data = _load_store()
    guild = _guild(data, guild_id)
    line = guild["lines"].get(line_id.upper().strip())
    if not line:
        raise EconomyError(f"Line {line_id} not found.")
    if line["status"] != "open":
        raise EconomyError(f"Line {line['line_id']} is not open.")
    if amount > int(line["max_wager"]):
        raise EconomyError(f"Maximum wager for this line is {line['max_wager']} points.")
    selected = _normalize_option(line, option)

    wallet = ensure_wallet(guild_id, user_id, display_name, user_id)
    data = _load_store()
    guild = _guild(data, guild_id)
    wallet = guild["wallets"][str(user_id)]
    if int(wallet["balance"]) < amount:
        raise EconomyError(f"Insufficient balance: {wallet['balance']} points available.")

    for wager in guild["wagers"].values():
        if (
            wager["line_id"] == line["line_id"]
            and wager["user_id"] == str(user_id)
            and wager["status"] == "placed"
        ):
            raise EconomyError("You already have a wager on this line.")

    wallet["balance"] = int(wallet["balance"]) - amount
    wallet["display_name"] = display_name or wallet.get("display_name", "")
    wallet["updated_at"] = _now()
    wager_id = _next_id(guild, "wager", "WG")
    wager = {
        "wager_id": wager_id,
        "guild_id": str(guild_id),
        "line_id": line["line_id"],
        "match_id": line["match_id"],
        "user_id": str(user_id),
        "display_name": wallet["display_name"],
        "option": selected,
        "amount": int(amount),
        "status": "placed",
        "payout": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }
    guild["wagers"][wager_id] = wager
    tx = _append_transaction(
        guild,
        user_id,
        wallet["display_name"],
        "wager_debit",
        -amount,
        wallet["balance"],
        "wager",
        wager_id,
        f"Wager on {line['line_id']} option {selected}",
        user_id,
    )
    _append_audit(guild, "wager.place", user_id, wager_id, {"line_id": line["line_id"], "amount": amount})
    _save_store(data)
    return {"line": line, "wager": wager, "wallet": wallet, "transaction": tx}


def list_wagers(guild_id: int | str, user_id: int | str | None = None) -> list[dict]:
    data = _load_store()
    guild = _guild(data, guild_id)
    wagers = list(guild["wagers"].values())
    if user_id is not None:
        wagers = [w for w in wagers if w["user_id"] == str(user_id)]
    return sorted(wagers, key=lambda wager: wager.get("created_at", 0), reverse=True)


def _line_wagers(guild: dict, line_id: str, status: str = "placed") -> list[dict]:
    return [
        wager for wager in guild["wagers"].values()
        if wager["line_id"] == line_id and wager["status"] == status
    ]


def settle_line(
    guild_id: int | str,
    line_id: str,
    winning_option: str,
    actor_id: int | str,
    match_status_provider=None,
) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    line = guild["lines"].get(line_id.upper().strip())
    if not line:
        raise EconomyError(f"Line {line_id} not found.")
    if line["status"] == "settled":
        raise EconomyError(f"Line {line['line_id']} is already settled.")
    if line["status"] == "voided":
        raise EconomyError(f"Line {line['line_id']} is voided.")
    if line["status"] not in {"closed", "locked"}:
        raise EconomyError(f"Line {line['line_id']} must be closed or locked before settlement.")

    match_status = _match_status(guild_id, line["match_id"], match_status_provider)
    if match_status != "official":
        raise EconomyError(
            f"Match {line['match_id']} must be official before settlement (current: {match_status})."
        )

    winner = _normalize_option(line, winning_option)
    wagers = _line_wagers(guild, line["line_id"])
    total_pool = sum(int(w["amount"]) for w in wagers)
    winning_wagers = [w for w in wagers if w["option"].lower() == winner.lower()]
    winning_pool = sum(int(w["amount"]) for w in winning_wagers)
    payout_amounts = _pool_payouts(winning_wagers, total_pool, winning_pool)
    payouts = []

    for wager in wagers:
        wager["updated_at"] = _now()
        if wager in winning_wagers and winning_pool > 0:
            payout = payout_amounts[wager["wager_id"]]
            wallet = guild["wallets"][wager["user_id"]]
            wallet["balance"] = int(wallet["balance"]) + payout
            wallet["updated_at"] = _now()
            wager["payout"] = payout
            payouts.append({"wager_id": wager["wager_id"], "user_id": wager["user_id"], "payout": payout})
            _append_transaction(
                guild,
                wager["user_id"],
                wager["display_name"],
                "wager_payout",
                payout,
                wallet["balance"],
                "wager",
                wager["wager_id"],
                f"Settlement payout for {line['line_id']}",
                actor_id,
            )
        wager["status"] = "settled"

    line["status"] = "settled"
    line["winning_option"] = winner
    line["updated_at"] = _now()
    _append_audit(guild, "line.settle", actor_id, line["line_id"], {"winner": winner, "payouts": payouts})
    _save_store(data)
    return {"line": line, "payouts": payouts, "total_pool": total_pool, "winning_pool": winning_pool}


def _pool_payouts(winning_wagers: list[dict], total_pool: int, winning_pool: int) -> dict[str, int]:
    if not winning_wagers or winning_pool <= 0 or total_pool <= 0:
        return {}

    shares = []
    allocated = 0
    for wager in winning_wagers:
        numerator = int(wager["amount"]) * total_pool
        base = numerator // winning_pool
        remainder = numerator % winning_pool
        allocated += base
        shares.append({
            "wager_id": wager["wager_id"],
            "base": base,
            "remainder": remainder,
        })

    payouts = {share["wager_id"]: share["base"] for share in shares}
    leftover = total_pool - allocated
    for share in sorted(shares, key=lambda item: (-item["remainder"], item["wager_id"]))[:leftover]:
        payouts[share["wager_id"]] += 1
    return payouts


def void_line(guild_id: int | str, line_id: str, actor_id: int | str, reason: str) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    line = guild["lines"].get(line_id.upper().strip())
    if not line:
        raise EconomyError(f"Line {line_id} not found.")
    if line["status"] == "settled":
        raise EconomyError(f"Line {line['line_id']} is already settled.")
    if line["status"] == "voided":
        raise EconomyError(f"Line {line['line_id']} is already voided.")

    refunds = []
    for wager in _line_wagers(guild, line["line_id"]):
        wallet = guild["wallets"][wager["user_id"]]
        amount = int(wager["amount"])
        wallet["balance"] = int(wallet["balance"]) + amount
        wallet["updated_at"] = _now()
        wager["status"] = "voided"
        wager["payout"] = amount
        wager["updated_at"] = _now()
        refunds.append({"wager_id": wager["wager_id"], "user_id": wager["user_id"], "refund": amount})
        _append_transaction(
            guild,
            wager["user_id"],
            wager["display_name"],
            "wager_refund",
            amount,
            wallet["balance"],
            "wager",
            wager["wager_id"],
            reason or f"Void refund for {line['line_id']}",
            actor_id,
        )

    line["status"] = "voided"
    line["updated_at"] = _now()
    _append_audit(guild, "line.void", actor_id, line["line_id"], {"reason": reason, "refunds": refunds})
    _save_store(data)
    return {"line": line, "refunds": refunds}


def record_ledger_post(
    guild_id: int | str,
    channel_id: int | str,
    message_id: int | str,
    actor_id: int | str,
    title: str = "",
    body: str = "",
    line_id: str = "",
) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    post = {
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "message_id": str(message_id),
        "created_by": str(actor_id),
        "title": title,
        "body": body,
        "line_id": line_id.upper().strip(),
        "created_at": _now(),
    }
    guild["ledger_posts"].append(post)
    _append_audit(guild, "ledger.post", actor_id, str(message_id), {"channel_id": str(channel_id)})
    _save_store(data)
    return post


def transactions(guild_id: int | str, user_id: int | str | None = None, limit: int = 20) -> list[dict]:
    data = _load_store()
    guild = _guild(data, guild_id)
    txs = list(reversed(guild["transactions"]))
    if user_id is not None:
        txs = [tx for tx in txs if tx["user_id"] == str(user_id)]
    return txs[:limit]


def audit_events(guild_id: int | str, target: str = "", limit: int = 20) -> list[dict]:
    data = _load_store()
    guild = _guild(data, guild_id)
    events = list(reversed(guild["audit"]))
    if target:
        normalized = target.upper().strip()
        events = [
            event for event in events
            if event.get("target", "").upper() == normalized
            or str(event.get("metadata", {}).get("line_id", "")).upper() == normalized
        ]
    return events[:limit]


def export_data(guild_id: int | str) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    match_export = match_service.export_guild_data(guild_id)
    return {
        "guild_id": str(guild_id),
        "exported_at": _now(),
        "storage_path": str(economy_path()),
        "match_storage_path": match_export["storage_path"],
        "wallets": list(guild["wallets"].values()),
        "wager_lines": list(guild["lines"].values()),
        "wagers": list(guild["wagers"].values()),
        "transactions": guild["transactions"],
        "audit": guild["audit"],
        "ledger_posts": guild["ledger_posts"],
        "matches": match_export["matches"],
        "active_match_contexts": match_export["active_match_contexts"],
        "unlinked_drafts": match_export["unlinked_drafts"],
    }


def health(guild_id: int | str) -> dict:
    data = _load_store()
    guild = _guild(data, guild_id)
    path = economy_path()
    active_lines = [
        line for line in guild["lines"].values()
        if line.get("status") in {"created", "open", "closed", "locked"}
    ]
    placed_wagers = [
        wager for wager in guild["wagers"].values()
        if wager.get("status") == "placed"
    ]
    cfg = guild_config_service.get_guild_config(guild_id)
    return {
        "guild_id": str(guild_id),
        "economy_enabled": bool(cfg.get("betting_enabled")),
        "storage_path": str(path),
        "storage_exists": path.exists(),
        "wallet_count": len(guild["wallets"]),
        "line_count": len(guild["lines"]),
        "active_line_count": len(active_lines),
        "placed_wager_count": len(placed_wagers),
        "transaction_count": len(guild["transactions"]),
        "audit_count": len(guild["audit"]),
        "ledger_post_count": len(guild["ledger_posts"]),
    }


def _match_status(guild_id: int | str, match_id: str, provider=None) -> str:
    if provider:
        return provider(guild_id, match_id)
    local_status = match_service.get_match_status(guild_id, match_id)
    if local_status:
        return local_status
    sheet_id = sheets_service.get_active_sheet_id(guild_id)
    if not sheet_id:
        return "missing_active_season"
    status = sheets_service.get_match_status(sheet_id, match_id, guild_id)
    return status.get("match_status") or "created"
