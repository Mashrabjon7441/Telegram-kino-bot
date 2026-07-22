import telebot
from telebot import types
import config
import database
import random

# Initialize database
database.init_db()

# Initialize bot
bot = telebot.TeleBot(config.BOT_TOKEN)

# Temporary dictionary to store admin states
admin_states = {}

def is_admin(user_id):
    return user_id in config.ADMIN_IDS

# Helper to generate unique random code
def generate_unique_code():
    while True:
        code = str(random.randint(1000, 9999))
        if not database.get_movie(code):
            return code

# Keyboards
def get_main_keyboard(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = types.KeyboardButton("🔍 Kino qidirish")
    keyboard.add(btn_search)
    
    if is_admin(user_id):
        btn_admin = types.KeyboardButton("⚙️ Admin panel")
        keyboard.add(btn_admin)
    return keyboard

def get_admin_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_add = types.KeyboardButton("➕ Kino qo'shish")
    btn_del = types.KeyboardButton("❌ Kino o'chirish")
    btn_list = types.KeyboardButton("📋 Barcha kinolar")
    btn_stats = types.KeyboardButton("📊 Statistika")
    btn_channels = types.KeyboardButton("📢 Homiylar / Kanallar")
    btn_adv = types.KeyboardButton("✉️ Reklama yuborish")
    btn_back = types.KeyboardButton("⬅️ Bosh sahifa")
    keyboard.row(btn_add, btn_del)
    keyboard.row(btn_list, btn_stats)
    keyboard.row(btn_channels, btn_adv)
    keyboard.row(btn_back)
    return keyboard

def get_channels_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_add_ch = types.KeyboardButton("➕ Kanal qo'shish")
    btn_del_ch = types.KeyboardButton("❌ Kanal o'chirish")
    btn_list_ch = types.KeyboardButton("📋 Kanallar ro'yxati")
    btn_back_ch = types.KeyboardButton("⬅️ Admin panelga qaytish")
    keyboard.row(btn_add_ch, btn_del_ch)
    keyboard.row(btn_list_ch, btn_back_ch)
    return keyboard

# Channel subscription check function
def get_unsubscribed_channels(user_id):
    if is_admin(user_id):
        return []
    
    channels = database.get_channels()
    unsubscribed = []
    
    for ch_id, title, invite_link in channels:
        try:
            res = bot.get_chat_member(ch_id, user_id)
            if res.status in ['left', 'kicked']:
                unsubscribed.append((title, invite_link))
        except Exception as e:
            print(f"Chat status checking error for {ch_id}: {e}")
            
    return unsubscribed

def check_must_join(message):
    unsubscribed = get_unsubscribed_channels(message.from_user.id)
    if unsubscribed:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for title, invite_link in unsubscribed:
            markup.add(types.InlineKeyboardButton(text=f"📢 {title}", url=invite_link))
        
        markup.add(types.InlineKeyboardButton(text="🔄 Tasdiqlash", callback_data="check_sub"))
        
        bot.send_message(
            message.chat.id,
            "⚠️ **Botdan foydalanish uchun quyidagi homiy kanallariga a'zo bo'lishingiz zarur:**\n\nA'zo bo'lgach, *Tasdiqlash* tugmasini bosing.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return False
    return True

# /start command
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username
    database.add_user(user_id, username)
    
    if not is_admin(user_id):
        if not check_must_join(message):
            return
            
    welcome_text = (
        f"Assalomu alaykum, {message.from_user.first_name}!\n\n"
        "🎬 Kinolarni kod orqali ko'rish botiga xush kelibsiz!\n"
        "Kino ko'rish uchun uning kodini yuboring (Masalan: 1230)."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard(user_id))

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "check_sub":
        unsubscribed = get_unsubscribed_channels(user_id)
        if unsubscribed:
            bot.answer_callback_query(call.id, "❌ Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "✅ Muvaffaqiyatli a'zo bo'ldingiz! Endi botdan foydalanishingiz mumkin.", show_alert=True)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            welcome_text = (
                f"Assalomu alaykum, {call.from_user.first_name}!\n\n"
                "🎬 Kinolarni kod orqali ko'rish botiga xush kelibsiz!\n"
                "Kino ko'rish uchun uning kodini yuboring (Masalan: 1230)."
            )
            bot.send_message(call.message.chat.id, welcome_text, reply_markup=get_main_keyboard(user_id))
            
    elif call.data == "admin_new_movie":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Yangi kino nomini (sarlavhasini) kiriting (Bekor qilish uchun 'bekor' deb yozing):")
        bot.register_next_step_handler(msg, process_new_movie_title)
        
    elif call.data == "admin_exist_movie":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Mavjud kinoning kodini yuboring (Masalan: 3201):")
        bot.register_next_step_handler(msg, process_existing_movie_code)
            
    elif call.data.startswith("add_more_ep:"):
        code = call.data.split(":")[1]
        bot.answer_callback_query(call.id)
        ask_for_episode_file(call.message, code)
        
    elif call.data == "finish_add_eps":
        bot.answer_callback_query(call.id, "Tizim yakunlandi!")
        bot.send_message(call.message.chat.id, "Kino va barcha seriyalar bazaga kiritildi! 🎥", reply_markup=get_admin_keyboard())
        
    elif call.data.startswith("play_ep:"):
        ep_id = int(call.data.split(":")[1])
        episode = database.get_episode_by_id(ep_id)
        if episode:
            file_id, episode_title, movie_code = episode
            movie = database.get_movie(movie_code)
            movie_title = movie[1] if movie else ""
            
            bot.answer_callback_query(call.id, f"Yuklanmoqda: {episode_title}")
            bot.send_chat_action(call.message.chat.id, 'upload_video')
            
            caption_full = f"🎬 **Kino nomi:** {movie_title}\n📌 **Qism:** {episode_title}\n🔑 **Kodi:** {movie_code}"
            try:
                bot.send_video(call.message.chat.id, file_id, caption=caption_full, parse_mode="Markdown")
            except Exception:
                try:
                    bot.send_document(call.message.chat.id, file_id, caption=caption_full, parse_mode="Markdown")
                except Exception as e:
                    bot.send_message(call.message.chat.id, f"Kino yuborishda xatolik yuz berdi: {e}")
        else:
            bot.answer_callback_query(call.id, "❌ Ushbu qism topilmadi!", show_alert=True)

    elif call.data.startswith("send_adv:"):
        _, from_chat_id, msg_id = call.data.split(":")
        from_chat_id = int(from_chat_id)
        msg_id = int(msg_id)
        
        bot.answer_callback_query(call.id, "Reklama yuborilmoqda...")
        bot.edit_message_text("Reklama barchaga yuborilmoqda... Iltimos kuting...", call.message.chat.id, call.message.message_id)
        
        users = database.get_users()
        success_count = 0
        fail_count = 0
        
        for u_id in users:
            try:
                bot.copy_message(chat_id=u_id, from_chat_id=from_chat_id, message_id=msg_id)
                success_count += 1
            except Exception as e:
                print(f"Ad delivery fail for {u_id}: {e}")
                fail_count += 1
                
        status_text = (
            f"📢 **Reklama tarqatish yakunlandi!**\n\n"
            f"✅ Yetkazildi: {success_count} ta foydalanuvchiga\n"
            f"❌ Yuborilmadi (bloklaganlar): {fail_count} ta"
        )
        bot.send_message(call.message.chat.id, status_text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
        
    elif call.data == "cancel_adv":
        bot.answer_callback_query(call.id, "Bekor qilindi")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Reklama yuborish bekor qilindi.", reply_markup=get_admin_keyboard())

# Text messages handler
@bot.message_handler(func=lambda msg: True)
def text_handler(message):
    user_id = message.from_user.id
    text = message.text

    # Check joining first
    if not is_admin(user_id):
        if not check_must_join(message):
            return

    # Normal commands
    if text == "🔍 Kino qidirish":
        bot.send_message(message.chat.id, "Kino kodini kiriting (Masalan: 1010):")
        return

    elif text == "⚙️ Admin panel" and is_admin(user_id):
        bot.send_message(message.chat.id, "Admin panelga xush kelibsiz. Amalni tanlaning:", reply_markup=get_admin_keyboard())
        return

    elif text == "⬅️ Bosh sahifa":
        bot.send_message(message.chat.id, "Bosh sahifa", reply_markup=get_main_keyboard(user_id))
        return

    # admin-only sections
    elif text == "➕ Kino qo'shish" and is_admin(user_id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(text="🆕 Yangi kino yaratish (Kod avtomatik beriladi)", callback_data="admin_new_movie"),
            types.InlineKeyboardButton(text="➕ Mavjud kinoga yangi qism qo'shish", callback_data="admin_exist_movie")
        )
        bot.send_message(message.chat.id, "Kino qo'shish turini tanlang:", reply_markup=markup)
        return

    elif text == "❌ Kino o'chirish" and is_admin(user_id):
        msg = bot.send_message(message.chat.id, "O'chiriladigan kino kodini kiriting (Barcha seriyalari ham o'chib ketadi):")
        bot.register_next_step_handler(msg, process_movie_delete)
        return

    elif text == "📋 Barcha kinolar" and is_admin(user_id):
        movies = database.get_all_movies()
        if not movies:
            bot.send_message(message.chat.id, "Hozircha ma'lumotlar bazasida kinolar yo'q.")
            return
        
        response = "📋 **Kinolar ro'yxati (kod - nomi):**\n\n"
        for code, title in movies:
            response += f"🔑 `{code}` - {title}\n"
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
        return

    elif text == "📊 Statistika" and is_admin(user_id):
        count = database.get_users_count()
        bot.send_message(message.chat.id, f"📊 Bot a'zolari soni (foydalanuvchilar): {count} ta")
        return

    # Channel configuration handlers
    elif text == "📢 Homiylar / Kanallar" and is_admin(user_id):
        bot.send_message(message.chat.id, "Kanallarni boshqarish bo'limi:", reply_markup=get_channels_keyboard())
        return

    elif text == "⬅️ Admin panelga qaytish" and is_admin(user_id):
        bot.send_message(message.chat.id, "Admin panelga qaytdingiz:", reply_markup=get_admin_keyboard())
        return

    elif text == "➕ Kanal qo'shish" and is_admin(user_id):
        msg = bot.send_message(message.chat.id, "Kanalning ID yoki foydalanuvchi nomini kiriting (Masalan: @kanal_nomi yoki -100123456789):\n⚠️ Diqqat: Bot shu kanalda administrator bo'lishi shart!")
        bot.register_next_step_handler(msg, process_channel_id)
        return

    elif text == "❌ Kanal o'chirish" and is_admin(user_id):
        msg = bot.send_message(message.chat.id, "O'chiriladigan kanal foydalanuvchi nomini kiriting:")
        bot.register_next_step_handler(msg, process_channel_delete)
        return

    elif text == "📋 Kanallar ro'yxati" and is_admin(user_id):
        channels = database.get_channels()
        if not channels:
            bot.send_message(message.chat.id, "Hozircha majburiy a'zolikka qo'shilgan kanallar yo'q.")
            return
        
        response = "📋 **Majburiy a'zolikdagi kanallar:**\n\n"
        for ch_id, title, invite_link in channels:
            response += f"📢 [{title}]({invite_link}) (`{ch_id}`)\n"
        bot.send_message(message.chat.id, response, parse_mode="Markdown", disable_web_page_preview=True)
        return

    # Advertising handler
    elif text == "✉️ Reklama yuborish" and is_admin(user_id):
        msg = bot.send_message(message.chat.id, "Foydalanuvchilarga yubormoqchi bo'lgan reklama xabarini yozib/fayl shaklida yuboring (Text, rasm, video, audio yoki ixtiyoriy format):\n\nBekor qilish uchun 'bekor' deb yozing.")
        bot.register_next_step_handler(msg, process_adv_message)
        return

    # User search movie by code
    code = text.strip()
    movie = database.get_movie(code)
    
    if movie:
        _, title, caption = movie
        episodes = database.get_episodes(code)
        
        if not episodes:
            bot.send_message(message.chat.id, f"⚠️ Ushbu `{code}` kodi bilan loyiha bor, ammo unga hali biron-bir qism yuklanmagan.", parse_mode="Markdown")
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ep_id, ep_title, _ in episodes:
            markup.add(types.InlineKeyboardButton(text=f"🎬 {ep_title}", callback_data=f"play_ep:{ep_id}"))
            
        caption_full = f"🎬 **Kino nomi:** {title}\n🔑 **Kodi:** {code}"
        if caption:
            caption_full += f"\n\n📝 **Tavsif:** {caption}"
            
        caption_full += "\n\nTomosha qilish uchun quyidagi tugmani bosing 👇"
        bot.send_message(message.chat.id, caption_full, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Bunday kodli kino topilmadi. Kodni tekshirib qaytadan kiritib ko'ring.")

# ----------------- ADD MOVIE WORKFLOW -----------------

def process_existing_movie_code(message):
    code = message.text.strip()
    if not code:
        bot.send_message(message.chat.id, "Xato: Kod bo'sh bo'lishi mumkin emas.", reply_markup=get_admin_keyboard())
        return

    existing = database.get_movie(code)
    if existing:
        title = existing[1]
        bot.send_message(message.chat.id, f"🎬 Mavjud film: *{title}* (Kod: `{code}`)\nYangi qism qo'shish jarayoni boshlanadi.", parse_mode="Markdown")
        ask_for_episode_file(message, code)
    else:
        bot.send_message(message.chat.id, f"❌ `{code}` kodli kino topilmadi. Avval yangi yaratib oling.", reply_markup=get_admin_keyboard())

def process_new_movie_title(message):
    title = message.text.strip()
    if not title:
        bot.send_message(message.chat.id, "Kino nomi bo'sh bo'lishi mumkin emas. Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
        
    if title.lower() == 'bekor':
        bot.send_message(message.chat.id, "Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
        
    msg = bot.send_message(message.chat.id, "Kino uchun qisqacha tavsif yuboring (yoki bekor qilmoqchi bo'lsangiz '-' kiriting):")
    bot.register_next_step_handler(msg, process_new_movie_caption, title)

def process_new_movie_caption(message, title):
    caption = message.text.strip()
    if caption == '-':
        caption = ""
        
    # Generate random unique code
    code = generate_unique_code()
    
    success = database.add_movie(code, title, caption)
    if success:
        bot.send_message(
            message.chat.id, 
            f"✅ Yangi kino yaratildi!\n🔑 Briketirilgan Kod: `{code}`\n🎬 Nomi: *{title}*\n\nEndi ushbu kod ostiga qismlarini (video fayllarini) yuklaymiz.", 
            parse_mode="Markdown"
        )
        ask_for_episode_file(message, code)
    else:
        bot.send_message(message.chat.id, "Xatolik yuz berdi ma'lumotlar bazasida.", reply_markup=get_admin_keyboard())

def ask_for_episode_file(message, code):
    msg = bot.send_message(message.chat.id, f"Kino videosini yoki faylini yuklang (Yoki bekor qilish uchun 'bekor' deb yozing):")
    bot.register_next_step_handler(msg, process_add_episode_file, code)

def process_add_episode_file(message, code):
    if message.text and message.text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
        
    file_id = None
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id
        
    if not file_id:
        msg = bot.send_message(message.chat.id, "Xato: Faqat video yoki hujjat yuboring (yoki 'bekor' deb yozing):")
        bot.register_next_step_handler(msg, process_add_episode_file, code)
        return
        
    msg = bot.send_message(message.chat.id, "Kino qismi sarlavhasini kiriting (Masalan: *1-qism*, *2-qism* yoki *To'liq film*):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_episode_title, code, file_id)

def process_add_episode_title(message, code, file_id):
    episode_title = message.text.strip()
    if not episode_title:
        episode_title = "Kino qismi"
        
    success = database.add_episode(code, episode_title, file_id)
    if success:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(text="➕ Yana qism qo'shish", callback_data=f"add_more_ep:{code}"),
            types.InlineKeyboardButton(text="✅ Yakunlash", callback_data="finish_add_eps")
        )
        bot.send_message(message.chat.id, f"✅ '{episode_title}' muvaffaqiyatli saqlandi! Yana qism qo'shasizmi?", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Xatolik yuz berdi ma'lumot saqlanishida.", reply_markup=get_admin_keyboard())

# ----------------- ADVERTISING BROADCAST WORKFLOW -----------------

def process_adv_message(message):
    user_id = message.from_user.id
    if message.text and message.text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Reklama yuborish bekor qilindi.", reply_markup=get_admin_keyboard())
        return
        
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"send_adv:{message.chat.id}:{message.message_id}"),
        types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_adv")
    )
    bot.send_message(message.chat.id, "⚠️ Ushbu xabarni barcha bot foydalanuvchilariga tarqatishni tasdiqlaysizmi?", reply_markup=markup)

# ----------------- DELETE MOVIE WORKFLOW -----------------

def process_movie_delete(message):
    code = message.text.strip()
    deleted = database.delete_movie(code)
    if deleted:
        bot.send_message(message.chat.id, f"✅ `{code}` kodli kino va uning barcha seriyalari muvaffaqiyatli o'chirildi!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, f"❌ `{code}` kodli kino topilmadi, shuning uchun o'chirilmadi.", parse_mode="Markdown", reply_markup=get_admin_keyboard())

# ----------------- CHANNELS CONFIGURATION WORKFLOW -----------------

def process_channel_id(message):
    channel_id = message.text.strip()
    if not channel_id:
        bot.send_message(message.chat.id, "Xato: bo'sh matn yuborildi.", reply_markup=get_channels_keyboard())
        return
        
    msg = bot.send_message(message.chat.id, "Kanal nomini kiriting (Tugmada chiqadigan yozuv):")
    bot.register_next_step_handler(msg, process_channel_title, channel_id)

def process_channel_title(message, channel_id):
    title = message.text.strip()
    if not title:
        bot.send_message(message.chat.id, "Xato: bo'sh yozuv kiritildi.", reply_markup=get_channels_keyboard())
        return
        
    msg = bot.send_message(message.chat.id, "Kanalga taklif havolasini (link) kiriting:")
    bot.register_next_step_handler(msg, process_channel_link, channel_id, title)

def process_channel_link(message, channel_id, title):
    invite_link = message.text.strip()
    if not invite_link:
        bot.send_message(message.chat.id, "Xato: bo'sh link yuborildi.", reply_markup=get_channels_keyboard())
        return
        
    success = database.add_channel(channel_id, title, invite_link)
    if success:
        bot.send_message(message.chat.id, f"✅ Kanal muvaffaqiyatli qo'shildi!\n\nID: `{channel_id}`\nNomi: {title}\nLink: {invite_link}", parse_mode="Markdown", reply_markup=get_channels_keyboard())
    else:
        bot.send_message(message.chat.id, "❌ Ma'lumotlarni saqlashda xatolik yuz berdi.", reply_markup=get_channels_keyboard())

def process_channel_delete(message):
    channel_id = message.text.strip()
    deleted = database.delete_channel(channel_id)
    if deleted:
        bot.send_message(message.chat.id, f"✅ `{channel_id}` majburiy kanallardan o'chirildi!", reply_markup=get_channels_keyboard())
    else:
        bot.send_message(message.chat.id, f"❌ `{channel_id}` ro'yxatda topilmadi.", reply_markup=get_channels_keyboard())

# Start polling
if __name__ == '__main__':
    print("Bot ishga tushmoqda...")
    bot.infinity_polling()
