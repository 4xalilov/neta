Kompozitsiyalar (1080×1920, 30fps) — `src/Root.tsx` da ro'yxatdan o'tgan:
- **ReelsBasic** (1.5): rasmlar + Ken Burns + kinetik subtitr (so'z timing) + audio + CTA — `ReelsBasic.tsx`
- **ReelsParallax** (2.4, stub): `depthUrl` bor sahnalarda chuqurlik xaritasi bilan 2 qatlamli 2.5D parallaks
  (`components/ParallaxImage.tsx`), `depthUrl` yo'q sahnalarda ReelsBasic kabi Ken Burns.

Ikkalasi ham umumiy `components/Reel.tsx` layoutidan foydalanadi. Uzunlik:
`calculateMetadata` → `round(sum(scenes[].durationS) * 30)` kadr (`lib/metadata.ts`).

Props (zod sxema: `src/props.ts`, to'liq tavsif: `apps/render/README.md`):
`{ audioUrl?, cta?, scenes:[{imageUrl, depthUrl?, durationS, words:[{w,start,end}], subtitle?}], brand:{font,color,accent,bg,surface?,logoUrl?} }`
`words[].start/end` — kompozitsiya boshidan soniyalarda.
