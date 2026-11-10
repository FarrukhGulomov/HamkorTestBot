from aiogram import Router

from src.presentation.handlers import consent, fallback, settings, start


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_routers(
        start.build_router(),
        settings.build_router(),
        consent.build_router(),
    )
    # fallback eng oxirida bo'lishi kerak, aks holda boshqa handlerlarni to'sib qo'yadi
    root.include_router(fallback.build_router())
    return root
