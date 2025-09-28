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

# =============================================================================
# ВАЛИДАЦИЯ КОШЕЛЬКОВ
# =============================================================================

def is_valid_wallet_address_erc20(address: str) -> bool:
    """
    Проверяет валидность адреса ERC20 кошелька
    """
    if not address:
        return False
    
    # ERC20 адреса начинаются с 0x и содержат 40 символов (42 всего)
    pattern = r'^0x[a-fA-F0-9]{40}$'
    return bool(re.match(pattern, address))

def is_valid_wallet_address_trc20(address: str) -> bool:
    """
    Проверяет валидность адреса TRC20 кошелька
    """
    if not address:
        return False
    
    # TRC20 адреса начинаются с T и содержат 33 символа
    pattern = r'^T[a-zA-Z0-9]{33}$'
    return bool(re.match(pattern, address))

def is_valid_wallet_address(address: str, network: str) -> bool:
    """
    Проверяет валидность адреса кошелька для указанной сети
    """
    if not address or not network:
        return False
    
    network = network.lower()
    if network == 'erc20':
        return is_valid_wallet_address_erc20(address)
    elif network == 'trc20':
        return is_valid_wallet_address_trc20(address)
    else:
        return False

def is_bot_wallet_address(address: str) -> bool:
    """
    Проверяет, не является ли адрес адресом бота
    """
    # Здесь нужно будет добавить проверку против адресов бота
    # Пока возвращаем False, так как адреса бота будут проверяться в другом месте
    return False