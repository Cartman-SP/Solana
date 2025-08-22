import requests
import base58
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair

signerKeypairs = [
    Keypair.from_base58_string("49ha1nF74ihQVXtM3JSVgDSuyrxCDQXrTscFZS7E1ZDNBppnaQZmrRgH5Jc6TzY8ividDGMuwy6Qrzx5MQfooft3"),
]

response = requests.post(
    "https://pumpportal.fun/api/trade-local",
    headers={"Content-Type": "application/json"},
    json=[
        {
            "publicKey": str(signerKeypairs[0].pubkey()),
            "action": "buy",  # "buy", "sell", or "create"
            "mint": "7cMM3yohhgB9f5W6cMm9QxKdwZQDJyJWnNAhosZ7pump", 
            "denominatedInSol": "true",
            "amount": 0.01,
            "slippage": 50,
            "priorityFee": 0.0005, # priority fee on the first tx is used for jito tip
            "pool": "pump"
        },
    ]
)

if response.status_code != 200: 
    print("Failed to generate transactions.")
    print(response.reason)
else:
    encodedTransactions = response.json()
    encodedSignedTransactions = []
    txSignatures = []

    for index, encodedTransaction in enumerate(encodedTransactions):
        signedTx = VersionedTransaction(VersionedTransaction.from_bytes(base58.b58decode(encodedTransaction)).message, [signerKeypairs[index]])
        encodedSignedTransactions.append(base58.b58encode(bytes(signedTx)).decode())
        txSignatures.append(str(signedTx.signatures[0]))

    jito_response = requests.post(
        "https://wispy-little-river.solana-mainnet.quiknode.pro/134b4b837e97bb3711c20296010e32eff69ad1af/",
        headers={"Content-Type": "application/json"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendBundle",
            "params": [
                encodedSignedTransactions
            ]
        }
    )

    for i, signature in enumerate(txSignatures):
        print(f'Transaction {i}: https://solscan.io/tx/{signature}')
