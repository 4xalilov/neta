"""Umumiy test sozlamalari.

``engine.settings`` import qilinganda hamma majburiy maydonlar (masalan
``database_url``) mavjud bo'lishi kerak. Bu fayl ularni ``engine`` import
qilinishidan OLDIN muhit o'zgaruvchisi sifatida o'rnatadi, shunda boshqa
testlar ham (bu fayl ular uchun ham umumiy) alohida sozlashsiz ishlay oladi.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("FAL_KEY", "test")
