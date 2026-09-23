# 02 — Ma'lumotlar modeli (Postgres)

Alembic migratsiyalar `apps/api/alembic/`. Hamma jadvalda `id uuid`, `created_at`, `updated_at`.
Multi-tenant: har jadvalda `workspace_id` (bitta ega = bitta workspace; keyin agentlik rejimi uchun tayyor).

## Content Engine

```sql
workspace(id, name, owner_tg_id, ig_business_id, timezone)
brand_profile(id, workspace_id, json)              -- ton, taqiq so'zlar, CTA, siz/sen, ranglar
ig_audit(id, workspace_id, json, created_at)       -- kuchli/zaif, post ritmi, hook turlari
reference_video(id, workspace_id, source_url, transcript, structure_json, embedding vector(768))
taste_memory(id, workspace_id, kind, text, reason, embedding vector(768))  -- kind: approved|rejected|note
content_plan(id, workspace_id, week_start, aida_json, status)
script(id, plan_id, day, hook_variants json, body, cta, tts_text, subtitle_json, score, iteration, status)
critic_review(id, script_id, critic, score, reasons json)
asset(id, script_id, kind, uri, meta json)         -- kind: audio|image|depth|video
post(id, script_id, ig_media_id, published_at, variant)
post_metrics(id, post_id, reach, saves, shares, comments, watch_time, fetched_at)
cost_log(id, workspace_id, node, provider, tokens_in, tokens_out, usd, created_at)
```

## CRM + Jarvis

```sql
campaign(id, workspace_id, post_id?, name, spend_usd, started_at)
lead(id, workspace_id, campaign_id, source, name, phone, ig_handle, score, temperature, stage, assigned_to)
   -- source: ig_dm|ig_comment|lead_form|site|phone ; stage: new|contacted|meeting|deal|lost
contact_event(id, lead_id, channel, direction, transcript, summary, created_at)
deal(id, lead_id, amount, currency, closed_at, status)
staff(id, workspace_id, name, tg_id, phone, role, habits json)
task(id, workspace_id, staff_id, lead_id?, title, due_at, status, reminders_sent, escalated_at)
call_log(id, workspace_id, lead_id?, staff_id?, direction, duration_s, recording_uri, transcript, summary, outcome)
jarvis_action(id, workspace_id, type, level, payload json, status, approved_by, executed_at)
   -- level: autonomous|requires_approval
daily_report(id, workspace_id, date, json, sent_at)
```

## Muhim indekslar
- `lead(workspace_id, stage)`, `task(due_at) where status='open'`, `taste_memory` ivfflat on embedding.
- `post_metrics` → `campaign` → `lead`: "qaysi Reels qancha lid/sotuv berdi" so'rovi uchun view `campaign_roi`.
