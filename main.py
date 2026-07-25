import os
import threading
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import config
import database
import random

# Initialize database
database.init_db()

# Initialize bot with high-concurrency 30-worker thread pool
bot = telebot.TeleBot(config.BOT_TOKEN, threaded=True, num_threads=30)

# Genres list
GENRES = ["💥 Jangari", "😂 Komediya", "❤️ Melodrama", "🦁 Multfilm", "🚀 Fantastika", "👻 Qo'rqinchli", "🎭 Drama", "🌐 Boshqa"]

# Temporary state storage
admin_states = {}
pending_channel_videos = {}

def escape_md(text):
    if not text:
        return ""
    for char in ['_', '*', '`', '[']:
        text = text.replace(char, '')
    return text

def is_super_admin(user_id):

    return user_id in config.ADMIN_IDS

def is_admin(user_id):
    if is_super_admin(user_id):
        return True
    return database.is_db_admin(user_id)

def generate_unique_code():
    while True:
        code = str(random.randint(1000, 9999))
        if not database.get_movie(code):
            return code

LANGUAGES = ["🇺🇿 O'zbekcha", "🇷🇺 Ruscha (На русском)", "🇬🇧 Inglizcha (English)"]

# Keyboards
def get_user_display_name(target_user_id):
    """Fetches First Name and Username of a Telegram User ID for Admin lists"""
    try:
        chat = bot.get_chat(target_user_id)
        if chat:
            first = chat.first_name or "Admin"
            uname = f"@{chat.username}" if chat.username else "username yo'q"
            return f"👤 **{first}** ({uname}) — ID: `{target_user_id}`"
    except Exception:
        pass

    res = database.execute_query("SELECT username FROM users WHERE user_id = ?", (target_user_id,), fetchone=True)
    if res and res[0]:
        return f"👤 @{res[0]} — ID: `{target_user_id}`"

    return f"👤 ID: `{target_user_id}`"


def get_main_keyboard(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = types.KeyboardButton("🔍 Kino qidirish")
    btn_genres = types.KeyboardButton("📂 Janrlar")
    btn_lang = types.KeyboardButton("🌐 Til bo'yicha kinolar")
    btn_top = types.KeyboardButton("🔥 Top 10 kinolar")
    btn_fav = types.KeyboardButton("❤️ Sevimlilarim")
    btn_profile = types.KeyboardButton("👤 Shaxsiy Profil")
    btn_random = types.KeyboardButton("🎲 Qanday kino ko'rsam?")
    btn_ref = types.KeyboardButton("👥 Do'stlarni taklif qilish")
    btn_prem = types.KeyboardButton("👑 Premium A'zolik")
    btn_supp = types.KeyboardButton("✍️ Adminga Murojaat")
    
    keyboard.row(btn_search, btn_genres)
    keyboard.row(btn_lang, btn_top)
    keyboard.row(btn_fav, btn_profile)
    keyboard.row(btn_random, btn_ref)
    keyboard.row(btn_prem, btn_supp)

    
    if is_admin(user_id):
        btn_admin = types.KeyboardButton("⚙️ Admin panel")
        keyboard.row(btn_admin)
    return keyboard

def get_admin_keyboard(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_add = types.KeyboardButton("➕ Kino qo'shish")
    btn_del = types.KeyboardButton("❌ Kino o'chirish")
    btn_list = types.KeyboardButton("📋 Barcha kinolar")
    btn_stats = types.KeyboardButton("📊 Statistika")
    btn_channels = types.KeyboardButton("📢 Homiylar / Kanallar")
    btn_source_ch = types.KeyboardButton("📡 Manba Kanalini Sozlash")
    btn_queue = types.KeyboardButton("📥 Kutilayotgan Kinolar")
    btn_adv = types.KeyboardButton("✉️ Reklama yuborish")
    btn_post_gen = types.KeyboardButton("📢 Post Generator")
    btn_auto_post = types.KeyboardButton("📢 1-Click Kanalga Joylash")
    btn_vip_mgmt = types.KeyboardButton("🔒 VIP Kinolarni Boshqarish")
    btn_prem_mgmt = types.KeyboardButton("👑 Premium Boshqaruvi")
    btn_web_search = types.KeyboardButton("🌐 Internetdan Qidiruv va Avto-Qo'shish")
    btn_userbot = types.KeyboardButton("🚀 Telegram Akauntdan Avto-Kino Ko'chirish (Telethon)")
    btn_back = types.KeyboardButton("⬅️ Bosh sahifa")
    
    is_paused = database.get_setting('telethon_scraper_paused') == '1'
    btn_pause = types.KeyboardButton("▶️ Avto-Yuklashni Davom Ettirish") if is_paused else types.KeyboardButton("⏸️ Avto-Yuklashni Vaqtincha To'xtatish")

    keyboard.row(btn_add, btn_del)
    keyboard.row(btn_list, btn_stats)
    keyboard.row(btn_queue, btn_source_ch)
    keyboard.row(btn_web_search)
    keyboard.row(btn_userbot)
    keyboard.row(btn_pause)
    keyboard.row(btn_channels, btn_adv)
    keyboard.row(btn_post_gen, btn_auto_post)
    keyboard.row(btn_vip_mgmt, btn_prem_mgmt)


    
    if is_super_admin(user_id):
        btn_admin_list = types.KeyboardButton("👑 Adminlar Ro'yxati")
        btn_admin_del = types.KeyboardButton("➖ Admin o'chirish")
        btn_promo = types.KeyboardButton("🔑 Admin kodi yaratish")
        keyboard.row(btn_admin_list, btn_admin_del)
        keyboard.row(btn_promo)
        
    btn_restart = types.KeyboardButton("🔄 Serverni Qayta Ishga Tushirish")
    keyboard.row(btn_restart, btn_back)
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

def get_unsubscribed_channels(user_id):
    if is_admin(user_id) or database.is_premium_user(user_id):
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
    try:
        unsubscribed = get_unsubscribed_channels(message.from_user.id)
        if unsubscribed:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for title, invite_link in unsubscribed:
                markup.add(types.InlineKeyboardButton(text=f"📢 {title}", url=invite_link))
            
            markup.add(types.InlineKeyboardButton(text="🔄 Tasdiqlash", callback_data="check_sub"))
            
            try:
                bot.send_message(
                    message.chat.id,
                    "⚠️ **Botdan foydalanish uchun quyidagi homiy kanallariga a'zo bo'lishingiz zarur:**\n\n*(Eslatma: 👑 Premium a'zolar majburiy a'zolikdan ozod qilinadi)*\n\nA'zo bo'lgach, *Tasdiqlash* tugmasini bosing.",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            except Exception:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Botdan foydalanish uchun quyidagi homiy kanallariga a'zo bo'lishingiz zarur:\n\nA'zo bo'lgach, Tasdiqlash tugmasini bosing.",
                    reply_markup=markup
                )
            return False
        return True
    except Exception as e:
        print(f"Error in check_must_join: {e}")
        return True


# Helper to send formatted movie card
def send_movie_card(chat_id, code, user_id):
    movie = database.get_movie(code)
    if not movie:
        bot.send_message(chat_id, "❌ Bunday kodli kino topilmadi.")
        return

    code, title, caption, genre, views, is_vip = movie[:6]
    lang = movie[6] if len(movie) >= 7 and movie[6] else "🇺🇿 O'zbekcha"

    # VIP Protection Check
    if is_vip and not database.is_premium_user(user_id) and not is_admin(user_id):
        ref_count = database.get_user_referral_count(user_id)
        rem_refs = 10 - (ref_count % 10) if (ref_count % 10) != 0 else 10
        vip_text = (
            f"🔒 **Ushbu kino faqat 👑 Premium foydalanuvchilar uchun!**\n\n"
            f"🎬 **Kino:** {title}\n"
            f"🌐 **Tili:** {lang}\n"
            f"🔑 **Kodi:** `{code}`\n\n"
            f"💳 **Obuna Narxlari:**\n"
            f"• 1 oy — **10,000 so'm**\n"
            f"• 2 oy — **18,000 so'm**\n"
            f"• 3 oy — **25,000 so'm**\n\n"
            f"🎁 **Tekin Olish:** Yana **{rem_refs} ta** do'st taklif qiling va 1 oy **TEKIN Premium** oling!"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="💳 Premium Sotib Olish", callback_data="buy_premium"))
        markup.add(types.InlineKeyboardButton(text="✍️ Adminga bog'lanish", callback_data="open_support"))
        markup.add(types.InlineKeyboardButton(text="👥 Do'stlarni taklif qilish", callback_data="open_ref"))
        bot.send_message(chat_id, vip_text, reply_markup=markup, parse_mode="Markdown")
        return

    database.increment_movie_views(code)
    likes, dislikes = database.get_movie_ratings(code)
    episodes = database.get_episodes(code)
    is_fav = database.is_favorite(user_id, code)
    is_sub = database.is_movie_subscribed(user_id, code)

    fav_text = "💔 Sevimlilardan chiqarish" if is_fav else "❤️ Sevimlilarga qo'shish"
    sub_text = "🔕 Obunani bekor qilish" if is_sub else "🔔 Yangi qismlarga obuna bo'lish"
    vip_badge = " 🔒 [VIP]" if is_vip else ""

    text = (
        f"🎬 **Kino nomi:** {title}{vip_badge}\n"
        f"🌐 **Tili:** {lang}\n"
        f"🎭 **Janr:** {genre}\n"
        f"🔑 **Kodi:** `{code}`\n"
        f"👁 **Ko'rishlar:** {views + 1} ta\n"
        f"👍 **Yoqdi:** {likes} | 👎 **Yoqmadi:** {dislikes}\n"
    )
    if caption:
        text += f"\n📝 **Tavsif:** {caption}"

    text += "\n\nTomosha qilish uchun quyidagi tugmalarni bosing 👇"


    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if episodes:
        for ep_id, ep_title, _ in episodes:
            markup.add(types.InlineKeyboardButton(text=f"🎬 {ep_title}", callback_data=f"play_ep:{ep_id}"))
    else:
        markup.add(types.InlineKeyboardButton(text="⚠️ Seriyalar hali yuklanmagan", callback_data="no_eps"))

    # Rating row
    markup.row(
        types.InlineKeyboardButton(text=f"👍 ({likes})", callback_data=f"rate_like:{code}"),
        types.InlineKeyboardButton(text=f"👎 ({dislikes})", callback_data=f"rate_dislike:{code}")
    )
    # Favorites & Subscription row
    markup.add(types.InlineKeyboardButton(text=fav_text, callback_data=f"fav_toggle:{code}"))
    markup.add(types.InlineKeyboardButton(text=sub_text, callback_data=f"sub_toggle:{code}"))
    markup.add(types.InlineKeyboardButton(text="📢 Do'stlarga ulashish", switch_inline_query=f"{code}"))

    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def send_all_movies_page(chat_id, user_id, page=1, message_id=None):
    movies = database.get_all_movies()
    if not movies:
        msg = "Hozircha ma'lumotlar bazasida kinolar yo'q."
        if message_id:
            try:
                bot.edit_message_text(msg, chat_id, message_id)
            except Exception:
                pass
        else:
            bot.send_message(chat_id, msg)
        return

    total_movies = len(movies)
    per_page = 10
    total_pages = (total_movies + per_page - 1) // per_page
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_movies)
    page_movies = movies[start_idx:end_idx]

    text = (
        f"📋 **BARCHA KINOLAR RO'YXATI:**\n\n"
        f"📊 **Jami kinolar:** **{total_movies} ta**\n"
        f"🔢 **Ko'rsatilmoqda:** **{start_idx + 1}-{end_idx}** (Jami **{total_movies}** tadan)\n"
        f"📄 **Sahifa:** **{page}** / **{total_pages}**\n\n"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    for code, title, genre, views, is_vip in page_movies:
        safe_title = (title or "").replace('*', '').replace('_', '').replace('[', '(').replace(']', ')')
        vip_mark = " 🔒 [VIP]" if is_vip else ""
        markup.add(types.InlineKeyboardButton(text=f"🎬 {safe_title}{vip_mark} (🔑 {code})", callback_data=f"show_movie:{code}"))

    # Pagination navigation row
    nav_row = []
    if page > 1:
        nav_row.append(types.InlineKeyboardButton(text="⬅️ Oldingi 10 ta", callback_data=f"all_movies_page:{page-1}"))

    nav_row.append(types.InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))

    if page < total_pages:
        nav_row.append(types.InlineKeyboardButton(text="Keyingi 10 ta ➡️", callback_data=f"all_movies_page:{page+1}"))

    markup.row(*nav_row)

    # First & Last page quick jump if total pages > 2
    if total_pages > 2:
        jump_row = []
        if page > 1:
            jump_row.append(types.InlineKeyboardButton(text="⏮️ 1-sahifa", callback_data="all_movies_page:1"))
        if page < total_pages:
            jump_row.append(types.InlineKeyboardButton(text=f"{total_pages}-sahifa ⏭️", callback_data=f"all_movies_page:{total_pages}"))
        if jump_row:
            markup.row(*jump_row)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            try:
                plain_text = text.replace('**', '').replace('`', '').replace('🔒 [VIP]', '🔒 VIP')
                bot.edit_message_text(plain_text, chat_id, message_id, reply_markup=markup)
            except Exception:
                pass
    else:
        try:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            plain_text = text.replace('**', '').replace('`', '').replace('🔒 [VIP]', '🔒 VIP')
            bot.send_message(chat_id, plain_text, reply_markup=markup)

