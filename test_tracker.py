import sys
import json
from typing import Optional

import requests
import re


def fetch_coin_info(mint: str, timeout_seconds: float = 10.0) -> Optional[dict]:
    url = f"https://frontend-api-v3.pump.fun/coins/{mint}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Python/requests script",
        "Accept-Language": "ru,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        print(f"Ошибка запроса: {exc}")
    except json.JSONDecodeError:
        print("Ошибка парсинга JSON-ответа")
    return None


def main() -> None:
    default_mint = "buZheLAT1QdL7C1nfiLUbLhVzvKbg4Ro9VW4BbBpump"
    mint = sys.argv[1] if len(sys.argv) > 1 else default_mint

    data = fetch_coin_info(mint)
    if data is None:
        sys.exit(1)

    print(json.dumps(data, ensure_ascii=False, indent=2))

    def find_community_ids(obj) -> set[str]:
        found: set[str] = set()

        def search_in_string(value: str) -> None:
            # 1) Явный шаблон /communities/<id> или /community/<id>
            for pattern in (
                r"/communities/([A-Za-z0-9_-]+)",
                r"/community/([A-Za-z0-9_-]+)",
            ):
                for m in re.finditer(pattern, value):
                    found.add(m.group(1))

        def walk(node) -> None:
            if isinstance(node, dict):
                for _, v in node.items():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            elif isinstance(node, str):
                search_in_string(node)

        walk(obj)
        return found

    community_ids = find_community_ids(data)
    if community_ids:
        print("\nНайденные community_id:")
        for cid in sorted(community_ids):
            print(cid)
    else:
        print("\ncommunity_id не найдено в полях ответа")


if __name__ == "__main__":
    main()


