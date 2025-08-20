# pip install requests base58 solders

import os, base64, base58, requests
from typing import List, Set
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.hash import Hash
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.system_program import ID as SYS_PROGRAM_ID

# ===================== CONFIG =====================
# (вставьте свои значения)
PUMP_PORTAL_URL = "https://pumpportal.fun/api/trade-local"
# Обычный RPC (QuickNode основной RPC, НЕ jito)
RPC_URL = "https://wispy-little-river.solana-mainnet.quiknode.pro/134b4b837e97bb3711c20296010e32eff69ad1af/"  # например, https://solana-mainnet.quiknode.pro/XXXX/
# Jito RPC (QuickNode Jito add-on: endpoint для sendTransaction)
JITO_RPC_URL = "https://wispy-little-river.solana-mainnet.quiknode.pro/134b4b837e97bb3711c20296010e32eff69ad1af/"  # например, https://<region>.jito.quicknode.com/XXXX/

# Ваш приватный ключ base58 (ГОРЯЧИЙ! только для тестов/минимальный баланс)
PAYER_B58 = "ZrY4T6jpBQB4WGonYn9eY5Z3q9UX6A9HDdCTavTEAYxB9BLNRCUQjhoviZgAxyYHE924pU7ZVxtHiQWqGqwbXAm"

MINT = "2xHkesAQteG9yz48SDaVAtKdFU6Bvdo9sXS3uQCbpump"
AMOUNT_TOKENS = 1000       # покупка в токенах (denominatedInSol = false)
SLIPPAGE_BPS = 50
POOL = "pump"
# Compute Budget
MAX_CU = 250_000
MICROLAMPORTS_PER_CU = 25_000  # = 0.025 lamports/CU (подберите под свою цель)

# Program IDs
PUMP_FUN_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
TOKEN_PROGRAM     = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATOKEN_PROGRAM    = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
COMPUTE_BUDGET_ID = Pubkey.from_string("ComputeBudget111111111111111111111111111111")
SYS_PROGRAM       = Pubkey.from_string("11111111111111111111111111111111")

ALLOWED_PROGRAMS = {SYS_PROGRAM, COMPUTE_BUDGET_ID, TOKEN_PROGRAM, ATOKEN_PROGRAM, PUMP_FUN_PROGRAM}

# ===================== HELPERS =====================
def rpc(method: str, params: list):
    r = requests.post(RPC_URL, json={"jsonrpc":"2.0","id":1,"method":method,"params":params}, timeout=5)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]

def resolve_all_keys(msg: MessageV0) -> List[Pubkey]:
    """Вернёт полный список account keys для v0 message (static + ALT)."""
    keys: List[Pubkey] = list(msg.account_keys)
    for lut in msg.address_table_lookups:
        res = rpc("getAddressLookupTable", [str(lut.account_key)])
        addrs = [Pubkey.from_string(x) for x in res["value"]["state"]["addresses"]]
        # writable сначала, потом readonly в порядке индексов:
        keys += [addrs[i] for i in lut.writable_indexes]
        keys += [addrs[i] for i in lut.readonly_indexes]
    return keys

def is_sys_transfer(ix, keys: List[Pubkey], my_pubkey: Pubkey):
    """Распознаём SystemProgram::transfer (data[0] == 2). Возвращаем: (is_outgoing, src, dst, lamports)."""
    prog = keys[ix.program_id_index]
    if prog != SYS_PROGRAM:
        return (False, None, None, None)
    data = bytes(ix.data)
    if not data or data[0] != 2:  # 2 = transfer
        return (False, None, None, None)
    src = keys[ix.accounts[0]]
    dst = keys[ix.accounts[1]]
    lamports = int.from_bytes(data[1:9], "little")
    return (src == my_pubkey, src, dst, lamports)

