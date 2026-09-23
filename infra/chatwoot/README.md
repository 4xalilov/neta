# Chatwoot self-host (bosqich 5.2)

`docker-compose.yml` — Rails + Sidekiq + o'z Postgres'i + o'z Redis'i, `ame_default`
tashqi tarmog'iga ulanadi.

DIQQAT: bu compose skelet, `CHATWOOT_VERSION` va ba'zi environment o'zgaruvchilar TAXMIN —
ishga tushirishdan oldin https://www.chatwoot.com/docs/self-hosted bilan solishtiring.

## Ishga tushirish
1. `.env` da qiymatlar bering: `CHATWOOT_VERSION`, `CHATWOOT_SECRET_KEY_BASE`
   (`openssl rand -hex 64`), `CHATWOOT_DB_PASSWORD`, `CHATWOOT_FRONTEND_URL`.
2. `docker network create ame_default` (agar mavjud bo'lmasa).
3. `docker compose -f infra/chatwoot/docker-compose.yml up -d`
4. Birinchi ishga tushirishda migratsiya/tayyorlov kerak bo'lishi mumkin:
   `docker compose -f infra/chatwoot/docker-compose.yml exec chatwoot-rails bundle exec rails db:chatwoot_prepare`
5. `http://localhost:3001` da super-admin/akkaunt yarating.

## Inboxlar (kanallar)
**Settings -> Inboxes -> Add inbox**:
- **Instagram** — DM va kommentlar uchun Meta bilan rasmiy integratsiya (App Review talab
  qiladi, docs/07: "1–2 hafta, erta boshlash kerak", bosqich 3 bilan parallel yuritiladi).
- **Telegram** — bot tokeni bilan ulanadi (bu — mijozlar uchun alohida Telegram bot;
  ega/xodimlar uchun `apps/bot` BIZNIKI Telegram bot ishlatiladi, ular aralashtirilmaydi).
- **Website** — widget skripti sayt chat uchun.

## Webhook -> Jarvis
Hisob darajasidagi **Settings -> Integrations -> Webhooks** (yoki har bir inboxning
**Configuration -> Webhook** bo'limi) da:

- URL: `http://api:8000/webhooks/chatwoot` (docker tarmog'i ichida; tashqi domendan esa
  `https://api.domain.uz/webhooks/chatwoot`).
- Voqealar: kamida `message_created`, `conversation_created`.

Chatwoot standart holatda webhookni imzolamaydi — shuning uchun maxfiy so'zni o'zimiz
qo'shamiz: Chatwoot'ning **Custom HTTP headers** (webhook sozlamasidagi "headers")
imkoniyati orqali `X-Webhook-Secret: <CHATWOOT_WEBHOOK_SECRET>` sarlavhasini qo'shing
(qiymat — `.env` dagi `CHATWOOT_WEBHOOK_SECRET` bilan bir xil). Agar Chatwoot
versiyangizda custom header qo'shib bo'lmasa — nginx/reverse-proxy darajasida qo'shish
yoki `integrations/chatwoot.py::verify_signature` ni shu holatga moslashtirish kerak
bo'ladi (TAXMIN — versiyaga qarab tekshiring).

## API token
Jarvis javob yozishi uchun (`integrations/chatwoot.py::reply`) — **Profile settings ->
Access Token** dan shaxsiy tokenni oling (yoki Agent Bot token, agar yaratilgan bo'lsa)
va `.env` dagi `CHATWOOT_API_TOKEN` ga qo'ying; so'rovlarda `api_access_token` sarlavhasi
bilan yuboriladi. `CHATWOOT_ACCOUNT_ID` — hisob ID'si (URL'da yoki Settings'da ko'rinadi).

## contact <-> lead bog'lanishi
Har yangi kontakt/lid `crm_link` jadvalida (`chatwoot_contact_id`, `twenty_person_id`,
`lead_id`) saqlanadi — `integrations/chatwoot.py::link_contact_to_lead` va
`handle_webhook` (yangi kontaktdan kirish xabari kelsa avtomatik chaqiriladi).