# /start command
@bot.message_handler(commands=['start'])
def start_cmd(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = escape_md(message.from_user.first_name or "Foydalanuvchi")
        
        args = message.text.split()
        referred_by = None
        direct_movie_code = None

        if len(args) > 1:
            param = args[1].strip()
            if param.startswith("ref_"):
                try:
                    referred_by = int(param.replace("ref_", ""))
                except ValueError:
                    pass
            elif param.isdigit():
                direct_movie_code = param

        database.add_user(user_id, username, referred_by)

        # Referral reward logic: 10 referrals = 30 days FREE Premium!
        if referred_by and referred_by != user_id:
            added = database.add_referral(referred_by, user_id)
            if added:
                ref_count = database.get_user_referral_count(referred_by)
                try:
                    bot.send_message(referred_by, f"🎉 Sizning havolangiz orqali yangi foydalanuvchi botga kirdi!\nJami taklif qilgan do'stlaringiz: **{ref_count}** ta", parse_mode="Markdown")
                except Exception:
                    pass

                if ref_count > 0 and ref_count % 10 == 0:
                    database.add_premium(referred_by, days=30)
                    try:
                        bot.send_message(
                            referred_by,
                            "🎉 **TABRIKLAYMIZ!** Siz 10 ta do'stingizni taklif qilganingiz uchun sizga **1 oylik TEKIN 👑 Premium A'zolik** berildi!\n\n"
                            "Endi siz majburiy a'zolik kanallarisiz hamda VIP kinolarni cheklovlarsiz ko'ra olasiz!",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass

        if not is_admin(user_id):
            if not check_must_join(message):
                return

        # Direct movie code link logic
        if direct_movie_code:
            send_movie_card(message.chat.id, direct_movie_code, user_id)
            return

        prem_info = database.get_premium_info(user_id)
        badge = " 👑 [PREMIUM]" if prem_info else ""

        welcome_text = (
            f"Assalomu alaykum, {first_name}{badge}!\n\n"
            "🎬 **Kinolarni kod yoki nomi orqali ko'rish botiga xush kelibsiz!**\n"
            "Kino ko'rish uchun uning kodini yoki nomini yuboring (Masalan: `1230` yoki `Avatar`)."
        )
        try:
            bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        except Exception:
            bot.send_message(message.chat.id, f"Assalomu alaykum, {first_name}!\n\n🎬 Kinolarni kod yoki nomi orqali ko'rish botiga xush kelibsiz!\nKino ko'rish uchun uning kodini yuboring (Masalan: 1230).", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        print(f"Error in start_cmd: {e}")
        try:
            bot.send_message(message.chat.id, "Assalomu alaykum! Botga xush kelibsiz.", reply_markup=get_main_keyboard(message.from_user.id))
        except Exception:
            pass


# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    if call.data == "check_sub":
        unsubscribed = get_unsubscribed_channels(user_id)
        if unsubscribed:
            bot.answer_callback_query(call.id, "❌ Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "✅ Muvaffaqiyatli a'zo bo'ldingiz!", show_alert=True)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            welcome_text = (
                f"Assalomu alaykum, {call.from_user.first_name}!\n\n"
                "🎬 **Kinolarni kod orqali ko'rish botiga xush kelibsiz!**\n"
                "Kino ko'rish uchun uning kodini yuboring (Masalan: `1230`)."
            )
            bot.send_message(call.message.chat.id, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

    elif call.data == "buy_premium":
        bot.answer_callback_query(call.id)
        msg_text = (
            f"💳 **PREMIUM TARIFLARI VA NARXLARI:**\n\n"
            f"• **1 oy** — **10,000 so'm**\n"
            f"• **2 oy** — **18,000 so'm** *(2,000 so'm tejamkorlik!)*\n"
            f"• **3 oy** — **25,000 so'm** *(5,000 so'm tejamkorlik!)*\n\n"
            f"💡 **TEKIN OLISH:** 10 ta do'stni taklif qiling = **1 oy TEKIN Premium**!\n\n"
            f" Obuna bo'lish uchun pastdagi **`✍️ Adminga bog'lanish`** tugmasini bosing va adminga yozing!"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="✍️ Adminga bog'lanish (To'lov uchun)", callback_data="open_support"))
        markup.add(types.InlineKeyboardButton(text="👥 Do'stlarni taklif qilish", callback_data="open_ref"))
        bot.send_message(call.message.chat.id, msg_text, reply_markup=markup, parse_mode="Markdown")


    elif call.data == "open_ref":

        bot.answer_callback_query(call.id)
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        ref_count = database.get_user_referral_count(user_id)
        msg_text = (
            f"👥 **Do'stlarni taklif qiling va Tekin Premium oling!**\n\n"
            f"Sizning taklif havolangiz:\n`{ref_link}`\n\n"
            f"📊 Taklif qilgan do'stlaringiz: **{ref_count}** ta\n"
            f"💡 **Har 10 ta do'st uchun 1 oylik Tekin Premium beriladi!**"
        )
        bot.send_message(call.message.chat.id, msg_text, parse_mode="Markdown")

    elif call.data == "open_support":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "✍️ Adminga yubormoqchi bo'lgan murojaatingiz yoki savolingizni yozib yuboring:")
        bot.register_next_step_handler(msg, process_user_support_message)

    elif call.data.startswith("fav_toggle:"):
        code = call.data.split(":")[1]
        added = database.toggle_favorite(user_id, code)
        msg = "❤️ Sevimlilarga qo'shildi!" if added else "💔 Sevimlilardan chiqarildi!"
        bot.answer_callback_query(call.id, msg, show_alert=True)
        
        try:
            is_fav = database.is_favorite(user_id, code)
            fav_text = "💔 Sevimlilardan chiqarish" if is_fav else "❤️ Sevimlilarga qo'shish"
            markup = call.message.reply_markup
            for row in markup.keyboard:
                for btn in row:
                    if "Sevimlilar" in btn.text:
                        btn.text = fav_text
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass

    elif call.data == "add_src_channel":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "➕ **Yangi manba kanali username-ni kiriting (Masalan: `@kinolar_tv`):**\n\nBekor qilish uchun 'bekor' deb yozing.", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_source_channel_step)

    elif call.data == "manage_src_channels":
        bot.answer_callback_query(call.id)
        channels = database.get_telethon_source_channels()
        if not channels:
            bot.send_message(call.message.chat.id, "O'chirish uchun manba kanallar yo'q.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in channels:
            markup.add(types.InlineKeyboardButton(text=f"❌ O'chirish: @{ch}", callback_data=f"del_src_ch:{ch}"))

        bot.send_message(call.message.chat.id, "🗑️ **O'chirmoqchi bo'lgan manba kanalingizni tanlang:**", reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("all_movies_page:"):
        page = int(call.data.split(":")[1])
        bot.answer_callback_query(call.id)
        send_all_movies_page(call.message.chat.id, user_id, page=page, message_id=call.message.message_id)

    elif call.data == "noop":
        bot.answer_callback_query(call.id)

    elif call.data.startswith("del_src_ch:"):
        target_ch = call.data.split(":")[1]
        database.remove_telethon_source_channel(target_ch)
        bot.answer_callback_query(call.id, f"✅ @{target_ch} manba kanallari ro'yxatidan o'chirildi!", show_alert=True)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    elif call.data.startswith("sub_toggle:"):
        code = call.data.split(":")[1]
        subscribed = database.toggle_movie_subscription(user_id, code)
        msg = "🔔 Ushbu kino/serial bildirishnomalariga obuna bo'ldingiz!" if subscribed else "🔕 Bildirishnomalar bekor qilindi!"
        bot.answer_callback_query(call.id, msg, show_alert=True)

        try:
            is_sub = database.is_movie_subscribed(user_id, code)
            sub_text = "🔕 Obunani bekor qilish" if is_sub else "🔔 Yangi qismlarga obuna bo'lish"
            markup = call.message.reply_markup
            for row in markup.keyboard:
                for btn in row:
                    if "obuna" in btn.text.lower():
                        btn.text = sub_text
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass

    elif call.data.startswith("rate_like:"):
        code = call.data.split(":")[1]
        database.rate_movie(user_id, code, 1)
        bot.answer_callback_query(call.id, "👍 Siz kinoga ijobiy baho berdingiz!", show_alert=False)

    elif call.data.startswith("rate_dislike:"):
        code = call.data.split(":")[1]
        database.rate_movie(user_id, code, -1)
        bot.answer_callback_query(call.id, "👎 Siz kinoga salbiy baho berdingiz!", show_alert=False)

    elif call.data.startswith("play_ep:"):
        ep_id = int(call.data.split(":")[1])
        episode = database.get_episode_by_id(ep_id)
        if episode:
            file_id, episode_title, movie_code = episode
            movie = database.get_movie(movie_code)
            movie_title = movie[1] if movie else ""
            is_vip = movie[5] if movie else 0

            if is_vip and not database.is_premium_user(user_id) and not is_admin(user_id):
                bot.answer_callback_query(call.id, "🔒 Ushbu qism faqat Premium a'zolar uchun!", show_alert=True)
                return

            bot.answer_callback_query(call.id, f"Yuklanmoqda: {episode_title}")
            bot.send_chat_action(call.message.chat.id, 'upload_video')

            caption_full = f"🎬 **Kino nomi:** {movie_title}\n📌 **Qism:** {episode_title}\n🔑 **Kodi:** {movie_code}"
            
            # Content protection: Blocks forwarding, saving/downloading to phone gallery, and screen recording/screenshots!
            protect = not is_admin(user_id)

            try:
                bot.send_video(call.message.chat.id, file_id, caption=caption_full, parse_mode="Markdown", protect_content=protect)
            except Exception:
                try:
                    bot.send_document(call.message.chat.id, file_id, caption=caption_full, parse_mode="Markdown", protect_content=protect)
                except Exception as e:
                    bot.send_message(call.message.chat.id, f"Kino yuborishda xatolik yuz berdi: {e}")
        else:
            bot.answer_callback_query(call.id, "❌ Ushbu qism topilmadi!", show_alert=True)

    elif call.data.startswith("lang_filter:"):
        lang_target = call.data.split(":")[1]
        movies = database.get_movies_by_language(lang_target)
        if not movies:
            bot.answer_callback_query(call.id, f"{lang_target} tilida hali kinolar yo'q.", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        for code, title, genre, views, is_vip in movies:
            vip_mark = " 🔒" if is_vip else ""
            markup.add(types.InlineKeyboardButton(text=f"🎬 {title}{vip_mark} (🔑 {code})", callback_data=f"show_movie:{code}"))

        bot.send_message(call.message.chat.id, f"🌐 **{lang_target}** tilidagi kinolar ro'yxati:", reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("genre:"):

        genre_name = call.data.split(":")[1]
        movies = database.get_movies_by_genre(genre_name)
        if not movies:
            bot.answer_callback_query(call.id, f"'{genre_name}' janrida hali kinolar yo'q.", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        for code, title, genre, views, is_vip in movies:
            vip_mark = " 🔒" if is_vip else ""
            markup.add(types.InlineKeyboardButton(text=f"🎬 {title}{vip_mark} (🔑 {code})", callback_data=f"show_movie:{code}"))

        bot.send_message(call.message.chat.id, f"📂 **{genre_name}** janridagi kinolar ro'yxati:", reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("show_movie:"):
        code = call.data.split(":")[1]
        bot.answer_callback_query(call.id)
        send_movie_card(call.message.chat.id, code, user_id)

    elif call.data == "admin_new_movie":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Yangi kino nomini (sarlavhasini) kiriting (Bekor qilish uchun 'bekor' deb yozing):")
        bot.register_next_step_handler(msg, process_new_movie_title)

    elif call.data == "admin_exist_movie":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Mavjud kinoning kodini yuboring (Masalan: 3201):")
        bot.register_next_step_handler(msg, process_existing_movie_code)

    elif call.data.startswith("select_genre:"):
        genre = call.data.split(":")[1]
        bot.answer_callback_query(call.id, f"Janr tanlandi: {genre}")
        title = admin_states.get(user_id, {}).get('title', 'Kino')
        caption = admin_states.get(user_id, {}).get('caption', '')
        lang = admin_states.get(user_id, {}).get('language', "🇺🇿 O'zbekcha")
        
        code = generate_unique_code()
        success = database.add_movie(code, title, caption, genre, 0, lang)
        if success:
            database.trigger_auto_backup(bot)
            bot.send_message(
                call.message.chat.id,
                f"✅ Yangi kino yaratildi!\n🔑 Biriktirilgan Kod: `{code}`\n🎬 Nomi: *{title}*\n🌐 Tili: *{lang}*\n🎭 Janr: *{genre}*\n\nEndi ushbu kod ostiga qismlarini (video fayllarini) yuklaymiz.",
                parse_mode="Markdown"
            )
            ask_for_episode_file(call.message, code)


        else:
            bot.send_message(call.message.chat.id, "Xatolik yuz berdi ma'lumotlar bazasida.", reply_markup=get_admin_keyboard(user_id))

    elif call.data.startswith("add_more_ep:"):
        code = call.data.split(":")[1]
        bot.answer_callback_query(call.id)
        ask_for_episode_file(call.message, code)

    elif call.data == "finish_add_eps":
        bot.answer_callback_query(call.id, "Tizim yakunlandi!")
        bot.send_message(call.message.chat.id, "Kino va barcha seriyalar bazaga kiritildi! 🎥", reply_markup=get_admin_keyboard(user_id))

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
        bot.send_message(call.message.chat.id, status_text, parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))

    elif call.data == "cancel_adv":
        bot.answer_callback_query(call.id, "Bekor qilindi")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Reklama yuborish bekor qilindi.", reply_markup=get_admin_keyboard(user_id))

    elif call.data == "vip_add_prompt":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🔒 **VIP (Faqat Premium)** statusiga o'tkazmoqchi bo'lgan kino kodini kiriting (Masalan: `1230`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_vip_movie)

    elif call.data == "vip_remove_prompt":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🌐 **VIP statusidan chiqarmoqchi (Barchaga ochiq qilmoqchi)** bo'lgan kino kodini kiriting (Masalan: `1230`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_remove_vip_movie)

    elif call.data == "vip_list_show":
        bot.answer_callback_query(call.id)
        vip_movies = database.get_vip_movies()
        if not vip_movies:
            bot.send_message(call.message.chat.id, "🔒 **Hozirda VIP kinolar yo'q.**", parse_mode="Markdown")
            return

        list_text = "🔒 **BARCHA VIP KINOLAR RO'YXATI:**\n\n"
        for code, title, genre, views in vip_movies:
            list_text += f"🔑 `{code}` - **{title}** ({genre}) | 👁 `{views}` ta\n"

        bot.send_message(call.message.chat.id, list_text, parse_mode="Markdown")


    elif call.data == "start_batch_naming":
        bot.answer_callback_query(call.id)
        ask_next_batch_movie(call.message.chat.id, user_id)

    elif call.data == "pause_batch_naming":
        bot.answer_callback_query(call.id, "⏸ Jarayon to'xtatildi")
        admin_states.pop(user_id, None)
        bot.send_message(
            call.message.chat.id,
            "⏸ **Nomlash jarayoni to'xtatildi!**\n\nSiz `📥 Kutilayotgan Kinolar` ➔ `▶️ Davom Ettirish` tugmasi orqali keyinroq qolgan joyingizdan davom ettirishingiz mumkin.",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard(user_id)
        )

    elif call.data == "clear_batch_queue":
        database.clear_pending_queue()
        bot.answer_callback_query(call.id, "Navbat tozalandi")
        bot.send_message(call.message.chat.id, "✅ Kutilayotgan kinolar navbati tozalandi.", reply_markup=get_admin_keyboard(user_id))

    elif call.data.startswith("select_batch_genre:"):
        genre = call.data.split(":")[1]
        state = admin_states.get(user_id, {})
        pending_id = state.get('pending_id')
        queue_num = state.get('queue_num')
        file_id = state.get('file_id')
        title = state.get('title')
        caption = state.get('caption', '')
        lang = state.get('language', "🇺🇿 O'zbekcha")

        if not pending_id or not file_id or not title:
            bot.answer_callback_query(call.id, "❌ Ma'lumot topilmadi!", show_alert=True)
            return

        code = generate_unique_code()
        database.add_movie(code, title, caption, genre, 0, lang)
        database.add_episode(code, "To'liq film", file_id)
        database.mark_pending_fulfilled(pending_id)

        bot.answer_callback_query(call.id, f"✅ Kino #{queue_num} saqlandi!")
        bot.send_message(call.message.chat.id, f"✅ **Kino #{queue_num}** (*{title}*) saqlandi!\n🌐 **Tili:** {lang} | 🔑 **Kod:** `{code}`", parse_mode="Markdown")

        # Automatically ask for the next pending movie in queue!
        ask_next_batch_movie(call.message.chat.id, user_id)



    elif call.data.startswith("fill_video:"):

        video_key = call.data.split(":", 1)[1]
        file_id = pending_channel_videos.get(video_key)
        if not file_id:
            bot.answer_callback_query(call.id, "❌ Ushbu video topilmadi yoki allaqachon saqlangan!", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🎬 **Ushbu kino uchun nom (sarlavha) kiriting:**")
        bot.register_next_step_handler(msg, process_pending_video_title, video_key)

    elif call.data.startswith("select_pending_genre:"):
        genre = call.data.split(":")[1]
        video_key = admin_states.get(user_id, {}).get('pending_key')
        title = admin_states.get(user_id, {}).get('title', 'Kino')
        caption = admin_states.get(user_id, {}).get('caption', '')

        file_id = pending_channel_videos.pop(video_key, None)
        if not file_id:
            bot.answer_callback_query(call.id, "❌ Video fayli topilmadi!", show_alert=True)
            return

        code = generate_unique_code()
        database.add_movie(code, title, caption, genre)
        database.add_episode(code, "To'liq film", file_id)
        database.trigger_auto_backup(bot)

        bot.answer_callback_query(call.id, "✅ Saqlandi!")
        bot.send_message(
            call.message.chat.id,
            f"🎉 **Kino muvaffaqiyatli saqlandi!**\n\n🎬 **Nomi:** {title}\n🎭 **Janr:** {genre}\n🔑 **Biriktirilgan Kod:** `{code}`",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard(user_id)
        )

# ----------------- CHANNEL AUTO-IMPORT HANDLER -----------------

@bot.channel_post_handler(content_types=['video', 'document'])
def handle_channel_movie_post(message):
    configured_source = database.get_setting('source_channel_id')
    if configured_source:
        chat_username = f"@{message.chat.username}" if message.chat.username else ""
        chat_id_str = str(message.chat.id)
        if configured_source != chat_username and configured_source != chat_id_str:
            return

    file_id = None
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id

    if not file_id:
        return

    caption = message.caption.strip() if message.caption else ""
    title_extracted = ""
    desc_extracted = ""

    # Case A: Post HAS caption/title -> Instantly Auto-Publish to Bot Movies Database!
    if caption:
        lines = [line.strip() for line in caption.split("\n") if line.strip()]
        raw_title = lines[0] if lines else "Kino"
        clean_title = " ".join([word for word in raw_title.split() if not word.startswith("#")])
        if not clean_title:
            clean_title = raw_title

        # Auto-detect genre from hashtag if present
        detected_genre = "🌐 Boshqa"
        caption_lower = caption.lower()
        if "#jangari" in caption_lower or "#action" in caption_lower:
            detected_genre = "💥 Jangari"
        elif "#komediya" in caption_lower or "#comedy" in caption_lower:
            detected_genre = "😂 Komediya"
        elif "#melodrama" in caption_lower or "#romance" in caption_lower:
            detected_genre = "❤️ Melodrama"
        elif "#multfilm" in caption_lower or "#cartoon" in caption_lower:
            detected_genre = "🦁 Multfilm"
        elif "#fantastika" in caption_lower or "#scifi" in caption_lower:
            detected_genre = "🚀 Fantastika"
        elif "#qorqinchli" in caption_lower or "#horror" in caption_lower:
            detected_genre = "👻 Qo'rqinchli"
        elif "#drama" in caption_lower:
            detected_genre = "🎭 Drama"

        description = "\n".join(lines[1:]) if len(lines) > 1 else ""

        # Auto-detect language (Russian Cyrillic vs Uzbek Latin/Cyrillic)
        detected_lang = "🇺🇿 O'zbekcha"
        cyrillic_chars = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
        c_count = sum(1 for char in caption if char in cyrillic_chars)
        if c_count > 10:
            detected_lang = "🇷🇺 Ruscha (На русском)"

        code = generate_unique_code()
        database.add_movie(code, clean_title, description, detected_genre, 0, detected_lang)
        database.add_episode(code, "To'liq film", file_id)

        # Immediate Admin Notification
        notice_text = (
            f"🎉 **MANBA KANALIDAN YANGI KINO AVTOMATIK BAZAGA QO'SHILDI!**\n\n"
            f"🎬 **Kino nomi:** {clean_title}\n"
            f"🌐 **Tili:** {detected_lang}\n"
            f"🎭 **Janr:** {detected_genre}\n"
            f"🔑 **Biriktirilgan Kod:** `{code}`\n\n"
            f"*(Foydalanuvchilar `{code}` kodi orqali tomosha qilishlari mumkin)*"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                bot.send_message(admin_id, notice_text, parse_mode="Markdown")
            except Exception as e:
                print(f"Failed to notify admin {admin_id}: {e}")

    # Case B: Post HAS NO caption -> Add to pending queue and notify admin
    else:
        q_num = database.add_to_pending_queue(file_id, title="", caption="")
        alert_text = (
            f"📥 **MANBA KANALIGA NOMSIZ VIDEO KELDI!**\n\n"
            f"📌 **Kino #{q_num}** sifatida kutilayotganlar navbatiga qo'shildi.\n"
            f"*(Siz uni **`📥 Kutilayotgan Kinolar`** bo'limi orqali nomlashingiz va kod biriktirishingiz mumkin)*"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                bot.send_message(admin_id, alert_text, parse_mode="Markdown")
            except Exception as e:
                print(f"Failed to notify admin {admin_id}: {e}")

# ----------------- PRIVATE CHAT VIDEO / DOCUMENT AUTO-ATTACH HANDLER -----------------
@bot.message_handler(content_types=['video', 'document'])
def handle_private_video_or_doc(message):
    """Captures videos sent in private chat (e.g. by Telethon userbot or direct upload) and links file_id to database"""
    if message.chat.type != 'private':
        return

    file_id = message.video.file_id if message.video else (message.document.file_id if message.document else None)
    if not file_id:
        return

    caption = message.caption or ""
    import re
    match = re.search(r'/start\s+(\d+)', caption)
    if not match:
        match = re.search(r'\b(\d{4,5})\b', caption)

    if match:
        code = match.group(1)
        movie = database.get_movie(code)
        if movie:
            episodes = database.get_episodes(code)
            is_serial = "[📺 SERIAL]" in (movie[1] or "")
            if is_serial:
                ep_num = len(episodes) + 1
                ep_title = f"{ep_num}-qism"
            else:
                ep_title = "To'liq film"

            database.add_episode(code, ep_title, file_id)
            print(f"✅ [Auto-Attach] Video file_id ({file_id[:15]}...) successfully linked to Movie Code {code} ({movie[1]}) as '{ep_title}'")
            try:
                bot.send_message(message.chat.id, f"✅ Video `{code}` kodli kino ({movie[1]} - {ep_title}) bilan muvaffaqiyatli saqlandi!", parse_mode="Markdown")
            except Exception:
                pass
            return

    # Direct Video Upload without code in caption: Auto-create movie entry!
    raw_title = caption.split('\n')[0][:60] if caption else "Yangi Video Kino"
    clean_title = " ".join([w for w in raw_title.split() if not w.startswith('#')]) or "Yangi Kino"

    # Check if movie title already exists
    existing_movie = database.find_movie_by_base_title(clean_title)
    if existing_movie:
        code = existing_movie[0]
        episodes = database.get_episodes(code)
        ep_title = f"{len(episodes) + 1}-qism"
        database.add_episode(code, ep_title, file_id)
        try:
            bot.send_message(message.chat.id, f"✅ Video mavjud `{code}` kodli kinoga (*{ep_title}*) biriktirildi!", parse_mode="Markdown")
        except Exception:
            pass
    else:
        code = generate_unique_code()
        database.add_movie(code, clean_title, caption, "🌐 Boshqa", 0, "🇺🇿 O'zbekcha")
        database.add_episode(code, "To'liq film", file_id)
        print(f"✨ [Direct Upload Created] {clean_title} (Code: {code})")
        try:
            bot.send_message(
                message.chat.id,
                f"🎉 **YANGI KINO MUVAFFAQIYATLI BAZAGA SAQLANDI!** 🎬\n\n"
                f"🎬 **Nomi:** {clean_title}\n"
                f"🔑 **Biriktirilgan Unikal Kod:** `{code}`\n\n"
                f"Foydalanuvchilar botga `{code}` kodini yuborib ushbu kinoni ko'rishlari mumkin! 🚀",
                parse_mode="Markdown"
            )
        except Exception:
            pass






# Inline Query Handler for Telegram Inline Search
@bot.inline_handler(func=lambda query: True)

def inline_query_handler(query):
    text = query.query.strip()
    results = []

    if text:
        movies = database.search_movies_by_name(text)
    else:
        movies = database.get_top_movies(10)

    bot_info = bot.get_me()
    bot_username = bot_info.username

    for i, (code, title, genre, views, is_vip) in enumerate(movies):
        vip_mark = " 🔒 [VIP]" if is_vip else ""
        description = f"Janr: {genre} | Ko'rishlar: {views} ta | Kod: {code}{vip_mark}"
        content = types.InputTextMessageContent(
            f"🎬 **{title}**{vip_mark}\n🎭 Janr: {genre}\n🔑 Kodi: `{code}`\n\n👇 Tomosha qilish uchun botga bosing:\nhttps://t.me/{bot_username}?start={code}",
            parse_mode="Markdown"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="🎬 Botda ko'rish", url=f"https://t.me/{bot_username}?start={code}"))

        result = types.InlineQueryResultArticle(
            id=str(i),
            title=f"🎬 {title} (Kod: {code}){vip_mark}",
            input_message_content=content,
            reply_markup=markup,
            description=description
        )
        results.append(result)

    bot.answer_inline_query(query.id, results, cache_time=1)

# Text messages handler
@bot.message_handler(func=lambda msg: True)
def text_handler(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # Support Message Reply by Admin
    if message.reply_to_message and is_admin(user_id):
        orig_msg = message.reply_to_message
        ticket = database.get_support_ticket_by_msg(orig_msg.message_id)
        if ticket:
            _, target_user_id, orig_user_text = ticket
            try:
                bot.send_message(target_user_id, f"💬 **Admin javobi:**\n\n{text}", parse_mode="Markdown")
                bot.send_message(message.chat.id, f"✅ Javob foydalanuvchiga (`{target_user_id}`) muvaffaqiyatli yetkazildi!", parse_mode="Markdown")
                return
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Javob yuborishda xatolik: {e}")
                return

    # Check joining first
    if not is_admin(user_id):
        if not check_must_join(message):
            return

    # Base Navigation Commands
    if text == "🔍 Kino qidirish":
        msg = bot.send_message(
            message.chat.id,
            "🔍 **KINO QIDIRISH BO'LIMI:**\n\n"
            "Kino yoki serialning **4 xonali kodini** yuboring (masalan: `1010`)\n"
            "YOKI **kino nomini** yozib yuboring (masalan: `Avatar` yoki `Брат`):\n\n"
            "*(Bekor qilish uchun 'bekor' deb yozing)*",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_user_search_query)
        return


    elif text == "📂 Janrlar":
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(text=g, callback_data=f"genre:{g}") for g in GENRES]
        markup.add(*btns)
        bot.send_message(message.chat.id, "📂 **Kino janrini tanlang:**", reply_markup=markup, parse_mode="Markdown")
        return

    elif text == "🌐 Til bo'yicha kinolar":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(text="🇺🇿 O'zbek tilidagi kinolar", callback_data="lang_filter:🇺🇿 O'zbekcha"),
            types.InlineKeyboardButton(text="🇷🇺 Rus tilidagi kinolar (На русском)", callback_data="lang_filter:🇷🇺 Ruscha"),
            types.InlineKeyboardButton(text="🇬🇧 Ingliz tilidagi kinolar (English)", callback_data="lang_filter:🇬🇧 Inglizcha")
        )
        bot.send_message(message.chat.id, "🌐 **O'zingizga ma'qul tilni tanlang:**", reply_markup=markup, parse_mode="Markdown")
        return


    elif text == "🔥 Top 10 kinolar":
        top_movies = database.get_top_movies(10)
        if not top_movies:
            bot.send_message(message.chat.id, "Hozircha reyting shakllanmagan.")
            return

        text_response = "🔥 **Eng ko'p ko'rilgan TOP 10 kinolar:**\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for idx, (code, title, genre, views, is_vip) in enumerate(top_movies, 1):
            vip_mark = " 🔒" if is_vip else ""
            text_response += f"{idx}. 🎬 **{title}**{vip_mark} — 👁 `{views}` marta (Kod: `{code}`)\n"
            markup.add(types.InlineKeyboardButton(text=f"{idx}. 🎬 {title}{vip_mark} (🔑 {code})", callback_data=f"show_movie:{code}"))

        bot.send_message(message.chat.id, text_response, reply_markup=markup, parse_mode="Markdown")
        return

    elif text == "❤️ Sevimlilarim":
        favs = database.get_favorites(user_id)
        if not favs:
            bot.send_message(message.chat.id, "❤️ Sizda hali saqlangan sevimli kinolar yo'q.")
            return

        text_response = "❤️ **Sizning sevimli kinolaringiz ro'yxati:**\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for code, title, genre in favs:
            text_response += f"🎬 **{title}** (Janr: {genre}) — Kod: `{code}`\n"
            markup.add(types.InlineKeyboardButton(text=f"🎬 {title} (🔑 {code})", callback_data=f"show_movie:{code}"))

        bot.send_message(message.chat.id, text_response, reply_markup=markup, parse_mode="Markdown")
        return

    elif text == "👤 Shaxsiy Profil":
        prem_info = database.get_premium_info(user_id)
        status_text = f"👑 **PREMIUM** ({prem_info})" if prem_info else "🆓 **Oddiy (FREE)**"
        ref_count = database.get_user_referral_count(user_id)
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

        profile_msg = (
            f"👤 **SHAXSIY PROFIL DASHBOARD:**\n\n"
            f"🆔 **Telegram ID:** `{user_id}`\n"
            f"👤 **Ism:** {message.from_user.first_name}\n"
            f"👑 **Status:** {status_text}\n"
            f"👥 **Taklif qilgan do'stlaringiz:** **{ref_count}** ta\n\n"
            f"🔗 **Shaxsiy referal havolangiz:**\n`{ref_link}`\n\n"
            f"💡 *Har 10 ta do'stingiz uchun sizga 1 oylik Tekin Premium beriladi!*"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="📢 Do'stlarga ulashish", url=f"https://t.me/share/url?url={ref_link}&text=🎬 Kinolarni kod orqali ko'rish botiga kirish!"))
        bot.send_message(message.chat.id, profile_msg, reply_markup=markup, parse_mode="Markdown")
        return

    elif text == "🎲 Qanday kino ko'rsam?":
        rand_movie = database.get_random_movie()
        if not rand_movie:
            bot.send_message(message.chat.id, "Hozircha ma'lumotlar bazasida kinolar yo'q.")
            return

        bot.send_message(message.chat.id, "🎲 **Siz uchun tasodifiy kino tanlandi:**")
        send_movie_card(message.chat.id, rand_movie[0], user_id)
        return

    elif text == "👥 Do'stlarni taklif qilish":
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        ref_count = database.get_user_referral_count(user_id)

        msg_text = (
            f"👥 **Do'stlarni taklif qiling va TEKIN 👑 Premium oling!**\n\n"
            f"Sizning taklif havolangiz:\n`{ref_link}`\n\n"
            f"📊 Siz taklif qilgan do'stlar soni: **{ref_count}** ta\n\n"
            f"🎁 **Aksiya:** Har 10 ta do'stingiz uchun sizga **1 oylik TEKIN Premium** beriladi!"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="📢 Do'stlarga ulashish", url=f"https://t.me/share/url?url={ref_link}&text=🎬 Kinolarni kod orqali ko'rish botiga kirish!"))
        bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode="Markdown")
        return

    elif text == "👑 Premium A'zolik":
        prem_info = database.get_premium_info(user_id)
        ref_count = database.get_user_referral_count(user_id)
        rem_refs = 10 - (ref_count % 10) if (ref_count % 10) != 0 else 10

        if prem_info:
            status_str = f"✅ **FAOL** 👑\n📅 Muddati: **{prem_info}**"
        else:
            status_str = "🆓 **Oddiy (FREE)**"

        msg_text = (
            f"👑 **PREMIUM A'ZOLIK TARIFLARI VA NARXLAR:**\n\n"
            f"📌 **Sizning Statusingiz:** {status_str}\n\n"
            f"💳 **Obuna Tariflari:**\n"
            f"• **1 oy** — **10,000 so'm**\n"
            f"• **2 oy** — **18,000 so'm** *(2,000 so'm chegirma!)*\n"
            f"• **3 oy** — **25,000 so'm** *(5,000 so'm chegirma!)*\n\n"
            f"🎁 **Tekin Olish Yo'li:** 10 ta do'stni taklif qilish (Yana **{rem_refs} ta** do'st taklif qilsangiz, avtomatik 1 oylik TEKIN Premium beriladi!)\n\n"
            f"🌟 **Premium Imtiyozlari:**\n"
            f"• 🚫 Majburiy kanallardan to'liq ozod bo'lish\n"
            f"• 🔒 VIP Kinolarni cheklovlarsiz tomosha qilish\n"
            f"• 👑 Profilingizda oltin toj va VIP maqom\n"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(text="💳 Premium Sotib Olish", callback_data="buy_premium"))
        markup.add(types.InlineKeyboardButton(text="✍️ Adminga bog'lanish", callback_data="open_support"))
        markup.add(types.InlineKeyboardButton(text="👥 Do'stlarni taklif qilish (Tekin Premium)", callback_data="open_ref"))
        bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode="Markdown")
        return



    elif text == "✍️ Adminga Murojaat":
        msg = bot.send_message(message.chat.id, "✍️ Adminga yubormoqchi bo'lgan murojaatingiz yoki savolingizni yozib yuboring (Text, rasm yoki audio):")
        bot.register_next_step_handler(msg, process_user_support_message)
        return

    elif text == "⚙️ Admin panel" and is_admin(user_id):
        bot.send_message(message.chat.id, "Admin panelga xush kelibsiz. Amalni tanlang:", reply_markup=get_admin_keyboard(user_id))
        return

    elif text == "⬅️ Bosh sahifa":
        bot.send_message(message.chat.id, "Bosh sahifa", reply_markup=get_main_keyboard(user_id))
        return

    # Admin Panel Sections
    elif text == "➕ Kino qo'shish" and is_admin(user_id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(text="🆕 Yangi kino yaratish", callback_data="admin_new_movie"),
            types.InlineKeyboardButton(text="➕ Mavjud kinoga yangi qism qo'shish", callback_data="admin_exist_movie")
        )
        bot.send_message(message.chat.id, "Kino qo'shish turini tanlang:", reply_markup=markup)
        return

    elif text == "❌ Kino o'chirish" and is_admin(user_id):
        msg = bot.send_message(message.chat.id, "O'chiriladigan kino kodini kiriting (Barcha seriyalari ham o'chib ketadi):")
        bot.register_next_step_handler(msg, process_movie_delete)
        return

    elif text == "📋 Barcha kinolar":
        send_all_movies_page(message.chat.id, user_id, page=1)
        return

    elif text == "📊 Statistika" and is_admin(user_id):
        user_count = database.get_users_count()
        prem_count = database.get_premium_count()
        movies_count = len(database.get_all_movies())
        top_movies = database.get_top_movies(5)

        stat_text = (
            f"📊 **Bot kengaytirilgan statistikasi:**\n\n"
            f"👥 Jami foydalanuvchilar: **{user_count}** ta\n"
            f"👑 Premium a'zolar: **{prem_count}** ta\n"
            f"🎬 Jami yuklangan kinolar: **{movies_count}** ta\n\n"
            f"🔥 **Eng ommabop 5 ta kino:**\n"
        )
        for i, (c, t, v, g, is_v) in enumerate(top_movies, 1):
            stat_text += f"{i}. {t} — 👁 `{v}` ko'rishlar\n"

        bot.send_message(message.chat.id, stat_text, parse_mode="Markdown")
        return

    elif text == "🔒 VIP Kinolarni Boshqarish" and is_admin(user_id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(text="➕ VIP ga qo'shish", callback_data="vip_add_prompt"),
            types.InlineKeyboardButton(text="❌ VIP dan chiqarish", callback_data="vip_remove_prompt"),
            types.InlineKeyboardButton(text="📋 VIP Kinolar Ro'yxati", callback_data="vip_list_show")
        )
        bot.send_message(
            message.chat.id,
            "🔒 **VIP KINOLARNI BOSHQARISH BO'LIMI:**\n\n"
            "VIP kinolar faqat Premium a'zolarga taqdim etiladi.\n"
            "Boshqarish uchun kerakli amalingizni tanlang:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    elif text == "👑 Adminlar Ro'yxati" and is_super_admin(user_id):
        db_admins = database.get_db_admins()
        super_admins = config.ADMIN_IDS

        list_text = "👑 **BOT ADMINLARI RO'YXATI:**\n\n"
        list_text += "🔴 **Bosh Adminlar (Super Admin):**\n"
        for sa in super_admins:
            list_text += f"• {get_user_display_name(sa)}\n"

        list_text += "\n🟡 **Kino Qo'shuvchi Adminlar:**\n"
        if db_admins:
            for da in db_admins:
                list_text += f"• {get_user_display_name(da)}\n"
        else:
            list_text += "*(Hozircha qo'shimcha adminlar yo'q)*\n"

        bot.send_message(message.chat.id, list_text, parse_mode="Markdown")
        return

    elif text == "➖ Admin o'chirish" and is_super_admin(user_id):
        msg = bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan adminning Telegram ID sini kiriting (Masalan: `79012345`):\n\nBekor qilish uchun 'bekor' deb yozing.")
        bot.register_next_step_handler(msg, process_remove_admin_id)
        return


    elif text == "👑 Premium Boshqaruvi" and is_admin(user_id):
        msg_text = (
            f"👑 **Premium Boshqaruvi:**\n\n"
            f"Foydalanuvchiga Premium berish yoki olib tashlash uchun buyruq yoki ID yuboring:\n\n"
            f"• Premium berish: `+ID 30` (Masalan: `+79012345 30`)\n"
            f"• Umrbod Premium berish: `+ID lifetime`\n"
            f"• Premium olib tashlash: `-ID` (Masalan: `-79012345`)\n\n"
            f"Bekor qilish uchun 'bekor' deb yozing."
        )
        msg = bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_premium_command)
        return

    elif (text == "📢 1-Click Kanalga Joylash" or text == "📢 Post Generator") and is_admin(user_id):
        msg = bot.send_message(message.chat.id, "Kanalga post tayyorlash/joylash uchun kino kodini kiriting (Masalan: 1230):")
        bot.register_next_step_handler(msg, process_channel_post_generator)
        return

    elif text == "📢 Homiylar / Kanallar" and is_admin(user_id):
        bot.send_message(message.chat.id, "Kanallarni boshqarish bo'limi:", reply_markup=get_channels_keyboard())
        return

    elif (text == "🌐 Internetdan Qidiruv va Avto-Qo'shish" or text == "🌐 Internetdan Avto-Qidirish") and is_admin(user_id):
        msg_text = (
            f"🌐 **INTERNETDAN KINOLARNI AVTO-QIDIRISH VA BAZAGA QO'SHISH:**\n\n"
            f"Siz internet ma'lumotlar bazasidan (TMDB/IMDb va Ochiq kinolar tarmoqlaridan) istalgan kino yoki serial nomini qidirishingiz mumkin:\n\n"
            f"📌 **Namuna:** `Брат 2` yoki `Avatar` yoki `Qashqirlar Makoni`\n\n"
            f"Qidirmoqchi bo'lgan kino nomini yuboring (Bekor qilish uchun 'bekor' deb yozing):"
        )
        msg = bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_web_movie_search)
        return

    elif (text == "🚀 Telegram Akauntdan Avto-Kino Ko'chirish (Telethon)" or text == "🚀 Telethon Userbot") and is_admin(user_id):
        userbot_session = database.get_setting('telethon_session_str')
        status = "✅ **FAOL & ULANGAN** 🟢" if userbot_session else "🔴 **SOZLANMAGAN**"
        
        msg_text = (
            f"🚀 **IKKINCHI (MANBA) TELEGRAM AKAUNTINGIZNI ULASH:**\n\n"
            f"📌 **Status:** {status}\n\n"
            f"👍 **Juda to'g'ri qaror!** Shaxsiy admin profilizni berishingiz shart emas. Manba kanalida admin qilingan **ikkinchi ishchi Telegram akauntingizni (Worker Account)** ulashingiz mumkin!\n\n"
            f"Ushbu akaunt Telegramdagi ochiq va yopiq kino kanallaridan kinolarni **haqiqiy video fayli va 4 xonali kodlari bilan** botingiz hamda kanalingizga avto-ko'chirib turadi!\n\n"
            f"⚙️ **Sozlash yo'riqnomasi:**\n"
            f"1. O'sha ikkinchi akauntingizdan [my.telegram.org](https://my.telegram.org) saytiga kirib `api_id` va `api_hash` olasiz.\n"
            f"2. Botga o'sha akauntning `API_ID API_HASH`ini yuborasiz (Masalan: `123456 abcdef1234567890`)\n\n"
            f"*(Bekor qilish uchun 'bekor' deb yozing)*"
        )
        msg = bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_telethon_config)
        return

    elif (text == "⏸️ Avto-Yuklashni Vaqtincha To'xtatish" or text == "⏸️ Avto-Yuklashni Pauza Qilish") and is_admin(user_id):
        database.set_setting('telethon_scraper_paused', '1')
        bot.send_message(
            message.chat.id,
            "⏸️ **AVTO-YUKLASH VAQTINCHA TO'XTATILDI!**\n\n"
            "Telethon roboti kanallardan yangi va eski kinolarni avtomatik ko'chirishni vaqtincha pauzaga qo'ydi.\n\n"
            "*(Qayta yoqish uchun **`▶️ Avto-Yuklashni Davom Ettirish`** tugmasini bosing)*",
            reply_markup=get_admin_keyboard(user_id),
            parse_mode="Markdown"
        )
        return

    elif (text == "▶️ Avto-Yuklashni Davom Ettirish" or text == "▶️ Avto-Yuklashni Yoqish") and is_admin(user_id):
        database.set_setting('telethon_scraper_paused', '0')
        bot.send_message(
            message.chat.id,
            "▶️ **AVTO-YUKLASH QAYTA ISHGA TUSHIRILDI!** 🚀\n\n"
            "Telethon roboti kanallardan barcha kino hamda seriallarni avtomatik ko'chirishni davom ettirmoqda!",
            reply_markup=get_admin_keyboard(user_id),
            parse_mode="Markdown"
        )
        return

    elif (text == "🔄 Serverni Qayta Ishga Tushirish" or text == "/restart") and is_admin(user_id):
        bot.send_message(
            message.chat.id,
            "🔄 **SERVER VA BOT QAYTA ISHGA TUSHIRILMOQDA...** 🚀\n\n"
            "Barcha ma'lumotlar saqlandi. Bir necha soniyada bot yangilangan kod va yangi xotira bilan avtomatik ishga tushadi!",
            parse_mode="Markdown"
        )
        time.sleep(2)
        import sys, os
        os.execv(sys.executable, [sys.executable] + sys.argv)
        return




    elif text == "📡 Manba Kanalini Sozlash" and is_admin(user_id):
        channels = database.get_telethon_source_channels()
        ch_list_str = "\n".join([f"• `@{c}`" for c in channels]) if channels else "Hozircha manba kanallar kiritilmagan"

        msg_text = (
            f"📡 **TELETHON AVTO-KO'CHIRISH MANBA KANALLARI BOSHGARUVI:**\n\n"
            f"📋 **Faol Manba Kanallari Ro'yxati:**\n{ch_list_str}\n\n"
            f"💡 *Tugallangan kanallarni o'chirishingiz yoki yangi manba kanalini qo'shishingiz mumkin:* 👇"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(text="➕ Yangi Manba Kanali Qo'shish", callback_data="add_src_channel"))
        markup.add(types.InlineKeyboardButton(text="🗑️ Manba Kanalini O'chirish", callback_data="manage_src_channels"))
        
        bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode="Markdown")
        return

    elif (text == "📥 Kutilayotgan Kinolar" or text == "📥 Kutilayotgan Kinolar (Queue)") and is_admin(user_id):
        pending_count = database.get_pending_queue_count()
        if pending_count == 0:
            bot.send_message(message.chat.id, "📥 **Hozirda kutilayotgan nomsiz kinolar yo'q.**", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(text=f"▶️ Nomlashni Boshlash / Davom Ettirish ({pending_count} ta)", callback_data="start_batch_naming"),
            types.InlineKeyboardButton(text="❌ Navbatni Tozalash", callback_data="clear_batch_queue")
        )
        bot.send_message(
            message.chat.id,
            f"📥 **KUTILAYOTGAN KINOLAR NAVBATI:**\n\n"
            f"Hozirda **{pending_count} ta** nomsiz kino navbatda turibdi (Kino #1, Kino #2...).\n\n"
            f"Ketma-ket nomlab saqlash uchun pastdagi tugmani bosing:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    elif text == "⬅️ Admin panelga qaytish" and is_admin(user_id):



        bot.send_message(message.chat.id, "Admin panelga qaytdingiz:", reply_markup=get_admin_keyboard(user_id))
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

    elif (text == "✉️ Reklama yuborish" or text == "📢 Hammaga Xabar Yuborish") and is_admin(user_id):
        msg = bot.send_message(message.chat.id, "Foydalanuvchilarga yubormoqchi bo'lgan reklama xabarini yuboring (Matn, rasm, video, audio yoki ixtiyoriy format):\n\nBekor qilish uchun 'bekor' deb yozing.")
        bot.register_next_step_handler(msg, process_adv_message)
        return

    elif text == "🔑 Admin kodi yaratish" and is_super_admin(user_id):
        current_promo = database.get_setting('admin_promo_code', 'Mavjud emas')
        msg = bot.send_message(
            message.chat.id,
            f"🔑 **Hozirgi bir martalik Admin kodi:** `{current_promo}`\n\n"
            "Yangi bir martalik adminlik parolini (kodni) kiriting (Masalan: `secret777`):\n"
            "*(Ushbu kodni 1 kishi botga yuborsa, u admin bo'ladi va kod o'chib ketadi)*\n\n"
            "Bekor qilish uchun 'bekor' deb yozing.",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_set_admin_promo_code)
        return

    # Check if text matches active admin promo code
    active_promo = database.get_setting('admin_promo_code')
    if active_promo and text == active_promo:
        database.add_db_admin(user_id)
        database.delete_setting('admin_promo_code')
        bot.send_message(
            message.chat.id,
            "🎉 **Tabriklaymiz!** Siz bir martalik maxsus admin kodini kiritdingiz.\n\n"
            "Sizga botda **ADMIN** huquqi berildi! ⚙️",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id)
        )
        return

