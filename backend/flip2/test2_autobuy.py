# pip install requests solders
import base64, random, requests
from typing import Optional

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.system_program import transfer, TransferParams
from solders.message import MessageV0
from solders.transaction import VersionedTransaction

class QuickNodeBuyerError(Exception): pass

def buy_pumpfun_via_quicknode(
    *,
    qn_http_url: str,
    payer_secret_b58: str,
    mint: str,
    sol_in_lamports: int,
    slippage_bps: int = 100,
    priority_fee_level: str = "high",
    commitment: str = "confirmed",
    jito_region: str = "frankfurt",
    tip_lamports: Optional[int] = None,
    tip_account: Optional[str] = None,
    return_bundle_status: bool = False,
    timeout: float = 3.5,
) -> dict:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})

    base = qn_http_url.rstrip("/")
    def _rpc(method: str, params=None):
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        r = s.post(base, json=body, timeout=timeout)
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise QuickNodeBuyerError(f"RPC {method} error: {j['error']}")
        return j["result"]

    def _pumpfun_swap_tx(wallet: str) -> tuple[str, Hash]:
        url =  "https://jupiter-swap-api.quiknode.pro/pump-fun/swap"
        payload = {
            "wallet": wallet,
            "type": "BUY",
            "mint": mint,
            "inAmount": str(sol_in_lamports),      # int, не строка
            "priorityFeeLevel": priority_fee_level,
            "slippageBps": str(slippage_bps),      # int, не строка
            "commitment": commitment,
        }
        r = s.post(url, json=payload, timeout=timeout)
        print(r.text)
        r.raise_for_status()
        j = r.json()
        tx_b64 = j.get("tx")
        if not tx_b64:
            raise QuickNodeBuyerError(f"/pump-fun/swap bad response: {j}")
        # Вытащим blockhash из swap-транзы, чтобы использовать его же в tip
        vt = VersionedTransaction.from_bytes(base64.b64decode(tx_b64))
        return tx_b64, vt.message.recent_blockhash

    def _get_tip_account() -> str:
        if tip_account:
            return tip_account
        accs = _rpc("getTipAccounts", [jito_region]) if jito_region else _rpc("getTipAccounts")
        return random.choice(accs)

    def _get_tip_amount_lamports() -> int:
        if tip_lamports is not None:
            return tip_lamports
        floor = _rpc("getTipFloor", [jito_region]) if jito_region else _rpc("getTipFloor")
        # floor[0]["landed_tips_50th_percentile"] в SOL
        median_sol = float(floor[0]["landed_tips_50th_percentile"])
        boosted = max(median_sol * 1.25, 0.0002)  # минимум 0.0002 SOL
        return int(boosted * 1_000_000_000)

    def _sign_base64_tx(unsigned_b64: str, payer: Keypair) -> str:
        vt = VersionedTransaction.from_bytes(base64.b64decode(unsigned_b64))
        signed = VersionedTransaction(vt.message, [payer])  # корректная подпись плательщиком
        return base64.b64encode(bytes(signed)).decode()

    def _build_tip_tx(payer: Keypair, tip_to: Pubkey, lamports: int, bh: Hash) -> str:
        ix = transfer(TransferParams(from_pubkey=payer.pubkey(), to_pubkey=tip_to, lamports=lamports))
        msg = MessageV0.try_compile(
            payer=payer.pubkey(),
            instructions=[ix],
            address_lookup_table_accounts=[],
            recent_blockhash=bh,  # тот же bh, что и у swap
        )
        tip_tx = VersionedTransaction(msg, [payer])
        return base64.b64encode(bytes(tip_tx)).decode()

    # 0) ключи
    payer = Keypair.from_base58_string(payer_secret_b58)
    wallet_addr = str(payer.pubkey())

    # 1) строим swap + берём его blockhash
    unsigned_swap_b64, swap_bh = _pumpfun_swap_tx(wallet_addr)

    # 2) подписываем swap
    signed_swap_b64 = _sign_base64_tx(unsigned_swap_b64, payer)
# 3) готовим tip (на тот же blockhash)
    tip_to = Pubkey.from_string(_get_tip_account())
    tip_amt = _get_tip_amount_lamports()
    tip_b64 = _build_tip_tx(payer, tip_to, tip_amt, swap_bh)

    # 4) отправляем бандл (swap, затем tip)
    params = [[signed_swap_b64, tip_b64]]
    if jito_region:
        params.append(jito_region)  # строковый регион, как у тебя
    bundle_id = _rpc("sendBundle", params)

    out = {
        "bundle_id": bundle_id,
        "wallet": wallet_addr,
        "mint": mint,
        "spent_sol": sol_in_lamports / 1_000_000_000,
        "priority_fee_level": priority_fee_level,
        "tip_lamports": tip_amt,
        "tip_account": str(tip_to),
        "region": jito_region,
    }
    if return_bundle_status:
        out["bundle_status"] = _rpc("getInflightBundleStatuses", [[bundle_id]])
    return out


result = buy_pumpfun_via_quicknode(
    qn_http_url="https://wispy-little-river.solana-mainnet.quiknode.pro/134b4b837e97bb3711c20296010e32eff69ad1af/",  # без / на конце
    payer_secret_b58="58mqJoN4nu67vqT45pP6uspZ7RRsjxXkyQjx61X52XUyH7wL6kiJei97DLps2c7peigZv9SvF4rHbzK3wEPuk8Yo",
    mint="YKEL74Vu4yMLruhdU9y4cpRTDAn8wV1Y9VZsRKZpump",  
    sol_in_lamports=5_000_000,   
    slippage_bps=100,              
    priority_fee_level="high",     
    jito_region="frankfurt",       
    tip_lamports=1_000_000,        
    return_bundle_status=False,    
    timeout=3.5,
)
print(result)