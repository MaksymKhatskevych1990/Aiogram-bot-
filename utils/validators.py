import re

def is_valid_tx_hash_trc20(tx_hash: str) -> bool:
    return bool(re.fullmatch(r'[a-fA-F0-9]{64}', tx_hash))

def is_valid_tx_hash_erc20(tx_hash: str) -> bool:
    return bool(re.fullmatch(r'^0x[a-fA-F0-9]{64}$', tx_hash))

def is_valid_tx_hash(tx_hash: str, network: str) -> bool:
    network = network.lower()
    if network == 'erc20':
        return is_valid_tx_hash_erc20(tx_hash)
    elif network == 'trc20':
        return is_valid_tx_hash_trc20(tx_hash)
    else:
        return False