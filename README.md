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
| `CONSENT_CHECK_INTERVAL_SECONDS` | tekshiruv oralig'i | `5` |

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
│                      #   RequestConsent, SaveConsent, GetUser + portlar (Clock, ConsentNotifier, Translator)
├── infrastructure/    # SQLAlchemy repozitoriy, JSON tarjimalar, fon scheduler, tizim vaqti
├── presentation/      # aiogram: handlerlar, klaviaturalar, middleware, Telegram orqali xabar yuboruvchi
├── config.py          # .env dan sozlamalarni o'qish
└── main.py            # composition root: barcha qatlamlar shu yerda bir-biriga ulanadi
```

- **domain** hech qanday tashqi kutubxonani import qilmaydi.
- **application** faqat domain va o'z portlarini biladi. Telegram yoki bazadan xabardor emas.
- **presentation** `infrastructure` ni import qilmaydi: tarjimalarga `application` dagi `Translator` porti orqali murojaat qiladi.
- Bu qoidalar `tests/test_architecture.py` da avtomatik tekshiriladi: qatlam ruxsat etilmagan modulni import qilsa, test yiqiladi.
- Bazani almashtirish uchun faqat `infrastructure/db` o'zgaradi, Telegram o'rniga boshqa kanal ulash uchun faqat `presentation`.

### Rozilik qanday ishlaydi

Savol foydalanuvchining shaxsiy ma'lumotlarini (telefon raqami va ism) qayta ishlashga rozilikni so'raydi.

1. `ActivityMiddleware` foydalanuvchining har bir xabarida `last_message_at` ni yangilaydi.
2. `ConsentScheduler` har 5 soniyada `RequestConsent` use case'ini ishga tushiradi.
3. Use case oxirgi xabari 3 daqiqadan oldin bo'lgan, til tanlagan va roziligi hali so'ralmagan
   foydalanuvchilarni topadi. Har biri uchun so'rov yuborish huquqi bazada vaqtincha (1 daqiqaga)
   egallanadi. Shu orada foydalanuvchi yozgan bo'lsa, u o'tkazib yuboriladi.
4. Xabar yuboriladi va so'rov yakunlangan deb belgilanadi (`consent_requested_at`).
5. Yuborish xato bilan tugasa yoki jarayon o'rtada to'xtab qolsa, egallash muddati tugagach so'rov
   qayta olinadi. Urinishlar soni bazada (`consent_attempts`) saqlanadi va 5 tadan oshmaydi, shuning
   uchun qayta ishga tushirish ham bu chegarani aylanib o'tolmaydi. Bot bloklangan bo'lsa, qayta urinilmaydi.
6. Tugma bosilganda `SaveConsent` javobni (`agreed` / `declined`) vaqti bilan bazaga yozadi.

Bilib qo'yish kerak bo'lgan jihatlar:

- So'rov oxirgi xabardan 180 soniyadan keyin, tekshiruv oralig'i hisobiga ko'pi bilan 5 soniya
  kechikib (180–185 soniya) yuboriladi.
- Rozilik har bir foydalanuvchidan bir marta so'raladi. Topshiriqda takrorlash qoidasi berilmagan,
  shuning uchun "Yo'q" javobidan keyin qayta so'ralmaydi.
- Foydalanuvchi ma'lumotlari maydon bo'yicha yangilanadi (butun yozuvni qayta yozish o'rniga),
  shuning uchun parallel ishlayotgan jarayonlar (scheduler va foydalanuvchi so'rovi) bir-birining
  tilini, faollik vaqtini yoki rozilik javobini bosib yozmaydi.
- Jadval tuzilmasi o'zgargan bo'lsa, bot ishga tushganda yetishmayotgan ustunlar eski bazaga
  avtomatik qo'shiladi.
