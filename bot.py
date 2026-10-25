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
QUANTITY, LOCATION, PAYMENT_PROOF = range(3)

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
            "👑 *ChannelCart Admin Dashboard*\n\nWelcome back! Use the permanent buttons below to manage your store:",
            reply_markup=ADMIN_REPLY_KEYBOARD,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    product_id = args[0] if args else "DEFAULT_ITEM"
    context.user_data["product_id"] = product_id
    
    await update.message.reply_text(
        f"📦 *Welcome to ChannelCart!*\n\n"
        f"Selected Product: `{product_id}`\n\n"
        f"How many items would you like to buy?",
        parse_mode="Markdown"
    )
    return QUANTITY


async def admin_home_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Brings admin back to the main control center."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    await update.message.reply_text(
        "👑 *ChannelCart Admin Control Center*",
        reply_markup=ADMIN_REPLY_KEYBOARD,
        parse_mode="Markdown"
    )


# --- BUYER CONVERSATION FLOW ---
async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quantity"] = update.message.text
    location_btn = KeyboardButton("📍 Share Location", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[location_btn]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Great! Next, please share your **delivery location** using the button below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return LOCATION


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    context.user_data["lat"] = location.latitude
    context.user_data["lng"] = location.longitude

    payment_instructions = (
        "Location received! 📍\n\n"
        "💳 **Please make your payment using one of the options below:**\n"
        "• **Telebirr:** `0912289675`\n"
        "• **CBE Account:** `1000223663568`\n\n"
        "Once paid, please send a **photo or screenshot of your payment receipt** here to complete your order."
    )

    await update.message.reply_text(
        payment_instructions,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return PAYMENT_PROOF


async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ORDER_COUNTER
    ORDER_COUNTER += 1
    order_id = f"ORD-{ORDER_COUNTER}"
    
    photo_file_id = update.message.photo[-1].file_id if update.message.photo else None
    buyer = update.message.from_user
    lat = context.user_data['lat']
    lng = context.user_data['lng']

    save_order(
        order_id=order_id,
        buyer_id=buyer.id,
        username=buyer.username or buyer.first_name,
        product_id=context.user_data['product_id'],
        quantity=context.user_data['quantity'],
        lat=lat,
        lng=lng
    )

    await update.message.reply_text(
        f"✅ *Order Placed Successfully via ChannelCart!*\n\n"
        f"🆔 Order ID: `{order_id}`\n"
        f"📦 Item: `{context.user_data['product_id']}`\n"
        f"🔢 Quantity: `{context.user_data['quantity']}`\n\n"
        f"The seller has been notified to verify your payment.",
        parse_mode="Markdown"
    )

    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("❌ Reject Order", callback_data=f"reject_{order_id}")
        ]
    ])

    maps_link = f"https://maps.google.com/?q={lat},{lng}"

    admin_caption = (
        f"🚨 *CHANNELCART: NEW ORDER!* 🚨\n\n"
        f"🆔 Order ID: `{order_id}`\n"
        f"👤 Buyer: @{buyer.username} (ID: {buyer.id})\n"
        f"📦 Product: `{context.user_data['product_id']}`\n"
        f"🔢 Quantity: `{context.user_data['quantity']}`\n\n"
        f"🗺️ [Google Maps Navigation Link]({maps_link})"
    )

    if photo_file_id:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo_file_id,
            caption=admin_caption,
            reply_markup=admin_markup,
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_caption,
            reply_markup=admin_markup,
            parse_mode="Markdown",
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
        f"📢 *Step 1/3: Product Title*\n\n"
        f"Generated Item ID: `{item_id}`\n\n"
        f"Please type the **Title/Name** of the product:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return POST_TITLE


async def receive_post_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_title"] = update.message.text
    await update.message.reply_text(
        "📢 *Step 2/3: Product Price*\n\n"
        "Please type the **Price** (e.g., `$24.99` or `500 ETB`):",
        parse_mode="Markdown"
    )
    return POST_PRICE


