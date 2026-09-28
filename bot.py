import os
import httpx
import json
import asyncio

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
WATCHLISTS = {}
WATCHLIST_FILE = "watchlists.json"
ALERTS = {}
ALERTS_FILE = "alerts.json"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Crypto Market Bot\n\n"
        "Use /help to see available commands."
    )

def load_watchlists():
    global WATCHLISTS

    try:
        with open(WATCHLIST_FILE, "r") as file:
            data = json.load(file)

        WATCHLISTS = {
            int(user_id): coins
            for user_id, coins in data.items()
        }

    except FileNotFoundError:
        WATCHLISTS = {}


def save_watchlists():
    with open(WATCHLIST_FILE, "w") as file:
        json.dump(WATCHLISTS, file, indent=4)

def load_alerts():
    global ALERTS

    try:
        with open(ALERTS_FILE, "r") as file:
            data = json.load(file)

        ALERTS = {
            int(user_id): alerts
            for user_id, alerts in data.items()
        }

    except FileNotFoundError:
        ALERTS = {}


def save_alerts():
    with open(ALERTS_FILE, "w", encoding="utf-8") as file:
        json.dump(ALERTS, file, indent=4)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show commands\n"
        "/price <symbol> - Check any supported crypto\n"
        "/top - Show top 5 cryptocurrencies by market cap\n"
        "/watch <symbol> - Add coin to watchlist\n"
        "/watchlist - Show your saved coins\n"
        "/unwatch <symbol> - Remove coin from watchlist\n"
        "/alert <symbol> <above|below> <price> - Create price alert\n"
        "/alerts - Show active price alerts\n"
        "/removealert <number> - Remove an alert\n"
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
        
async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /watch BTC"
        )
        return

    user_id = update.effective_user.id
    symbol = context.args[0].upper()

    coin_id = await find_coin_id(symbol)

    if not coin_id:
        await update.message.reply_text(
            f"Could not find a coin with symbol: {symbol}"
        )
        return

    if user_id not in WATCHLISTS:
        WATCHLISTS[user_id] = []

    if symbol in WATCHLISTS[user_id]:
        await update.message.reply_text(
            f"{symbol} is already in your watchlist."
        )
        return

    WATCHLISTS[user_id].append(symbol)
    save_watchlists()

    await update.message.reply_text(
        f"{symbol} added to your watchlist."
    )


async def watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in WATCHLISTS or not WATCHLISTS[user_id]:
        await update.message.reply_text(
            "Your watchlist is empty.\n"
            "Use /watch BTC to add a coin."
        )
        return

    message = "⭐ Your Watchlist\n\n"

    for i, symbol in enumerate(WATCHLISTS[user_id], start=1):
        coin_id = await find_coin_id(symbol)

        url = "https://api.coingecko.com/api/v3/simple/price"

        params = {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=COINGECKO_HEADERS
                )
                response.raise_for_status()

            data = response.json()

            price = data[coin_id]["usd"]
            change = data[coin_id].get("usd_24h_change", 0)

            message += (
                f"{i}. {symbol}\n"
                f"Price: ${price:,.2f}\n"
                f"24h: {change:+.2f}%\n\n"
            )

        except Exception:
            message += (
                f"{i}. {symbol}\n"
                "Unable to fetch price right now.\n\n"
            )

    await update.message.reply_text(message)

