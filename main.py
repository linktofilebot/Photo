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

# --- Flask Server (Render-এর জন্য দরকার) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"

def run():
    app.run(host='0.0.0.0', port=os.getenv("PORT", 8080))

# --- কনফিগারেশন ---
TOKEN = os.getenv('BOT_TOKEN') # Render এর Environment Variables এ টোকেন দিবেন
logging.basicConfig(level=logging.INFO)

# --- লোগো জেনারেটর ফাংশন ---
def generate_logo(text, bg_color):
    # ৫০০x৫০০ সাইজের লোগো
    img = Image.new('RGB', (500, 500), color=bg_color)
    d = ImageDraw.Draw(img)
    # ফন্ট ফাইল না থাকলে ডিফল্ট টেক্সট ড্র হবে
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
        "✨ /edit - ছবি অটো এনহ্যান্স করুন\n"
        "💎 /logo [Name] - আপনার নাম দিয়ে লোগো বানান (১০০টি পর্যন্ত)"
    )

# ব্যাকগ্রাউন্ড রিমুভ কমান্ড
async def remove_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'remove'
    await update.message.reply_text("ছবিটি পাঠান যার ব্যাকগ্রাউন্ড রিমুভ করতে চান।")

# ব্যাকগ্রাউন্ড কালার অ্যাড কমান্ড
async def add_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: `/addbackground red`", parse_mode="Markdown")
        return
    context.user_data['action'] = 'add'
    context.user_data['color'] = context.args[0]
    await update.message.reply_text(f"এখন ছবিটি পাঠান। আমি ব্যাকগ্রাউন্ড {context.args[0]} করে দেব।")

# ছবির পেছনে অন্য ছবি অ্যাড কমান্ড
async def add_back_logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'get_bg_image'
    await update.message.reply_text("প্রথমে **ব্যাকগ্রাউন্ড** হিসেবে যে ছবিটি ব্যবহার করতে চান সেটি পাঠান।")

# অটো এডিট কমান্ড
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'edit'
    await update.message.reply_text("অটো এডিট (ব্রাইটনেস ও শার্পনেস) করার জন্য ছবিটি পাঠান।")

# লোগো মেকার কমান্ড
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"'{name}' নামে কয়টি লোগো বানাতে চান?", reply_markup=reply_markup)

# লোগো বাটন সিলেকশন হ্যান্ডলার
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data)
    name = context.user_data.get('logo_name', 'Logo')
    
    await query.edit_message_text(f"আপনার জন্য {count}টি লোগো তৈরি হচ্ছে... একটু সময় দিন।")
    
    for i in range(count):
        random_color = (random.randint(0,200), random.randint(0,200), random.randint(0,200))
        logo_bio = generate_logo(name, random_color)
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=logo_bio)
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ লোগো পাঠানো সম্পন্ন হয়েছে!")

# ইমেজ হ্যান্ডলিং (সব কমান্ডের ছবির কাজ এখানে হয়)
async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get('action')
    
    if action == 'get_bg_image':
        file = await update.message.photo[-1].get_file()
        context.user_data['stored_bg'] = await file.download_as_bytearray()
        context.user_data['action'] = 'get_subject_image'
        await update.message.reply_text("ব্যাকগ্রাউন্ড পাওয়া গেছে! এবার **মূল ছবিটি** পাঠান যার ব্যাকগ্রাউন্ড পাল্টাতে চান।")
        return

    if not action:
        await update.message.reply_text("প্রথমে একটি কমান্ড দিন (যেমন: /removebackground)")
        return

    wait_msg = await update.message.reply_text("AI প্রসেসিং হচ্ছে... কিছুক্ষণ অপেক্ষা করুন।")
    
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

        # রেজাল্ট পাঠানো
        bio = io.BytesIO()
        output.save(bio, 'PNG')
        bio.seek(0)
        await update.message.reply_document(document=bio, filename="edited_by_bot.png")
        await wait_msg.delete()

    except Exception as e:
        await update.message.reply_text("দুঃখিত, কোনো সমস্যা হয়েছে। আবার চেষ্টা করুন।")
        logging.error(e)
    
    context.user_data.clear()

# --- মেইন ফাংশন ---
def main():
    # রান ফ্লাস্ক থ্রেড
    Thread(target=run).start()

    # বট অ্যাপ্লিকেশন
    app_bot = Application.builder().token(TOKEN).build()
    
    # কমান্ড রেজিস্টার
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("removebackground", remove_bg_cmd))
    app_bot.add_handler(CommandHandler("addbackground", add_bg_cmd))
    app_bot.add_handler(CommandHandler("addbacklogo", add_back_logo_cmd))
    app_bot.add_handler(CommandHandler("logo", logo_cmd))
    app_bot.add_handler(CommandHandler("edit", edit_cmd))
    app_bot.add_handler(CallbackQueryHandler(button_callback))
    app_bot.add_handler(MessageHandler(filters.PHOTO, image_handler))
    
    print("বটটি সক্রিয় হয়েছে...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
