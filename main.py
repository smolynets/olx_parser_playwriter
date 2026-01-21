import os
import re
import math
import time
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from datetime import datetime

current_date = datetime.now()


mail_subject = "Test HTML Email"
smtp_server = 'smtp.gmail.com'
smtp_port = 587


to_email = os.getenv("TO_EMAIL")
from_email = os.getenv("FROM_EMAIL")
email_app_password = os.getenv("EMAIL_APP_PASSWORD")


# helpers

def send_html_email(email_subject, to_email, from_email, email_app_password, records):
    to_email = to_email.split(",")
    prices = [
        ad["Вартість одного квадрату"]
        for ad in records.values()
        if "Вартість одного квадрату" in ad and ad["Вартість одного квадрату"] is not None
    ]
    price_per_square_average = round(sum(prices) / len(prices)) if prices else 0
    ads_count = len(records)
    email_html_body = f"""
    <html>
    <body>
    <h1>{current_date.strftime("%d %B")} - OLX python parser</h1>
    <h2> Кількість оголошень - {ads_count}</h2>
    <h3> Середня вартість кв. метра - {price_per_square_average}</h3>
    <ul>
    """

    for k, v in records.items():
        email_html_body += f"<li><strong>Заголовок - {v["Заголовок"]}</strong></li>\n"
        email_html_body += f"<li><strong>Посилання - {k}</strong></li>\n"
        # email_html_body += (
        #     f"<li>"
        #     f"<a href=\"{v['Фото']}\">{v['Фото']}</a>"
        #     f"</li>\n"
        # )
        email_html_body += f"<li><strong>Ціна - {v["Ціна"]}</strong></li>\n"
        email_html_body += f"<li><strong>Площа - {v["Площа"]}</strong></li>\n"
        email_html_body += f"<li><strong>Вартість одного квадрату - {v["Вартість одного квадрату"]}</strong></li>\n"
        email_html_body += f"<li><strong>Опис - {v["Опис"]}</strong></li>\n"
        email_html_body += "<li>----------------------------</li>\n"
        email_html_body += "<br>"
    email_html_body += """
        </ul>
        </body>
        </html>
    """

    # Create the MIME message
    message = MIMEMultipart()
    message['From'] = from_email
    message['To'] = ", ".join(to_email)
    message['Subject'] = email_subject

    # Attach the HTML body with UTF-8 encoding
    message.attach(MIMEText(email_html_body, 'html', 'utf-8'))

    # Send the email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()  # Start TLS Encryption
        server.login(from_email, email_app_password)
        server.send_message(message)  # Use send_message to automatically handle encodings


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


def extract_main_photo(card):
    img = card.find("img", src=True)
    if img and "no_thumbnail" not in img["src"]:
        return img["src"]
    if img and img.get("srcset"):
        srcset_url = img["srcset"].split()[0]
        if "no_thumbnail" not in srcset_url:
            return srcset_url
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

    # забираємо все, крім цифр і крапки
    cleaned = re.sub(r"[^\d.]", "", price_text)

    try:
        price = math.floor(float(cleaned))
    except ValueError:
        return None

    return price


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


def load_page(page, url, wait_selector=None):
    print(f"Завантаження: {url}")
    page.goto(url, timeout=60000)
    page.wait_for_timeout(random.randint(2500, 4500))

    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=15000)

    return page.content()


# Parsers

def parse_listing_page(html, prev_day_str):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", {"data-cy": "l-card"})

    ads = {}
    found_yesterday = False

    for card in cards:
        # date
        date_text = ""
        for p in card.find_all("p"):
            if prev_day_str in p.text.lower():
                date_text = p.text.strip()
                break

        if prev_day_str not in date_text:
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


def parse_detailed_description(html):
    soup = BeautifulSoup(html, "html.parser")
    
    # OLX description container
    desc_tag = soup.find("div", {"data-cy": "ad_description"})
    
    # fallback: if data-cy dont work, take the biggest <div> with text
    if not desc_tag:
        all_divs = soup.find_all("div")
        desc_tag = max(all_divs, key=lambda d: len(d.get_text(strip=True) or ""))
    
    description = desc_tag.get_text(separator="\n", strip=True) if desc_tag else "Опис не знайдено"
    
    return description


def getch_olx_data(all_steps_ads, base_url, context):
    prev_day_str = get_prev_day_str()
    page_num = 1
    while True:
        # create page obj for main page
        list_page = context.new_page()
        stealth_sync(list_page)
        # create url for each page number
        url = base_url if page_num == 1 else f"{base_url}&page={page_num}"
        html = load_page(list_page, url, 'div[data-cy="l-card"]')
        ads, found_yesterday = parse_listing_page(html, prev_day_str)
        for full_link, ad_data in ads.items():
            if full_link not in all_steps_ads:
                time.sleep(random.randint(33, 128))
                # create detailed page
                detailed_page = context.new_page()
                stealth_sync(detailed_page)
                html = load_page(detailed_page, full_link, 'body')
                description = parse_detailed_description(html)
                # add to main dict
                ad_data["Опис"] = description
                all_steps_ads[full_link] = ad_data
        if not ads:
            break
        if not found_yesterday:
            break
        page_num += 1
        time.sleep(random.randint(67, 133))


if __name__ == "__main__":
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
            time.sleep(random.randint(100, 873))
            step += 1
            print(f"Step number {step}")
            getch_olx_data(all_steps_ads, base_url, context)
    finally:
        browser.close()
        p.stop()
    print(f"\nЗнайдено {len(all_steps_ads)} оголошень:")
    for k, v in all_steps_ads.items():
        print(f"{k}---{v}")
    send_html_email("Test olx", to_email, from_email, email_app_password, all_steps_ads)
    # calculate spended time
    end = time.perf_counter()
    print(f"Час виконання: {end - start:.3f} сек")
