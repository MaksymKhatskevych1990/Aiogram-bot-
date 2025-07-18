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
            [KeyboardButton(text=get_message("back", lang))]
        ],
        resize_keyboard=True
    )

def get_back_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_message("back", lang))]
        ],
        resize_keyboard=True
    )

def get_network_keyboard_with_back(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ERC20"), KeyboardButton(text="TRC20"), KeyboardButton(text="BEP20")],
            [KeyboardButton(text=get_message("back", lang))]
        ],
        resize_keyboard=True
    )

def get_currency_keyboard_with_back(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="USD"), KeyboardButton(text="UAH")],
            [KeyboardButton(text=get_message("back", lang))]
        ],
        resize_keyboard=True
    )

def get_start_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_message("start", lang))]
        ],
        resize_keyboard=True
    )

CITY_BRANCHES = {
    "Днепр": ["Гагарина, 12", "Центральная, 1"],
    "Львов": ["Зеленая, 5", "Шевченко, 10"]
}

def get_city_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=city)] for city in CITY_BRANCHES.keys()
    ] + [[KeyboardButton(text=get_message("back", lang))]], resize_keyboard=True)

def get_branch_keyboard(city, lang="ru"):
    branches = CITY_BRANCHES.get(city, [])
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=branch)] for branch in branches
    ] + [[KeyboardButton(text=get_message("back", lang))]], resize_keyboard=True)

def get_time_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Сегодня, до 17:00")],
        [KeyboardButton(text="Завтра, утро")],
        [KeyboardButton(text="Завтра, день")],
        [KeyboardButton(text="Завтра, вечер")],
        [KeyboardButton(text=get_message("back", lang))]
    ], resize_keyboard=True)
