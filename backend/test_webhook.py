import requests
import json

# Тестовые данные вебхука (пример из webhooks.txt)
test_webhook_data = [
    {
        "blockTime": 1754714851,
        "indexWithinBlock": 1611,
        "meta": {
            "err": None,
            "fee": 14667,
            "innerInstructions": [],
            "loadedAddresses": {
                "readonly": [],
                "writable": []
            },
            "logMessages": [
                "Program ComputeBudget111111111111111111111111111111 invoke [1]",
                "Program ComputeBudget111111111111111111111111111111 success",
                "Program ComputeBudget111111111111111111111111111111 invoke [1]",
                "Program ComputeBudget111111111111111111111111111111 success",
                "Program ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL invoke [1]",
                "Program log: Create",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]",
                "Program log: Instruction: GetAccountDataSize",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 1569 of 90850 compute units",
                "Program return: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA pQAAAAAAAAA=",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
                "Program 11111111111111111111111111111111 invoke [2]",
                "Program 11111111111111111111111111111111 success",
                "Program log: Initialize the associated token account",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]",
                "Program log: Instruction: InitializeImmutableOwner",
                "Program log: Please upgrade to SPL Token 2022 for immutable owner support",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 1405 of 84263 compute units",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]",
                "Program log: Instruction: InitializeAccount3",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 4188 of 80381 compute units",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
                "Program ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL consumed 20488 of 96364 compute units",
                "Program ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL success",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [1]",
                "Program log: Instruction: Buy",
                "Program 11111111111111111111111111111111 invoke [2]",
                "Program 11111111111111111111111111111111 success",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]",
                "Program log: Instruction: Transfer",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 4645 of 43822 compute units",
                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
                "Program 11111111111111111111111111111111 invoke [2]",
                "Program 11111111111111111111111111111111 success",
                "Program 11111111111111111111111111111111 invoke [2]",
                "Program 11111111111111111111111111111111 success",
                "Program 11111111111111111111111111111111 invoke [2]",
                "Program 11111111111111111111111111111111 success",
                "Program data: vdt/007mYe4BO8iEB2ucxHaEOaBSip7TsJfpI7Rt+sQQfSbRN0Pxz4AF20QAAAAAPcXg5tsTAAABvDrHwIGil+aqYFYtPSiSYmoBEthZEU4tJ0GGvy1L8Vvj0pZoAAAAACP6a74JAAAAYmMv/5G7AgAjTkjCAgAAAGLLHLMAvQEASsL40N1cvJfjKJwZfLUGKlTz2Va5zm5RFfllZ6pcs+ZfAAAAAAAAAOt0pwAAAAAA25JSuH+E0GPma7TgYQU4JyLNTJ/dbFglSGDS9P440BEFAAAAAAAAAEPQCAAAAAAA",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [2]",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P consumed 2027 of 27337 compute units",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P consumed 55565 of 75876 compute units",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [1]",
                "Program log: Instruction: CloseUserVolumeAccumulator",
                "Program data: kp+9rJJYOPS8OsfAgaKX5qpgVi09KJJiagES2FkRTi0nQYa/LUvxW+PSlmgAAAAA",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [2]",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P consumed 2027 of 11354 compute units",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P consumed 11364 of 20311 compute units",
                "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success",
                "Program 11111111111111111111111111111111 invoke [1]",
                "Program 11111111111111111111111111111111 success",
                "Program 11111111111111111111111111111111 invoke [1]",
                "Program 11111111111111111111111111111111 success"
            ],
            "postBalances": [
                270038796,
                2039280,
                22560647024145,
                11851387971,
                2039280,
                9404691,
                5066880,
                0,
                3091832250,
                3482596463411,
                1461600,
                1,
                4534961825,
                1009200,
                450770805,
                147104475,
                390734595,
                1,
                746719890
            ],
            "postTokenBalances": [
                {
                    "accountIndex": 1,
                    "mint": "5pHFzocHLqwcjqJK6n67jfz45TqnQShNEAgDdrPpump",
                    "owner": "Dfmdhbdcews1dVgJu7ecFAk8W3U63xcmkhuijGpxXNUA",
                    "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    "uiTokenAmount": {
                        "amount": "21835192255805",
                        "decimals": 6,
                        "uiAmount": 21835192,
                        "uiAmountString": "21835192.255805"
                    }
                },
                {
                    "accountIndex": 4,
                    "mint": "5pHFzocHLqwcjqJK6n67jfz45TqnQShNEAgDdrPpump",
                    "owner": "3uap9xXAZ8WazFR3PUJVJcd7moWUZPQYeB4hV7Qd9tn1",
                    "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    "uiTokenAmount": {
                        "amount": "696185679369058",
                        "decimals": 6,
                        "uiAmount": 696185660,
                        "uiAmountString": "696185679.369058"
                    }
                }
            ],
            "preBalances": [
                1439849369,
                0,
                22560636049702,
                10696183491,
                2039280,
                8827088,
                5066880,
                0,
                3090832250,
                3482596463311,
                1461600,
                1,
                4534961825,
                1009200,
                450770805,
                147104475,
                390734595,
                1,
                746719890
            ],
            "preTokenBalances": [
                {
                    "accountIndex": 4,
                    "mint": "5pHFzocHLqwcjqJK6n67jfz45TqnQShNEAgDdrPpump",
                    "owner": "3uap9xXAZ8WazFR3PUJVJcd7moWUZPQYeB4hV7Qd9tn1",
                    "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    "uiTokenAmount": {
                        "amount": "718020871624863",
                        "decimals": 6,
                        "uiAmount": 718020860,
                        "uiAmountString": "718020871.624863"
                    }
                }
            ],
            "rewards": []
        },
        "slot": 358830488,
        "transaction": {
            "message": {
                "accountKeys": [
                    "Dfmdhbdcews1dVgJu7ecFAk8W3U63xcmkhuijGpxXNUA",
                    "5PeCuBQB4qBwk3nQ9LEQzpGEt4sPYN74Zshdjxge6WUd",
                    "62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV",
                    "3uap9xXAZ8WazFR3PUJVJcd7moWUZPQYeB4hV7Qd9tn1",
                    "3xhEpD6AyASeuahJMQQtFgvNodVzj6dkupVjDhPtjCfT",
                    "AFgATZFZEDRYV7GuRRXtwur7E3T7FgJLbwVauaYrQJcA",
                    "Hq2wp8uJ9jCPsYgNHex8RtqdvMPfVGoYwjvF1ATiwn2Y",
                    "6UiCsAHfWR9FfkqACxhZCn7d4MczqRRoqKQ6wU7iWdJc",
                    "astrazznxsGUhWShqgNtAdfrzP2G83DzcWVJDxwV9bF",
                    "9RYJ3qr5eU5xAooqVcbmdeusjcViL5Nkiq7Gske3tiKq",
                    "5pHFzocHLqwcjqJK6n67jfz45TqnQShNEAgDdrPpump",
                    "11111111111111111111111111111111",
                    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    "SysvarRent111111111111111111111111111111111",
                    "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf",
                    "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1",
                    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
                    "ComputeBudget111111111111111111111111111111",
                    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
                ],
                "addressTableLookups": None,
                "header": {
                    "numReadonlySignedAccounts": 0,
                    "numReadonlyUnsignedAccounts": 9,
                    "numRequiredSignatures": 1
                },
                "instructions": [
                    {
                        "accounts": [],
                        "data": "Hz7RU3",
                        "programIdIndex": 17
                    },
                    {
                        "accounts": [],
                        "data": "3gJqkocMWaMm",
                        "programIdIndex": 17
                    },
                    {
                        "accounts": [
                            0,
                            1,
                            0,
                            10,
                            11,
                            12,
                            13
                        ],
                        "data": "",
                        "programIdIndex": 18
                    },
                    {
                        "accounts": [
                            14,
                            2,
                            10,
                            3,
                            4,
                            1,
                            0,
                            11,
                            12,
                            5,
                            15,
                            16,
                            6,
                            7
                        ],
                        "data": "AJTQ2h9DXrBkmacqR2VxbVztKSN9j6vQo",
                        "programIdIndex": 16
                    },
                    {
                        "accounts": [
                            0,
                            7,
                            15,
                            16
                        ],
                        "data": "ihFZiQrP7CM",
                        "programIdIndex": 16
                    },
                    {
                        "accounts": [
                            0,
                            8
                        ],
                        "data": "3Bxs4Bc3VYuGVB19",
                        "programIdIndex": 11
                    },
                    {
                        "accounts": [
                            0,
                            9
                        ],
                        "data": "3Bxs4HanWsHUZCbH",
                        "programIdIndex": 11
                    }
                ],
                "recentBlockhash": "B5giqr4qf31RsdTmWJL3C45mjZjNyR9hG1wKvUjkGCWs"
            },
            "signatures": [
                "3rbbfyAYBJUcoymLmQghhfMvn6eLRmhJXhHYHjMJAfcnuyMvm8GWqNVx5FrahbNWmPpAvPEfuxXuKjfrMYpZ1QHB"
            ]
        },
        "version": "legacy"
    }
]

def test_webhook():
    """Тестирует эндпоинт bonk_webhook"""
    url = "http://localhost:8000/api/bonk/"
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=test_webhook_data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_webhook() 