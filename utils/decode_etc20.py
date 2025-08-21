from typing import Dict, Any


def decode_erc20_input(input_data: str) -> Dict[str, Any]:
    if not input_data.startswith("0x"):
        input_data = "0x" + input_data

    method_id = input_data[:10]
    if method_id != "0xa9059cbb":
        return {}
    
    # Убираем '0x' и method_id
    data = input_data[10:]  # тут остаётся 64 + 64 = 128 символов

    if len(data) < 128:
        return {}

    to_address_hex = data[:64]
    raw_amount = data[64:128]

    to_address = "0x" + to_address_hex[-40:]  # берём последние 40 символов (адрес = 20 байт = 40 hex)
    amount = int(raw_amount, 16)

    return {"to": to_address, "amount": amount}
