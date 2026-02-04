import os
import json
import hashlib
import re
import math
import time
import random
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from settings import settings
from mongo_atlas import OlxAdsRepository


current_date = datetime.now()
current_hour = current_date.strftime("%H")
week_day = datetime.now().weekday()


mail_subject = "Test HTML Email"
smtp_server = 'smtp.gmail.com'
smtp_port = 587

mongo_repo = OlxAdsRepository(mongo_uri=settings.mongo_url)


# helpers

def send_html_email(email_subject, records):
    to_email = settings.to_email.split(",")
    prices = [
        ad["Вартість одного квадрату"]
        for ad in records.values()
        if "Вартість одного квадрату" in ad and ad["Вартість одного квадрату"] is not None
    ]
    price_per_square_average = round(sum(prices) / len(prices)) if prices else 0
    ads_count = len(records)
    has_probable_duplicate = any(
        "!!! Ймовірний дублікат" in ad
        for ad in records.values()
    )
    is_some_duplicated = "!!!!!! Є йомвірні дублікати" if has_probable_duplicate else "Немає дублікатів"
    email_html_body = f"""
    <html>
    <body>
    <h1>{current_date.strftime("%d %B")} - OLX python parser</h1>
    <h2> Кількість оголошень - {ads_count}</h2>
    <h3> Середня вартість кв. метра - {price_per_square_average}</h3>
    <h4>{is_some_duplicated}</h4>
    <ul>
    """
    for k, v in records.items():
        short_desc = f'{" ".join(v["Опис"].split()[:5])}...'
        email_html_body += f"<li><strong>Опис - {short_desc}</strong></li>\n"
        email_html_body += f"<li><strong>Посилання - {k}</strong></li>\n"
        for v_k, v_v in v.items():
            if v_k != "Опис":
                email_html_body += f"<li><strong>{v_k} - {v_v}</strong></li>\n"
        email_html_body += "<li>----------------------------</li>\n"
        email_html_body += "<br>"
    email_html_body += """
        </ul>
        </body>
        </html>
    """

    # Create the MIME message
    message = MIMEMultipart()
    message['From'] = settings.from_email
    message['To'] = ", ".join(to_email)
    message['Subject'] = email_subject

    # Attach the HTML body with UTF-8 encoding
    message.attach(MIMEText(email_html_body, 'html', 'utf-8'))

    # Send the email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()  # Start TLS Encryption
        server.login(settings.from_email, settings.email_app_password)
        server.send_message(message)  # Use send_message to automatically handle encodings


def get_update_mongo_atlas(link: str, value: dict):
    ads_hash = value["Хеш опису"]
    ads = mongo_repo.get_ad_by_hash(ads_hash)
    if not ads:
        doc = {
            "ads_hash": ads_hash,
            "ads_link": link,
            "description": value["Опис"],
            "created_at": datetime.now(timezone.utc)
        }
        mongo_repo.upsert_ad(doc)
        print(f"Added - {doc}")
    else:
        print(f"{ads_hash} exists")
        if ads["created_at"].date() != current_date.date():
            print(f"{ads_hash} today added")
            return ads["ads_link"]


def get_prev_day_str():
    yesterday = datetime.today() - timedelta(days=1)
    months = [
        'січня', 'лютого', 'березня', 'квітня', 'травня', 'червня',
        'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'
    ]
    return f"{yesterday.day} {months[yesterday.month - 1]}"


def extract_title(card):
    for a in card.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/d/uk/obyavlenie/"):
            title = a.get_text(strip=True)
            if title:
                return title
    return None


def extract_location_and_date(card):
    for p in card.find_all("p"):
        span = p.find("span")
        if not span:
            continue
        date_text = span.get_text(strip=True)
        if "р." not in date_text:
            continue
        from bs4 import NavigableString
        location_parts = [
            t.strip()
            for t in p.contents
            if isinstance(t, NavigableString) and t.strip()
        ]
        location_text = location_parts[0] if location_parts else None
        return location_text, date_text
    return None, None


def get_price(card):
    price_tag = card.select_one('[data-testid="ad-price"]')
    if not price_tag:
        return None
    price_text = price_tag.get_text(strip=True)
    # get all exceot digits
    cleaned = re.sub(r"[^\d.]", "", price_text)
    try:
        price = math.floor(float(cleaned))
    except ValueError:
        return None
    return price


def normalize_description_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[^\wа-я0-9]', '', text)
    return text

def get_text_hash(text: str) -> str:
    norm = normalize_description_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# Playwright factory
def create_stealth_context(headless=True):
    ua = UserAgent()
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
    )
    context = browser.new_context(
        user_agent=ua.random,
        locale="uk-UA",
        viewport={"width": 1366, "height": 768},
    )
    return p, browser, context


# Parsers
def parse_listing_page(html, prev_day_str):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", {"data-cy": "l-card"})
    ads = {}
    found_yesterday = False
    for card in cards:
        if not any(
            prev_day_str.lower() in p.get_text(strip=True).lower()
            for p in card.find_all("p")
        ):
            continue
        # miss "ТОП"
        if card.find("div", string=lambda t: t and t.strip().lower() == "топ"):
            continue
        found_yesterday = True
        price = get_price(card)
        if not price or price < 20000:
            continue
        title = extract_title(card)
        link = card.find("a", href=True)
        full_link = f"https://www.olx.ua{link['href']}" if link else None
        size_text = "Площа не знайдена"
        for span in card.find_all("span"):
            text = span.get_text(strip=True)
            if "м²" in text:
                size_text = text
                break
        try:
            size_int = int(float(size_text.split()[0]))
        except:
            size_int = None
        price_per_square = round(price / size_int) if size_int else None
        ads[full_link] = {
            "Заголовок": title,
            "Ціна": price,
            "Площа": size_text,
            "Вартість одного квадрату": price_per_square,
        }
    return ads, found_yesterday


