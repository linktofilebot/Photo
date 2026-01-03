import os
import io
import random
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from rembg import remove
from PIL import Image, ImageDraw, ImageEnhance
from flask import Flask
from threading import Thread

# --- Render Port Binding Fix (Flask Server) ---
# Render-এ Web Service চালাতে গেলে এটি অবশ্যই লাগবে
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- কনফিগারেশন ---
TOKEN = os.getenv('BOT_TOKEN') # Render এর Environment Variables এ টোকেন দিবেন
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- লোগো জেনারেটর ফাংশন ---
def generate_logo(text, bg_color):
    img = Image.new('RGB', (500, 500), color=bg_color)
    d = ImageDraw.Draw(img)
    # টেক্সট মাঝখানে বসানো
    d.text((150, 230), text, fill=(255, 255, 255)) 
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- কমান্ড হ্যান্ডলারস ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 **অটো ফটো এডিট বক্সে স্বাগতম!** 🔥\n\n"
        "নিচের কমান্ডগুলো ব্যবহার করুন:\n"
        "🖼 /removebackground - ছবির ব্যাকগ্রাউন্ড মুছুন\n"
        "🎨 /addbackground [color] - এক রঙের ব্যাকগ্রাউন্ড (উদা: /addbackground blue)\n"
        "📸 /addbacklogo - ছবির পেছনে অন্য ছবি সেট করুন\n"
        "✨ /edit - ছবি অটো এডিট (Bright & Sharp)\n"
        "💎 /logo [Name] - নাম দিয়ে লোগো বানান (১০০টি পর্যন্ত)"
    )

# ১. ব্যাকগ্রাউন্ড রিমুভ কমান্ড
async def remove_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'remove'
    await update.message.reply_text("🖼 ছবিটি পাঠান যার ব্যাকগ্রাউন্ড রিমুভ করতে চান।")

# ২. ব্যাকগ্রাউন্ড কালার অ্যাড কমান্ড
async def add_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: `/addbackground red` (বা অন্য কালার)")
        return
    context.user_data['action'] = 'add'
    context.user_data['color'] = context.args[0]
    await update.message.reply_text(f"এখন ছবিটি পাঠান। আমি ব্যাকগ্রাউন্ড {context.args[0]} করে দেব।")

# ৩. ছবির পেছনে অন্য ছবি (Logo/BG) অ্যাড করা
async def add_back_logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'get_bg_image'
    await update.message.reply_text("📸 প্রথমে **ব্যাকগ্রাউন্ড** হিসেবে যে ছবিটি ব্যবহার করতে চান সেটি পাঠান।")

# ৪. অটো এডিট কমান্ড
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'edit'
    await update.message.reply_text("✨ অটো এডিট করার জন্য ছবিটি পাঠান।")

# ৫. লোগো মেকার কমান্ড
async def logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: `/logo YourName`")
        return
    name = " ".join(context.args)
    context.user_data['logo_name'] = name
    
    keyboard = [
        [InlineKeyboardButton("১০টি", callback_data='10'), InlineKeyboardButton("৫০টি", callback_data='50')],
        [InlineKeyboardButton("১০০টি", callback_data='100')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"💎 '{name}' নামে কয়টি লোগো বানাতে চান?", reply_markup=reply_markup)

# লোগো বাটন হ্যান্ডলার (একসাথে ১০০ লোগো জেনারেশন)
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data)
    name = context.user_data.get('logo_name', 'Logo')
    
    await query.edit_message_text(f"⏳ আপনার জন্য {count}টি লোগো তৈরি হচ্ছে... (কিছুটা সময় লাগবে)")
    
    for i in range(count):
        random_color = (random.randint(0,200), random.randint(0,200), random.randint(0,200))
        logo_bio = generate_logo(name, random_color)
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=logo_bio)
        if i % 10 == 0: time.sleep(1) # টেলিগ্রাম ফ্লাড কন্ট্রোল
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ সব লোগো পাঠানো শেষ!")

# --- ইমেজ প্রসেসিং (সব ছবির কাজ এখানে হয়) ---
async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get('action')
    
    # /addbacklogo এর প্রথম ধাপ: ব্যাকগ্রাউন্ড সেভ করা
    if action == 'get_bg_image':
        file = await update.message.photo[-1].get_file()
        context.user_data['stored_bg'] = await file.download_as_bytearray()
        context.user_data['action'] = 'get_subject_image'
        await update.message.reply_text("✅ ব্যাকগ্রাউন্ড পাওয়া গেছে! এবার **মূল ছবিটি** পাঠান।")
        return

    if not action:
        await update.message.reply_text("আগে একটি কমান্ড দিন। যেমন: /removebackground")
        return

    msg = await update.message.reply_text("⚙️ AI প্রসেসিং হচ্ছে... কিছুক্ষণ অপেক্ষা করুন।")
    
    try:
        # ইউজার থেকে আসা ফটো ডাউনলোড করা
        file = await update.message.photo[-1].get_file()
        img_bytes = await file.download_as_bytearray()
        input_img = Image.open(io.BytesIO(img_bytes))

        # কন্ডিশন অনুযায়ী এডিট করা
        if action == 'remove':
            output = remove(input_img)
        
        elif action == 'add':
            color = context.user_data.get('color', 'white')
            no_bg = remove(input_img)
            output = Image.new("RGB", no_bg.size, color)
            output.paste(no_bg, (0, 0), no_bg)
        
        elif action == 'get_subject_image':
            subj_no_bg = remove(input_img)
            bg_img = Image.open(io.BytesIO(context.user_data['stored_bg'])).convert("RGBA")
            # রিসাইজ করে ব্যাকগ্রাউন্ডের সমান করা
            subj_no_bg = subj_no_bg.resize(bg_img.size, Image.LANCZOS)
            bg_img.alpha_composite(subj_no_bg)
            output = bg_img.convert("RGB")
            
        elif action == 'edit':
            enhancer = ImageEnhance.Brightness(input_img)
            input_img = enhancer.enhance(1.2)
            output = ImageEnhance.Sharpness(input_img).enhance(2.0)

        # রেজাল্ট পাঠানো
        out_bio = io.BytesIO()
        output.save(out_bio, 'PNG')
        out_bio.seek(0)
        await update.message.reply_document(document=out_bio, filename="edited_by_bot.png")
        await msg.delete()

    except Exception as e:
        logging.error(e)
        await update.message.reply_text("❌ দুঃখিত, প্রসেসিং এর সময় ভুল হয়েছে।")
    
    context.user_data.clear()

# --- মেইন ফাংশন ---
def main():
    # Flask সার্ভারকে আলাদা থ্রেডে চালানো (Render পোর্ট ফিক্স)
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    # টেলিগ্রাম বট সেটআপ
    app_bot = Application.builder().token(TOKEN).build()
    
    # হ্যান্ডলার রেজিস্টার করা
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("removebackground", remove_bg_cmd))
    app_bot.add_handler(CommandHandler("addbackground", add_bg_cmd))
    app_bot.add_handler(CommandHandler("addbacklogo", add_back_logo_cmd))
    app_bot.add_handler(CommandHandler("logo", logo_cmd))
    app_bot.add_handler(CommandHandler("edit", edit_cmd))
    app_bot.add_handler(CallbackQueryHandler(button_callback))
    app_bot.add_handler(MessageHandler(filters.PHOTO, image_handler))
    
    print("Bot is Polling...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
