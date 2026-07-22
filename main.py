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

# Initialize bot
bot = telebot.TeleBot(config.BOT_TOKEN)

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

# Keyboards
def get_main_keyboard(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = types.KeyboardButton("🔍 Kino qidirish")
    btn_genres = types.KeyboardButton("📂 Janrlar")
    btn_top = types.KeyboardButton("🔥 Top 10 kinolar")
    btn_fav = types.KeyboardButton("❤️ Sevimlilarim")
    btn_profile = types.KeyboardButton("👤 Shaxsiy Profil")
    btn_random = types.KeyboardButton("🎲 Qanday kino ko'rsam?")
    btn_ref = types.KeyboardButton("👥 Do'stlarni taklif qilish")
    btn_prem = types.KeyboardButton("👑 Premium A'zolik")
    btn_supp = types.KeyboardButton("✍️ Adminga Murojaat")
    
    keyboard.row(btn_search, btn_genres)
    keyboard.row(btn_top, btn_fav)
    keyboard.row(btn_profile, btn_random)
    keyboard.row(btn_ref, btn_prem)
    keyboard.row(btn_supp)
    
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
    btn_back = types.KeyboardButton("⬅️ Bosh sahifa")
    
    keyboard.row(btn_add, btn_del)
    keyboard.row(btn_list, btn_stats)
    keyboard.row(btn_queue, btn_source_ch)
    keyboard.row(btn_channels, btn_adv)
    keyboard.row(btn_post_gen, btn_auto_post)
    keyboard.row(btn_vip_mgmt, btn_prem_mgmt)
    
    if is_super_admin(user_id):
        btn_promo = types.KeyboardButton("🔑 Admin kodi yaratish")
        keyboard.row(btn_promo)
        
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

    code, title, caption, genre, views, is_vip = movie

    # VIP Protection Check
    if is_vip and not database.is_premium_user(user_id) and not is_admin(user_id):
        ref_count = database.get_user_referral_count(user_id)
        rem_refs = 10 - (ref_count % 10) if (ref_count % 10) != 0 else 10
        vip_text = (
            f"🔒 **Ushbu kino faqat 👑 Premium foydalanuvchilar uchun!**\n\n"
            f"🎬 **Kino:** {title}\n"
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

    elif call.data.startswith("genre:"):
        genre_name = call.data.split(":")[1]
        movies = database.get_movies_by_genre(genre_name)
        if not movies:
            bot.answer_callback_query(call.id, f"'{genre_name}' janrida hali kinolar yo'q.", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        for code, title, views, is_vip in movies:
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
        
        code = generate_unique_code()
        success = database.add_movie(code, title, caption, genre)
        if success:
            database.trigger_auto_backup(bot)
            bot.send_message(
                call.message.chat.id,
                f"✅ Yangi kino yaratildi!\n🔑 Biriktirilgan Kod: `{code}`\n🎬 Nomi: *{title}*\n🎭 Janr: *{genre}*\n\nEndi ushbu kod ostiga qismlarini (video fayllarini) yuklaymiz.",
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

        if not pending_id or not file_id or not title:
            bot.answer_callback_query(call.id, "❌ Ma'lumot topilmadi!", show_alert=True)
            return

        code = generate_unique_code()
        database.add_movie(code, title, caption, genre)
        database.add_episode(code, "To'liq film", file_id)
        database.mark_pending_fulfilled(pending_id)

        bot.answer_callback_query(call.id, f"✅ Kino #{queue_num} saqlandi!")
        bot.send_message(call.message.chat.id, f"✅ **Kino #{queue_num}** (*{title}*) saqlandi! (🔑 Kod: `{code}`)", parse_mode="Markdown")

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

    # Case A: Post HAS caption
    if caption:
        lines = [line.strip() for line in caption.split("\n") if line.strip()]
        raw_title = lines[0] if lines else "Kino"
        
        # Clean title from hashtags
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

        code = generate_unique_code()
        database.add_movie(code, clean_title, description, detected_genre)
        database.add_episode(code, "To'liq film", file_id)
        database.trigger_auto_backup(bot)


        # Notify Super Admins
        notice_text = (
            f"📥 **MANBA KANALIDAN YANGI KINO AVTOMATIK SAQLANDI!**\n\n"
            f"🎬 **Nomi:** {clean_title}\n"
            f"🎭 **Janr:** {detected_genre}\n"
            f"🔑 **Biriktirilgan Kod:** `{code}`\n\n"
            f"*(Foydalanuvchilar `{code}` kodi orqali ko'rishlari mumkin)*"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                bot.send_message(admin_id, notice_text, parse_mode="Markdown")
            except Exception as e:
                print(f"Failed to notify admin {admin_id}: {e}")

    # Case B: Post HAS NO caption (Nameless video -> added to pending_queue)
    else:
        q_num = database.add_to_pending_queue(file_id)
        alert_text = (
            f"📥 **MANBA KANALIGA NOMSIZ VIDEO JOYLASHDI!**\n\n"
            f"📌 **Kino #{q_num}** sifatida navbatga qo'shildi.\n"
            f"Siz uni **`📥 Kutilayotgan Kinolar`** bo'limi orqali ketma-ket nomlashingiz mumkin."
        )
        for admin_id in config.ADMIN_IDS:
            try:
                bot.send_message(admin_id, alert_text, parse_mode="Markdown")
            except Exception as e:
                print(f"Failed to notify admin {admin_id}: {e}")


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
        bot.send_message(message.chat.id, "Kino kodi yoki nomini kiriting (Masalan: `1010` yoki `Avatar`):", parse_mode="Markdown")
        return

    elif text == "📂 Janrlar":
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(text=g, callback_data=f"genre:{g}") for g in GENRES]
        markup.add(*btns)
        bot.send_message(message.chat.id, "📂 **Kino janrini tanlang:**", reply_markup=markup, parse_mode="Markdown")
        return

    elif text == "🔥 Top 10 kinolar":
        top_movies = database.get_top_movies(10)
        if not top_movies:
            bot.send_message(message.chat.id, "Hozircha reyting shakllanmagan.")
            return

        text_response = "🔥 **Eng ko'p ko'rilgan TOP 10 kinolar:**\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for idx, (code, title, views, genre, is_vip) in enumerate(top_movies, 1):
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

    elif text == "📋 Barcha kinolar" and is_admin(user_id):
        movies = database.get_all_movies()
        if not movies:
            bot.send_message(message.chat.id, "Hozircha ma'lumotlar bazasida kinolar yo'q.")
            return

        response = "📋 **Kinolar ro'yxati (kod - nomi - janr - ko'rishlar - VIP):**\n\n"
        for code, title, genre, views, is_vip in movies:
            vip_mark = " 🔒 [VIP]" if is_vip else ""
            response += f"🔑 `{code}` - **{title}**{vip_mark} ({genre}) | 👁 {views} ta\n"
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
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
        msg = bot.send_message(message.chat.id, "VIP statusini o'zgartirmoqchi bo'lgan kino kodini kiriting (Masalan: 1230):")
        bot.register_next_step_handler(msg, process_toggle_vip_movie)
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

    elif text == "📡 Manba Kanalini Sozlash" and is_admin(user_id):
        current_source = database.get_setting('source_channel_id', 'Sozlanmagan (Barcha admin kanallaridan qabul qilinadi)')
        msg_text = (
            f"📡 **KINOLAR UCHUN MANBA KANALI SOZLAMALARI:**\n\n"
            f"📌 **Hozirgi Manba Kanali:** `{current_source}`\n\n"
            f"Yangi manba kanali username yoki ID-sini kiriting (Masalan: `@my_private_movies` yoki `-100123456789`):\n"
            f"*(Kanaldan avtomatik kinolar olinishi uchun bot shu kanalda Admin bo'lishi shart!)*\n\n"
            f"Bekor qilish uchun 'bekor' deb yozing."
        )
        msg = bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_set_source_channel)
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

    # Check Direct Movie Code Search
    movie = database.get_movie(text)
    if movie:
        send_movie_card(message.chat.id, text, user_id)
        return

    # Name / Keyword Search Fallback
    matches = database.search_movies_by_name(text)
    if matches:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for code, title, genre, views, is_vip in matches:
            vip_mark = " 🔒" if is_vip else ""
            markup.add(types.InlineKeyboardButton(text=f"🎬 {title}{vip_mark} (🔑 {code})", callback_data=f"show_movie:{code}"))

        bot.send_message(message.chat.id, f"🔍 **'{text}' bo'yicha topilgan kinolar:**", reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Bunday kodli yoki nomli kino topilmadi. Kodni yoki nomini tekshirib qaytadan kiritib ko'ring.")

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

    pending_id, queue_num, file_id = next_item
    admin_states[user_id] = {
        'pending_id': pending_id,
        'queue_num': queue_num,
        'file_id': file_id
    }

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="⏸ To'xtatish (Pause)", callback_data="pause_batch_naming"))

    msg = bot.send_message(
        chat_id,
        f"🎬 **KINO #{queue_num}** (Navbatdagi kutilayotgan kino):\n\n"
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

    title = message.text.strip() if message.text else ""
    if not title:
        msg = bot.send_message(message.chat.id, "Xato: Bo'sh matn. Iltimos, kino nomini kiriting:")
        bot.register_next_step_handler(msg, process_batch_movie_title)
        return

    if user_id not in admin_states:
        bot.send_message(message.chat.id, "Jarayon to'xtatilgan.", reply_markup=get_admin_keyboard(user_id))
        return

    admin_states[user_id]['title'] = title
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="⏸ To'xtatish (Pause)", callback_data="pause_batch_naming"))

    msg = bot.send_message(
        message.chat.id,
        f"📝 **Kino #{admin_states[user_id]['queue_num']}** (*{title}*) uchun tavsif kiriting:\n"
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

    caption = message.text.strip() if message.text else ""
    if caption == '-':
        caption = ""

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

def process_toggle_vip_movie(message):

    user_id = message.from_user.id
    code = message.text.strip() if message.text else ""
    if not code or code.lower() == 'bekor':
        bot.send_message(message.chat.id, "Amal bekor qilindi.", reply_markup=get_admin_keyboard(user_id))
        return

    found, is_vip = database.toggle_movie_vip(code)
    if found:
        status_str = "🔒 **VIP (Faqat Premium)**" if is_vip else "🌐 **Oddiy (Barchaga ochiq)**"
        bot.send_message(message.chat.id, f"✅ `{code}` kodli kino statusi o'zgartirildi: {status_str}", parse_mode="Markdown", reply_markup=get_admin_keyboard(user_id))
    else:
        bot.send_message(message.chat.id, f"❌ `{code}` kodli kino topilmadi.", reply_markup=get_admin_keyboard(user_id))

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

# Start polling
if __name__ == '__main__':
    web_thread = threading.Thread(target=start_health_check_server, daemon=True)
    web_thread.start()

    ping_thread = threading.Thread(target=keep_alive_pinger, daemon=True)
    ping_thread.start()

    auto_restore_on_startup()

    print("Bot ishga tushmoqda...")
    bot.infinity_polling()