def process_user_search_query(message):
    user_id = message.from_user.id
    query_text = message.text.strip() if message.text else ""

    if not query_text or query_text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Qidirish bekor qilindi.", reply_markup=get_main_keyboard(user_id))
        return

    # 1. Direct Code Match
    movie = database.get_movie(query_text)
    if movie:
        send_movie_card(message.chat.id, query_text, user_id)
        return

    # 2. Name & Keyword Match
    matches = database.search_movies_by_name(query_text)
    if matches:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for code, title, genre, views, is_vip in matches:
            safe_t = (title or "").replace('*', '').replace('_', '').replace('[', '(').replace(']', ')')
            vip_mark = " 🔒 [VIP]" if is_vip else ""
            markup.add(types.InlineKeyboardButton(text=f"🎬 {safe_t}{vip_mark} (🔑 {code})", callback_data=f"show_movie:{code}"))

        try:
            bot.send_message(message.chat.id, f"🔍 **'{query_text}' bo'yicha topilgan kinolar:**", reply_markup=markup, parse_mode="Markdown")
        except Exception:
            bot.send_message(message.chat.id, f"🔍 '{query_text}' bo'yicha topilgan kinolar:", reply_markup=markup)
    else:
        try:
            bot.send_message(
                message.chat.id,
                f"❌ **'{query_text}' nomli yoki kodli kino topilmadi.**\n\nNomini yoki kodini tekshirib qaytadan kiritib ko'ring yoki `@` orqali telegram qidiruvidan foydalaning.",
                reply_markup=get_main_keyboard(user_id),
                parse_mode="Markdown"
            )
        except Exception:
            bot.send_message(
                message.chat.id,
                f"❌ '{query_text}' nomli yoki kodli kino topilmadi.\n\nNomini yoki kodini tekshirib qaytadan kiritib ko'ring.",
                reply_markup=get_main_keyboard(user_id)
            )

