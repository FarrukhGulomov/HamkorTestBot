FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Bot oddiy (root bo'lmagan) foydalanuvchi nomidan ishlaydi; /data baza fayli uchun
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data \
    && chown app:app /data

WORKDIR /app

# Aniq versiyalar (requirements.lock): har safar bir xil image yig'iladi
COPY requirements.lock .
RUN pip install -r requirements.lock

# Kod root egaligida qoladi: bot o'z kodini o'zgartira olmaydi
COPY src ./src

USER app

CMD ["python", "-m", "src.main"]