def sanitize_tx(encoded_tx_b58: str, my_pubkey: Pubkey) -> VersionedTransaction:
    """Выкидывает чужие программы и левые переводы, добавляет наш ComputeBudget."""
    tx = VersionedTransaction.from_bytes(base58.b58decode(encoded_tx_b58))
    msg: MessageV0 = tx.message  # type: ignore
    keys = resolve_all_keys(msg)

    # Сбор аккаунтов из Pump.fun-инструкций (чтобы разрешить переводы только на эти адреса)
    pump_fun_accounts: Set[Pubkey] = set()
    for ix in msg.compiled_instructions:
        if keys[ix.program_id_index] == PUMP_FUN_PROGRAM:
            for idx in ix.accounts:
                pump_fun_accounts.add(keys[idx])

    new_instructions = []

    for ix in msg.compiled_instructions:
        prog = keys[ix.program_id_index]

        # 1) выбрасываем НЕразрешённые программы
        if prog not in ALLOWED_PROGRAMS:
            continue

        # 2) выбрасываем чужие ComputeBudget — поставим свои
        if prog == COMPUTE_BUDGET_ID:
            continue

        # 3) проверяем SystemProgram::transfer только если ИСХОДЯЩИЙ от нас
        is_out, src, dst, lamports = is_sys_transfer(ix, keys, my_pubkey)
        if is_out:
            # Разрешаем перевод только на аккаунты, присутствующие в Pump.fun-инструкциях (bonding curve/fees/creator)
            if dst not in pump_fun_accounts:
                # Левый перевод → выкидываем
                continue

        # всё ок — оставляем инструкцию
        new_instructions.append(ix)

    # 4) добавляем СВОИ ComputeBudget-инструкции в начало
    new_instructions.insert(0, set_compute_unit_price(MICROLAMPORTS_PER_CU))
    new_instructions.insert(0, set_compute_unit_limit(MAX_CU))

    # 5) пересобираем message с тем же блокхэшем, теми же ключами и заголовком
    new_msg = MessageV0.new_with_blockhash(
        msg.header,
        msg.account_keys,
        new_instructions,
        Hash(msg.recent_blockhash),
    )
    return VersionedTransaction(new_msg, [])

def jito_send_transaction(jito_url: str, signed_tx_bytes: bytes) -> str:
    """Отправка через Jito sendTransaction (base64). Возвращает сигнатуру."""
    tx_b64 = base64.b64encode(signed_tx_bytes).decode()
    r = requests.post(
        jito_url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [tx_b64, {"encoding":"base64"}]
        },
        timeout=5
    )
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]

# ===================== MAIN FLOW =====================
if __name__ == "__main__":
    payer = Keypair.from_base58_string(PAYER_B58)
    payer_pk = payer.pubkey()

    # 1) Получаем сырую tx от PumpPortal (buy)
    resp = requests.post(
        PUMP_PORTAL_URL,
        headers={"Content-Type": "application/json"},
        json=[{
            "publicKey": str(payer_pk),
            "action": "buy",
            "mint": MINT,
            "denominatedInSol": "false",
            "amount": AMOUNT_TOKENS,
            "slippage": SLIPPAGE_BPS,
            "priorityFee": 0.0,   # мы используем ComputeUnitPrice как tip, отдельный transfer не добавляем
            "pool": POOL
        }],
        timeout=3
    )
    resp.raise_for_status()
    encoded_list = resp.json()
    if not encoded_list or not isinstance(encoded_list, list):
        raise RuntimeError("PumpPortal: unexpected response")

    encoded_tx_b58 = encoded_list[0]

    # 2) Санитайзим и подписываем локально
    tx_to_sign = sanitize_tx(encoded_tx_b58, payer_pk)
    signed_tx = VersionedTransaction(tx_to_sign.message, [payer])

    # 3) Отправляем через Jito sendTransaction
    sig = jito_send_transaction(JITO_RPC_URL, bytes(signed_tx))
    print("Signature:", sig)
    print("Solscan:", f"https://solscan.io/tx/{sig}")
