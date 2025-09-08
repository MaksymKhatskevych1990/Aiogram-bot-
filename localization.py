MESSAGES = {
    "greeting": {
        "ru": "👋 Привет! Пожалуйста, выберите язык:",
        "ua": "👋 Вітаю! Будь ласка, оберіть мову:",
        "en": "👋 Hello! Please select a language:"
    },
    "choose_language": {
        "ru": "Пожалуйста, выберите язык:",
        "ua": "Будь ласка, оберіть мову:",
        "en": "Please select a language:"
    },
    "choose_action": {
        "ru": "Выберите действие:",
        "ua": "Оберіть дію:",
        "en": "Choose an action:"
    },
    "please_press_start": {
        "ru": "Пожалуйста, нажмите кнопку «Старт» для начала работы с ботом.",
        "ua": "Будь ласка, натисніть кнопку «Старт» для початку роботи з ботом.",
        "en": "Please press the «Start» button to begin working with the bot."
    },
    "choose_currency": {
        "ru": "Выберите валюту:",
        "ua": "Оберіть валюту:",
        "en": "Choose currency:"
    },
    "enter_amount": {
        "ru": "Введите сумму:",
        "ua": "Введіть суму:",
        "en": "Enter the amount:"
    },
    "choose_city_branch": {
        "ru": "Выберите город и отделение:",
        "ua": "Оберіть місто та відділення:",
        "en": "Choose city and branch:"
    },
    "choose_time": {
        "ru": "Выберите удобное время визита:",
        "ua": "Оберіть зручний час візиту:",
        "en": "Choose a convenient visit time:"
    },
    "enter_name": {
        "ru": "Введите имя:",
        "ua": "Введіть ім'я:",
        "en": "Enter your name:"
    },
    "enter_phone": {
        "ru": "Введите номер телефона:",
        "ua": "Введіть номер телефону:",
        "en": "Enter your phone number:"
    },
    "cash_request_summary": {
        "ru": "Новая заявка на внесение наличных:\nВалюта: {currency}\nСумма: {amount}\nГород: {city}\nОтделение: {branch}\nВремя визита: {time}\nИмя клиента: {name}\nТелефон: {phone}\nTelegram: @{username}",
        "ua": "Нова заявка на внесення готівки:\nВалюта: {currency}\nСума: {amount}\nМісто: {city}\nВідділення: {branch}\nЧас візиту: {time}\nІм'я клієнта: {name}\nТелефон: {phone}\nTelegram: @{username}",
        "en": "New cash deposit request:\nCurrency: {currency}\nAmount: {amount}\nCity: {city}\nBranch: {branch}\nVisit time: {time}\nClient name: {name}\nPhone: {phone}\nTelegram: @{username}"
    },
    "cash_request_success": {
        "ru": "Спасибо! Менеджер свяжется с вами в ближайшее время для подтверждения и уточнения деталей.",
        "ua": "Дякуємо! Менеджер зв'яжеться з вами найближчим часом для підтвердження та уточнення деталей.",
        "en": "Thank you! A manager will contact you soon to confirm and clarify the details."
    },
    "choose_network": {
        "ru": "Выберите сеть для USDT:",
        "ua": "Оберіть мережу для USDT:",
        "en": "Choose network for USDT:"
    },
    "send_to_address": {
        "ru": "💳 *Адрес кошелька для получения USDT*\n\n🌐 Сеть: {network}\n📝 Адрес: `{wallet_address}`\n\n⚠️ *ВНИМАНИЕ:* Отправляйте USDT ТОЛЬКО на этот адрес!",
        "ua": "💳 *Адреса гаманця для отримання USDT*\n\n🌐 Мережа: {network}\n📝 Адреса: `{wallet_address}`\n\n⚠️ *УВАГА:* Надсилайте USDT ТІЛЬКИ на цю адресу!",
        "en": "💳 *Wallet address for receiving USDT*\n\n🌐 Network: {network}\n📝 Address: `{wallet_address}`\n\n⚠️ *WARNING:* Send USDT ONLY to this address!"
    },
    "address_error": {
        "ru": "❌ Ошибка: Не удалось получить адрес кошелька для выбранной сети",
        "ua": "❌ Помилка: Не вдалося отримати адресу гаманця для обраної мережі",
        "en": "❌ Error: Failed to get wallet address for selected network"
    },
    "enter_tx_hash": {
        "ru": "🔍 После отправки криптовалюты, пожалуйста, введите хеш транзакции:\n\n💡 Хеш транзакции можно найти в вашем кошельке или на сайте блокчейн-эксплорера",
        "ua": "🔍 Після відправки криптовалюти, будь ласка, введіть хеш транзакції:\n\n💡 Хеш транзакції можна знайти у вашому гаманці або на сайті блокчейн-експлорера",
        "en": "🔍 After sending cryptocurrency, please enter the transaction hash:\n\n💡 The transaction hash can be found in your wallet or on the blockchain explorer website."
    },
    "invalid_tx_hash": {
        "ru": "❌ Введите корректный хеш или ссылку на транзакцию.",
        "ua": "❌ Введіть коректний хеш або посилання на транзакцію.",
        "en": "❌ Enter a valid hash or transaction link."
    },
    "checking_tx": {
        "ru": "🔍 Проверяю транзакцию...\n⏳ Это может занять несколько секунд.",
        "ua": "🔍 Перевіряю транзакцію...\n⏳ Це може зайняти декілька секунд.",
        "en": "🔍 Checking transaction...\n⏳ This may take a few seconds."
    },
    "invalid_tx_format": {
        "ru": "❌ Неверный формат хеша транзакции. Попробуйте еще раз.",
        "ua": "❌ Невірний формат хеша транзакції. Спробуйте ще раз.",
        "en": "❌ Invalid transaction hash format. Try again."
    },
    "tx_confirmed": {
        "ru": "✅ Транзакция подтверждена!\n\n📊 Сумма: {amount}\n👤 От: {from_addr}\n📅 Время: {timestamp}\n\nТеперь укажите ваш контакт для связи (номер телефона или Telegram).",
        "ua": "✅ Транзакція підтверджена!\n\n📊 Сума: {amount}\n👤 Від: {from_addr}\n📅 Час: {timestamp}\n\nТепер вкажіть ваш контакт для зв'язку (номер телефону або Telegram).",
        "en": "✅ Transaction confirmed!\n\n📊 Amount: {amount}\n👤 From: {from_addr}\n📅 Time: {timestamp}\n\nNow provide your contact for communication (phone number or Telegram)."
    },
    "tx_not_confirmed": {
        "ru": "❌ Транзакция не подтверждена!\n\n🔍 Ошибка: {error}\n\nВозможные причины:\n• Транзакция еще не прошла\n• Неверный хеш транзакции\n• Транзакция отправлена на другой адрес\n• Проблемы с сетью\n\nПопробуйте еще раз или обратитесь в поддержку.",
        "ua": "❌ Транзакція не підтверджена!\n\n🔍 Помилка: {error}\n\nМожливі причини:\n• Транзакція ще не пройшла\n• Невірний хеш транзакції\n• Транзакція відправлена на іншу адресу\n• Проблеми з мережею\n\nСпробуйте ще раз або зверніться в підтримку.",
        "en": "❌ Transaction not confirmed!\n\n🔍 Error: {error}\n\nPossible reasons:\n• Transaction not yet processed\n• Invalid transaction hash\n• Transaction sent to another address\n• Network issues\n\nTry again or contact support."
    },
    "invalid_token_erc": {
        "ru": "❗️ Вы отправили токен, который не является USDT (ERC-20). Мы не можем обработать этот перевод.",
        "ua": "❗️ Вы отправили токен, который не является USDT (ERC-20). Мы не можем обработать этот перевод.",
        "en": "❗️ Вы отправили токен, который не является USDT (ERC-20). Мы не можем обработать этот перевод."
    },
    "invalid_token_trc": {
        "ru": "❗️ Вы отправили токен, который не является USDT (TRC-20). Мы не можем обработать этот перевод.",
        "ua": "❗️ Вы отправили токен, который не является USDT (TRC-20). Мы не можем обработать этот перевод.",
        "en": "❗️ Вы отправили токен, который не является USDT (TRC-20). Мы не можем обработать этот перевод."
    },
    "is_duplicate_transaction": {
        "ru": "❗️ Эта транзакция уже была обработана ранее. Убедитесь, что вы ввели правильный хэш. Если проблема сохраняется — обратитесь в техподдержку.",
        "ua": "❗️ Эта транзакция уже была обработана ранее. Убедитесь, что вы ввели правильный хэш. Если проблема сохраняется — обратитесь в техподдержку.",
        "en": "❗️ Эта транзакция уже была обработана ранее. Убедитесь, что вы ввели правильный хэш. Если проблема сохраняется — обратитесь в техподдержку."
    },
    "invalid_recipient": {
        "ru": "❗️ Ошибка: USDT были отправлены на адрес, отличающийся от выданного вам. Проверьте адрес назначения.",
        "ua": "❗️ Ошибка: USDT были отправлены на адрес, отличающийся от выданного вам. Проверьте адрес назначения.",
        "en": "❗️ Ошибка: USDT были отправлены на адрес, отличающийся от выданного вам. Проверьте адрес назначения."
    },
    "expired": {
        "ru": "⚠️ Мы не получили подтверждения по вашей транзакции в течение 2 часов.\n\nОна будет удалена. Если нужна помощь — напишите в поддержку.",
        "ua": "⚠️ Мы не получили подтверждения по вашей транзакции в течение 2 часов.\n\nОна будет удалена. Если нужна помощь — напишите в поддержку.",
        "en": "⚠️ Мы не получили подтверждения по вашей транзакции в течение 2 часов.\n\nОна будет удалена. Если нужна помощь — напишите в поддержку."
    },
    "crypto_request_summary": {
        "ru": "Новая заявка на обмен USDT:\nВалюта: USDT\nСумма: {amount}\nСеть: {network}\nАдрес кошелька: {wallet_address}\nХеш транзакции: {tx_hash}\nКонтакт: {contact}\nTelegram: @{username}",
        "ua": "Нова заявка на обмін USDT:\nВалюта: USDT\nСума: {amount}\nМережа: {network}\nАдреса гаманця: {wallet_address}\nХеш транзакції: {tx_hash}\nКонтакт: {contact}\nTelegram: @{username}",
        "en": "New USDT exchange request:\nCurrency: USDT\nAmount: {amount}\nNetwork: {network}\nWallet address: {wallet_address}\nTransaction hash: {tx_hash}\nContact: {contact}\nTelegram: @{username}"
    },
    "crypto_request_success": {
        "ru": "✅ Заявка на обмен принята!\n\n{summary}\n\n📞 Оператор свяжется с вами в ближайшее время.\n⏰ Обычно это занимает 5-15 минут.",
        "ua": "✅ Заявка на обмін прийнята!\n\n{summary}\n\n📞 Оператор зв'яжеться з вами найближчим часом.\n⏰ Зазвичай це займає 5-15 хвилин.",
        "en": "✅ Exchange request accepted!\n\n{summary}\n\n📞 The operator will contact you soon.\n⏰ Usually it takes 5-15 minutes."
    },
    "back": {
        "ru": "🔙 Назад",
        "ua": "🔙 Назад",
        "en": "🔙 Back"
    },
    "back_to_main": {
        "ru": "🏠 Вернуться на главную",
        "ua": "🏠 Повернутися на головну",
        "en": "🏠 Back to main menu"
    },
    "cash_exchange": {
        "ru": "💵 Обмен наличных",
        "ua": "💵 Обмін готівки",
        "en": "💵 Cash exchange"
    },
    "crypto_exchange": {
        "ru": "💸 Обмен крипты",
        "ua": "💸 Обмін крипти",
        "en": "💸 Crypto exchange"
    },
    "invalid_action": {
        "ru": "Пожалуйста, выберите действие с помощью кнопок.",
        "ua": "Будь ласка, оберіть дію за допомогою кнопок.",
        "en": "Please choose an action using the buttons."
    },
    "invalid_currency": {
        "ru": "Пожалуйста, выберите валюту с помощью кнопок.",
        "ua": "Будь ласка, оберіть валюту за допомогою кнопок.",
        "en": "Please choose a currency using the buttons."
    },
    "invalid_network": {
        "ru": "Пожалуйста, выберите сеть с помощью кнопок.",
        "ua": "Будь ласка, оберіть мережу за допомогою кнопок.",
        "en": "Please choose a network using the buttons."
    },
    "invalid_time": {
        "ru": "Пожалуйста, выберите время с помощью кнопок.",
        "ua": "Будь ласка, оберіть час за допомогою кнопок.",
        "en": "Please choose a time using the buttons."
    },
    "invalid_city": {
        "ru": "Пожалуйста, выберите город с помощью кнопок.",
        "ua": "Будь ласка, оберіть місто за допомогою кнопок.",
        "en": "Please choose a city using the buttons."
    },
    "invalid_branch": {
        "ru": "Пожалуйста, выберите отделение с помощью кнопок.",
        "ua": "Будь ласка, оберіть відділення за допомогою кнопок.",
        "en": "Please choose a branch using the buttons."
    },
    "currency_rates_error": {
        "ru": "❌ Ошибка загрузки курсов.",
        "ua": "❌ Помилка завантаження курсів.",
        "en": "❌ Error loading rates."
    },
    "amount_info": {
        "ru": "📊 Сумма: {amount}\n\n⚠️ Актуальный курс недоступен.\nПредположим, вы получите ~XXX USD за {amount} монет.\nТочный расчет будет сделан оператором обменника.",
        "ua": "📊 Сума: {amount}\n\n⚠️ Актуальний курс недоступний.\nПрипустимо, ви отримаєте ~XXX USD за {amount} монет.\nТочний розрахунок зробить оператор обмінника.",
        "en": "📊 Amount: {amount}\n\n⚠️ Current rate unavailable.\nAssume you will get ~XXX USD for {amount} coins.\nThe exact calculation will be made by the operator."
    },
    "commission_calculation": {
        "ru": "💰 *Расчет комиссии*\n\n📊 Сумма: {amount} {currency_from}\n💱 Курс: {rate}\n💸 Комиссия: {commission} {currency_to}\n💰 Итого к получению: {final_amount} {currency_to}\n\n{commission_note}",
        "ua": "💰 *Розрахунок комісії*\n\n📊 Сума: {amount} {currency_from}\n💱 Курс: {rate}\n💸 Комісія: {commission} {currency_to}\n💰 Разом до отримання: {final_amount} {currency_to}\n\n{commission_note}",
        "en": "💰 *Commission calculation*\n\n📊 Amount: {amount} {currency_from}\n💱 Rate: {rate}\n💸 Commission: {commission} {currency_to}\n💰 Total to receive: {final_amount} {currency_to}\n\n{commission_note}"
    },
    "commission_manager_required": {
        "ru": "⚠️ *Сумма от 5000 USD - требуется связь с менеджером*",
        "ua": "⚠️ *Сума від 5000 USD - потрібен зв'язок з менеджером*",
        "en": "⚠️ *Amount from 5000 USD - manager contact required*"
    },
    "commission_percentage": {
        "ru": "📈 Комиссия: {percentage}% от курса",
        "ua": "📈 Комісія: {percentage}% від курсу",
        "en": "📈 Commission: {percentage}% of the rate"
    },
    "commission_fixed": {
        "ru": "💵 Фиксированная комиссия: {amount} USD",
        "ua": "💵 Фіксована комісія: {amount} USD",
        "en": "💵 Fixed commission: {amount} USD"
    },
    "invalid_amount": {
        "ru": "❌ Введите корректную сумму больше 0",
        "ua": "❌ Введіть коректну суму більше 0",
        "en": "❌ Enter a valid amount greater than 0"
    },
    "qr_caption": {
        "ru": "💳 Адрес получателя:\n`{address}`",
        "ua": "💳 Адреса отримувача:\n`{address}`",
        "en": "💳 Recipient address:\n`{address}`"
    },
    "start": {
        "ru": "Старт",
        "en": "Start",
        "ua": "Старт"
},
    "choose_crypto_operation": {
        "ru": "Выберите операцию с USDT:",
        "ua": "Оберіть операцію з USDT:",
        "en": "Choose USDT operation:"
    },
    "choose_cash_operation": {
        "ru": "Выберите операцию с наличными USD:",
        "ua": "Оберіть операцію з готівкою USD:",
        "en": "Choose cash USD operation:"
    },
    "crypto_buy_usdt": {
        "ru": "Купить USDT",
        "ua": "Купити USDT",
        "en": "Buy USDT"
    },
    "crypto_sell_usdt": {
        "ru": "Продать USDT",
        "ua": "Продати USDT",
        "en": "Sell USDT"
    },
    "cash_buy_usd": {
        "ru": "Купить USD",
        "ua": "Купити USD",
        "en": "Buy USD"
    },
    "cash_sell_usd": {
        "ru": "Продать USD",
        "ua": "Продати USD",
        "en": "Sell USD"
    },
    "enter_client_wallet": {
        "ru": "Введите адрес вашего кошелька USDT в выбранной сети:",
        "ua": "Введіть адресу вашого гаманця USDT у вибраній мережі:",
        "en": "Enter your USDT wallet address in the selected network:"
    },
    "cash_withdraw_request_summary": {
        "ru": "Заявка на выдачу средств:\nВалюта: {currency}\nСумма: {amount}\nГород: {city}\nОтделение: {branch}\nВремя визита: {time}\nИмя клиента: {name}\nТелефон: {phone}\nTelegram: @{username}",
        "ua": "Заявка на видачу коштів:\nВалюта: {currency}\nСума: {amount}\nМісто: {city}\nВідділення: {branch}\nЧас візиту: {time}\nІм'я клієнта: {name}\nТелефон: {phone}\nTelegram: @{username}",
        "en": "Cash withdrawal request:\nCurrency: {currency}\nAmount: {amount}\nCity: {city}\nBranch: {branch}\nVisit time: {time}\nClient name: {name}\nPhone: {phone}\nTelegram: @{username}"
    },
    "current_rates": {
        "ru": "Актуальный курс валют",
        "ua": "Актуальний курс валют",
        "en": "Current exchange rates"
    },
    "rates_header": {
        "ru": "📊 Актуальные курсы валют:\n\n",
        "ua": "📊 Актуальні курси валют:\n\n",
        "en": "📊 Current exchange rates:\n\n"
    },
    "rate_format": {
        "ru": "💱 {pair}: {buy} / {sell} UAH",
        "ua": "💱 {pair}: {buy} / {sell} UAH",
        "en": "💱 {pair}: {buy} / {sell} UAH"
    },
    "rates_source": {
        "ru": "\n\n📡 Источник: @obmenvalut13",
        "ua": "\n\n📡 Джерело: @obmenvalut13",
        "en": "\n\n📡 Source: @obmenvalut13"
    },
    "wallet_address_header": {
        "ru": "💳 *Адрес кошелька для получения USDT*",
        "ua": "💳 *Адреса гаманця для отримання USDT*",
        "en": "💳 *Wallet address for receiving USDT*"
    },
    "wallet_network": {
        "ru": "🌐 Сеть: {network}",
        "ua": "🌐 Мережа: {network}",
        "en": "🌐 Network: {network}"
    },
    "wallet_address": {
        "ru": "📝 Адрес: `{address}`",
        "ua": "📝 Адреса: `{address}`",
        "en": "📝 Address: `{address}`"
    },
    "wallet_warning": {
        "ru": "⚠️ *ВНИМАНИЕ:* Отправляйте USDT ТОЛЬКО на этот адрес!",
        "ua": "⚠️ *УВАГА:* Надсилайте USDT ТІЛЬКИ на цю адресу!",
        "en": "⚠️ *WARNING:* Send USDT ONLY to this address!"
    },
    "sell_instruction_header": {
        "ru": "📋 *Инструкция по продаже USDT:*",
        "ua": "📋 *Інструкція по продажу USDT:*",
        "en": "📋 *USDT Sale Instructions:*"
    },
    "sell_instruction_step1": {
        "ru": "1️⃣ Отправьте {amount} USDT на указанный адрес",
        "ua": "1️⃣ Надішліть {amount} USDT на вказану адресу",
        "en": "1️⃣ Send {amount} USDT to the specified address"
    },
    "sell_instruction_step2": {
        "ru": "2️⃣ Дождитесь подтверждения транзакции",
        "ua": "2️⃣ Дочекайтеся підтвердження транзакції",
        "en": "2️⃣ Wait for transaction confirmation"
    },
    "sell_instruction_step3": {
        "ru": "3️⃣ Введите хеш транзакции для проверки",
        "ua": "3️⃣ Введіть хеш транзакції для перевірки",
        "en": "3️⃣ Enter transaction hash for verification"
    },
    "sell_instruction_final": {
        "ru": "💡 После подтверждения вы получите {amount} USD",
        "ua": "💡 Після підтвердження ви отримаєте {amount} USD",
        "en": "💡 After confirmation you will receive {amount} USD"
    },
    "wallet_address_error": {
        "ru": "❌ Ошибка: Не удалось получить адрес кошелька",
        "ua": "❌ Помилка: Не вдалося отримати адресу гаманця",
        "en": "❌ Error: Failed to get wallet address"
    },
    "qr_code_error": {
        "ru": "❌ Ошибка при генерации QR кода",
        "ua": "❌ Помилка при генерації QR коду",
        "en": "❌ Error generating QR code"
    },
    "enter_name": {
        "ru": "👤 Введите ваше имя:",
        "ua": "👤 Введіть ваше ім'я:",
        "en": "👤 Enter your name:"
    },
}

def get_message(key, lang="ru", **kwargs):
    text = MESSAGES.get(key, {}).get(lang)
    if not text:
        text = MESSAGES.get(key, {}).get("ru", "")
    return text.format(**kwargs) if kwargs else text
