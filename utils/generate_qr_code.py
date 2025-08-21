from html import escape as quote_html
import qrcode
from PIL import Image
from io import BytesIO
from aiogram.types import BufferedInputFile
from localization import get_message

async def generate_wallet_qr(bot, chat_id: int, address: str, network: str, logo_path: str, lang: str = "ru"):
    if network.strip().upper() == 'TRC20':
        qr_data = f"tron:{address}"
    elif network.strip().upper() == 'ERC20':
        qr_data = f"ethereum:{address}"
    elif network.strip().upper() == 'BEP20':
        qr_data = f"bnb:{address}"
    else:
        qr_data = address  # fallback

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # Открываем логотип
    logo = Image.open(logo_path)

    # Изменяем размер логотипа (например, 1/4 от размера QR)
    qr_width, qr_height = img.size
    logo_size = int(qr_width / 4)
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

    # Вставляем логотип в центр
    pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
    img.paste(logo, pos, mask=logo if logo.mode == 'RGBA' else None)

    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)

    photo_file = BufferedInputFile(bio.getvalue(), filename="qr.png")

    await bot.send_photo(
        chat_id,
        photo=photo_file,
        caption=get_message("qr_caption", lang, address=address),
        parse_mode="Markdown"
    )
