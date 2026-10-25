import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from database import (
    init_db, save_order, update_order_status, 
    get_order, get_all_orders, get_latest_order_counter, 
    get_next_item_id, save_product, get_all_products, delete_product, get_sales_stats
)

# Enable Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# Bot Configuration
BOT_TOKEN = "8426725362:AAE4Xe9-POLpyZWmFGcnCh5rS_uSbm2gpqU"
ADMIN_CHAT_ID = 333571879  # Seller Chat ID / Admin ID
CHANNEL_ID = "@Bright_Kids_Shop"  # Your channel handle

# Conversation States for Buyers
QUANTITY, LOCATION, PHONE, PAYMENT_PROOF = range(4)

# Conversation States for Admin Product Posting
POST_TITLE, POST_PRICE, POST_PHOTO = range(10, 13)

# Automatically sync order counter from database on startup
ORDER_COUNTER = get_latest_order_counter()

# Upgraded Persistent Admin Keyboard Layout
ADMIN_REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📋 View Recent Orders"), KeyboardButton("📢 Post New Product")],
        [KeyboardButton("📦 Manage Products"), KeyboardButton("📊 Sales Stats")],
        [KeyboardButton("🏠 Admin Home")]
    ],
    resize_keyboard=True
)


async def post_init(application):
    """Sets up the permanent Telegram command menu button."""
    commands = [
        BotCommand("start", "Start shopping or open Admin Dashboard"),
        BotCommand("cancel", "Cancel current action")
    ]
    await application.bot.set_my_commands(commands)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command, showing Admin Dashboard for seller or Buyer flow for customers."""
    user_id = update.effective_user.id
    args = context.args
    
    if user_id == ADMIN_CHAT_ID and not args:
        await update.message.reply_text(
            "👑 <b>ChannelCart Admin Dashboard</b>\n\nWelcome back! Use the permanent buttons below to manage your store:",
            reply_markup=ADMIN_REPLY_KEYBOARD,
            parse_mode="HTML"
        )
        return ConversationHandler.END

    product_id = args[0] if args else "DEFAULT_ITEM"
    context.user_data["product_id"] = product_id
    
    await update.message.reply_text(
        f"📦 <b>Welcome to ChannelCart!</b>\n\n"
        f"Selected Product: <code>{product_id}</code>\n\n"
        f"How many items would you like to buy?",
        parse_mode="HTML"
    )
    return QUANTITY


async def admin_home_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Brings admin back to the main control center."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    await update.message.reply_text(
        "👑 <b>ChannelCart Admin Control Center</b>",
        reply_markup=ADMIN_REPLY_KEYBOARD,
        parse_mode="HTML"
    )


# --- BUYER CONVERSATION FLOW ---
async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quantity"] = update.message.text
    location_btn = KeyboardButton("📍 Share Location", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[location_btn]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Great! Next, please share your <b>delivery location</b> using the button below:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    return LOCATION


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.location:
        await update.message.reply_text("⚠️ Please use the <b>'📍 Share Location'</b> button below.", parse_mode="HTML")
        return LOCATION

    location = update.message.location
    context.user_data["lat"] = location.latitude
    context.user_data["lng"] = location.longitude

    contact_btn = KeyboardButton("📞 Share Phone Number", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_btn]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Location received! 📍\n\n"
        "Now, please share your <b>phone number</b> using the button below so the delivery team can contact you:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    return PHONE


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone_number = update.message.contact.phone_number
    elif update.message.text:
        phone_number = update.message.text
    else:
        await update.message.reply_text("⚠️ Please share your phone number using the button.", parse_mode="HTML")
        return PHONE

    context.user_data["phone"] = phone_number

    payment_instructions = (
        "Phone number received! 📞\n\n"
        "💳 <b>Please make your payment using one of the options below:</b>\n"
        "• <b>Telebirr:</b> <code>0912289675</code>\n"
        "• <b>CBE Account:</b> <code>1000223663568</code>\n\n"
        "Once paid, please send a <b>photo or screenshot of your payment receipt</b> here to complete your order."
    )

    await update.message.reply_text(
        payment_instructions,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    return PAYMENT_PROOF


async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ORDER_COUNTER
    ORDER_COUNTER += 1
    order_id = f"ORD-{ORDER_COUNTER}"
    
    photo_file_id = update.message.photo[-1].file_id if update.message.photo else None
    buyer = update.message.from_user
    lat = context.user_data.get('lat')
    lng = context.user_data.get('lng')
    phone = context.user_data.get('phone')
    username = f"@{buyer.username}" if buyer.username else buyer.first_name

    save_order(
        order_id=order_id,
        buyer_id=buyer.id,
        username=username,
        product_id=context.user_data.get('product_id', 'DEFAULT_ITEM'),
        quantity=context.user_data.get('quantity', '1'),
        phone=phone,
        lat=lat,
        lng=lng
    )

    await update.message.reply_text(
        f"✅ <b>Order Placed Successfully via ChannelCart!</b>\n\n"
        f"🆔 Order ID: <code>{order_id}</code>\n"
        f"📦 Item: <code>{context.user_data.get('product_id')}</code>\n"
        f"🔢 Quantity: <code>{context.user_data.get('quantity')}</code>\n"
        f"📞 Phone: <code>{phone}</code>\n\n"
        f"The seller has been notified to verify your payment.",
        reply_markup=ADMIN_REPLY_KEYBOARD,
        parse_mode="HTML"
    )

    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("❌ Reject Order", callback_data=f"reject_{order_id}")
        ]
    ])

    maps_link = f"https://maps.google.com/?q={lat},{lng}" if lat and lng else "https://maps.google.com"

    admin_caption = (
        f"🚨 <b>CHANNELCART: NEW ORDER!</b> 🚨\n\n"
        f"🆔 Order ID: <code>{order_id}</code>\n"
        f"👤 Buyer: {username} (ID: <code>{buyer.id}</code>)\n"
        f"📞 Phone: <code>{phone}</code>\n"
        f"📦 Product: <code>{context.user_data.get('product_id')}</code>\n"
        f"🔢 Quantity: <code>{context.user_data.get('quantity')}</code>\n\n"
        f"🗺️ <a href='{maps_link}'>Click Here for Google Maps Navigation</a>"
    )

    if photo_file_id:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo_file_id,
            caption=admin_caption,
            reply_markup=admin_markup,
            parse_mode="HTML"
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_caption,
            reply_markup=admin_markup,
            parse_mode="HTML",
            disable_web_page_preview=False
        )

    return ConversationHandler.END


# --- ADMIN STEP-BY-STEP POSTING FLOW ---
async def start_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates step-by-step product posting by the admin via keyboard button."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    item_id = get_next_item_id()
    context.user_data["post_item_id"] = item_id

    await update.message.reply_text(
        f"📢 <b>Step 1/3: Product Title</b>\n\n"
        f"Generated Item ID: <code>{item_id}</code>\n\n"
        f"Please type the <b>Title/Name</b> of the product:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    return POST_TITLE


async def receive_post_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_title"] = update.message.text
    await update.message.reply_text(
        "📢 <b>Step 2/3: Product Price</b>\n\n"
        "Please type the <b>Price</b> (e.g., <code>$24.99</code> or <code>500 ETB</code>):",
        parse_mode="HTML"
    )
    return POST_PRICE


async def receive_post_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_price"] = update.message.text
    await update.message.reply_text(
        "📢 <b>Step 3/3: Product Photo</b>\n\n"
        f"Please send the <b>photo</b> of the product to publish it to <code>{CHANNEL_ID}</code>:",
        parse_mode="HTML"
    )
    return POST_PHOTO


async def publish_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives product photo, compiles details, saves to products DB, and posts to channel."""
    if not update.message.photo:
        await update.message.reply_text("Please send a valid product photo.")
        return POST_PHOTO

    photo_file_id = update.message.photo[-1].file_id
    item_id = context.user_data.get("post_item_id")
    title = context.user_data.get("post_title")
    price = context.user_data.get("post_price")

    save_product(item_id, title, price)

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Order Now", url=f"https://t.me/{bot_username}?start={item_id}")]
    ])

    product_caption = (
        f"📦 <b>{title}</b>\n\n"
        f"💵 Price: <code>{price}</code>\n\n"
        f"Click the button below to buy instantly via ChannelCart!"
    )

    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=photo_file_id,
            caption=product_caption,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await update.message.reply_text(
            f"✅ Success! Product published to <code>{CHANNEL_ID}</code> with ID <code>{item_id}</code>.",
            reply_markup=ADMIN_REPLY_KEYBOARD,
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to post. Error: {e}",
            reply_markup=ADMIN_REPLY_KEYBOARD
        )

    return ConversationHandler.END


