# Hamkor AI Telegram bot

Hamkorbank AI-yordamchisi uchun Telegram bot. Python, aiogram 3, Clean Architecture.

## Imkoniyatlar

- `/start` da foydalanuvchidan telefon raqami so'raladi (faqat o'zining kontakti qabul qilinadi)
- keyin til tanlanadi: O'zbekcha, Ўзбекча, Русский, English, Qaraqalpaqsha, 中文
- salomlashish tanlangan tilda chiqadi
- tilni keyinroq `/settings` buyrug'i yoki "⚙️ Sozlamalar" tugmasi orqali almashtirish mumkin
- foydalanuvchi oxirgi marta yozganidan 3 daqiqa o'tsa, ma'lumotlarni qayta ishlashga rozilik so'raladi
  (Roziman / Yo'q). Javob bazaga yoziladi. Rozilik har bir foydalanuvchidan bir marta so'raladi.

## Ishga tushirish

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # BOT_TOKEN ni @BotFather dan olib yozing
python -m src.main
```

Docker bilan:

```bash
cp .env.example .env
docker compose up -d --build
```

### Sozlamalar (`.env`)

| O'zgaruvchi | Izoh | Standart |
|---|---|---|
| `BOT_TOKEN` | Telegram bot tokeni | — |
| `DATABASE_URL` | SQLite yoki PostgreSQL | `sqlite+aiosqlite:///./hamkor_bot.db` |
| `CONSENT_IDLE_SECONDS` | rozilik so'ralishidan oldingi kutish vaqti | `180` |
| `CONSENT_CHECK_INTERVAL_SECONDS` | tekshiruv oralig'i | `30` |

PostgreSQL uchun `pip install asyncpg` qiling va `DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db` deb yozing.
Jadvallar bot ishga tushganda avtomatik yaratiladi.

## Testlar

```bash
pip install -r requirements-dev.txt
pytest
```

## Arxitektura

Loyiha Clean Architecture bo'yicha qatlamlarga bo'lingan. Bog'liqlik faqat ichkariga qarab yo'naladi:
`presentation → application → domain`, `infrastructure` esa domain va application dagi interfeyslarni amalga oshiradi.

```
src/
├── domain/            # biznes qoidalari: User, Language, ConsentStatus, UserRepository (interfeys)
├── application/       # use case'lar: RegisterContact, ChangeLanguage, TrackActivity,
│                      #   RequestConsent, SaveConsent, GetUser + portlar (Clock, ConsentNotifier)
├── infrastructure/    # SQLAlchemy repozitoriy, tarjimalar (JSON), fon scheduler, tizim vaqti
├── presentation/      # aiogram: handlerlar, klaviaturalar, middleware, Telegram orqali xabar yuboruvchi
├── config.py          # .env dan sozlamalarni o'qish
└── main.py            # composition root: barcha qatlamlar shu yerda bir-biriga ulanadi
```

- **domain** hech qanday tashqi kutubxonani import qilmaydi.
- **application** faqat domain va o'z portlarini biladi. Telegram yoki bazadan xabardor emas.
- Bazani almashtirish uchun faqat `infrastructure/db` o'zgaradi, Telegram o'rniga boshqa kanal ulash uchun faqat `presentation`.

### Rozilik qanday ishlaydi

1. `ActivityMiddleware` foydalanuvchining har bir xabarida `last_message_at` ni yangilaydi.
2. `ConsentScheduler` har 30 soniyada `RequestConsent` use case'ini ishga tushiradi.
3. Use case oxirgi xabari 3 daqiqadan oldin bo'lgan, til tanlagan va roziligi hali so'ralmagan
   foydalanuvchilarni topadi, ularga so'rov yuboradi va `consent_requested_at` ni belgilaydi.
4. Tugma bosilganda `SaveConsent` javobni (`agreed` / `declined`) vaqti bilan bazaga yozadi.

Foydalanuvchi "Yo'q" desa, rozilik qayta so'ralmaydi.
