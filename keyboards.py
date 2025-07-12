from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇦 Українська"), KeyboardButton(text="🇷🇺 Русский")],
            [KeyboardButton(text="🇬🇧 English")]
        ],
        resize_keyboard=True
    )


def get_network_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="TRC20 (Tron)", callback_data="TRC20")],
        [InlineKeyboardButton(text="ERC20 (Ethereum)", callback_data="ERC20")]
    ])
    return kb

def get_action_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💵 Обмен наличных"), KeyboardButton(text="💸 Обмен крипты")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )

def get_back_keyboard():
    """Универсальная клавиатура с кнопкой назад"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )

def get_network_keyboard_with_back():
    """Клавиатура выбора сети с кнопкой назад"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ERC20"), KeyboardButton(text="TRC20"), KeyboardButton(text="BEP20")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )

def get_currency_keyboard_with_back():
    """Клавиатура выбора валюты с кнопкой назад"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="USD"), KeyboardButton(text="UAH")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )

CITY_BRANCHES = {
    "Днепр": ["Гагарина, 12", "Центральная, 1"],
    "Львов": ["Зеленая, 5", "Шевченко, 10"]
}

def get_city_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=city)] for city in CITY_BRANCHES.keys()
    ] + [[KeyboardButton(text="🔙 Назад")]], resize_keyboard=True)

def get_branch_keyboard(city):
    branches = CITY_BRANCHES.get(city, [])
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=branch)] for branch in branches
    ] + [[KeyboardButton(text="🔙 Назад")]], resize_keyboard=True)

def get_time_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Сегодня, до 17:00")],
        [KeyboardButton(text="Завтра, утро")],
        [KeyboardButton(text="Завтра, день")],
        [KeyboardButton(text="Завтра, вечер")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True)