async def list_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays recent orders for the admin."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    orders = get_all_orders()
    if not orders:
        text = "📭 No orders found in the database yet."
    else:
        text = "📋 <b>ChannelCart - Recent Orders</b>\n\n"
        for order in orders[:10]:
            order_id, product_id, quantity, status, created_at = order[0], order[1], order[2], order[3], order[4]
            text += f"🆔 <code>{order_id}</code>\n📦 Product: <code>{product_id}</code> (Qty: {quantity})\n📌 Status: <b>{status}</b>\n🕒 Time: {created_at}\n\n"

    await update.message.reply_text(text, reply_markup=ADMIN_REPLY_KEYBOARD, parse_mode="HTML")


async def manage_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays active products with options to delete them."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    products = get_all_products()
    if not products:
        await update.message.reply_text("📭 No products posted yet.", reply_markup=ADMIN_REPLY_KEYBOARD)
        return

    for prod in products:
        prod_id, title, price, created = prod
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"🗑️ Delete {prod_id}", callback_data=f"delprod_{prod_id}")]])
        await update.message.reply_text(text=f"📦 <code>{prod_id}</code> — <b>{title}</b> ({price})", reply_markup=keyboard, parse_mode="HTML")


async def show_sales_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays revenue and analytics stats."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    total, completed, pending, rejected = get_sales_stats()

    stats_text = (
        f"📊 <b>ChannelCart Sales Analytics</b>\n\n"
        f"📦 Total Orders: <code>{total}</code>\n"
        f"🟢 Completed Orders: <code>{completed}</code>\n"
        f"⏳ Pending Orders: <code>{pending}</code>\n"
        f"🔴 Rejected Orders: <code>{rejected}</code>\n"
    )

    await update.message.reply_text(stats_text, reply_markup=ADMIN_REPLY_KEYBOARD, parse_mode="HTML")


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("delprod_"):
        prod_id = data.split("_", 1)[1]
        delete_product(prod_id)
        await query.edit_message_text(f"🗑️ Product <code>{prod_id}</code> has been deleted from active inventory.", parse_mode="HTML")
        return

    if "_" in data:
        action, order_id = data.split("_", 1)
        order = get_order(order_id)
        if not order:
            await query.edit_message_caption("❌ Order not found in database.")
            return

        buyer_id = order[1]

        if action == "confirm":
            update_order_status(order_id, "Payment Confirmed")
            delivery_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚚 Mark Out for Delivery", callback_data=f"delivering_{order_id}")],
                [InlineKeyboardButton("✅ Mark Delivered", callback_data=f"completed_{order_id}")]
            ])
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n🟢 <b>STATUS: Payment Confirmed</b>",
                reply_markup=delivery_markup,
                parse_mode="HTML"
            )
            await context.bot.send_message(chat_id=buyer_id, text=f"🎉 Your payment for ChannelCart order <b>{order_id}</b> has been confirmed!", parse_mode="HTML")

        elif action == "reject":
            update_order_status(order_id, "Rejected")
            await query.edit_message_caption(caption=query.message.caption + "\n\n🔴 <b>STATUS: Payment Rejected</b>", parse_mode="HTML")
            await context.bot.send_message(chat_id=buyer_id, text=f"❌ Payment for ChannelCart order <b>{order_id}</b> could not be verified.", parse_mode="HTML")

        elif action == "delivering":
            update_order_status(order_id, "Out for Delivery")
            await context.bot.send_message(chat_id=buyer_id, text=f"🚚 Your ChannelCart order <b>{order_id}</b> is now out for delivery!", parse_mode="HTML")

        elif action == "completed":
            update_order_status(order_id, "Completed")
            await context.bot.send_message(chat_id=buyer_id, text=f"📦 ChannelCart order <b>{order_id}</b> has been successfully delivered. Thank you!", parse_mode="HTML")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Process cancelled.", reply_markup=ADMIN_REPLY_KEYBOARD)
    return ConversationHandler.END


