# কোডের শুরুতে multiprocessing সেট করা হয়েছে মেমোরি ও প্রসেস ম্যানেজমেন্টের জন্য
import multiprocessing
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass

import os
import io
import random
import logging
import threading
import time
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFilter

# --- ১. Render পোর্ট ফিক্স (Flask Server) ---
app = Flask(__name__)
@app.route('/')
def health_check(): 
    return "Ultra Premium Photo Bot is Online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ফ্ল্যাস্ক সার্ভারকে আলাদা থ্রেডে চালু করা
threading.Thread(target=run_flask, daemon=True).start()

# --- ২. কনফিগারেশন ও সিম্বল লাইব্রেরি ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv('BOT_TOKEN')

LOG_SYMBOLS = {
    "Technology 💻": ["💻", "🖥️", "⚙️", "🚀", "📱", "🌐", "🛡️", "💾", "📡", "🔋", "🔌", "🔧", "🧬", "🧪", "🛰️", "🤖"],
    "Media/Movie 🎬": ["🎬", "🎥", "🍿", "🎞️", "📽️", "🌟", "🎭", "📻", "📺", "📷", "📸", "🎵", "🎶", "🎤", "🎧"],
    "Gaming 🎮": ["🎮", "🕹️", "👾", "🎯", "⚔️", "🏆", "🃏", "🎲", "🧩", "🎳", "🎢", "🎡", "🏰", "🦄", "🌋", "🐉"],
    "Business 💼": ["💼", "📊", "📈", "🏢", "🤝", "💰", "💳", "🏦", "💎", "⚖️", "🗝️", "🔓", "📦", "🚚", "🌍", "🏗️"],
    "Creative 🎨": ["🎨", "🖌️", "🖋️", "✒️", "🌈", "🖍️", "🧶", "🧵", "🎼", "🎻", "🎸", "🎹", "🎺", "🎍", "🎐", "🐚"]
}

# --- ৩. ইমেজ প্রসেসিং ফাংশনসমূহ ---

def premium_hdr_edit(img):
    img = img.convert("RGB")
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Color(img).enhance(1.4)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = img.filter(ImageFilter.DETAIL)
    return img

def generate_logo_image(text, category, color, style):
    img = Image.new('RGBA', (800, 800), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if style == "Circle":
        draw.ellipse([50, 50, 750, 750], fill=color, outline="white", width=15)
    elif style == "Square":
        draw.rectangle([50, 50, 750, 750], fill=color, outline="white", width=15)
    else: # Diamond
        draw.polygon([(400, 50), (750, 400), (400, 750), (50, 400)], fill=color, outline="white", width=15)

    symbol = random.choice(LOG_SYMBOLS.get(category, ["✨"]))
    draw.text((400, 320), symbol, fill="white", anchor="mm", font_size=250)
    draw.text((400, 580), text, fill="white", anchor="mm", font_size=80)
    
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- ৪. কমান্ড হ্যান্ডলারস ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Ultra Premium Photo Editor & Logo Bot** 🚀\n\n"
        "✨ **ফটো এডিট কমান্ডস:**\n"
        "🖼 /removebackground - ব্যাকগ্রাউন্ড মুছুন\n"
        "🎨 /addbackground [রঙ] - রঙ সেট করুন\n"
        "📸 /addbacklogo - পেছনের ছবি পরিবর্তন\n"
        "✨ /edit - **Premium HDR Auto Edit**\n\n"
        "💎 **লোগো ডিজাইন:**\n"
        "/logo [নাম] - প্রফেশনাল লোগো বানান"
    )

async def remove_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'remove'
    await update.message.reply_text("🖼 ছবিটি পাঠান যার ব্যাকগ্রাউন্ড রিমুভ হবে।")

async def add_bg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: /addbackground blue")
        return
    context.user_data['action'] = 'add'
    context.user_data['color'] = context.args[0]
    await update.message.reply_text(f"এখন ছবিটি পাঠান।")

async def add_back_logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'get_bg_image'
    await update.message.reply_text("📸 প্রথমে **ব্যাকগ্রাউন্ড** হিসেবে যে ছবি দিতে চান সেটি পাঠান।")

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'edit'
    await update.message.reply_text("✨ প্রিমিয়াম এইচডিআর এডিটের জন্য ছবিটি পাঠান।")

