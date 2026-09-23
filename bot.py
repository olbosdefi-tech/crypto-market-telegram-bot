import os
import httpx

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

COINS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Crypto Market Bot\n\n"
        "Use /help to see available commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show commands\n"
        "/price BTC - Check a crypto price"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /price BTC"
        )
        return

    symbol = context.args[0].upper()

    coin_id = COINS.get(symbol)

    if not coin_id:
        await update.message.reply_text(
            "Coin not supported yet\n"
            "Try: BTC, ETH or SOL"
        )
        return

    url = "https://api.coingecko.com/api/v3/simple/price"

    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0)as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()

        current_price = data[coin_id]["usd"]
        change_24h = data[coin_id].get("usd_24h_change", 0)

        await update.message.reply_text(
            f"{symbol} MarketPrice\n\n"
            f"Price: ${current_price:,.2f}\n"
            f"24h Change: {change_24h:+.2f}%"
        )

    except Exception:
        await update.message.reply_text(
            "Unable to fetch market data right now."
        )

def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN was not found in .env")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("price", price))

    print("Bot is running...")

    app.run_polling()

if __name__ == "__main__":
    main()