def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Buyer Conversation Handler
    buyer_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)],
            LOCATION: [MessageHandler(filters.LOCATION, handle_location)],
            PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), handle_phone)],
            PAYMENT_PROOF: [
                MessageHandler(filters.PHOTO, handle_payment),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Admin Posting Conversation Handler
    post_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Post New Product$") & filters.User(user_id=ADMIN_CHAT_ID), start_posting)],
        states={
            POST_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_post_title)],
            POST_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_post_price)],
            POST_PHOTO: [MessageHandler(filters.PHOTO, publish_product)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(buyer_conv)
    app.add_handler(post_conv)
    app.add_handler(MessageHandler(filters.Regex("^📋 View Recent Orders$") & filters.User(user_id=ADMIN_CHAT_ID), list_orders))
    app.add_handler(MessageHandler(filters.Regex("^📦 Manage Products$") & filters.User(user_id=ADMIN_CHAT_ID), manage_products))
    app.add_handler(MessageHandler(filters.Regex("^📊 Sales Stats$") & filters.User(user_id=ADMIN_CHAT_ID), show_sales_stats))
    app.add_handler(MessageHandler(filters.Regex("^🏠 Admin Home$") & filters.User(user_id=ADMIN_CHAT_ID), admin_home_handler))
    app.add_handler(CallbackQueryHandler(admin_callback_handler))

    print("ChannelCart Bot is running cleanly...")
    app.run_polling()


if __name__ == "__main__":
    main()