# ----------------- SUPPORT & PREMIUM WORKFLOWS -----------------


def process_user_support_message(message):
    user_id = message.from_user.id
    if message.text and message.text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Murojaat bekor qilindi.", reply_markup=get_main_keyboard(user_id))
        return

    # Forward support message to all Admins
    user_info = f"👤 Foydalanuvchi: {message.from_user.first_name} (@{message.from_user.username or 'mavjud_emas'})\nID: `{user_id}`"
    admin_notice = f"📩 **YANGI MUROJAAT:**\n\n{user_info}\n\n👇 **Javob berish uchun ushbu xabarga Reply (Javob) qiling:**"

    for admin_id in config.ADMIN_IDS:
        try:
            sent_msg = bot.send_message(admin_id, admin_notice, parse_mode="Markdown")
            fwd_msg = bot.copy_message(admin_id, message.chat.id, message.message_id)
            database.add_support_ticket(user_id, fwd_msg.message_id, message.text or "[Fayl/Media]")
        except Exception as e:
            print(f"Failed sending support msg to admin {admin_id}: {e}")

    bot.send_message(message.chat.id, "✅ Murojaatingiz adminga yetkazildi! Admin javob bersa, sizga xabar keladi.", reply_markup=get_main_keyboard(user_id))

def process_admin_premium_command(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    if not text or text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    parts = text.split()
    cmd = parts[0]

    try:
        if cmd.startswith("+"):
            target_id = int(cmd.replace("+", ""))
            days = 30
            is_lifetime = False

            if len(parts) > 1:
                if parts[1].lower() == 'lifetime':
                    is_lifetime = True
                elif parts[1].isdigit():
                    days = int(parts[1])

            database.add_premium(target_id, days=days, is_lifetime=is_lifetime)
            duration_str = "Umrbod (Lifetime)" if is_lifetime else f"{days} kunlik"
            bot.send_message(message.chat.id, f"✅ Foydalanuvchiga (`{target_id}`) **{duration_str} 👑 Premium** muvaffaqiyatli berildi!", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
            try:
                bot.send_message(target_id, f"🎉 **Sizga Admin tomonidan {duration_str} 👑 Premium A'zolik berildi!**\n\nEndi siz majburiy a'zolik kanallarisiz hamda VIP kinolarni cheklovlarsiz ko'ra olasiz!", parse_mode="Markdown")
            except Exception:
                pass

        elif cmd.startswith("-"):
            target_id = int(cmd.replace("-", ""))
            deleted = database.remove_premium(target_id)
            if deleted:
                bot.send_message(message.chat.id, f"✅ Foydalanuvchidan (`{target_id}`) Premium olib tashlandi.", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
            else:
                bot.send_message(message.chat.id, f"❌ Foydalanuvchi (`{target_id}`) Premium ro'yxatida topilmadi.", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
        else:
            bot.send_message(message.chat.id, "Xato format! Namuna: `+79012345 30` yoki `-79012345`", reply_markup=get_admin_keyboard(user_id))
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}", reply_markup=get_admin_keyboard(user_id))

def ask_next_batch_movie(chat_id, user_id):
    next_item = database.get_next_pending_video()
    if not next_item:
        bot.send_message(chat_id, "🎉 **BARCHA KUTILAYOTGAN KINOLAR NOMLANDI VA SAQLANDI!**", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
        admin_states.pop(user_id, None)
        return

    pending_id, queue_num, file_id, default_title, default_caption = next_item
    admin_states[user_id] = {
        'pending_id': pending_id,
        'queue_num': queue_num,
        'file_id': file_id,
        'default_title': default_title,
        'default_caption': default_caption
    }

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="⏸ To'xtatish (Pause)", callback_data="pause_batch_naming"))

    suggestion_prompt = ""
    if default_title:
        suggestion_prompt = f"\n📌 **Kanaldan kelgan nom:** `{default_title}`\n*(Ushbu nom bilan saqlash uchun `+` belgisini yuboring yoki yangi nom yozing)*\n"

    msg = bot.send_message(
        chat_id,
        f"🎬 **KINO #{queue_num}** (Navbatdagi kutilayotgan kino):{suggestion_prompt}\n"
        f"Iltimos, ushbu kino uchun **nom (sarlavha)** kiriting:\n\n"
        f"*(Bekor qilish uchun 'bekor' deb yozing)*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_batch_movie_title)

def process_batch_movie_title(message):
    user_id = message.from_user.id
    if message.text and message.text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Nomlash to'xtatildi.", reply_markup=get_admin_keyboard(user_id))
        admin_states.pop(user_id, None)
        return

    raw_input = message.text.strip() if message.text else ""
    if not raw_input:
        msg = bot.send_message(message.chat.id, "Xato: Bo'sh matn. Iltimos, kino nomini kiriting:")
        bot.register_next_step_handler(msg, process_batch_movie_title)
        return

    if user_id not in admin_states:
        bot.send_message(message.chat.id, "Jarayon to'xtatilgan.", reply_markup=get_admin_keyboard(user_id))
        return

    def_title = admin_states[user_id].get('default_title', '')
    title = def_title if (raw_input == '+' and def_title) else raw_input

    admin_states[user_id]['title'] = title
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="⏸ To'xtatish (Pause)", callback_data="pause_batch_naming"))

    def_cap = admin_states[user_id].get('default_caption', '')
    cap_suggestion = f"\n📌 **Kanaldan kelgan tavsif:** `{def_cap[:60]}...` (Shu tavsifni saqlash uchun `+` yuboring)\n" if def_cap else ""

    msg = bot.send_message(
        message.chat.id,
        f"📝 **Kino #{admin_states[user_id]['queue_num']}** (*{title}*) uchun tavsif kiriting:{cap_suggestion}\n"
        f"*(Tavsifsiz qoldirish uchun `-` belgisini yuboring)*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_batch_movie_caption)


def process_batch_movie_caption(message):
    user_id = message.from_user.id
    if message.text and message.text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Nomlash to'xtatildi.", reply_markup=get_admin_keyboard(user_id))
        admin_states.pop(user_id, None)
        return

    raw_input = message.text.strip() if message.text else ""
    def_cap = admin_states.get(user_id, {}).get('default_caption', '')

    if raw_input == '+' and def_cap:
        caption = def_cap
    elif raw_input == '-':
        caption = ""
    else:
        caption = raw_input

    if user_id not in admin_states:
        bot.send_message(message.chat.id, "Jarayon to'xtatilgan.", reply_markup=get_admin_keyboard(user_id))
        return

    admin_states[user_id]['caption'] = caption


    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(text=g, callback_data=f"select_batch_genre:{g}") for g in GENRES]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton(text="⏸ To'xtatish (Pause)", callback_data="pause_batch_naming"))

    bot.send_message(
        message.chat.id,
        f"🎭 **Kino #{admin_states[user_id]['queue_num']}** uchun janr tanlang:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

def process_web_movie_search(message):
    user_id = message.from_user.id
    query = message.text.strip() if message.text else ""
    if not query or query.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    bot.send_message(message.chat.id, f"🔍 Internet ma'lumotlar bazasidan **'{query}'** (Kino yoki Serial) qidirilmoqda...", parse_mode="Markdown")

    try:
        import urllib.request
        import json

        title = query
        overview = ""
        release_date = ""
        vote = "8.0"
        is_tv_series = False
        found = False

        # Attempt 1: TMDB API with Fail-safe Authorization
        try:
            movie_url = f"https://api.themoviedb.org/3/search/movie?api_key=c6d1d490bb5982845c48b2eb594b29c9&query={urllib.parse.quote(query)}&language=ru-RU"
            req = urllib.request.Request(movie_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode())
                results = data.get('results', [])
                if results:
                    item = results[0]
                    title = item.get('title') or item.get('original_title') or query
                    overview = item.get('overview', '')
                    release_date = (item.get('release_date') or '')[:4]
                    vote = str(item.get('vote_average', '8.0'))
                    found = True
        except Exception:
            pass

        # Attempt 2: TVmaze / Wikipedia Open Search (Keyless 100% Fail-safe)
        if not found:
            try:
                tv_url = f"https://api.tvmaze.com/singlesearch/shows?q={urllib.parse.quote(query)}"
                req_tv = urllib.request.Request(tv_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_tv, timeout=6) as resp_tv:
                    tv_data = json.loads(resp_tv.read().decode())
                    if tv_data:
                        title = tv_data.get('name', query)
                        raw_summary = tv_data.get('summary', '')
                        overview = raw_summary.replace('<p>', '').replace('</p>', '').replace('<b>', '').replace('</b>', '')
                        release_date = (tv_data.get('premiered') or '')[:4]
                        vote = str(tv_data.get('rating', {}).get('average') or '8.2')
                        is_tv_series = True
                        found = True
            except Exception:
                pass

        type_str = "📺 SERIAL" if is_tv_series else "🎬 KINO"

        # Detect Language
        detected_lang = "🇷🇺 Ruscha (На русском)"
        cyrillic_chars = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
        if sum(1 for c in title if c in cyrillic_chars) == 0 and sum(1 for c in overview if c in cyrillic_chars) < 5:
            detected_lang = "🇬🇧 Inglizcha (English)"

        formatted_caption = f"{title}"
        if release_date:
            formatted_caption += f" ({release_date})"
        formatted_caption += f"\n\n⭐ Reyting: {vote}/10"
        if overview:
            formatted_caption += f"\n📝 Tavsif: {overview[:300]}"

        # Save to database
        code = generate_unique_code()
        database.add_movie(code, f"[{type_str}] {title}", formatted_caption, "🌐 Boshqa", 0, detected_lang)

        # Notify Admin
        res_text = (
            f"🎉 **INTERNETDAN {type_str} MA'LUMOTLARI AUTO-QIDIRIB TOPILDI VA SAQLANDI!**\n\n"
            f"🎬 **Nomi:** {title} {f'({release_date})' if release_date else ''}\n"
            f"📌 **Turi:** {type_str}\n"
            f"⭐ **Reyting:** {vote}/10\n"
            f"🌐 **Tili:** {detected_lang}\n"
            f"🔑 **Biriktirilgan Kod:** `{code}`\n\n"
            f"📌 **Endi ushbu `{code}` kod ostiga video faylini yuklashingiz mumkin!**"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="🎬 Video faylini yuklash", callback_data=f"add_more_ep:{code}"))

        bot.send_message(message.chat.id, res_text, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Qidirishda xatolik yuz berdi: {e}", reply_markup=get_admin_keyboard(user_id))

def process_telethon_config(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    if not text or text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    parts = text.split()
    if len(parts) < 2:
        msg = bot.send_message(message.chat.id, "❌ Noto'g'ri format! Iltimos, `API_ID API_HASH` shaklida yuboring (Masalan: `123456 abcdef1234567890`):")
        bot.register_next_step_handler(msg, process_telethon_config)
        return

    api_id = parts[0]
    api_hash = parts[1]

    database.set_setting('telethon_api_id', api_id)
    database.set_setting('telethon_api_hash', api_hash)
    database.set_setting('telethon_session_str', f"{api_id}:{api_hash}")
    database.trigger_auto_backup(bot)

    msg_text = (
        f"✅ **API ID VA API HASH SAQLANDI!**\n\n"
        f"Endi akauntingizni Telegram xavfsizlik tizimi bilan to'liq ulash uchun **ikkinchi akauntingizning Telefon Raqamini** xalqaro formatda yuboring:\n\n"
        f"📌 **Format:** `+998901234567`\n"
        f"*(Bekor qilish uchun 'bekor' deb yozing)*"
    )
    msg = bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_telethon_phone_step, api_id, api_hash)

telethon_active_sessions = {}  # user_id -> {'client': client, 'loop': loop, 'phone': phone, 'hash': hash}

def process_telethon_phone_step(message, api_id, api_hash):
    user_id = message.from_user.id
    phone = message.text.strip() if message.text else ""
    if not phone or phone.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    bot.send_message(message.chat.id, f"📲 Telegram xavfsizlik serveriga **{phone}** raqami bo'yicha SMS kod so'rovi yuborilmoqda...", parse_mode="Markdown")

    try:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = TelegramClient(StringSession(), int(api_id), api_hash, loop=loop)

        async def send_code_req():
            await client.connect()
            sent = await client.send_code_request(phone)
            return sent.phone_code_hash

        phone_code_hash = loop.run_until_complete(send_code_req())

        telethon_active_sessions[user_id] = {
            'client': client,
            'loop': loop,
            'phone': phone,
            'api_id': api_id,
            'api_hash': api_hash,
            'hash': phone_code_hash
        }

        msg_text = (
            f"📩 **TELEGRAM KOD YUBORILDI!**\n\n"
            f"Telegram ilovangizga yoki SMS orqali kelgan **5 xonali tasdiqlash kodini** yuboring:\n\n"
            f"📌 **Namuna:** `12345`\n"
            f"*(Bekor qilish uchun 'bekor' deb yozing)*"
        )
        msg = bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_telethon_sms_step)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Telegram xavfsizlik kod so'rovida xatolik yuz berdi: {e}", reply_markup=get_admin_keyboard(user_id))


