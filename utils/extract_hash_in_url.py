import re
from typing import Optional

def extract_tx_hash(input_str: str) -> Optional[str]:
    """
    Извлекает хеш транзакции из ссылки или текста.
    Поддерживает:
    - https://etherscan.io/tx/0x...
    - https://tronscan.org/#/transaction/...
    - просто хеш: 0x... или без 0x
    """

    # Ищем хеш с 0x после /tx/ или /transaction/ или #/transaction/
    match = re.search(r'(?:#?/transaction/|/tx/)(0x[a-fA-F0-9]{64}|[a-fA-F0-9]{64})', input_str)
    if match:
        return match.group(1)

    # Если просто ввели хеш с 0x
    if re.fullmatch(r'0x[a-fA-F0-9]{64}', input_str):
        return input_str

    # Если просто ввели хеш без 0x (TRON)
    if re.fullmatch(r'[a-fA-F0-9]{64}', input_str):
        return input_str

    return None