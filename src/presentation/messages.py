from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def set_reply_markup(message: Message, markup: InlineKeyboardMarkup | None) -> None:
    """Klaviaturani almashtiradi (`None` bo'lsa, olib tashlaydi). Tugma ikki marta bosilsa, Telegram bir xil klaviaturani
    qayta o'rnatishni (yoki yo'q klaviaturani qayta olib tashlashni) "message is not modified" xatosi bilan rad etadi: bu xato e'tiborsiz qoldiriladi."""
    try:
        await message.edit_reply_markup(reply_markup=markup)
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise
