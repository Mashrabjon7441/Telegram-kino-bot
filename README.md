# Telegram Kino Bot (Kod orqali kino ko'rish)

Ushbu Telegram bot foydalanuvchilarga maxsus kod yuborish orqali kinolarni to'g'ridan-to'g'ri Telegramdan yuklab olish imkonini beradi. Shuningdek, botda homiy kanallarga a'zolikni tekshirish va reklama tarqatish tizimlari mavjud.

## Xususiyatlari
- **Kino qidirish**: Kod yuboriladi va bot ma'lumotlar bazasidan kinoni topib uning qismlarini (seriyalarini) inline tugmalar orqali yuboradi.
- **Bitta kodga bir nechta seriya**: Admin bir xil kod ostida cheksiz miqdorda video/hujjat fayllarini yuklay oladi.
- **Avtomatik random kodlar**: Yangi kino yaratilganda bot o'zi tasodifiy 4-xonali unikal kod biriktiradi.
- **Majburiy a'zolik (Forced Subscribe)**: Foydalanuvchi botdan foydalanishdan oldin admin tomonidan belgilangan kanallarga a'zo bo'lishi shart bo'ladi.
- **Reklama yuborish (Broadcast)**: Admin bot a'zolariga istalgan ko'rinishdagi xabarni (rasm, video, matn, audio) bitta bosish orqali tarqata oladi.
- **Admin panel**: Quyidagi bo'limlardan iborat:
  - Yangi kino yaratish va mavjudiga yangi seriya qo'shish.
  - Kinoni o'chirish.
  - Homiylar / Majburiy kanallarni boshqarish.
  - Bot a'zolariga reklama yuborish.
  - Foydalanuvchilar soni (statistika)ni ko'rish.

## Sozlash va ishga tushirish

### 1-qadam: Kutubxonalarni o'rnatish
Terminal (CMD) yoki buyruqlar satrida loyiha papkasiga o'tib, quyidagi buyruqni ishga tushiring:
```bash
pip install -r requirements.txt
```

### 2-qadam: Bot Token va Admin ID kiritish
`config.py` faylini oching va quyidagi ma'lumotlarni o'zgartiring:
- `BOT_TOKEN`: @BotFather dan olingan bot tokeningizni yozing.
- `ADMIN_IDS`: Adminlarning Telegram ID sini yozing (Masalan: `[790123456]`).

### 3-qadam: Botni ishga tushirish
Loyihani ishga tushirish uchun konsolda quyidagi buyruqni bering:
```bash
python main.py
```

## Admin foydalanish qo'llanmasi

### Reklama tarqatish:
1. `⚙️ Admin panel` -> **`✉️ Reklama yuborish`** tugmasini tanlang.
2. Botga reklama postini yuboring. Unda rasm, video, matn bo'lishi yoki boshqa kanaldan forward-xabar bo'lishi ham mumkin.
3. Bot tasdiqlash uchun inline tugma yuboradi. `✅ Tasdiqlash` tugmasini bossangiz, reklama barcha foydalanuvchilarga jo'natiladi va yakunida hisobot chiqariladi.