async def logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ব্যবহার: /logo BrandName")
        return
    context.user_data['logo_name'] = " ".join(context.args)
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in LOG_SYMBOLS.keys()]
    await update.message.reply_text("💎 লোগোর ক্যাটাগরি বেছে নিন:", reply_markup=InlineKeyboardMarkup(keyboard))

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['logo_cat'] = query.data.replace("cat_", "")
    keyboard = [
        [InlineKeyboardButton("Circle 🔴", callback_data='style_Circle'), InlineKeyboardButton("Square ⬛", callback_data='style_Square')],
        [InlineKeyboardButton("Diamond 💎", callback_data='style_Diamond')]
    ]
    await query.edit_message_text("এবার লোগোর **ডিজাইন স্টাইল** সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

async def style_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['logo_style'] = query.data.replace("style_", "")
    keyboard = [
        [InlineKeyboardButton("Black 🖤", callback_data='col_black'), InlineKeyboardButton("Gold 💛", callback_data='gold')],
        [InlineKeyboardButton("Blue 💙", callback_data='navy'), InlineKeyboardButton("Red ❤️", callback_data='crimson')],
        [InlineKeyboardButton("Random 🎲", callback_data='col_random')]
    ]
    await query.edit_message_text("লোগোর **কালার থিম** সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

async def color_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    color = query.data.replace('col_', '')
    if color == 'random': color = "#%06x" % random.randint(0, 0xFFFFFF)
    
    name = context.user_data.get('logo_name', 'Brand')
    category = context.user_data.get('logo_cat', 'Technology 💻')
    style = context.user_data.get('logo_style', 'Circle')
    
    await query.edit_message_text(f"⏳ আপনার জন্য ২০টি ইউনিক লোগো তৈরি হচ্ছে...")
    
    for i in range(20):
        logo_bio = generate_logo_image(name, category, color, style)
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=logo_bio)
        if i % 5 == 0: time.sleep(0.5)
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="✅ প্রিমিয়াম লোগো পাঠানো শেষ!")

# --- ৫. মেইন ইমেজ প্রসেসিং হ্যান্ডলার (Memory Optimized) ---
async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get('action')
    
    if action == 'get_bg_image':
        file = await update.message.photo[-1].get_file()
        context.user_data['stored_bg'] = await file.download_as_bytearray()
        context.user_data['action'] = 'get_subject_image'
        await update.message.reply_text("✅ ব্যাকগ্রাউন্ড পাওয়া গেছে! এবার আপনার **মূল ছবিটি** পাঠান।")
        return

    if not action: return

    wait_msg = await update.message.reply_text("⚙️ AI Processing... কিছুক্ষণ অপেক্ষা করুন।")
    try:
        # rembg মেমোরি বাঁচাতে ফাংশনের ভেতর ইম্পোর্ট করা হয়েছে
        from rembg import remove as rm_bg
        
        file = await update.message.photo[-1].get_file()
        img_bytes = await file.download_as_bytearray()
        input_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        if action == 'remove':
            output = rm_bg(input_img)
        elif action == 'add':
            color = context.user_data.get('color', 'white')
            no_bg = rm_bg(input_img)
            output = Image.new("RGBA", no_bg.size, color)
            output.paste(no_bg, (0, 0), no_bg)
        elif action == 'get_subject_image':
            subj_no_bg = rm_bg(input_img)
            bg_img = Image.open(io.BytesIO(context.user_data['stored_bg'])).convert("RGBA")
            subj_no_bg = subj_no_bg.resize(bg_img.size, Image.LANCZOS)
            bg_img.alpha_composite(subj_no_bg)
            output = bg_img
        elif action == 'edit':
            output = premium_hdr_edit(input_img)

        bio = io.BytesIO()
        output.convert("RGB").save(bio, 'JPEG', quality=100)
        bio.seek(0)
        await update.message.reply_photo(photo=bio, caption="✨ এডিট সম্পন্ন হয়েছে!")
        await wait_msg.delete()
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("❌ সমস্যা হয়েছে! ছবি ছোট করে আবার পাঠান।")
    
    context.user_data.clear()

def main():
    if not TOKEN:
        print("Error: BOT_TOKEN not found!")
        return
        
    app_bot = Application.builder().token(TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("removebackground", remove_bg_cmd))
    app_bot.add_handler(CommandHandler("addbackground", add_bg_cmd))
    app_bot.add_handler(CommandHandler("addbacklogo", add_back_logo_cmd))
    app_bot.add_handler(CommandHandler("edit", edit_cmd))
    app_bot.add_handler(CommandHandler("logo", logo_cmd))
    app_bot.add_handler(CallbackQueryHandler(category_handler, pattern='^cat_'))
    app_bot.add_handler(CallbackQueryHandler(style_handler, pattern='^style_'))
    app_bot.add_handler(CallbackQueryHandler(color_handler, pattern='^(navy|crimson|gold|black|col_random)$'))
    app_bot.add_handler(MessageHandler(filters.PHOTO, image_handler))
    
    print("Bot is Polling...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