def parse_detailed(html):
    # parse main contant
    soup = BeautifulSoup(html, "html.parser")
    ld = soup.find("script", type="application/ld+json")
    data = json.loads(ld.string)
    # parse parameters
    containers = soup.find_all(attrs={"data-testid": "ad-parameters-container"})
    for container in containers:
        if not container.get_text(strip=True):
            continue
        items = container.find_all("p")
        if not items:
            continue
        # Add params to data list
        items = list(container.find_all("p"))
        for item in items:
            text = item.get_text(strip=True)
            if ":" in text:
                key, value = map(str.strip, text.split(":", 1))
                data[key] = value
    return data


def is_olx_blocked(html: str) -> bool:
    html_l = html.lower()

    # HTML so small - antibot
    if len(html) < 50_000:
        print("239########")
        return True

    # no cards
    if "data-cy=\"l-card\"" not in html:
        print("244########")
        return True

    # blocking signals
    anti_signals = [
        "please verify you are a human",
        "access denied",
        "unusual traffic",
        "check your browser before accessing",
    ]
    if any(signal in html_l for signal in anti_signals):
        print("255########")
        return True
    print("257########")
    return False



def getch_olx_data(all_steps_ads, base_url, context):
    prev_day_str = get_prev_day_str()
    page_num = 1
    while True:
        # create page obj for main page
        list_page = context.new_page()
        stealth_sync(list_page)
        # create url for each page number
        url = base_url if page_num == 1 else f"{base_url}&page={page_num}"
        ####
        # slow human start
        time.sleep(random.randint(120, 153))

        list_page.goto(url, wait_until="domcontentloaded", timeout=60000)
        list_page.wait_for_timeout(3000)

        # minimal scroll for rendering
        list_page.mouse.wheel(0, 800)
        list_page.wait_for_timeout(2000)

        html = list_page.content()

        # logs for debaging
        print("HTML size:", len(html))
        print("l-card count:", html.count('data-cy="l-card"'))
        print("Blocked?", is_olx_blocked(html))

        if is_olx_blocked(html):
            list_page.close()
            raise RuntimeError("OLX anti-bot / empty listing page detected")
        ######
        ads, found_yesterday = parse_listing_page(html, prev_day_str)
        for full_link, ad_data in ads.items():
            if full_link not in all_steps_ads:
                time.sleep(random.randint(65, 153))
                # create detailed page
                detailed_page = context.new_page()
                stealth_sync(detailed_page)
                print(f"Завантаження: {full_link}")
                detailed_page.goto(full_link, timeout=60000)
                # detailed_page.wait_for_selector(
                #     '[data-testid="ad-parameters-container"]',
                #     timeout=30000,
                #     state="attached"
                # )
                html = detailed_page.content()
                details = parse_detailed(html)
                hash_obj = get_text_hash(details.get("description"))
                # add to main dict
                ad_data["Опис"] = details.get("description")
                ad_data["Хеш опису"] = hash_obj
                ad_data["Вид об'єкта"] = details.get("Вид об'єкта")
                ad_data["Поверх"] = details.get("Поверх")
                ad_data["Поверховість"] = details.get("Поверховість")
                ad_data["Опалення"] = details.get("Опалення")
                ad_data["Клас житла"] = details.get("Клас житла")
                ad_data["Район"] = details.get("offers", {}).get("areaServed", {}).get("name")
                all_steps_ads[full_link] = ad_data
                list_page.close()
                detailed_page.close()
                is_duplicate = get_update_mongo_atlas(full_link, ad_data)
                if is_duplicate:
                    ad_data["!!! Ймовірний дублікат"] = is_duplicate
        if not ads:
            break
        if not found_yesterday:
            break
        page_num += 1
        time.sleep(random.randint(67, 133))


if __name__ == "__main__":
    SCHEDULE = {
        0: '10',
        1: '09',
        2: '08',
        3: '09',
        4: '10',
        5: '09',
        6: '08',
    }
    allowed_hour = SCHEDULE.get(week_day)
    # if current_hour == str(allowed_hour):
    start = time.perf_counter()
    base_url = (
        "https://www.olx.ua/uk/nedvizhimost/kvartiry/"
        "prodazha-kvartir/lvov/"
        "?currency=USD"
        "&search%5Bfilter_float_price%3Ato%5D=50000"
        "&search%5Border%5D=created_at%3Adesc"
    )
    all_steps_ads = {}
    p, browser, context = create_stealth_context(headless=True)
    try:
        for step in range(random.randint(2, 3)):
            time.sleep(random.randint(111, 755))
            step += 1
            print(f"Step number {step}")
            getch_olx_data(all_steps_ads, base_url, context)
    finally:
        browser.close()
        p.stop()
    print(f"\nЗнайдено {len(all_steps_ads)} оголошень:")
    for k, v in all_steps_ads.items():
        print(f"{k}---{v}")
    send_html_email("Test olx", all_steps_ads)
    # calculate spended time
    end = time.perf_counter()
    print(f"Час виконання: {end - start:.3f} сек")
    # else:
    #     print("Поточна година недозволена для виконання")