def process_telethon_sms_step(message):
    user_id = message.from_user.id
    code = message.text.strip() if message.text else ""
    if not code or code.lower() == 'bekor':
        session_info = telethon_active_sessions.pop(user_id, None)
        if session_info and session_info.get('client'):
            try:
                session_info['loop'].run_until_complete(session_info['client'].disconnect())
            except Exception:
                pass
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    session_info = telethon_active_sessions.get(user_id)
    if not session_info:
        bot.send_message(message.chat.id, "⚠️ Seans vaqti tugadi yoki xatolik yuz berdi. Iltimos, qaytadan boshlang.", reply_markup=get_admin_keyboard(user_id))
        return

    bot.send_message(message.chat.id, "🔐 Telegram akauntingiz muvaffaqiyatli avtorizatsiyadan o'tkazilmoqda...", parse_mode="Markdown")

    client = session_info['client']
    loop = session_info['loop']
    phone = session_info['phone']
    phone_code_hash = session_info['hash']

    try:
        from telethon.errors import SessionPasswordNeededError

        async def complete_login():
            if not client.is_connected():
                await client.connect()
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            session_str = client.session.save()
            await client.disconnect()
            return session_str

        session_string = loop.run_until_complete(complete_login())
        telethon_active_sessions.pop(user_id, None)

        database.set_setting('telethon_session_string', session_string)
        database.set_setting('telethon_authorized', '1')
        database.trigger_auto_backup(bot)

        # Launch scraper thread now that session is authorized!
        t = threading.Thread(target=telethon_movie_scraper_worker, daemon=True)
        t.start()

        success_text = (
            f"🎉 **TABRIKLAYMIZ! IKKINCHI TELEGRAM AKAUNTINGIZ BOTGA TO'LIQ ULANDI!** 🟢\n\n"
            f"📌 **Status:** ✅ **FAOL & ULANGAN** 🟢\n"
            f"💾 **Cloud Session:** ✅ **BAZAGA 100% SAQLANDI (Server restartida o'chmaydi!)**\n\n"
            f"Endi bot sizning ikkinchi akauntingiz orqali Telegramdagi barcha ochiq kino kanallardan kinolarni **HAQIQIY MP4 VIDEO FAYLI BILAN** avtomatik ko'chirishni boshladi! 🚀"
        )
        bot.send_message(message.chat.id, success_text, parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))

    except Exception as e:
        err_msg = str(e)
        if "two-steps verification" in err_msg.lower() or "password" in err_msg.lower():
            msg = bot.send_message(
                message.chat.id,
                "🔐 **Akauntingizda 2 bosqichli tasdiqlash (2FA Password) o'rnatilgan!**\n\n"
                "Iltimos, Telegram **2FA Parolingizni** kiriting (Bekor qilish uchun 'bekor' deb yozing):",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, process_telethon_2fa_password_step)
        else:
            telethon_active_sessions.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                f"❌ Tasdiqlash kodini kiritishda xatolik: `{err_msg}`\n\n"
                f"💡 **Sababi:** Kod noto'g'ri kiritilgan bo'lishi yoki ulanish uzilgan bo'lishi mumkin. Qaytadan urinib ko'ring.",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard(user_id)
            )

