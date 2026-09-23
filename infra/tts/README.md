# Navoiy TTS — O'zbek Ovozli Sintez Server

O'zbekcha matndan tabiiy ovoz generatsiyasi uchun self-hosted FastAPI serveri.
[CosyVoice2-0.5B fine-tune](https://huggingface.co/aisha-org/navoiy-tts) asosida.
Litsenziya: Apache 2.0

## Ishni boshlash

### Yo'l-xaritalari bilan

GPU profili bilan (tavsiya etiladi):

```bash
docker compose --profile gpu up -d tts
```

GPU siz (sekin, test uchun):

```bash
docker compose up -d tts
```

### To'g'ridan-to'g'ri Python bilan

```bash
pip install fastapi uvicorn numpy soundfile torch torchaudio

# CosyVoice va model yuklanishini o'rnatish (ixtiyoriy)
pip install huggingface-hub

python server.py
# Server http://localhost:8010 da ishga tushadi
```

## Resurslar

### Minimal talablar

| Kompyuter                  | RAM   | VRAM  | Tezlik | Holat       |
|----------------------------|-------|-------|--------|-------------|
| CPU (PyTorch)              | 8 GB  | —     | sekin  | Ishchi     |
| GPU (RTX 3060, 12 GB)      | 4 GB  | 8 GB  | yaxshi | Tavsiya    |
| GPU (RTX 4090, 24 GB)      | 4 GB  | 6 GB  | juda   | Optimal    |
| Bulut GPU (Vast/RunPod)    | 4 GB  | 8 GB  | yaxshi | ~$0.2/soat |

### CPU bilan ishlash (dev)

```bash
# stub mode — 1 soniyalik jim ovoz qaytaradi
docker compose up -d tts
curl -X POST http://localhost:8010/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Salom dunyo","voice":"neutral"}'
```

### GPU bilan ishlash (ishlab chiqarish)

`docker-compose.yml` da `tts` service profili `gpu`:

```bash
# Avtomatik GPU'ni taqdim qiladi
docker compose --profile gpu up -d tts

# GPU ni tekshirish
docker compose exec tts nvidia-smi
```

## API

### GET /health

```bash
curl http://localhost:8010/health
```

Javob:
```json
{
  "status": "ok",
  "cosyvoice_available": true,
  "model_dir": "/models"
}
```

### POST /synthesize

Uzbek matnni ovozga o'zgartiraddi.

```bash
curl -X POST http://localhost:8010/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Xush kelibsiz Navoiy TTS ga",
    "voice": "neutral",
    "speed": 1.0
  }' \
  --output output.wav
```

**Parametrlar:**

- `text` (string, majburiy): O'zbekcha matn
- `voice` (string, default "neutral"): `"neutral"` yoki `"expressive"`
- `speed` (float, default 1.0): Suhbat tezligi (0.5–2.0)

**Javob:** WAV audio (24 kHz, mono)

## Konfiguratsiya

`.env` faylda:

```bash
# Navoiy TTS ishlatish
TTS_PROVIDER=navoiy
NAVOIY_URL=http://tts:8010

# Yoki: edge (bepul, zaxira), azure (rasmiy, to'lanadi), aisha (mahalliy)
TTS_FALLBACK=azure
```

### Taqdim etilganlar

- **navoiy** — self-hosted, hech narsa to'lanmaydi (server xarajati)
- **edge** — bepul, lekin norasmiy (vaqti-vaqti 403 xatosi)
- **azure** — rasmiy, ~$0.006 har 30s Reels uchun
- **aisha** — mahalliy, eng tabiiy o'zbek urg'u (UZS to'lash)

## Model yuklanishi

CosyVoice va Navoiy TTS og'irligi:

```bash
# Birinchi ishga tushirish vaqtida avtomatik yuklanadi
# yoki Dockerfile assembly paytida:

RUN pip install huggingface-hub && \
    python -c "
    from huggingface_hub import snapshot_download
    snapshot_download('aisha-org/navoiy-tts', local_dir='/models')
    "
```

## Xatoliklarni aniqlash

### 1. CosyVoice olib o'rnatilmagan

```
WARNING CosyVoice dependencies not available.
Server will run in stub mode (returns silence WAV).
```

**Yechim:** Dockerfile `pip install FunAudioLLM` qatorini faol qiling va qayta build qiling:

```bash
docker compose --profile gpu build --no-cache tts
```

### 2. VRAM natamom

```
RuntimeError: CUDA out of memory
```

**Yechim:**
- CPU mode'ga o'ting: `docker compose up tts`
- Bulut GPU: Vast.ai yoki RunPod (o'zbek kompyuteri sifatida)

### 3. API 500 xatosi qaytaradi

```bash
docker compose logs tts
```

Loglarni tekshiring. Ehtimol, model yuklanmagan.

## Test

```bash
# Stub mode (CPU)
docker compose up -d tts
sleep 2
curl -X POST http://localhost:8010/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Test"}' \
  --output test.wav

# WAV fayli tayyor
ffprobe test.wav
# Duration: 1 second, 24 kHz, mono (stub mode)
```

## Tuning

### Tezlikni tekshirish

20 ta jumla synthesis time:

```bash
time for i in {1..20}; do
  curl -s -X POST http://localhost:8010/synthesize \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"Jumla $i\"}" \
    > /dev/null
done
```

- CPU: ~5–10 sekund / jumla (sekin)
- GPU: ~0.1–0.2 sekund / jumla (juda tez)

### Memory xayotiyati

Persistent volume `ttsmodels` model loadi uchun:

```bash
docker volume ls | grep ttsmodels
docker volume inspect neta_ttsmodels
```

## Litsenziya

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)

Model: [aisha-org/navoiy-tts](https://huggingface.co/aisha-org/navoiy-tts)
