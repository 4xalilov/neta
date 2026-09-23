"""Deterministik, tarmoqsiz "fake" kritik — ``engine.evals.run --fake`` uchun.

Bu haqiqiy LLM emas: ``llm.set_fake`` handleri sifatida ishlaydi, prompt matnining
birinchi qatoridan (``# Rol: UzCritic`` va h.k. — ``engine/agents/prompts/*.md``)
qaysi kritik chaqirilganini aniqlaydi, so'ng ``use()`` orqali o'rnatilgan joriy
ssenariy/brend/did ustida oddiy qoida-asosidagi tekshiruvlarni bajaradi.

Maqsad — ``docs/03-roadmap.md`` 2.3: runner va testlar tarmoqsiz/LLM'siz ishlasin va
``evals/scripts/`` dagi 11 ta atayin nuqson (flaw) kategoriyasi ishonchli
aniqlanishini tasdiqlasin. Ballar rubrikadagi haqiqiy og'irliklarga emas — faqat
yaxshi/yomon ssenariyni ishonchli ajratishga mo'ljallangan (har buzilish uchun bir xil
-3/-4/-5 chegirma, natija hech qachon aralashmasin uchun).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_KALKA_PATTERNS = (
    "amalga oshirishni boshlaymiz",
    "amalga oshirib boradi",
    "sodir bo'lmoqda",
    "qilib olish",
)

_JARGON_WORDS = ("voobshe", "tema bo'yicha", "konkretno", "vobshem")

_ABBREV_RE = re.compile(r"\bva h\.k\.|\bt\.r\.\b|\bva hk\b", re.IGNORECASE)

_SIZ_RE = re.compile(r"\bsiz\w*", re.IGNORECASE)
_SEN_RE = re.compile(r"\bsen(ga|ing|da|dan)?\b", re.IGNORECASE)

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_CONTRAST_WORDS = ("lekin", "ammo", "aslida", "biroq")

_UZ_DEDUCTION = 3
_BRAND_FORBIDDEN_DEDUCTION = 5
_BRAND_TASTE_DEDUCTION = 4
_HOOK_NO_CUE_DEDUCTION = 4
_HOOK_DISCONNECT_DEDUCTION = 3


def _sentences(*texts: str) -> list[str]:
    out: list[str] = []
    for t in texts:
        out.extend(s.strip() for s in _SENT_SPLIT_RE.split(t or "") if s.strip())
    return out


def _max_sentence_words(*texts: str) -> int:
    return max((len(s.split()) for s in _sentences(*texts)), default=0)


@dataclass
class HeuristicCritic:
    """``llm.set_fake(HeuristicCritic())`` handleri. Har ssenariyni tekshirishdan oldin
    ``use(script, brand_profile, taste_memory)`` chaqiring."""

    script: dict[str, Any] = field(default_factory=dict)
    brand: dict[str, Any] = field(default_factory=dict)
    taste: list[Any] = field(default_factory=list)

    def use(self, script: dict[str, Any], brand: dict[str, Any] | None = None,
            taste: list[Any] | None = None) -> None:
        self.script = script
        self.brand = brand or {}
        self.taste = taste or []

    def __call__(self, tier: str, system: str, user: str) -> dict[str, Any]:
        head = system.splitlines()[0] if system else ""
        if "UzCritic" in head:
            return self._uz()
        if "BrandCritic" in head:
            return self._brand()
        if "HookCritic" in head:
            return self._hook()
        raise AssertionError(f"heuristic_critic: noma'lum prompt sarlavhasi: {head!r}")

    # ------------------------------------------------------------ UzCritic

    def _uz(self) -> dict[str, Any]:
        script = self.script
        body = script.get("body", "")
        tts = script.get("tts_text", "")
        cta = script.get("cta", "")
        combined = f"{body} {tts} {cta}"

        score = 10
        reasons: list[str] = []
        fixes: list[str] = []

        for pat in _KALKA_PATTERNS:
            if pat in combined:
                score -= _UZ_DEDUCTION
                reasons.append(f'kalka/ruscha konstruksiya: "{pat}"')
                fixes.append(f'"{pat}" -> tabiiyroq o\'zbekcha ibora bilan almashtiring')
                break

        if _SIZ_RE.search(combined) and _SEN_RE.search(combined):
            score -= _UZ_DEDUCTION
            reasons.append("murojaat shakli aralashgan (matnda ham \"siz\", ham \"sen\" bor)")
            fixes.append('butun matn davomida faqat bitta murojaat shaklini ishlating')

        if any(ch.isdigit() for ch in tts):
            score -= _UZ_DEDUCTION
            reasons.append("tts_text ichida raqam so'zga aylantirilmagan")
            fixes.append('raqamlarni so\'z bilan yozing (masalan "15%" -> "o\'n besh foiz")')

        if _ABBREV_RE.search(tts):
            score -= _UZ_DEDUCTION
            reasons.append("tts_text ichida ochilmagan qisqartma bor")
            fixes.append('qisqartmani to\'liq so\'z bilan yozing (masalan "va h.k." -> "va hokazo")')

        long_subtitle = next(
            (sc.get("subtitle", "") for sc in script.get("scenes", [])
             if len(sc.get("subtitle", "")) > 42), None,
        )
        if long_subtitle is not None:
            score -= _UZ_DEDUCTION
            reasons.append(f'subtitr 42 belgidan uzun: "{long_subtitle}" ({len(long_subtitle)} belgi)')
            fixes.append("subtitrni so'z chegarasida qisqartiring (<= 42 belgi)")

        allowed = {w.lower() for w in (self.brand.get("allowed_loanwords") or [])}
        for w in _JARGON_WORDS:
            if w in combined.lower() and w not in allowed:
                score -= _UZ_DEDUCTION
                reasons.append(f'ruxsatsiz jargon/ruscha so\'z: "{w}"')
                fixes.append(f'"{w}" o\'rniga o\'zbekcha muqobilini ishlating')
                break

        if _max_sentence_words(body, tts) > 18:
            score -= _UZ_DEDUCTION
            reasons.append("18 so'zdan uzun jumla bor (TTS intonatsiyasi uchun noqulay)")
            fixes.append("uzun jumlani ikki qisqa jumlaga bo'ling")

        return {"score": max(0, score), "reasons": reasons, "fixes": fixes}

    # --------------------------------------------------------- BrandCritic

    def _brand(self) -> dict[str, Any]:
        script = self.script
        combined = " ".join([
            script.get("body", ""), script.get("cta", ""),
            script.get("tts_text", ""), script.get("display_text", ""),
            *(script.get("hooks") or []),
        ]).lower()

        score = 10
        reasons: list[str] = []
        fixes: list[str] = []

        for w in self.brand.get("forbidden_words") or []:
            if w.lower() in combined:
                score -= _BRAND_FORBIDDEN_DEDUCTION
                reasons.append(f'taqiqlangan so\'z/ibora ishlatilgan: "{w}"')
                fixes.append(f'"{w}" iborasini olib tashlang')

        for item in self.taste:
            trigger = (item.get("trigger_phrase") if isinstance(item, dict) else str(item)) or ""
            if trigger and trigger.lower() in combined:
                reason = item.get("reason", trigger) if isinstance(item, dict) else trigger
                score -= _BRAND_TASTE_DEDUCTION
                reasons.append(f"avval rad etilgan sabab takrorlandi: {reason}")
                fixes.append("bu ibora/uslubni qayta ishlatmang (taste_memory)")

        return {"score": max(0, score), "reasons": reasons, "fixes": fixes}

    # ---------------------------------------------------------- HookCritic

    def _hook(self) -> dict[str, Any]:
        hooks: list[str] = self.script.get("hooks") or [""]
        body = self.script.get("body", "")

        score = 10
        reasons: list[str] = []
        fixes: list[str] = []

        def has_cue(h: str) -> bool:
            return "?" in h or any(ch.isdigit() for ch in h) or \
                any(w in h.lower() for w in _CONTRAST_WORDS)

        cued = [i for i, h in enumerate(hooks) if has_cue(h)]
        if not cued:
            score -= _HOOK_NO_CUE_DEDUCTION
            reasons.append("hech qaysi hook 0-3s ichida aniq savol/raqam/qarama-qarshilik bermaydi")
            fixes.append("hookka savol belgisi, raqam yoki qarama-qarshilik (\"lekin\") qo'shing")
            best_idx = 0
        else:
            best_idx = cued[0]

        best_hook = hooks[best_idx] if hooks else ""
        numbers = re.findall(r"\d+", best_hook)
        if numbers and not any(n in body for n in numbers):
            score -= _HOOK_DISCONNECT_DEDUCTION
            reasons.append("hook bergan raqam/va'da body'da davom etmaydi (uzilish)")
            fixes.append("body'da hookdagi raqam/va'dani aniq tasdiqlang")

        return {"score": max(0, score), "best_hook_idx": best_idx,
                "reasons": reasons, "fixes": fixes}
