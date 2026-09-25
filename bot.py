import os
import httpx

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")

COINGECKO_HEADERS = {
    "x-cg-demo-api-key": COINGECKO_API_KEY
}

COIN_IDS = {}

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
        "/price <symbol> - Check any supported crypto\n"
        "/top - Show top 5 cryptocurrencies by market cap"
    )

async def find_coin_id(symbol: str):
    symbol = symbol.strip().upper()

    if symbol in COIN_IDS:
        return COIN_IDS[symbol]

    url = "https://api.coingecko.com/api/v3/search"
    params = {"query": symbol}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                params=params,
                headers=COINGECKO_HEADERS
            )
            response.raise_for_status()

        coins = response.json().get("coins", [])

        for coin in coins:
            coin_symbol = str(coin.get("symbol", "")).strip().upper()

            if coin_symbol == symbol:
                coin_id = coin["id"]
                COIN_IDS[symbol] = coin_id
                return coin_id

        return None

    except Exception as e:
        print("find_coin_id error:", type(e).name, e)
        return None

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /price BTC"
        )
        return

    symbol = context.args[0].upper()

    coin_id = await find_coin_id(symbol)

    if not coin_id:
        await update.message.reply_text(
            f"Could not find a coin with symbol: {symbol}"
        )
        return
    
    url = "https://api.coingecko.com/api/v3/simple/price"

    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0)as client:
            response = await client.get(url, params=params, headers=COINGECKO_HEADERS)
            response.raise_for_status()

        data = response.json()

        current_price = data[coin_id]["usd"]
        change_24h = data[coin_id].get("usd_24h_change", 0)
        market_cap = data[coin_id].get("usd_market_cap", 0)

        await update.message.reply_text(
            f"{symbol} MarketPrice\n\n"
            f"Price: ${current_price:,.2f}\n"
            f"24h Change: {change_24h:+.2f}%\n"
            f"Market Cap: ${market_cap:,.0f}"
        )

    except Exception:
        await update.message.reply_text(
            "Unable to fetch market data right now."
        )

async def top_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://api.coingecko.com/api/v3/coins/markets"

    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 5,
        "page": 1,
        "sparkline": "false",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0)as client:
            response = await client.get(url, params=params, headers=COINGECKO_HEADERS)
            response.raise_for_status()

        coins = response.json()

    except Exception:
        await update.message.reply_text(
            "Unable to fetch top market data right now"
        )
        return

    message = "Top 5 Cryptocurrencies by Market Cap\n\n"

    for i, coin in enumerate(coins, start=1):
        symbol = coin["symbol"].upper()
        price = coin["current_price"]
        change = coin.get("price_change_percentage_24h") or 0

        message += (
            f"{i}. {symbol}\n"
            f"Price: ${price:,.2f}\n"
            f"24h: {change:+.2f}%\n\n"
        )

    await update.message.reply_text(message)

def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN was not found in .env")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("top", top_coins))

    print("Bot is running...")

    app.run_polling()

if __name__ == "__main__":
    main()