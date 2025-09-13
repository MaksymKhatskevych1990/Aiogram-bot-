from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from localization import get_message

def get_language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇦 Українська"), KeyboardButton(text="🇷🇺 Русский")],
            [KeyboardButton(text="🇬🇧 English")]
        ],
        resize_keyboard=True
    )

def get_start_keyboard(lang="ru"):
    """Клавиатура с кнопкой Старт"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_message("start", lang))]
        ],
        resize_keyboard=True
    )

def get_network_keyboard(lang="ru"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="TRC20 (Tron)", callback_data="TRC20")],
        [InlineKeyboardButton(text="ERC20 (Ethereum)", callback_data="ERC20")]
    ])
    return kb

def get_action_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_message("cash_exchange", lang)), KeyboardButton(text=get_message("crypto_exchange", lang))],
            [KeyboardButton(text=get_message("current_rates", lang))],
            [KeyboardButton(text=get_message("back", lang))]
        ],
        resize_keyboard=True
    )

def get_back_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_message("back", lang))],
            [KeyboardButton(text=get_message("back_to_main", lang))]
        ],
        resize_keyboard=True
    )

def get_network_keyboard_with_back(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="TRC20"), KeyboardButton(text="ERC20")],
            [KeyboardButton(text=get_message("back", lang))],
            [KeyboardButton(text=get_message("back_to_main", lang))]
        ],
        resize_keyboard=True
    )

def get_currency_keyboard_with_back(lang="ru"):
    """Клавиатура для выбора валюты с кнопкой назад"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="USD"), KeyboardButton(text="EUR")],
            [KeyboardButton(text=get_message("back", lang))],
            [KeyboardButton(text=get_message("back_to_main", lang))]
        ],
        resize_keyboard=True
    )

def get_city_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Киев"), KeyboardButton(text="Харьков")],
            [KeyboardButton(text="Одесса"), KeyboardButton(text="Днепр")],
            [KeyboardButton(text=get_message("back", lang))],
            [KeyboardButton(text=get_message("back_to_main", lang))]
        ],
        resize_keyboard=True
    )

def get_branch_keyboard(city, lang="ru"):
    if city == "Киев":
        branches = [
            [KeyboardButton(text="Центр"), KeyboardButton(text="Печерск")],
            [KeyboardButton(text="Оболонь"), KeyboardButton(text="Троещина")]
        ]
    elif city == "Харьков":
        branches = [
            [KeyboardButton(text="Центр"), KeyboardButton(text="Салтовка")],
            [KeyboardButton(text="Алексеевка"), KeyboardButton(text="Холодная гора")]
        ]
    elif city == "Одесса":
        branches = [
            [KeyboardButton(text="Центр"), KeyboardButton(text="Малиновский")],
            [KeyboardButton(text="Приморский"), KeyboardButton(text="Суворовский")]
        ]
    elif city == "Днепр":
        branches = [
            [KeyboardButton(text="Центр"), KeyboardButton(text="Покровский")],
            [KeyboardButton(text="Соборный"), KeyboardButton(text="Новокодакский")]
        ]
    else:
        branches = [[KeyboardButton(text="Центр")]]
    
    branches.extend([
        [KeyboardButton(text=get_message("back", lang))],
        [KeyboardButton(text=get_message("back_to_main", lang))]
    ])
    
    return ReplyKeyboardMarkup(keyboard=branches, resize_keyboard=True)

def get_time_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="09:00"), KeyboardButton(text="10:00"), KeyboardButton(text="11:00")],
            [KeyboardButton(text="12:00"), KeyboardButton(text="13:00"), KeyboardButton(text="14:00")],
            [KeyboardButton(text="15:00"), KeyboardButton(text="16:00"), KeyboardButton(text="17:00")],
            [KeyboardButton(text=get_message("back", lang))],
            [KeyboardButton(text=get_message("back_to_main", lang))]
        ],
        resize_keyboard=True
    )


def get_crypto_operation_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_message("crypto_buy_usdt", lang)),
                KeyboardButton(text=get_message("crypto_sell_usdt", lang)),
            ],
            [KeyboardButton(text=get_message("back", lang))],
            [KeyboardButton(text=get_message("back_to_main", lang))],
        ],
        resize_keyboard=True,
    )


def get_cash_operation_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_message("cash_buy_usd", lang)),
                KeyboardButton(text=get_message("cash_sell_usd", lang)),
            ],
            [KeyboardButton(text=get_message("back", lang))],
            [KeyboardButton(text=get_message("back_to_main", lang))],
        ],
        resize_keyboard=True,
    )

def get_pin_generation_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Клавиатура для генерации PIN-кода"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_message("generate_pin", lang))],
            [KeyboardButton(text=get_message("back", lang))],
            [KeyboardButton(text=get_message("back_to_main", lang))],
        ],
        resize_keyboard=True,
    )
