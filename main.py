import os
import io
import random
import logging
import time
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageEnhance

# --- ১. Render পোর্ট ফিক্স (Flask Server) ---
# এটি সবার আগে রাখা হয়েছে যাতে Render দ্রুত পোর্ট খুঁজে পায়
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Running!", 200

def run_flask():
    # Render সাধারণত পোর্ট ১০০০০ বা এনভায়রনমেন্ট পোর্ট ব্যবহার করে
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ফ্ল্যাস্ক সার্ভারকে আলাদা থ্রেডে দ্রুত চালু করা
threading.Thread(target=run_flask, daemon=True).start()

# --- ২. কনফিগারেশন এবং লাইব্রেরি ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv('BOT_TOKEN') # Render-এর Environment Variables-এ এটি দিবেন

# ভারি লাইব্রেরি rembg ফাংশনের ভেতর কল করা হবে মেমোরি বাঁচাতে
def remove_bg(input_image):
    from rembg import remove
    return remove(input_image)

# --- ৩. লজিক ফাংশনসমূহ ---

def generate_logo(text, bg_color):
    img = Image.new('RGB', (500, 500), color=bg_color)
    d = ImageDraw.Draw(img)
    # ফন্ট ফাইল না থাকলে ডিফল্ট টেক্সট ব্যবহার করবে
    d.text((150, 230), text, fill=(255, 255, 255)) 
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- ৪. কমান্ড হ্যান্ডলারস ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 **অল-ইন-ওয়ান ফটো এডিট বট** 🔥\n\n"
        "কমান্ড লিস্ট:\n"
        "🖼 /removebackground - ছবির ব্যাকগ্রাউন্ড মুছুন\n"
        "🎨 /addbackground [color] - কালার ব্যাকগ্রাউন্ড (উদা: /addbackground blue)\n"
        "📸 /addbacklogo - ছবির পেছনে নতুন ছবি দিন\n"
        "✨ /edit - অটো এডিট (ব্রাইটনেস ও শার্পনেস)\n"
        "💎 /logo [Name] - লোগো মেকার (১০০টি পর্যন্ত)"
    )

async def remove_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'remove'
    await update.message.reply_text("🖼 ছবিটি পাঠান যার ব্যাকগ্রাউন্ড রিমুভ করবেন।")

async def add_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: `/addbackground red`", parse_mode="Markdown")
        return
    context.user_data['action'] = 'add'
    context.user_data['color'] = context.args[0]
    await update.message.reply_text(f"এখন ছবিটি পাঠান।")

async def add_back_logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'get_bg_image'
    await update.message.reply_text("📸 প্রথমে **ব্যাকগ্রাউন্ড** হিসেবে যে ছবি দিতে চান সেটি পাঠান।")

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'edit'
    await update.message.reply_text("✨ এডিট করার জন্য ছবিটি পাঠান।")

async def logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: `/logo YourName`", parse_mode="Markdown")
        return
    name = " ".join(context.args)
    context.user_data['logo_name'] = name
    keyboard = [
        [InlineKeyboardButton("১০টি", callback_data='10'), InlineKeyboardButton("৫০টি", callback_data='50')],
        [InlineKeyboardButton("১০০টি", callback_data='100')]
    ]
    await update.message.reply_text(f"💎 কতটি লোগো বানাতে চান?", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data)
    name = context.user_data.get('logo_name', 'Logo')
    await query.edit_message_text(f"⏳ {count}টি লোগো তৈরি হচ্ছে...")
    
    for i in range(count):
        random_color = (random.randint(0,200), random.randint(0,200), random.randint(0,200))
        logo_bio = generate_logo(name, random_color)
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=logo_bio)
        if i % 10 == 0: time.sleep(1) # টেলিগ্রাম ফ্লাড কন্ট্রোল
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ সব লোগো পাঠানো শেষ!")

# --- ৫. ফটো প্রসেসিং হ্যান্ডলার (মেইন কাজ এখানে) ---
async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get('action')
    
    # ব্যাকগ্রাউন্ড ছবি রিসিভ করা (addbacklogo এর জন্য)
    if action == 'get_bg_image':
        file = await update.message.photo[-1].get_file()
        context.user_data['stored_bg'] = await file.download_as_bytearray()
        context.user_data['action'] = 'get_subject_image'
        await update.message.reply_text("✅ ব্যাকগ্রাউন্ড পাওয়া গেছে! এবার আপনার **মূল ছবিটি** পাঠান।")
        return

    if not action:
        await update.message.reply_text("প্রথমে একটি কমান্ড দিন (উদা: /removebackground)")
        return

    wait_msg = await update.message.reply_text("⚙️ AI প্রসেসিং হচ্ছে... কিছুক্ষণ অপেক্ষা করুন।")
    
    try:
        file = await update.message.photo[-1].get_file()
        img_bytes = await file.download_as_bytearray()
        input_img = Image.open(io.BytesIO(img_bytes))

        if action == 'remove':
            output = remove_bg(input_img)
        
        elif action == 'add':
            color = context.user_data.get('color', 'white')
            no_bg = remove_bg(input_img)
            output = Image.new("RGB", no_bg.size, color)
            output.paste(no_bg, (0, 0), no_bg)
        
        elif action == 'get_subject_image':
            subj_no_bg = remove_bg(input_img)
            bg_img = Image.open(io.BytesIO(context.user_data['stored_bg'])).convert("RGBA")
            subj_no_bg = subj_no_bg.resize(bg_img.size, Image.LANCZOS)
            bg_img.alpha_composite(subj_no_bg)
            output = bg_img.convert("RGB")
            
        elif action == 'edit':
            enhancer = ImageEnhance.Brightness(input_img)
            input_img = enhancer.enhance(1.2)
            output = ImageEnhance.Sharpness(input_img).enhance(2.0)

        # রেজাল্ট সেন্ড করা
        bio = io.BytesIO()
        output.save(bio, 'PNG')
        bio.seek(0)
        await update.message.reply_document(document=bio, filename="edited_photo.png")
        await wait_msg.delete()

    except Exception as e:
        logging.error(e)
        await update.message.reply_text("❌ সমস্যা হয়েছে! ছবিটির কোয়ালিটি বা সাইজ চেক করে আবার পাঠান।")
    
    context.user_data.clear()

# --- ৬. মেইন স্টার্টার ---
def main():
    if not TOKEN:
        print("Error: BOT_TOKEN not found!")
        return

    application = Application.builder().token(TOKEN).build()
    
    # হ্যান্ডলার রেজিস্টার
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("removebackground", remove_bg_cmd))
    application.add_handler(CommandHandler("addbackground", add_bg_cmd))
    application.add_handler(CommandHandler("addbacklogo", add_back_logo_cmd))
    application.add_handler(CommandHandler("logo", logo_cmd))
    application.add_handler(CommandHandler("edit", edit_cmd))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, image_handler))
    
    print("Bot is starting polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
