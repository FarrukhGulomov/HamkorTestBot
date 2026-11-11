# Hamkor AI Telegram bot

Hamkorbank AI-yordamchisi uchun Telegram bot. Python, aiogram 3, Clean Architecture.

## Imkoniyatlar

- `/start` da foydalanuvchidan telefon raqami so'raladi (faqat o'zining kontakti qabul qilinadi)
- keyin til tanlanadi: O'zbekcha, Ўзбекча, Русский, English, Qaraqalpaqsha, 中文
- salomlashish tanlangan tilda chiqadi
- tilni keyinroq `/settings` buyrug'i yoki "⚙️ Sozlamalar" tugmasi orqali almashtirish mumkin
- foydalanuvchi savol yozsa (masalan, "Omonat ochmoqchiman, foizi qancha?"), bot tanlangan tilda qisqa javob
  beradi va javob ostida 👍 / 👎 baho tugmalari chiqadi. Baho bazaga yoziladi (har bir javobga bir marta)
- foydalanuvchi oxirgi marta yozganidan 3 daqiqa o'tsa, ma'lumotlarni qayta ishlashga rozilik so'raladi
  (Roziman / Yo'q). Javob bazaga yoziladi. Rozilik har bir foydalanuvchidan bir marta so'raladi.
- "Yo'q" javobida telefon raqami, ism va avval saqlangan savol matnlari o'chiriladi, keyingi savollar
  matni saqlanmaydi (bot javob berishda davom etadi)
- bitta foydalanuvchi qisqa vaqtda ko'p xabar yuborsa, ortiqchalari e'tiborsiz qoldiriladi;
  savol-javoblar belgilangan muddatdan keyin avtomatik o'chiriladi

## Ishga tushirish

Python **3.11 yoki undan yangisi** kerak (`python3 --version` bilan tekshiring). macOS'dagi tizim
Python'i odatda eski bo'ladi, yangisini `brew install python` bilan o'rnating.

```bash
python3 -m venv .venv
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
| `BOT_TOKEN` | Telegram bot tokeni (`123456789:AAH...` ko'rinishida) | — |
| `DATABASE_URL` | SQLite yoki PostgreSQL | `sqlite+aiosqlite:///./hamkor_bot.db` |
| `CONSENT_IDLE_SECONDS` | rozilik so'ralishidan oldingi kutish vaqti (1 dan katta) | `180` |
| `CONSENT_CHECK_INTERVAL_SECONDS` | tekshiruv oralig'i (1 dan katta) | `5` |
| `INTERACTION_RETENTION_DAYS` | savol-javoblar necha kun saqlanadi | `30` |
| `RATE_LIMIT_MAX_MESSAGES` | oyna ichida bitta foydalanuvchining ko'pi bilan nechta xabari qayta ishlanadi | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | tezlik cheklovi oynasi | `10` |

Noto'g'ri sozlama (masalan, bo'sh yoki xato token, nol oraliq) bot ishga tushishida aniq xato bilan to'xtatiladi.
Bot faqat shaxsiy suhbatda ishlaydi, guruh va kanallardagi xabarlar e'tiborsiz qoldiriladi.

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
├── application/       # use case'lar: RegisterContact, ChangeLanguage, TrackActivity, RequestConsent,
│                      #   SaveConsent, GetUser, AnswerQuestion, RateAnswer
│                      #   + portlar (Clock, ConsentNotifier, Translator, AnswerProvider)
├── infrastructure/    # SQLAlchemy repozitoriylar, JSON tarjimalar, FAQ javoblar, fon scheduler, tizim vaqti
├── presentation/      # aiogram: handlerlar, klaviaturalar, middleware, Telegram orqali xabar yuboruvchi
├── config.py          # .env dan sozlamalarni o'qish
└── main.py            # composition root: barcha qatlamlar shu yerda bir-biriga ulanadi
```

- **domain** hech qanday tashqi kutubxonani import qilmaydi.
- **application** faqat domain va o'z portlarini biladi. Telegram yoki bazadan xabardor emas.
- **presentation** `infrastructure` ni import qilmaydi: tarjimalarga `application` dagi `Translator` porti orqali murojaat qiladi.
- Bu qoidalar `tests/test_architecture.py` da avtomatik tekshiriladi: qatlam ruxsat etilmagan modulni import qilsa, test yiqiladi.
- Bazani almashtirish uchun faqat `infrastructure/db` o'zgaradi, Telegram o'rniga boshqa kanal ulash uchun faqat `presentation`.

### Savolga javob va baho

`AnswerQuestion` use case'i `AnswerProvider` portidan javob oladi. Hozirgi amalga oshirish
(`infrastructure/faq`) savoldagi kalit so'z bo'yicha mavzuni (omonat, kredit, karta) aniqlaydi va
foydalanuvchi tilida tayyor javob qaytaradi. Kalit so'z so'zning boshida bo'lishi kerak
("kartamni" mos, "discard" mos emas); bir necha mavzu uchrasa, birinchi uchragani tanlanadi.
Kalit so'z topilmasa, umumiy javob beriladi. Savol 1000 belgigacha qisqartiriladi.
Javoblardagi `XX%` va `XXX` qiymatlari namuna (skrinshotdagidek): haqiqiy ma'lumotlarni
`src/infrastructure/faq/faq.json` da almashtiring. Keyinchalik LLM ulash uchun faqat yangi
`AnswerProvider` yozish kifoya, boshqa qatlamlar o'zgarmaydi.
`RateAnswer` bahoni `interactions` jadvaliga yozadi va faqat savol egasining bahosini qabul qiladi.

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
   Javob "Yo'q" bo'lsa, shu use case foydalanuvchining telefon raqami, ismi va saqlangan savol
   matnlarini o'chiradi. Keyin kontakt qayta ulashilsa ham ular qayta saqlanmaydi. Baho va botning
   javobi statistika uchun qoladi.

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