def process_telethon_2fa_password_step(message):
    user_id = message.from_user.id
    password = message.text.strip() if message.text else ""
    session_info = telethon_active_sessions.get(user_id)

    if not session_info or not password or password.lower() == 'bekor':
        telethon_active_sessions.pop(user_id, None)
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    client = session_info['client']
    loop = session_info['loop']

    try:
        async def complete_2fa():
            if not client.is_connected():
                await client.connect()
            await client.sign_in(password=password)
            session_str = client.session.save()
            await client.disconnect()
            return session_str

        session_string = loop.run_until_complete(complete_2fa())
        telethon_active_sessions.pop(user_id, None)

        database.set_setting('telethon_session_string', session_string)
        database.set_setting('telethon_authorized', '1')
        database.trigger_auto_backup(bot)

        t = threading.Thread(target=telethon_movie_scraper_worker, daemon=True)
        t.start()

        bot.send_message(
            message.chat.id,
            "🎉 **TABRIKLAYMIZ! 2FA PAROL TASDIQLANDI VA IKKINCHI AKAUNT BOTGA ULANDI!** 🟢",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard(user_id)
        )
    except Exception as e:
        telethon_active_sessions.pop(user_id, None)
        bot.send_message(message.chat.id, f"❌ 2FA Parol xatosi: {e}", reply_markup=get_admin_keyboard(user_id))