async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /unwatch BTC"
        )
        return

    user_id = update.effective_user.id
    symbol = context.args[0].upper()

    if user_id not in WATCHLISTS or symbol not in WATCHLISTS[user_id]:
        await update.message.reply_text(
            f"{symbol} is not in your watchlist."
        )
        return

    WATCHLISTS[user_id].remove(symbol)
    save_watchlists()

    await update.message.reply_text(
        f"{symbol} removed from your watchlist."
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

async def alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text(
            "Usage:\n"
            "/alert BTC above 90000\n"
            "/alert BTC below 80000"
        )
        return

    user_id = update.effective_user.id

    symbol = context.args[0].upper()
    direction = context.args[1].lower()

    if direction not in ("above", "below"):
        await update.message.reply_text(
            "Direction must be 'above' or 'below'."
        )
        return

    try:
        target_price = float(context.args[2])

        if target_price <= 0:
            raise ValueError

    except ValueError:
        await update.message.reply_text(
            "Target price must be a positive number."
        )
        return

    coin_id = await find_coin_id(symbol)

    if not coin_id:
        await update.message.reply_text(
            f"Could not find coin: {symbol}"
        )
        return

    if user_id not in ALERTS:
        ALERTS[user_id] = []

    for item in ALERTS[user_id]:
        if (
            item["symbol"] == symbol
            and item["direction"] == direction
            and item["target"] == target_price
        ):
            await update.message.reply_text(
                "That exact alert already exists."
            )
            return

    ALERTS[user_id].append(
        {
            "symbol": symbol,
            "coin_id": coin_id,
            "direction": direction,
            "target": target_price
        }
    )

    save_alerts()

    await update.message.reply_text(
        f"🔔 Alert created\n\n"
        f"{symbol} {direction} ${target_price:,.2f}"
    )

async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_alerts = ALERTS.get(user_id, [])

    if not user_alerts:
        await update.message.reply_text(
            "You have no active price alerts."
        )
        return

    message = "🔔 Your Price Alerts\n\n"

    for i, item in enumerate(user_alerts, start=1):
        message += (
            f"{i}. {item['symbol']} "
            f"{item['direction']} "
            f"${item['target']:,.2f}\n"
        )

    await update.message.reply_text(message)

async def remove_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /removealert 1"
        )
        return

    user_id = update.effective_user.id

    user_alerts = ALERTS.get(user_id, [])

    if not user_alerts:
        await update.message.reply_text(
            "You have no active alerts."
        )
        return

    try:
        alert_number = int(context.args[0])

    except ValueError:
        await update.message.reply_text(
            "Alert number must be a number."
        )
        return

    index = alert_number - 1

    if index < 0 or index >= len(user_alerts):
        await update.message.reply_text(
            "Invalid alert number.\n"
            "Use /alerts to see your alerts."
        )
        return

    removed = user_alerts.pop(index)

    ALERTS[user_id] = user_alerts
    save_alerts()

    await update.message.reply_text(
        f"Removed alert:\n"
        f"{removed['symbol']} "
        f"{removed['direction']} "
        f"${removed['target']:,.2f}"
    )

async def check_price_alerts(application):
    if not ALERTS:
        return

    coin_ids = set()

    for user_alerts in ALERTS.values():
        for item in user_alerts:
            coin_ids.add(item["coin_id"])

    if not coin_ids:
        return

    url = "https://api.coingecko.com/api/v3/simple/price"

    params = {
        "ids": ",".join(coin_ids),
        "vs_currencies": "usd"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                params=params,
                headers=COINGECKO_HEADERS
            )
            response.raise_for_status()

        prices = response.json()

    except Exception as e:
        print("Alert price check error:", type(e).name, e)
        return

    alerts_changed = False

    for user_id, user_alerts in list(ALERTS.items()):
        remaining_alerts = []

        for item in user_alerts:
            coin_id = item["coin_id"]

            if coin_id not in prices:
                remaining_alerts.append(item)
                continue

            current_price = prices[coin_id].get("usd")

            if current_price is None:
                remaining_alerts.append(item)
                continue

            direction = item["direction"]
            target = item["target"]

            triggered = (
                direction == "above" and current_price >= target
            ) or (
                direction == "below" and current_price <= target
            )

            if triggered:
                try:
                    await application.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"🚨 PRICE ALERT\n\n"
                            f"{item['symbol']} is now "
                            f"${current_price:,.2f}\n\n"
                            f"Target: {direction} "
                            f"${target:,.2f}"
                        )
                    )

                    alerts_changed = True

                except Exception as e:
                    print(
                        "Alert message error:",
                        type(e).name,
                        e
                    )

                    remaining_alerts.append(item)

            else:
                remaining_alerts.append(item)

        ALERTS[user_id] = remaining_alerts

    if alerts_changed:
        save_alerts()

async def alert_monitor(application):
    await asyncio.sleep(10)

    while True:
        await check_price_alerts(application)
        await asyncio.sleep(60)

async def post_init(application):
    application.bot_data["alert_monitor_task"] = asyncio.create_task(
        alert_monitor(application)
    )

async def post_shutdown(application):
    task = application.bot_data.get("alert_monitor_task")

    if task:
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

def main():
    load_watchlists()
    load_alerts()
    
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN was not found in .env")

    app = (
    Application.builder()
    .token(TOKEN)
    .post_init(post_init)
    .post_shutdown(post_shutdown)
    .build()
)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("top", top_coins))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("watchlist", watchlist))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("alert", alert))
    app.add_handler(CommandHandler("alerts", alerts))
    app.add_handler(CommandHandler("removealert", remove_alert))


    print("Bot is running...")

    app.run_polling()

if __name__ == "__main__":
    main()