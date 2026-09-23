# Twenty CRM self-host (bosqich 5.1)

`docker-compose.yml` — Twenty server + worker + o'z Postgres'i + o'z Redis'i, `ame_default`
tashqi tarmog'iga ulanadi (asosiy API konteyneri bilan bir tarmoqda bo'lishi uchun).

DIQQAT: bu compose skelet — versiyalar (`TWENTY_VERSION`) va ba'zi environment
o'zgaruvchilar/komandalar TAXMIN. Ishga tushirishdan oldin
https://twenty.com/developers/section/self-hosting bilan solishtiring va
`docker-compose.yml` ichidagi "TAXMIN"/"verify" izohlarini tekshiring (docs/07:
"Twenty tez o'zgaradi -> faqat adapter orqali").

## Ishga tushirish
1. `.env` da qiymatlar bering: `TWENTY_VERSION`, `TWENTY_APP_SECRET`
   (`openssl rand -hex 32`), `TWENTY_DB_PASSWORD`, `TWENTY_SERVER_URL`
   (masalan `https://crm.domain.uz`).
2. Tarmoq mavjud emasligini tekshiring: `docker network create ame_default`
   (agar yo'q bo'lsa; asosiy `docker-compose.yml` shu tarmoqqa ulanishi kerak).
3. `docker compose -f infra/twenty/docker-compose.yml up -d`
4. `http://localhost:3000` da birinchi foydalanuvchini (workspace owner) yarating.

## API kalit yaratish
1. Twenty UI -> **Settings -> APIs & Webhooks** (yoki **Developers**) bo'limiga kiring.
2. **Create API key** tugmasini bosing, nomini yozing (masalan `jarvis-adapter`).
3. Ko'rsatilgan tokenni faqat bir marta ko'rasiz — uni `.env` dagi `TWENTY_API_KEY`
   ga qo'ying.
4. `crm_adapter.py` (`TwentyCRM`) har so'rovda `Authorization: Bearer <TWENTY_API_KEY>`
   sarlavhasini yuboradi.

## Custom obyektlar
Twenty UI -> **Settings -> Data model -> Create object**. Quyidagi obyekt/maydonlarni
yarating (nomlar TAXMIN — Twenty versiyasiga qarab maydon turi/nomi biroz farq qilishi
mumkin; real yaratgach `crm_adapter.py::TwentyCRM._PATHS` va maydon xaritasini shunga
moslang):

### Lead (custom obyekt)
| Maydon | Tur | Izoh |
|---|---|---|
| name | Text | Lid ismi |
| phone | Phone | Telefon raqami |
| ig_handle | Text | Instagram foydalanuvchi nomi |
| source | Select | `ig_dm` \| `ig_comment` \| `lead_form` \| `site` \| `phone` |
| temperature | Select | `hot` \| `warm` \| `cold` — LeadScorer to'ldiradi |
| stage | Select | `new` \| `contacted` \| `meeting` \| `deal` \| `lost` |
| score | Number | 0–100, LeadScorer to'ldiradi |
| campaign_id | Relation -> Campaign | Qaysi kampaniyadan kelgan |
| assigned_to | Relation -> Staff (yoki Workspace Member) | Mas'ul xodim |

### Campaign (custom obyekt)
`name`, `post_id` (Text/Relation), `spend_usd` (Number), `started_at` (Date).

### Staff (custom obyekt, yoki Twenty "Workspace Member" ishlatiladi)
`name`, `tg_id` (Number), `phone` (Phone), `role` (Text), `habits` (hozircha ishlatilmaydi).

Task uchun alohida custom obyekt yaratilmaydi — Twenty'ning o'z **Tasks** obyekti
ishlatiladi (`crm_adapter.py::TwentyCRM.create_task`/`complete_task`/`list_*_tasks`).

## Zaxira
Twenty muammo chiqarsa — `docs/07-open-source-foundations.md`: "O'z HTMX CRM" ga
`crm_adapter.py` orqali almashtirish mumkin (interfeys — `crm_adapter.CRM` Protocol,
`InMemoryCRM` uning eng oddiy misoli).