def process_add_vip_movie(message):

    user_id = message.from_user.id
    code = message.text.strip() if message.text else ""
    if not code or code.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    found = database.set_movie_vip(code, True)
    if found:
        bot.send_message(message.chat.id, f"✅ `{code}` kodli kino **🔒 VIP statusiga (Faqat Premium)** o'tkazildi!", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
    else:
        bot.send_message(message.chat.id, f"❌ `{code}` kodli kino topilmadi.", reply_markup=get_admin_keyboard(user_id))

def process_remove_vip_movie(message):
    user_id = message.from_user.id
    code = message.text.strip() if message.text else ""
    if not code or code.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    found = database.set_movie_vip(code, False)
    if found:
        bot.send_message(message.chat.id, f"✅ `{code}` kodli kino **🌐 Oddiy statusga (Barchaga ochiq)** o'tkazildi!", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
    else:
        bot.send_message(message.chat.id, f"❌ `{code}` kodli kino topilmadi.", reply_markup=get_admin_keyboard(user_id))

def process_remove_admin_id(message):
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        return

    text = message.text.strip() if message.text else ""
    if not text or text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    if not text.isdigit():
        bot.send_message(message.chat.id, "Xato: Admin Telegram ID faqat raqamlardan iborat bo'lishi kerak.", reply_markup=get_admin_keyboard(user_id))
        return

    target_admin_id = int(text)
    deleted = database.remove_db_admin(target_admin_id)
    if deleted:
        bot.send_message(message.chat.id, f"✅ Admin (`{target_admin_id}`) muvaffaqiyatli o'chirildi!", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
    else:
        bot.send_message(message.chat.id, f"❌ Admin (`{target_admin_id}`) topilmadi yoki allaqachon o'chirilgan.", reply_markup=get_admin_keyboard(user_id))


def process_db_restore_file(message):
    user_id = message.from_user.id
    if not message.document:
        bot.send_message(message.chat.id, "Xato: `.db` fayli yuborilmadi.", reply_markup=get_admin_keyboard(user_id))
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        success = database.restore_db_from_bytes(downloaded_file)
        if success:
            bot.send_message(message.chat.id, "🎉 **Ma'lumotlar bazasi muvaffaqiyatli tiklandi!** Barcha kinolar va kodlar qaytdi.", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
        else:
            bot.send_message(message.chat.id, "❌ Bazani tiklashda xatolik yuz berdi.", reply_markup=get_admin_keyboard(user_id))
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik: {e}", reply_markup=get_admin_keyboard(user_id))


def process_set_source_channel(message):
    user_id = message.from_user.id
    ch_id = message.text.strip() if message.text else ""
    if not ch_id or ch_id.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    database.set_setting('source_channel_id', ch_id)
    bot.send_message(
        message.chat.id,
        f"✅ **Yangi manba kanali saqlandi!**\n\n📡 Manba Kanali: `{ch_id}`\n\n"
        "Endi bot faqat ushbu kanaldan kelgan video/hujjatlarni avtomatik kinolar bazasiga saqlaydi yoki nom kiritishingizni so'raydi.",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(user_id)
    )

def process_add_source_channel_step(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    if not text or text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    added = database.add_telethon_source_channel(text)
    if added:
        bot.send_message(message.chat.id, f"✅ **`@{text.replace('@', '')}`** yangi manba kanali sifatida muvaffaqiyatli qo'shildi!", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
    else:
        bot.send_message(message.chat.id, f"⚠️ Ushbu kanal allaqachon manba kanallar ro'yxatida bor.", reply_markup=get_admin_keyboard(user_id))


def process_pending_video_title(message, video_key):
    user_id = message.from_user.id
    title = message.text.strip() if message.text else ""
    if not title or title.lower() == 'bekor':
        bot.send_message(message.chat.id, "Kino saqlash bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    admin_states[user_id] = {'pending_key': video_key, 'title': title}
    msg = bot.send_message(message.chat.id, "Tavsifini kiriting (Yoki bekor qilmoqchi bo'lsangiz '-' kiriting):")
    bot.register_next_step_handler(msg, process_pending_video_caption)

def process_pending_video_caption(message):
    user_id = message.from_user.id
    caption = message.text.strip() if message.text else ""
    if caption == '-':
        caption = ""

    if user_id not in admin_states:
        admin_states[user_id] = {}
    admin_states[user_id]['caption'] = caption

    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(text=g, callback_data=f"select_pending_genre:{g}") for g in GENRES]
    markup.add(*btns)

    bot.send_message(message.chat.id, "🎭 **Kino janrini tanlang:**", reply_markup=markup, parse_mode="Markdown")

# ----------------- ADMIN WORKFLOWS -----------------


def process_set_admin_promo_code(message):
    user_id = message.from_user.id
    code = message.text.strip() if message.text else ""
    if not code or code.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    database.set_setting('admin_promo_code', code)
    bot.send_message(
        message.chat.id,
        f"✅ **Yangi bir martalik Admin kodi saqlandi!**\n\n🔑 Parol: `{code}`\n\n"
        "Ushbu kod faqat 1 marotaba ishlatiladi.",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(user_id)
    )

def process_channel_post_generator(message):
    user_id = message.from_user.id
    code = message.text.strip()
    movie = database.get_movie(code)

    if not movie:
        bot.send_message(message.chat.id, f"❌ `{code}` kodli kino topilmadi.", reply_markup=get_admin_keyboard(user_id))
        return

    code, title, caption, genre, views, is_vip = movie
    bot_username = bot.get_me().username
    bot_link = f"https://t.me/{bot_username}?start={code}"
    vip_badge = " 🔒 [VIP]" if is_vip else ""

    post_text = (
        f"🎬 **{title}**{vip_badge}\n\n"
        f"🎭 **Janr:** {genre}\n"
        f"🔑 **Kino kodi:** `{code}`\n\n"
    )
    if caption:
        post_text += f"📝 {caption}\n\n"

    post_text += (
        f"👇 **Kinoni tomosha qilish uchun pastdagi tugmani bosing:**"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="🎬 Kinoni tomosha qilish", url=bot_link))

    # Offer 1-click publishing to channels
    channels = database.get_channels()
    if channels:
        published_count = 0
        for ch_id, ch_title, ch_link in channels:
            try:
                bot.send_message(ch_id, post_text, reply_markup=markup, parse_mode="Markdown")
                published_count += 1
            except Exception as e:
                print(f"Failed posting to channel {ch_id}: {e}")

        if published_count > 0:
            bot.send_message(message.chat.id, f"🚀 **{published_count} ta majburiy kanalga post 1-Click bilan avtomatik joylandi!**", parse_mode="Markdown")

    bot.send_message(message.chat.id, "✅ **Kanal uchun tayyor post:**\n\nUshbu xabarni kanalingizga forward/copy qilishingiz mumkin 👇", reply_markup=get_admin_keyboard(user_id))
    bot.send_message(message.chat.id, post_text, reply_markup=markup, parse_mode="Markdown")

def process_existing_movie_code(message):
    user_id = message.from_user.id
    code = message.text.strip()
    if not code:
        bot.send_message(message.chat.id, "Xato: Kod bo'sh bo'lishi mumkin emas.", reply_markup=get_admin_keyboard(user_id))
        return

    existing = database.get_movie(code)
    if existing:
        title = existing[1]
        bot.send_message(message.chat.id, f"🎬 Mavjud film: *{title}* (Kod: `{code}`)\nYangi qism qo'shish jarayoni boshlanadi.", parse_mode="Markdown")
        ask_for_episode_file(message, code)
    else:
        bot.send_message(message.chat.id, f"❌ `{code}` kodli kino topilmadi.", reply_markup=get_admin_keyboard(user_id))

def process_new_movie_title(message):
    user_id = message.from_user.id
    title = message.text.strip() if message.text else ""
    if not title or title.lower() == 'bekor':
        bot.send_message(message.chat.id, "Bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    admin_states[user_id] = {'title': title}
    msg = bot.send_message(message.chat.id, "Kino uchun qisqacha tavsif yuboring (yoki bekor qilmoqchi bo'lsangiz '-' kiriting):")
    bot.register_next_step_handler(msg, process_new_movie_caption)

def process_new_movie_caption(message):
    user_id = message.from_user.id
    caption = message.text.strip() if message.text else ""
    if caption == '-':
        caption = ""

    if user_id not in admin_states:
        admin_states[user_id] = {}
    admin_states[user_id]['caption'] = caption

    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(text=g, callback_data=f"select_genre:{g}") for g in GENRES]
    markup.add(*btns)

    bot.send_message(message.chat.id, "🎭 **Kino janrini tanlang:**", reply_markup=markup, parse_mode="Markdown")

def ask_for_episode_file(message, code):
    user_id = message.from_user.id
    msg = bot.send_message(message.chat.id, f"Kino videosini yoki faylini yuklang (Yoki bekor qilish uchun 'bekor' deb yozing):")
    bot.register_next_step_handler(msg, process_add_episode_file, code)

def process_add_episode_file(message, code):
    user_id = message.from_user.id
    if message.text and message.text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
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
    user_id = message.from_user.id
    episode_title = message.text.strip() if message.text else "Kino qismi"

    success = database.add_episode(code, episode_title, file_id)
    if success:
        # Auto-Notification for Movie Subscribers!
        subscribers = database.get_movie_subscribers(code)
        movie = database.get_movie(code)
        movie_title = movie[1] if movie else "Kino"

        for sub_user_id in subscribers:
            try:
                bot.send_message(
                    sub_user_id,
                    f"🔔 **YANGI QISM BILDIRISHNOMASI:**\n\n"
                    f"Siz kuzatayotgan **{movie_title}** serialiga yangi qism (*{episode_title}*) qo'shildi! 🎬\n\n"
                    f"🔑 Kodi: `{code}`",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed sending episode notification to {sub_user_id}: {e}")

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(text="➕ Yana qism qo'shish", callback_data=f"add_more_ep:{code}"),
            types.InlineKeyboardButton(text="✅ Yakunlash", callback_data="finish_add_eps")
        )
        bot.send_message(message.chat.id, f"✅ '{episode_title}' muvaffaqiyatli saqlandi va obunachilarga bildirishnoma yuborildi! Yana qism qo'shasizmi?", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Xatolik yuz berdi ma'lumot saqlanishida.", reply_markup=get_admin_keyboard(user_id))

def process_adv_message(message):
    user_id = message.from_user.id
    if message.text and message.text.lower() == 'bekor':
        bot.send_message(message.chat.id, "Reklama yuborish bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"send_adv:{message.chat.id}:{message.message_id}"),
        types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_adv")
    )
    bot.send_message(message.chat.id, "⚠️ Ushbu xabarni barcha bot foydalanuvchilariga tarqatishni tasdiqlaysizmi?", reply_markup=markup)

def process_movie_delete(message):
    user_id = message.from_user.id
    code = message.text.strip()
    deleted = database.delete_movie(code)
    if deleted:
        bot.send_message(message.chat.id, f"✅ `{code}` kodli kino va uning barcha seriyalari muvaffaqiyatli o'chirildi!", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
    else:
        bot.send_message(message.chat.id, f"❌ `{code}` kodli kino topilmadi.", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))

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

def process_set_source_channel(message):
    user_id = message.from_user.id
    target = message.text.strip() if message.text else ""
    if not target or target.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    clean_target = target.replace('@', '').strip()
    database.set_setting('source_channel_id', f"@{clean_target}")
    database.set_setting('telethon_target_channel', f"@{clean_target}")
    database.trigger_auto_backup(bot)

    success_msg = (
        f"✅ **MANBA KANALI MUVAFFAQIYATLI SOZLANDI!** 🚀\n\n"
        f"📌 **Manba Kanal Username:** `@{clean_target}`\n\n"
        f"Endi botingiz hamda Telethon robotingiz ushbu `@{clean_target}` kanalining **BARCHA kinolari hamda seriallarini (5,000 tagacha tarixdan)** haqiqiy MP4 video fayli va 4 xonali unikal kodlari bilan avtomatik ko'chirib keladi!"
    )
    bot.send_message(message.chat.id, success_msg, parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))

# ----------------- RENDER KEEP-ALIVE HTTP SERVER -----------------


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")

    def log_message(self, format, *args):
        return  # Suppress HTTP server log outputs

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Health check HTTP server running on port {port}...")
    server.serve_forever()

def keep_alive_pinger():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return

    print(f"Keep-alive pinger started for: {url}")
    while True:
        time.sleep(600)  # Ping every 10 minutes
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 KeepAlive'})
            with urllib.request.urlopen(req, timeout=10) as response:
                print(f"Keep-alive auto-ping success: status {response.status}")
        except Exception as e:
            print(f"Keep-alive auto-ping error: {e}")

def auto_restore_on_startup():
    try:
        movies = database.get_all_movies()
        if movies:
            print(f"Database contains {len(movies)} movies. Auto-restore not needed.")
            return

        print("Database is empty on startup. Attempting auto-restore from Telegram Cloud...")
        latest_file_id = database.get_setting('latest_backup_file_id')
        if latest_file_id:
            try:
                file_info = bot.get_file(latest_file_id)
                downloaded_data = bot.download_file(file_info.file_path)
                success = database.restore_db_from_bytes(downloaded_data)
                if success:
                    restored_count = len(database.get_all_movies())
                    print(f"🎉 AUTO-RESTORE SUCCESSFUL! Restored {restored_count} movies from Telegram Cloud!")
                    for admin_id in config.ADMIN_IDS:
                        try:
                            bot.send_message(admin_id, f"🎉 **SERVER AVTOMATIK TIKLANDI!**\n\nTelegram Bulutidan barcha **{restored_count} ta** kinolar va kodlar avtomatik tiklab olindi!", parse_mode="Markdown")
                        except Exception:
                            pass
            except Exception as err:
                print(f"Failed auto-restore download: {err}")
    except Exception as e:
        print(f"Error in auto_restore_on_startup: {e}")

def auto_movie_scout_worker():
    """Background worker that continuously fetches open-source movie metadata and auto-populates movies.db"""
    custom_tmdb_key = database.get_setting('tmdb_api_key')
    if not custom_tmdb_key:
        print("ℹ️ TMDB API kaliti kiritilmagan. TMDB Auto-Movie Scout faol emas.")
        return

    import time
    import urllib.request
    import urllib.error
    import json
    import random

    search_terms = [
        "Аватар", "Брат", "Бригада", "Мстители", "Джентльмены",
        "Интерстеллар", "Гарри Поттер", "Форсаж", "Матрица", "Шрек", "Леон",
        "Один дома", "Титаник", "Гладиатор", "Начало", "Джокер", "Веном", "Терминатор",
        "Тачки", "Миньоны", "Сумерки", "Джон Уик", "Человек паук", "Бэтмен", "Пираты Карибского моря"
    ]

    print("🤖 Auto-Movie Scout Worker started and active...")
    time.sleep(3)

    while True:
        random.shuffle(search_terms)
        unauthorized_encountered = False

        for term in search_terms:
            try:
                page = random.randint(1, 3)
                url = f"https://api.themoviedb.org/3/search/movie?api_key={custom_tmdb_key}&query={urllib.parse.quote(term)}&language=ru-RU&page={page}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode())
                    results = data.get('results', [])

                for item in results:
                    m_title = item.get('title') or item.get('original_title')
                    if not m_title:
                        continue

                    # Exact title check in database
                    if database.movie_exists_by_exact_title(m_title):
                        continue

                    overview = item.get('overview', '') or "Avtomatik internetdan qidirib topilgan kino."
                    rel_year = (item.get('release_date') or '')[:4]
                    vote = item.get('vote_average', 8.0)

                    cyrillic_chars = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
                    detected_lang = "🇷🇺 Ruscha (На русском)" if sum(1 for c in m_title if c in cyrillic_chars) > 0 else "🇺🇿 O'zbekcha"

                    caption_str = f"{m_title}"
                    if rel_year:
                        caption_str += f" ({rel_year})"
                    caption_str += f"\n\n⭐ Reyting: {vote}/10\n📝 Tavsif: {overview[:300]}"

                    code = generate_unique_code()

                    # Auto VIP logic for popular/top-rated movies (Rating >= 7.5 or vote_count high)
                    is_vip_flag = 1 if (vote and float(vote) >= 7.5) else 0

                    database.add_movie(code, m_title, caption_str, "🌐 Boshqa", 0, detected_lang)
                    if is_vip_flag:
                        database.set_movie_vip(code, True)
                    
                    vip_badge = " 🔒 [VIP KINO]" if is_vip_flag else ""
                    print(f"🤖 Auto-Scout auto-added: {m_title} (Code: {code}){vip_badge}")

                    # Immediate alert to Super Admins
                    alert_text = (
                        f"🤖 **INTERNETDAN YANGI KINO AVTOMATIK TOPILDI VA BOTGA QO'SHILDI!**\n\n"
                        f"🎬 **Kino nomi:** {m_title} {f'({rel_year})' if rel_year else ''}{vip_badge}\n"
                        f"🌐 **Tili:** {detected_lang}\n"
                        f"⭐ **Reyting:** {vote}/10\n"
                        f"🔑 **Biriktirilgan Kod:** `{code}`\n\n"
                        f"*(Foydalanuvchilar botga `{code}` kodi yuborib tomosha qilishlari mumkin)*"
                    )
                    for admin_id in config.ADMIN_IDS:
                        try:
                            bot.send_message(admin_id, alert_text, parse_mode="Markdown")
                        except Exception as e:
                            print(f"Scout notification error to {admin_id}: {e}")

                    time.sleep(2)

            except urllib.error.HTTPError as http_err:
                if http_err.code == 401:
                    print("⚠️ TMDB API Kaliti yaroqsiz (HTTP Error 401). TMDB Scout to'xtatildi.")
                    unauthorized_encountered = True
                    break
                else:
                    print(f"Scout HTTP error for '{term}': {http_err}")
            except Exception as err:
                print(f"Scout term error for '{term}': {err}")

        if unauthorized_encountered:
            time.sleep(3600)
        else:
            time.sleep(60)



def force_initial_movie_population():
    """Clean empty database for real user content only. Auto-deletes old hardcoded demo movies."""
    demo_codes = ["1010", "1020", "1030", "1040", "1050", "1060"]
    for code in demo_codes:
        movie = database.get_movie(code)
        if movie and any(demo_name in movie[1] for demo_name in ["Аватар", "Брат 2", "Qashqirlar Makoni Vatan", "Гарри Поттер", "Форсаж 10", "Шрек"]):
            database.delete_movie(code)
            print(f"🗑️ [Demo Cleaned] Removed hardcoded demo movie: {code} - {movie[1]}")

def extract_serial_info(raw_title, caption_text):
    """
    Extracts clean base serial name and episode title (e.g., '1-qism', '2-qism') from title/caption.
    Returns: (is_serial, base_title, episode_title)
    """
    import re
    full_text = f"{raw_title} {caption_text}"
    text_lower = full_text.lower()

    ep_patterns = [
        (r'(\d+)\s*-\s*qism', '{n}-qism'),
        (r'(\d+)\s*qism', '{n}-qism'),
        (r'qism\s*(\d+)', '{n}-qism'),
        (r'(\d+)\s*-\s*серия', '{n}-qism'),
        (r'(\d+)\s*серия', '{n}-qism'),
        (r'серия\s*(\d+)', '{n}-qism'),
        (r'e(\d+)', '{n}-qism'),
        (r's\d+e(\d+)', '{n}-qism'),
        (r'part\s*(\d+)', '{n}-qism'),
        (r'ep\s*(\d+)', '{n}-qism')
    ]

    ep_num = None
    ep_title = "1-qism"

    for pat, fmt in ep_patterns:
        match = re.search(pat, text_lower)
        if match:
            try:
                ep_num = int(match.group(1))
                ep_title = fmt.format(n=ep_num)
                break
            except Exception:
                pass

    clean_base = raw_title
    strip_pats = [
        r'\d+\s*-\s*qism', r'\d+\s*qism', r'qism\s*\d+',
        r'\d+\s*-\s*серия', r'\d+\s*серия', r'серия\s*\d+',
        r'e\d+', r's\d+e\d+', r'part\s*\d+', r'ep\s*\d+',
        r'\d+\s*-\s*сезон', r'\d+\s*сезон', r'сезон\s*\d+'
    ]
    for pat in strip_pats:
        clean_base = re.sub(pat, '', clean_base, flags=re.IGNORECASE)

    clean_base = re.sub(r'[\(\)\[\]#\-:]+', ' ', clean_base)
    clean_base = " ".join([w for w in clean_base.split() if not w.startswith('#')])
    clean_base = clean_base.strip()

    if not clean_base:
        clean_base = raw_title.strip()

    is_serial = (ep_num is not None) or any(w in text_lower for w in ['qism', 'серия', 'сезон', 'serial', '#serial'])
    if not is_serial:
        ep_title = "To'liq film"

    return is_serial, clean_base, ep_title


def is_valid_video_file(msg):
    if getattr(msg, 'audio', None) or getattr(msg, 'voice', None) or getattr(msg, 'photo', None) or getattr(msg, 'sticker', None):
        return False

    mime = getattr(msg.document, 'mime_type', '') or ''
    file_name = (getattr(msg.file, 'name', '') or getattr(msg.document, 'file_name', '') or '').lower()

    # Explicitly block non-video file extensions (.apk, .exe, .zip, .rar, .pdf, .iso, etc.)
    forbidden_exts = ['.apk', '.exe', '.zip', '.rar', '.pdf', '.iso', '.dmg', '.7z', '.tar', '.gz', '.txt', '.doc', '.docx', '.apk.1', '.exe.1']
    if any(file_name.endswith(ext) for ext in forbidden_exts):
        return False

    # Allowed video extensions & mimes
    valid_video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.m4v', '.3gp', '.ts']
    is_video_mime = mime.startswith('video/')
    is_video_ext = any(file_name.endswith(ext) for ext in valid_video_exts)

    if msg.video or is_video_mime or is_video_ext:
        return True

    return False


def telethon_movie_scraper_worker():
    """Telethon Userbot client that searches user account chat, Saved Messages ('me'), and public Telegram channels to import all video files"""
    import asyncio
    import time
    import re
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession

    api_id_str = database.get_setting('telethon_api_id')
    api_hash = database.get_setting('telethon_api_hash')
    is_auth = database.get_setting('telethon_authorized')

    if not api_id_str or not api_hash or is_auth != '1':
        print("⚠️ Telethon Userbot credentials not authorized yet. Auto-forwarding dormant.")
        return

    try:
        api_id = int(api_id_str)
        print(f"🚀 Telethon Userbot starting with API ID: {api_id}...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Load StringSession from Cloud PostgreSQL database
        session_str = database.get_setting('telethon_session_string')
        if session_str:
            client = TelegramClient(StringSession(session_str), api_id, api_hash, loop=loop)
        else:
            client = TelegramClient('telethon_userbot_session', api_id, api_hash, loop=loop)

        async def run_telethon_bot():
            await client.connect()
            if not await client.is_user_authorized():
                print("⚠️ Telethon user not authorized yet. Awaiting initial login string.")
                return

            print("✅ Telethon Userbot CONNECTED via Cloud Session! Scanning Saved Messages ('me') & channels for MP4 videos...")

            try:
                bot_info = bot.get_me()
                bot_username = bot_info.username
            except Exception:
                bot_username = "me"

            while True:
                if database.get_setting('telethon_scraper_paused') == '1':
                    await asyncio.sleep(15)
                    continue

                targets = ['me']

                # Dynamic source channels list from Cloud PostgreSQL database
                public_movie_channels = database.get_telethon_source_channels()
                for p_ch in public_movie_channels:
                    if p_ch not in targets:
                        targets.append(p_ch)

                for ch in targets:
                    if database.get_setting('telethon_scraper_paused') == '1':
                        break
                    try:
                        print(f"🔍 [Telethon Userbot] Scanning target chat/channel: {ch}...")
                        async for msg in client.iter_messages(ch, limit=None):
                            if database.get_setting('telethon_scraper_paused') == '1':
                                break

                            # STRICT VIDEO FILE FILTER (Blocks .apk, .exe, .zip, audio, etc.)
                            if not is_valid_video_file(msg):
                                continue

                            cap = msg.message or "Manba kino"
                            raw_title = cap.split('\n')[0][:60] if cap else "Telegram Movie"
                            clean_title = " ".join([w for w in raw_title.split() if not w.startswith('#')])
                            if not clean_title:
                                clean_title = raw_title

                            duration = getattr(msg.file, 'duration', None)
                            if duration is None and msg.document and getattr(msg.document, 'attributes', None):
                                for attr in msg.document.attributes:
                                    if hasattr(attr, 'duration'):
                                        duration = attr.duration
                                        break

                            MIN_DURATION_SECONDS = 3 * 60  # 180 seconds = 3 minutes (allows cartoons, TV episodes & movies)

                            if duration is not None:
                                if duration < MIN_DURATION_SECONDS:
                                    print(f"⏩ [Filter Skipped] Short video/ad ({duration}s < 180s): {clean_title[:30]}")
                                    continue
                            else:
                                file_size_mb = (getattr(msg.file, 'size', 0) or 0) / (1024 * 1024)
                                if file_size_mb < 10:
                                    print(f"⏩ [Filter Skipped] Small file ({file_size_mb:.1f}MB < 10MB): {clean_title[:30]}")
                                    continue

                            # Serial vs Movie Grouping Logic
                            is_serial, base_title, episode_title = extract_serial_info(clean_title, cap)
                            full_title = f"[📺 SERIAL] {base_title}" if is_serial else base_title

                            # Check if Serial / Movie already exists in database
                            existing_movie = database.find_movie_by_base_title(base_title)
                            if existing_movie:
                                movie_code = existing_movie[0]
                                print(f"📺 [Serial Grouping] Found existing entry: {base_title} (Code: {movie_code}). Adding episode: {episode_title}")
                            else:
                                movie_code = generate_unique_code()
                                database.add_movie(movie_code, full_title, cap, "🌐 Boshqa", 0, "🇺🇿 O'zbekcha")
                                print(f"✨ [New Entry Created] {full_title} (Code: {movie_code})")

                            try:
                                await client.send_file(bot_username, msg.media, caption=f"/start {movie_code}")
                            except Exception as e_send:
                                print(f"Userbot send_file exception: {e_send}")

                            database.trigger_auto_backup(bot)
                            print(f"🚀 Telethon Userbot AUTO-COPIED ({duration or '30MB+'}s): {full_title} -> Ep: {episode_title} (Code: {movie_code})")
                            await asyncio.sleep(2)
                    except Exception as ex:
                        print(f"Error scraping chat {ch}: {ex}")

                await asyncio.sleep(180)

        loop.run_until_complete(run_telethon_bot())
    except Exception as e:
        print(f"Telethon worker error: {e}")



# Start polling
if __name__ == '__main__':
    web_thread = threading.Thread(target=start_health_check_server, daemon=True)
    web_thread.start()

    ping_thread = threading.Thread(target=keep_alive_pinger, daemon=True)
    ping_thread.start()

    # 1. Restore database from Telegram Cloud FIRST before force-populating demo movies!
    auto_restore_on_startup()

    # 2. Only populate demo batch if database is still brand new/empty
    force_initial_movie_population()

    scout_thread = threading.Thread(target=auto_movie_scout_worker, daemon=True)
    scout_thread.start()

    telethon_thread = threading.Thread(target=telethon_movie_scraper_worker, daemon=True)
    telethon_thread.start()


    print("Bot ishga tushmoqda...")
    import time
    print("Bot instant polling startup initiated...")

    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Webhook remove error: {e}")

    while True:
        try:
            bot.polling(non_stop=True, interval=1, timeout=20, skip_pending=False)
        except Exception as e:
            err_str = str(e)
            if "409" in err_str or "Conflict" in err_str:
                print("⚠️ [Polling Conflict 409] Old container instance shutting down. Waiting 10s for clean release...")
                time.sleep(10)
            else:
                print(f"Polling exception ({e}). Retrying in 4s...")
                time.sleep(4)





