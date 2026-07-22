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



## Render.com serveriga deploy qilish yo'riqnomasi

1. **GitHub repository yaratish va kodlarni yuklash:**
   - GitHub.com saytida yangi repository yarating (Masalan: `telegram-kino-bot`).
   - Terminalda ushbu buyruqlarni ketma-ket bajaring:
     ```bash
     git add .
     git commit -m "Deploy for Render"
     git remote add origin https://github.com/USERNAME/telegram-kino-bot.git
     git branch -M main
     git push -u origin main
     ```

2. **Render.com ga ulash:**
   - [Render.com](https://render.com) saytiga kiring va akkountingizga kiring.
   - **New +** tugmasini bosing va **Background Worker** xizmatini tanlang.
   - GitHub repongizni tanlang.
   - Sozlamalarda:
     - **Name**: `telegram-kino-bot`
     - **Environment**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `python main.py`
   - **Environment Variables** bo'limida quyidagi o'zgaruvchilarni qo'shing:
     - `BOT_TOKEN`: BotFather'dan olingan bot tokeningiz
     - `ADMIN_IDS`: Telegram ID ingiz (masalan: `7637932499`)
   - **Create Background Worker** tugmasini bosing.

Bot 24/7 rejimida Render serverida ishlay boshlaydi!