async def receive_post_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_price"] = update.message.text
    await update.message.reply_text(
        "📢 *Step 3/3: Product Photo*\n\n"
        f"Please send the **photo** of the product to publish it to `{CHANNEL_ID}`:",
        parse_mode="Markdown"
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

    # Save to products database
    save_product(item_id, title, price)

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Order Now", url=f"https://t.me/{bot_username}?start={item_id}")]
    ])

    product_caption = (
        f"📦 **{title}**\n\n"
        f"💵 Price: `{price}`\n\n"
        f"Click the button below to buy instantly via ChannelCart!"
    )

    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=photo_file_id,
            caption=product_caption,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            f"✅ Success! Product published to `{CHANNEL_ID}` with ID `{item_id}`.",
            reply_markup=ADMIN_REPLY_KEYBOARD,
            parse_mode="Markdown"
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
        text = "📋 *ChannelCart - Recent Orders*\n\n"
        for order in orders[:10]:
            order_id, product_id, quantity, status, created_at = order
            text += f"🆔 `{order_id}`\n📦 Product: `{product_id}` (Qty: {quantity})\n📌 Status: *{status}*\n🕒 Time: {created_at}\n\n"

    await update.message.reply_text(text, reply_markup=ADMIN_REPLY_KEYBOARD, parse_mode="Markdown")


async def manage_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays active products with options to delete them."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    products = get_all_products()
    if not products:
        await update.message.reply_text("📭 No products posted yet.", reply_markup=ADMIN_REPLY_KEYBOARD)
        return

    text = "📦 *Active Products Management*\n\n"
    for prod in products:
        prod_id, title, price, created = prod
        text += f"🆔 `{prod_id}` | *{title}* | 💵 `{price}`\n"

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"🗑️ Delete {prod_id}", callback_data=f"delprod_{prod_id}")]])
        await update.message.reply_text(text=f"📦 `{prod_id}` — **{title}** ({price})", reply_markup=keyboard, parse_mode="Markdown")
        text = ""


async def show_sales_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays revenue and analytics stats."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    total, completed, pending, rejected = get_sales_stats()

    stats_text = (
        f"📊 *ChannelCart Sales Analytics*\n\n"
        f"📦 Total Orders: `{total}`\n"
        f"🟢 Completed Orders: `{completed}`\n"
        f"⏳ Pending Orders: `{pending}`\n"
        f"🔴 Rejected Orders: `{rejected}`\n"
    )

    await update.message.reply_text(stats_text, reply_markup=ADMIN_REPLY_KEYBOARD, parse_mode="Markdown")


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Handle Product Deletion
    if data.startswith("delprod_"):
        prod_id = data.split("_", 1)[1]
        delete_product(prod_id)
        await query.edit_message_text(f"🗑️ Product `{prod_id}` has been deleted from active inventory.", parse_mode="Markdown")
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
                caption=query.message.caption + "\n\n🟢 *STATUS: Payment Confirmed*",
                reply_markup=delivery_markup,
                parse_mode="Markdown"
            )
            await context.bot.send_message(chat_id=buyer_id, text=f"🎉 Your payment for ChannelCart order **{order_id}** has been confirmed!")

        elif action == "reject":
            update_order_status(order_id, "Rejected")
            await query.edit_message_caption(caption=query.message.caption + "\n\n🔴 *STATUS: Payment Rejected*")
            await context.bot.send_message(chat_id=buyer_id, text=f"❌ Payment for ChannelCart order **{order_id}** could not be verified.")

        elif action == "delivering":
            update_order_status(order_id, "Out for Delivery")
            await context.bot.send_message(chat_id=buyer_id, text=f"🚚 Your ChannelCart order **{order_id}** is now out for delivery!")

        elif action == "completed":
            update_order_status(order_id, "Completed")
            await context.bot.send_message(chat_id=buyer_id, text=f"📦 ChannelCart order **{order_id}** has been successfully delivered. Thank you!")


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
            PAYMENT_PROOF: [MessageHandler(filters.PHOTO, handle_payment)],
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

    print("ChannelCart Bot is running with Analytics, Product Manager, and Maps Links...")
    app.run_polling()


if __name__ == "__main__":
    main()