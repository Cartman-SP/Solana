# pip install requests solders
import base64, random, time, requests
from typing import Optional, Tuple

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.system_program import transfer, TransferParams
from solders.message import MessageV0, to_bytes_versioned
from solders.transaction import VersionedTransaction

class QuickNodeBuyerError(Exception): pass

def buy_pumpfun_via_quicknode(
    *,
    # ТВОИ ДАННЫЕ
    qn_http_url: str,              # твой HTTPS QuickNode endpoint, например "https://xxx.quiknode.pro/abcdef/"
    payer_secret_b58: str,         # приватный ключ кошелька в base58
    mint: str,                     # mint адрес токена pump.fun (....pump)
    sol_in_lamports: int,          # сколько SOL потратить (в лампортах, 1 SOL = 1_000_000_000)
    # НАСТРОЙКИ СБОРКИ SWAP
    slippage_bps: int = 100,       # 100 = 1%
    priority_fee_level: str = "high",  # low | medium | high | extreme
    commitment: str = "confirmed",
    # JITO / BUNDLE
    jito_region: str = "frankfurt",# region для Lil’ JIT (см. getRegions)
    tip_lamports: Optional[int] = None, # размер чаевых валидатору (если None — возьмём ~медиану через getTipFloor)
    tip_account: Optional[str] = None,  # фикс. tip-аккаунт (если None — получим любой через getTipAccounts)
    # ДОП
    return_bundle_status: bool = False, # если True — сразу проверим статус bundle (доп. вызов)
    timeout: float = 3.5,               # таймауты HTTP
) -> dict:
    """
    Быстрая покупка токена на pump.fun через QuickNode:
      1) POST /pump-fun/swap -> base64 tx (unsigned)
      2) подпись этой транзы локально
      3) сборка отдельной tip-транзы на Jito аккаунт
      4) sendBundle([swap, tip]) через Lil' JIT

    Возвращает: dict с bundle_id, использованным tip и пр.
    """
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.timeout = timeout

    def _rpc(method: str, params=None):
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        r = s.post(qn_http_url, json=body)
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise QuickNodeBuyerError(f"RPC {method} error: {j['error']}")
        return j["result"]

    def _pumpfun_swap_tx(wallet: str) -> str:
        url = "https://crimson-indulgent-sanctuary.solana-mainnet.quiknode.pro.jupiterapi.com/c52cff6028619a1d3ce102170734805304c499fc/pump-fun/swap"
        "https://public.jupiterapi.com"
        
        print(url)
        payload = {
            "wallet": wallet,
            "type": "BUY",
            "mint": mint,
            "inAmount": str(sol_in_lamports),
            "priorityFeeLevel": priority_fee_level,
            "slippageBps": str(slippage_bps),
            "commitment": commitment,
        }
        r = s.post(url, json=payload)
        print(r.text)
        r.raise_for_status()
        j = r.json()
        if "tx" not in j:
            raise QuickNodeBuyerError(f"/pump-fun/swap bad response: {j}")
        return j["tx"]  # base64 unsigned

    def _get_tip_account() -> str:
        if tip_account:
            return tip_account
        # Быстрее — захардкодить один из Jito tip accounts у себя.
        # Здесь берём любой через RPC (1 вызов).
        accs = _rpc("getTipAccounts", [jito_region]) if jito_region else _rpc("getTipAccounts")
        return random.choice(accs)

    def _get_tip_amount_lamports() -> int:
        if tip_lamports is not None:
            return tip_lamports
        # Берём медиану из getTipFloor и конвертим SOL -> лампорты
        floor = _rpc("getTipFloor")
        # floor = [{..., "landed_tips_50th_percentile": 0.0005, ...}]
        median_sol = float(floor[0]["landed_tips_50th_percentile"])
        # немного бустим, чтобы выигрывать аукцион
        boosted = max(median_sol * 1.25, 0.0002)  # min 0.0002 SOL
        return int(boosted * 1_000_000_000)

    def _latest_blockhash() -> Hash:
        result = _rpc("getLatestBlockhash", [{"commitment": commitment}])
        return Hash.from_string(result["value"]["blockhash"])
    def _sign_base64_tx(unsigned_b64: str, payer: Keypair) -> str:
        tx_bytes = base64.b64decode(unsigned_b64)
        vt = VersionedTransaction.from_bytes(tx_bytes)
        msg = vt.message
        # найдём индекс нашей подписи и подставим её
        keys = list(msg.account_keys)
        try:
            i = keys.index(payer.pubkey())
        except ValueError:
            # иногда провайдер кладёт dummy-сигу на payer месте — всё равно можно поставить свою
            i = None
        sigs = list(vt.signatures)
        sig = payer.sign_message(to_bytes_versioned(msg))
        if i is not None:
            sigs[i] = sig
        else:
            # если место не найдено (редко), просто вставим/заменим первую
            if sigs:
                sigs[0] = sig
            else:
                sigs = [sig]
        vt.signatures = sigs
        return base64.b64encode(bytes(vt)).decode()

    def _build_tip_tx(payer: Keypair, tip_to: Pubkey, lamports: int, bh: Hash):
        ix = transfer(TransferParams(from_pubkey=payer.pubkey(), to_pubkey=tip_to, lamports=lamports))
        msg = MessageV0.try_compile(
            payer=payer.pubkey(),
            instructions=[ix],
            address_lookup_table_accounts=[],
            recent_blockhash=bh,
        )
        tip_tx = VersionedTransaction(msg, [payer])
        return base64.b64encode(bytes(tip_tx)).decode()

    # 0) ключи
    payer = Keypair.from_base58_string(payer_secret_b58)
    wallet_addr = str(payer.pubkey())

    # 1) строим swap
    unsigned_swap_b64 = _pumpfun_swap_tx(wallet_addr)

    # 2) подписываем swap
    signed_swap_b64 = _sign_base64_tx(unsigned_swap_b64, payer)

    # 3) готовим tip
    tip_to = Pubkey.from_string(_get_tip_account())
    tip_amt = _get_tip_amount_lamports()
    bh = _latest_blockhash()
    tip_b64 = _build_tip_tx(payer, tip_to, tip_amt, bh)

    # 4) отправляем бандл (порядок: сначала swap, потом tip — атомарно)
    params = [[signed_swap_b64, tip_b64]]
    if jito_region:
        params.append(jito_region)
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
        # NB: необязательно; лишний вызов = +задержка
        status = _rpc("getInflightBundleStatuses", [[bundle_id]])
        out["bundle_status"] = status

    return out


result = buy_pumpfun_via_quicknode(
    qn_http_url="",
    payer_secret_b58="58mqJoN4nu67vqT45pP6uspZ7RRsjxXkyQjx61X52XUyH7wL6kiJei97DLps2c7peigZv9SvF4rHbzK3wEPuk8Yo",
    mint="5XA5z7d9keFfebVbm1AGaUigaojgdGSkZ9Rwmqrcpump",
    sol_in_lamports=50_000_000,  # 0.10 SOL
    slippage_bps=100,
    priority_fee_level="extreme",
    jito_region="frankfurt",
    tip_lamports=1_000_000,   #
    return_bundle_status=False,
)
print(result)