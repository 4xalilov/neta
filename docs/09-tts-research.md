# 09 — O'zbek TTS tadqiqoti va qaror (2026-09)

Maqsad: Reels ovozi va Jarvis ovozi uchun arzon, sifatli, so'z-timing beradigan TTS.

## Nomzodlar
| # | Nomzod | Turi | Litsenziya / narx | Sifat | So'z timing | Talab | Havola |
|---|---|---|---|---|---|---|---|
| 1 | **Navoiy TTS** (Aisha, CosyVoice2-0.5B fine-tune) | ochiq kod, self-host | Apache 2.0, bepul | yuqori, ifodali (neutral/expressive), lotin+kirill normalizatori bor | yo'q → forced alignment | GPU 6–8 GB VRAM tavsiya (CPU sekin) | https://huggingface.co/aisha-org/navoiy-tts , https://aisha.group/en/blog/navoiy-tts-open-source-uzbek-text-to-speech |
| 2 | **Sayro TTS 1.7B** (uzlm, Qwen3-TTS) | ochiq kod | ochiq checkpoint | yuqori | yo'q | GPU ≥ 8 GB | https://huggingface.co/uzlm/sayro-tts-1.7B |
| 3 | **MMS-TTS uzb** (Meta, VITS) | ochiq kod | CC-BY-NC 4.0 (tijorat cheklov!) | o'rta, robotik | yo'q | CPU yetarli | https://huggingface.co/facebook/mms-tts-uzb-script_cyrillic |
| 4 | **TurkicTTS** (ISSAI) | ochiq kod | tadqiqot | o'rta | yo'q | GPU/CPU | https://github.com/IS2AI/TurkicTTS |
| 5 | **Edge-TTS** (Microsoft uz-UZ Madina/Sardor, norasmiy) | bulut, kalitsiz | bepul, lekin norasmiy (403 uzilishlar bo'ladi) | yuqori (Azure bilan bir xil ovoz) | **bor** (WordBoundary) | internet | https://github.com/rany2/edge-tts |
| 6 | **Azure Speech** uz-UZ | bulut, rasmiy | ~$16 / 1M belgi (neural) | yuqori | **bor** | kalit | https://learn.microsoft.com/azure/ai-services/speech-service/ |
| 7 | **Aisha AI API** (uzbekvoice muallifi) | bulut, rasmiy, O'zbekiston | UZS, foydalanganga to'lov, obuna yo'q | yuqori, o'zbekcha urg'u eng tabiiy | tekshiriladi | kalit | https://aisha.group/en/tts-uzbek , https://aisha.group/en/pricing |
| 8 | **uzbekvoice.ai** | bulut / korpus | STT API ochiq; TTS — so'rov bilan | — | — | — | https://uzbekvoice.ai/en-US/developers/api/stt |

## Qaror (adapter `engine/integrations/tts.py`, provayder `.env: TTS_PROVIDER`)
1. **Ishlab chiqish va qoralama:** `edge` — bepul, so'z-timing beradi. 403 bo'lsa avtomatik `azure` yoki `navoiy` ga o'tadi (`TTS_FALLBACK`).
2. **Ishlab chiqarish, arzon:** `navoiy` — o'z serverimizda (`infra/tts/` konteyner, HTTP `/synthesize`), narx = server. 30s Reels uchun $0 marginal.
   So'z-timing: `whisperx`/`stable-ts` forced alignment yoki proporsional taxmin (`tts.estimate_word_timings`).
3. **Zaxira rasmiy:** `azure` (word boundary bilan) yoki `aisha` (eng tabiiy o'zbek urg'u, mahalliy to'lov).
4. MMS-TTS faqat test uchun (NC litsenziya). Sayro — GPU bo'lsa Navoiy bilan A/B.

Bitta 30s Reels TTS xarajati: edge $0 · navoiy $0 (+server) · azure ≈ $0.006 · aisha ≈ arzon (UZS, tekshiriladi).

## Sinov rejasi (bosqich 1.2, `evals/tts_test.md`)
Har provayderdan 20 jumla → ega 1–5 baholaydi: apostrof, raqam, chet so'z, savol intonatsiyasi, tez temp.
GPU server: Navoiy/Sayro uchun kamida RTX 3060 12 GB yoki bulut GPU (Vast/RunPod ~ $0.2/soat, faqat render vaqtida).
