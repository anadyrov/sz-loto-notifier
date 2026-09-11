import asyncio
import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright


load_dotenv()

SRV_URL = "https://sz.kz/srv"
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Almaty"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"
SMS_PHONE = os.getenv("SMS_PHONE", "").replace("+", "").replace(" ", "")
MOBIZON_API_KEY = os.getenv("MOBIZON_API_KEY", "")
LOTTERIES = [
    {
        "name": "Loto 5/36",
        "url": "https://sz.kz/resultsGame?gAlias=bet_sz_536",
        "game_id": "1084",
        "hour": 21,
        "minute": 0,
        "state_file": Path("last_draw_536.txt"),
        "status_file": Path("status_536.json"),
    },
    {
        "name": "Loto 6/49",
        "url": "https://sz.kz/resultsGame?gAlias=bet_sz_649",
        "game_id": "1079",
        "hour": 22,
        "minute": 0,
        "state_file": Path("last_draw_649.txt"),
        "status_file": Path("status_649.json"),
    },
]


def telegram_send(message: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=30,
    )
    response.raise_for_status()


def sms_send(message: str) -> None:
    if not SMS_ENABLED:
        return
    if not SMS_PHONE or not MOBIZON_API_KEY:
        raise RuntimeError("SMS включен, но не указаны SMS_PHONE или MOBIZON_API_KEY")
    response = requests.post(
        "https://api.mobizon.kz/service/message/sendsmsmessage",
        data={
            "apiKey": MOBIZON_API_KEY,
            "output": "json",
            "api": "v1",
            "recipient": SMS_PHONE,
            "text": message,
        },
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 0:
        raise RuntimeError(f"Mobizon API: {result.get('message', 'неизвестная ошибка')}")


def parse_srv_response(raw_response: str) -> dict | list:
    fields = parse_qs(raw_response)
    if fields.get("status", [""])[0] != "OK":
        raise RuntimeError(f"SZ.KZ вернул ошибку: {raw_response[:300]}")
    return json.loads(fields["msg"][0])


async def fetch_result(lottery: dict, target_date=None) -> dict | None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            locale="ru-RU",
        )
        try:
            await page.goto(lottery["url"], wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3000)
            await page.wait_for_selector("body", timeout=15_000)

            async def request_srv(data: dict) -> dict | list:
                raw_response = await page.evaluate(
                    """async (body) => {
                        const response = await fetch('/srv', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'},
                            signal: AbortSignal.timeout(15000),
                            body
                        });
                        return await response.text();
                    }""",
                    urlencode(data),
                )
                return parse_srv_response(raw_response)

            months = await request_srv(
                {
                    "srv": "drawResultsMonth",
                    "gameId": lottery["game_id"],
                    "find": "",
                    "prizeRaffled": "",
                    "sortNumbers": "",
                }
            )
            for month in months:
                results = await request_srv(
                    {
                        "srv": "drawResultsEx",
                        "gameId": lottery["game_id"],
                        "intervalID": month["ID"],
                        "find": "",
                        "prizeRaffled": "",
                        "sortNumbers": "",
                        "page": "",
                    }
                )
                for draw in results.get("draws", []):
                    draw_datetime = datetime.strptime(draw["makeDate"], "%d.%m.%Y %H:%M:%S")
                    if target_date is not None and draw_datetime.date() != target_date:
                        continue
                    return {
                        "number": draw["drawId"],
                        "date": draw_datetime.strftime("%d.%m.%Y"),
                        "numbers": [int(value) for value in draw["balls"]],
                        "bonus_numbers": [
                            int(value) for value in (draw.get("bonusBalls") or [])
                        ],
                    }
            return None
        finally:
            await browser.close()


async def fetch_today_result(lottery: dict) -> dict | None:
    return await fetch_result(lottery, datetime.now(TIMEZONE).date())


async def fetch_latest_result(lottery: dict) -> dict | None:
    return await fetch_result(lottery)


