# -*- coding: utf-8 -*-
# pip install requests solders
import os, sys, json, requests
from typing import Optional
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.commitment_config import CommitmentLevel

PUMPPORTAL_TRADE_LOCAL = "https://pumpportal.fun/api/trade-local"

HELIUS_HTTP: Optional[str] = os.getenv("HELIUS") or None     # можно заранее экспортнуть переменную окружения HELIUS
DEFAULT_SLIPPAGE = 10.0df 
DEFAULT_PRIORITY_FEE = 0.00005
DEFAULT_POOL = "pump"   # варианты: pump | pump-amm | raydium | auto

def info(msg: str): print(f"[i] {msg}")
def ok(msg: str):   print(f"[✓] {msg}")
def err(msg: str):  print(f"[x] {msg}", file=sys.stderr)

def clean_amount(s: str) -> float:
    s = s.strip().replace(",", ".")
    s = s.strip("()[]")
    return float(s)

def keypair_from_base58(secret_b58: str) -> Keypair:
    return Keypair.from_base58_string(secret_b58.strip())

def build_buy_tx(mint: str,
                 buyer_pubkey: str,
                 sol_amount: float,
                 slippage_percent: float = DEFAULT_SLIPPAGE,
                 priority_fee_sol: float = DEFAULT_PRIORITY_FEE,
                 pool: str = DEFAULT_POOL) -> bytes:
    payload = {
        "publicKey": buyer_pubkey,
        "action": "buy",
        "mint": mint,
        "amount": sol_amount,          # тратим X SOL
        "denominatedInSol": "true",    # сумма в SOL
        "slippage": slippage_percent,  # % слиппеджа
        "priorityFee": priority_fee_sol,  # приорити-комиссия, SOL
        "pool": pool
    }
    r = requests.post(PUMPPORTAL_TRADE_LOCAL,
                      headers={"Content-Type": "application/json"},
                      data=json.dumps(payload),
                      timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"PumpPortal error {r.status_code}: {r.text}")
    return r.content  # сериализованный VersionedTransaction (bytes)

def send_vt_via_helius(vt_bytes: bytes, kp: Keypair, helius_http: str) -> str:
    vt = VersionedTransaction.from_bytes(vt_bytes)
    signed_tx = VersionedTransaction(vt.message, [kp])
    cfg = RpcSendTransactionConfig(preflight_commitment=CommitmentLevel.Confirmed)
    body = SendVersionedTransaction(signed_tx, cfg).to_json()
    r = requests.post(helius_http,
                      headers={"Content-Type": "application/json"},
                      data=body,
                      timeout=10)
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"Helius send error: {data['error']}")
    sig = data.get("result")
    if not sig:
        raise RuntimeError(f"Unexpected Helius response: {data}")
    return sig

def handle_buy(parts):
    """
    /buy <mint> <sol> <base58_privkey> [slip=%] [prio=SOL] [pool=pump]
    """
    global HELIUS_HTTP
    if HELIUS_HTTP is None:
        err("Сначала укажи Helius RPC через команду /helius <url>")
        return

    if len(parts) < 4:
        print("usage: /buy <mint> <sol> <privkey> [slip=10] [prio=0.00005] [pool=pump]")
        return

    mint = parts[1].strip()
    sol = clean_amount(parts[2])
    priv = parts[3].strip()

    # необязательные параметры
    slip = DEFAULT_SLIPPAGE
    prio = DEFAULT_PRIORITY_FEE
    pool = DEFAULT_POOL
    for p in parts[4:]:
        p = p.strip()
        if p.startswith("slip="):
            slip = float(p.split("=", 1)[1])
        elif p.startswith("prio="):
            prio = float(p.split("=", 1)[1])
        elif p.startswith("pool="):
            pool = p.split("=", 1)[1]

    try:
        kp = keypair_from_base58(priv)
        buyer_pubkey = str(kp.pubkey())
        info(f"Покупка {mint} на {sol} SOL | slippage={slip}% | prio={prio} SOL | pool={pool}")
        info(f"Покупатель: {buyer_pubkey}")

        tx_bytes = build_buy_tx(
            mint=mint,
            buyer_pubkey=buyer_pubkey,
            sol_amount=sol,
            slippage_percent=slip,
            priority_fee_sol=prio,
            pool=pool
        )
        sig = send_vt_via_helius(tx_bytes, kp, HELIUS_HTTP)
        ok(f"TX sent: {sig}")
        print(f"https://solscan.io/tx/{sig}")
    except Exception as e:
        err(str(e))

def handle_helius(parts):
    """
    /helius <http_url>
    """
    global HELIUS_HTTP
    if len(parts) != 2:
        print("usage: /helius https://mainnet.helius-rpc.com/?api-key=XXXX")
        return
    HELIUS_HTTP = parts[1].strip().strip('"').strip("'")
    ok(f"HELIUS set: {HELIUS_HTTP}")

def handle_help():
    print("Команды:")
    print("  /helius <url>                                   — установить Helius RPC (HTTP)")
    print("  /buy <mint> <sol> <privkey> [slip=10] [prio=0.00005] [pool=pump]")
    print("  /exit                                           — выход")
    print("\nПример:")
    print("  /helius https://mainnet.helius-rpc.com/?api-key=XXXX")
    print("  /buy 8dvBfsWym8vdpBspPHrMu88VkgzintaYpGnDkNhBpump 0.005 58mqJo...k8Yo")

def main():
    global HELIUS_HTTP
    print("Pump.fun CLI готов. Напиши /help для справки.")
    if HELIUS_HTTP:
        info(f"HELIUS из ENV: {HELIUS_HTTP}")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd == "/help":
            handle_help()
        elif cmd == "/helius":
            handle_helius(parts)
        elif cmd == "/buy":
            handle_buy(parts)
        elif cmd == "/exit":
            print("Bye.")
            break
        else:
            print("Неизвестная команда. /help")

if __name__ == "__main__":
    main()
