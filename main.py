import os
import io
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from rembg import remove
from PIL import Image, ImageDraw, ImageEnhance
from flask import Flask
from threading import Thread

# --- Render Port Binding Fix ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Running!", 200

def run_flask():
    # Render সাধারণত 10000 পোর্ট ব্যবহার করে, তাই এটি নির্দিষ্ট করে দেওয়া ভালো
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# বট শুরু হওয়ার আগেই ফ্ল্যাস্ক সার্ভার চালু করে দেওয়া
Thread(target=run_flask).start()

# --- কনফিগারেশন ও বট লজিক ---
TOKEN = os.getenv('BOT_TOKEN')
logging.basicConfig(level=logging.INFO)

# লোগো জেনারেটর ফাংশন
def generate_logo(text, bg_color):
    img = Image.new('RGB', (500, 500), color=bg_color)
    d = ImageDraw.Draw(img)
    d.text((150, 230), text, fill=(255, 255, 255)) 
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 **বট অনলাইন!** 🔥\n\n"
        "/removebackground - ব্যাকগ্রাউন্ড মুছুন\n"
        "/addbackground [color] - কালার ব্যাকগ্রাউন্ড\n"
        "/addbacklogo - নতুন ব্যাকগ্রাউন্ড ফটো সেট করুন\n"
        "/edit - অটো এডিট\n"
        "/logo [Name] - লোগো বানান"
    )

async def remove_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'remove'
    await update.message.reply_text("ছবিটি পাঠান।")

async def add_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: /addbackground blue")
        return
    context.user_data['action'] = 'add'
    context.user_data['color'] = context.args[0]
    await update.message.reply_text(f"এখন ছবিটি পাঠান।")

async def add_back_logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'get_bg_image'
    await update.message.reply_text("প্রথমে **ব্যাকগ্রাউন্ড** ছবিটি পাঠান।")

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'edit'
    await update.message.reply_text("এডিট করার জন্য ছবিটি পাঠান।")

async def logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: /logo YourName")
        return
    name = " ".join(context.args)
    context.user_data['logo_name'] = name
    keyboard = [[InlineKeyboardButton("১০টি", callback_data='10'), InlineKeyboardButton("৫০টি", callback_data='50')], [InlineKeyboardButton("১০০টি", callback_data='100')]]
    await update.message.reply_text(f"'{name}' নামে কয়টি লোগো চান?", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data)
    name = context.user_data.get('logo_name', 'Logo')
    await query.edit_message_text(f"{count}টি লোগো তৈরি হচ্ছে...")
    for i in range(count):
        random_color = (random.randint(0,200), random.randint(0,200), random.randint(0,200))
        logo_bio = generate_logo(name, random_color)
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=logo_bio)

async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get('action')
    if action == 'get_bg_image':
        file = await update.message.photo[-1].get_file()
        context.user_data['stored_bg'] = await file.download_as_bytearray()
        context.user_data['action'] = 'get_subject_image'
        await update.message.reply_text("ব্যাকগ্রাউন্ড সেভ হয়েছে। এবার **আপনার ছবিটি** পাঠান।")
        return
    if not action: return
    wait_msg = await update.message.reply_text("AI কাজ করছে... অপেক্ষা করুন।")
    try:
        file = await update.message.photo[-1].get_file()
        img_bytes = await file.download_as_bytearray()
        input_img = Image.open(io.BytesIO(img_bytes))
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
            subj_no_bg = subj_no_bg.resize(bg_img.size, Image.LANCZOS)
            bg_img.alpha_composite(subj_no_bg)
            output = bg_img.convert("RGB")
        elif action == 'edit':
            enhancer = ImageEnhance.Brightness(input_img)
            input_img = enhancer.enhance(1.2)
            output = ImageEnhance.Sharpness(input_img).enhance(2.0)
        bio = io.BytesIO()
        output.save(bio, 'PNG')
        bio.seek(0)
        await update.message.reply_document(document=bio, filename="result.png")
        await wait_msg.delete()
    except Exception as e:
        await update.message.reply_text("ভুল হয়েছে।")
    context.user_data.clear()

def main():
    app_bot = Application.builder().token(TOKEN).build()
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