def make_message(lottery: dict, result: dict) -> str:
    ticket_numbers = {
        int(value)
        for value in os.getenv("TICKET_NUMBERS", "").split(",")
        if value.strip().isdigit()
    }
    numbers = result["numbers"]
    bonus_numbers = result.get("bonus_numbers", [])
    message = (
        f"{lottery['name']}\n"
        f"Тираж №{result['number']} от {result['date']}\n"
        f"Результат: {' - '.join(map(str, numbers))}"
    )
    if bonus_numbers:
        message += f"\nБонусный шар: {' - '.join(map(str, bonus_numbers))}"
    if ticket_numbers:
        matches = sorted(ticket_numbers.intersection(numbers))
        message += f"\nВаши совпадения: {', '.join(map(str, matches)) if matches else 'нет'}"
    return message


def already_sent(lottery: dict, draw_number: str) -> bool:
    state_file = lottery["state_file"]
    return state_file.exists() and state_file.read_text(encoding="utf-8").strip() == draw_number


def mark_sent(lottery: dict, draw_number: str) -> None:
    lottery["state_file"].write_text(draw_number, encoding="utf-8")


def status_sent(lottery: dict, status: str, current_date: str) -> bool:
    status_file = lottery["status_file"]
    if not status_file.exists():
        return False
    try:
        saved = json.loads(status_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return saved.get("date") == current_date and saved.get("status") == status


def mark_status(lottery: dict, status: str, current_date: str) -> None:
    lottery["status_file"].write_text(
        json.dumps({"date": current_date, "status": status}), encoding="utf-8"
    )


def send_status_once(lottery: dict, status: str, message: str, current_date: str) -> None:
    if not status_sent(lottery, status, current_date):
        telegram_send(message)
        mark_status(lottery, status, current_date)


async def run_lottery(lottery: dict, force_latest: bool = False) -> None:
    now = datetime.now(TIMEZONE)
    cutoff = (lottery["hour"], lottery["minute"])
    if not force_latest and (now.hour, now.minute) < cutoff:
        return
    current_date = now.strftime("%d.%m.%Y")
    try:
        result = await (
            fetch_latest_result(lottery) if force_latest else fetch_today_result(lottery)
        )
    except Exception:
        if not force_latest:
            send_status_once(
                lottery,
                "site_error",
                f"{lottery['name']}: сайт SZ.KZ сейчас недоступен. Повторяю проверку.",
                current_date,
            )
        raise
    if result is None:
        if not force_latest:
            send_status_once(
                lottery,
                "waiting",
                f"{lottery['name']}: результатов еще нет. Ожидайте, проверяю каждую минуту.",
                current_date,
            )
        print(f"Результат {lottery['name']} еще не опубликован", flush=True)
        return
    if not force_latest and already_sent(lottery, result["number"]):
        return
    telegram_send(make_message(lottery, result))
    sms_send(make_message(lottery, result))
    mark_sent(lottery, result["number"])
    print(f"Отправлен результат {lottery['name']} тиража {result['number']}", flush=True)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--latest",
        action="store_true",
        help="отправить последний опубликованный результат и завершить работу",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="выполнить одну плановую проверку и завершить работу",
    )
    parser.add_argument(
        "--window",
        action="store_true",
        help="проверять каждую минуту в течение вечернего окна и завершиться",
    )
    arguments = parser.parse_args()
    if arguments.latest:
        try:
            for lottery in LOTTERIES:
                await run_lottery(lottery, force_latest=True)
        except Exception as error:
            print(f"Ошибка разовой проверки: {error}", flush=True)
        return
    if arguments.once:
        for lottery in LOTTERIES:
            try:
                await run_lottery(lottery)
            except Exception as error:
                print(f"Ошибка проверки {lottery['name']}: {error}", flush=True)
        return
    if arguments.window:
        started_at = time.monotonic()
        while time.monotonic() - started_at < 3 * 60 * 60:
            for lottery in LOTTERIES:
                try:
                    await run_lottery(lottery)
                except Exception as error:
                    print(f"Ошибка проверки {lottery['name']}: {error}", flush=True)
            await asyncio.sleep(POLL_SECONDS)
        return
    while True:
        for lottery in LOTTERIES:
            try:
                await run_lottery(lottery)
            except Exception as error:
                print(f"Ошибка проверки {lottery['name']}: {error}", flush=True)
        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())