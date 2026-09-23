# `engine/models` — yangi model va migratsiya qo'shish

Modellar ikki faylda: **Content Engine** jadvallari `content.py`, **CRM/Jarvis**
jadvallari `crm.py` (docs/02-data-model.md ga mos). Umumiy asos —
`engine/db.py` dagi `Base`, `UUIDPkMixin`, `TimestampMixin`.

## Yangi model qo'shish

1. `content.py` yoki `crm.py` ichida yangi klass yoz:

   ```python
   class MyTable(UUIDPkMixin, TimestampMixin, Base):
       __tablename__ = "my_table"

       workspace_id: Mapped[uuid.UUID] = mapped_column(
           ForeignKey("workspace.id", ondelete="CASCADE"), index=True
       )
       title: Mapped[str] = mapped_column(String(200))
   ```

   - `UUIDPkMixin` va `TimestampMixin` — `id`, `created_at`, `updated_at` ni
     avtomatik qo'shadi (docs/02: "Hamma jadvalda id uuid, created_at, updated_at").
   - Deyarli har bir jadvalda `workspace_id` bo'lishi kerak (multi-tenant).
     Faqat ota-jadval orqali workspace'ga bog'langan "farzand" jadvallar
     (masalan `critic_review`, `asset`, `post`) buni o'tkazib yuboradi.
   - JSON ustun uchun: `JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")`
     dan foydalan (postgresda JSONB, sqlite'da oddiy JSON — testlar shu bilan ishlaydi).
   - Embedding (pgvector) ustun uchun: `vector_column(768)` funksiyasidan
     foydalan (`content.py`) — postgresda `Vector(768)`, sqlite'da JSON fallback.
   - Qat'iy qiymatlar ro'yxati bo'lgan maydon (enum) uchun: `enum.StrEnum`
     klass yoz + `CheckConstraint("col IN (...)")` qo'sh (misollar: `LeadSource`,
     `LeadStage`, `AssetKind`).

2. Klassni `models/__init__.py` dagi importlarga va `__all__` ro'yxatiga qo'sh.

3. Alembic migratsiya yoz (bu loyihada **qo'lda**, avtogenerate emas — dev
   muhitida Postgres yo'q, shu sabab `alembic revision --autogenerate`
   ishlatilmaydi):

   - `apps/api/alembic/versions/000N_<qisqa_nom>.py` fayl yarat,
     `0001_initial.py` dan namuna ol.
   - `revision = "000N"`, `down_revision = "000(N-1)"` (oldingi migratsiyaning
     revision id'si) qo'y.
   - `upgrade()` ichida `op.create_table(...)`, kerakli `op.create_index(...)`,
     `downgrade()` ichida teskarisi (`op.drop_table(...)` va h.k.).
   - Postgresga xos narsalar (`ivfflat` indeks, partial index `WHERE ...`)
     uchun `op.execute("CREATE INDEX ... ")` dan foydalan — `pgvector` shart
     bo'lsa, `CREATE EXTENSION IF NOT EXISTS vector` allaqachon `0001` da bor.

4. Test qo'sh/yangila: `tests/test_models.py` dagi `EXPECTED_TABLES` ro'yxatiga
   yangi jadval nomini qo'sh, testlarni sqlite ustida ishga tushir:

   ```bash
   cd apps/api && .venv/bin/python -m pytest -q tests/test_models.py
   ```

## Postgres vs sqlite (testlar)

Testlar haqiqiy Postgres'siz, `sqlite+aiosqlite:///:memory:` ustida ishlaydi
(`engine.db.init_models`). Shu sabab:

- Har bir JSON/JSONB ustun `.with_variant(JSONB, "postgresql")` orqali
  yoziladi — sqlite'da oddiy `JSON` bo'lib qoladi.
- Har bir `Vector(...)` ustun `.with_variant(JSON(), "sqlite")` orqali
  yoziladi.
- Faqat postgresda ishlaydigan indekslar (`ivfflat`, `postgresql_where` bilan
  qisman indeks) `Index(..., info={"postgres_only": True})` bilan belgilanadi;
  `engine.db.init_models()` ularni sqlite uchun `create_all` chaqirishidan oldin
  vaqtincha metadata'dan olib tashlaydi.

Haqiqiy migratsiya (`alembic/versions/*.py`) esa faqat Postgresda ishlaydi va
bu cheklovlarga muhtoj emas — u to'g'ridan-to'g'ri `UUID`, `JSONB`,
`Vector(768)`, `ivfflat` va partial indekslardan foydalanadi.

## Migratsiyani ishga tushirish (Postgres bilan)

```bash
cd apps/api
export DATABASE_URL=postgresql+asyncpg://...
.venv/bin/alembic upgrade head
```
