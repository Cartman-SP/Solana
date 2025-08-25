import json, re, os
from typing import List, Dict, Any, Tuple

INPUT = "/mnt/data/process_datas.txt"

SERVICE_PATTERNS = [
    re.compile(r"^JUP", re.I),                        # Jupiter program-owned accounts
    re.compile(r"^jitodontfront", re.I),              # Jito 'don't front' markers seen in data
    re.compile(r"^Axiom", re.I),                      # Axiom router
    re.compile(r"^Bloom", re.I),                      # Bloom router
    re.compile(r"^4pP8eDKACuV7T2rbFPE8CHxGKDYAzSdRsdMsGvz2k4oc$"),  # jitodontfront program id seen
]

COMPUTE_BUDGET_PROGRAM = "ComputeBudget111111111111111111111111111111"

def load_all_txs(path: str) -> List[Dict[str, Any]]:
    txs: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # expecting "<timestamp> - <json>"
            if " - " not in line:
                continue
            json_part = line.split(" - ", 1)[1]
            try:
                data = json.loads(json_part)
            except Exception:
                # try to salvage by finding the first '[' and last ']' to parse an array
                m_start = json_part.find('[')
                m_end = json_part.rfind(']')
                if m_start != -1 and m_end != -1 and m_end > m_start:
                    try:
                        data = json.loads(json_part[m_start:m_end+1])
                    except Exception:
                        continue
                else:
                    continue
            # data is expected to be a list of tx dicts
            if isinstance(data, list):
                for tx in data:
                    if isinstance(tx, dict):
                        txs.append(tx)
            elif isinstance(data, dict):
                # sometimes wrapped as {"items": [...]}
                items = data.get("items") or []
                if isinstance(items, list):
                    txs.extend([x for x in items if isinstance(x, dict)])
    return txs

def classify_native_transfer_account(pubkey: str) -> str:
    if pubkey == COMPUTE_BUDGET_PROGRAM:
        return "priority"
    for pat in SERVICE_PATTERNS:
        if pat.search(pubkey or ""):
            return "service"
    return ""

def sum_fees(txs: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    total_network_fee_lamports = 0
    total_priority_fee_lamports = 0
    total_service_fee_lamports = 0

    for tx in txs:
        # 1) base network fee (includes prioritization in Solana core, but we keep it as-is)
        fee = tx.get("fee", 0) or 0
        try:
            total_network_fee_lamports += int(fee)
        except Exception:
            pass

        # 2) scan nativeTransfers for extra outflows to ComputeBudget (priority) and services
        for nt in tx.get("nativeTransfers", []) or []:
            to_acc = nt.get("toUserAccount") or ""
            amount = nt.get("amount", 0) or 0
            cls = classify_native_transfer_account(to_acc)
            if cls == "priority":
                total_priority_fee_lamports += int(amount)
            elif cls == "service":
                total_service_fee_lamports += int(amount)

    return total_network_fee_lamports, total_priority_fee_lamports, total_service_fee_lamports

txs = load_all_txs(INPUT)
net_lamports, prio_lamports, svc_lamports = sum_fees(txs)

def lamports_to_sol(lamports: int) -> float:
    return lamports / 1_000_000_000

result = {
    "tx_count": len(txs),
    "network_fee": {
        "lamports": net_lamports,
        "SOL": lamports_to_sol(net_lamports)
    },
    "priority_fee": {
        "lamports": prio_lamports,
        "SOL": lamports_to_sol(prio_lamports)
    },
    "service_fee": {
        "lamports": svc_lamports,
        "SOL": lamports_to_sol(svc_lamports)
    },
    "grand_total_SOL": lamports_to_sol(net_lamports + prio_lamports + svc_lamports)
}
