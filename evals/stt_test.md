# STT + niyat testi (roadmap 5.10) — ega ovozli buyruqlari, 50 ta

Qabul mezoni (docs/03 5-bosqich): ega 10 ovozli buyruqdan ≥ 9 tasini yozmasdan bajartira oladi
(STT + niyat ≥ 90%). Ushbu ro'yxat — referens matn (ega AYNAN shu gapni aytadi), kutilgan
niyat va asosiy ma'lumotlar. Aralash: rasmiy/so'zlashuv (Toshkent), raqamlar, ismlar, ruscha
o'zlashmalar (zakaz, otchyot, skidka, zvonit, srochno, prays, otmena).

Yozib olish: har qatorni telefon Telegram voice'da (shovqinli joyda ham) aytib,
`evals/stt_audio/<N>.ogg` qilib saqlang (`.wav`/`.mp3` ham bo'ladi). Keyin:

```bash
PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m evals.stt_bench \
    --audio-dir evals/stt_audio --providers gemini,whisper --intents --out evals/out/stt/
apps/api/.venv/bin/python -m evals.stt_bench --fake --intents --out evals/out/stt/   # oflayn
```

Test kontekstidagi nomlar: xodimlar — Aziz, Dilnoza, Jasur, Nodira; lidlar — Malika,
Sardor Aliyev; mijozlar (workspace) — Qahva uyi, Fitnes klub Olimp.

Format: `N. <referens matn> → <intent> <entities JSON>`

1. Azizga ayt, zakazni ertaga 3 gacha yopsin → assign_task {"staff_name": "Aziz", "task_title": "zakazni yopish", "due_text": "ertaga 3 gacha"}
2. Hammasiga ha → approve_all {}
3. Kechagi hisobotni ayt → daily_report {"period": "yesterday"}
4. Issiq lidlarga yoz → message_lead {"temperature": "hot"}
5. Fitnes klub uchun 3 ta reels tayyorla → create_brief {"workspace_name": "fitnes klub", "count": 3}
6. Bugun nechta lid keldi? → query_leads {"period": "today"}
7. Dilnozaga eslat, otchyotni bugun 18:00 gacha tashlasin → remind_staff {"staff_name": "Dilnoza", "due_text": "bugun 18:00 gacha"}
8. Ha, yubor → approve {}
9. Yo'q, kerakmas → reject {}
10. Malikaga qo'ng'iroq qil → call_lead {"lead_name": "Malika"}
11. Qancha vazifa kechikyapti? → query_tasks {}
12. Jasurga ayt, yangi klientlarga prays-list jo'natsin, juma kunigacha → assign_task {"staff_name": "Jasur", "due_text": "juma kunigacha"}
13. Bugungi hisobot qani? → daily_report {"period": "today"}
14. Sen deb gapir, rasmiyatchilik kerakmas → update_settings {"setting_key": "pronoun", "setting_value": "sen"}
15. Ovozni Sardorga o'zgartir → update_settings {"setting_key": "voice", "setting_value": "sardor"}
16. Qahva uyiga o't → select_workspace {"workspace_name": "Qahva uyi"}
17. Salom Jarvis, qalaysan? → smalltalk {}
18. Iliq lidlar qancha? → query_leads {"temperature": "warm"}
19. Sovuq lidlarga skidka haqida yozib chiq → message_lead {"temperature": "cold"}
20. Azizda nechta ochiq ish bor? → query_tasks {"staff_name": "Aziz"}
21. Chegirma haqida bitta reels qil, 20 foiz skidka → create_brief {"count": 1}
22. Nodiraga ayt, 2 soatdan keyin mijozga qayta zvonit qilsin → assign_task {"staff_name": "Nodira", "due_text": "2 soatdan keyin"}
23. Sardor Aliyevga qo'ng'iroq qil, srochno → call_lead {"lead_name": "Sardor Aliyev"}
24. Haftalik hisobotni ber → daily_report {"period": "week"}
25. Xodimlarni turtib qo'y, kechikkan ishlar ko'p → remind_staff {}
26. Mayli, tasdiqlayman → approve {}
27. Buni bekor qil → reject {}
28. Hammasini yubor → approve_all {}
29. Sardor Aliyevga yozib qo'y, ertaga uchrashuvga taklif qil → message_lead {"lead_name": "Sardor Aliyev"}
30. Ertaga soat 19:00 da reelsni joyla → schedule_post {"due_text": "ertaga soat 19:00 da"}
31. Rasmiyroq gapir → update_settings {"setting_key": "register", "setting_value": "formal"}
32. Fitnes klubga o't → select_workspace {"workspace_name": "Fitnes klub"}
33. Rahmat, zo'r ishlading → smalltalk {}
34. Kecha nechta sotuv bo'ldi? → daily_report {"period": "yesterday"}
35. Dilnoza opaga topshir: indinga ertalab soat 9 da ofisga kelib, shartnomani imzolasin → assign_task {"staff_name": "Dilnoza", "due_text": "indinga ertalab soat 9 da"}
36. 5 ta issiq lidga qo'ng'iroq qil → call_lead {"temperature": "hot", "count": 5}
37. Bu hafta nechta lid tushdi? → query_leads {"period": "week"}
38. Kuzgi kolleksiya haqida 2 ta video tayyorla → create_brief {"count": 2}
39. Jasurga eslatib qo'y, kontent-planni tushgacha yuborsin → remind_staff {"staff_name": "Jasur", "due_text": "tushgacha"}
40. Anavi narsani qil → unknown {}
41. Otmena, lidga yozma → reject {}
42. Ha, hammasiga roziman → approve_all {}
43. Azizga yangi vazifa: saytdagi narxlarni yangilasin, 3 kundan keyin tayyor bo'lsin → assign_task {"staff_name": "Aziz", "due_text": "3 kundan keyin"}
44. Malikaga yana yoz, javob bermadi → message_lead {"lead_name": "Malika"}
45. Vazifalar holati qanday? → query_tasks {}
46. Qahva uyi uchun yangi menyu haqida reels, bugun kechqurun tayyor bo'lsin → create_brief {"workspace_name": "Qahva uyi"}
47. Olimpga o't → select_workspace {"workspace_name": "Olimp"}
48. Soat uchda Nodiraga ayt, 1 500 000 so'mlik invoysni tekshirsin → assign_task {"staff_name": "Nodira", "due_text": "soat uchda"}
49. Nodiraning kechikkan vazifalari bormi? → query_tasks {"staff_name": "Nodira"}
50. Issiq lidlarga yozvor, skidka 15 foiz deb → message_lead {"temperature": "hot"}
