from typing import Dict, Any


def decode_erc20_input(input_data: str) -> Dict[str, Any]:
    """
    Расшифровывает input поля для transfer(address, uint256)
    """
    method_id = input_data[:10]  # 0xa9059cbb
    if method_id != "0xa9059cbb":
        return {}
    
    to_address = "0x" + input_data[34:74]  # 32 байта после 0x + 4 байта метода
    raw_amount = input_data[74:]  # оставшиеся 32 байта
    amount = int(raw_amount, 16)

    return {"to": to_address, "amount": amount}