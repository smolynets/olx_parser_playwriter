import os
import re
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

def send_html_email(email_subject, to_email, from_email, email_app_password, records):
    to_email = to_email.split(",")
    prices = [r["Вартість одного квадрату"] for r in records if r.get("Вартість одного квадрату") is not None]
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

    for record in records:
        email_html_body += f"<li><strong>{record["Заголовок"]}</strong></li>\n"
        email_html_body += (
            f"<li>"
            f"<a href=\"{record['Фото']}\">{record['Фото']}</a>"
            f"</li>\n"
        )
        email_html_body += f"<li><strong>Ціна - {record["Ціна"]}</strong></li>\n"
        email_html_body += f"<li><strong>Посилання - {record["Посилання"]}</strong></li>\n"
        email_html_body += f"<li><strong>Площа - {record["Площа"]}</strong></li>\n"
        email_html_body += f"<li><strong>Вартість одного квадрату - {record["Вартість одного квадрату"]}</strong></li>\n"
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
    if price_tag:
        price_text = price_tag.get_text(strip=True)
        digits_price = re.findall(r"\d+", price_text)
        price = int("".join(digits_price))
    else:
        price = None
    return price



def getch_olx_data():
    ua = UserAgent()
    user_agent = ua.random

    base_url = (
        "https://www.olx.ua/uk/nedvizhimost/kvartiry/"
        "prodazha-kvartir/lvov/"
        "?currency=USD"
        "&search%5Bfilter_float_price%3Ato%5D=50000"
        "&search%5Border%5D=created_at%3Adesc"
    )

    prev_day_str = get_prev_day_str().lower()
    all_ads = []

    with sync_playwright() as p:
        time.sleep(random.uniform(35, 333))
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )

        context = browser.new_context(
            user_agent=user_agent,
            locale="uk-UA",
            viewport={"width": 1366, "height": 768},
        )

        page = context.new_page()

        stealth_sync(page)

        page_num = 1

        while True:
            # real work
            ###########
            url = base_url if page_num == 1 else f"{base_url}&page={page_num}"
            print(f"Завантаження сторінки: {url}")

            page.goto(url, timeout=60000)
            page.wait_for_timeout(random.randint(2500, 4500))

            try:
                page.wait_for_selector('div[data-cy="l-card"]', timeout=15000)
            except:
                print("Оголошення не завантажились")
                break
            
            ##
            # html = page.content()

            # with open("olx_page.html", "w", encoding="utf-8") as f:
            #     f.write(html)
            ##

            soup = BeautifulSoup(page.content(), "html.parser")
            ############
            # local work
            ###################
            # with open("olx_page.html", "r", encoding="utf-8") as f:
            #     html = f.read()

            # soup = BeautifulSoup(html, "html.parser")
            ################

            cards = soup.find_all("div", {"data-cy": "l-card"})
            if not cards:
                break

            found_yesterday = False

            cards_n = len(cards)
            print(f"number_of_cards_{cards_n}")

            for card in cards:
                date_text = ""

                p_tags = card.find_all("p")
                for p in p_tags:
                    if prev_day_str in p.text:
                        date_text = p.text.strip()
                        break
                
                if prev_day_str not in date_text:
                    continue

                # miss "ТОП"
                if card.find("div", string=lambda t: t and t.strip().lower() == "топ"):
                    continue

                found_yesterday = True

                title = card.find("h4")
                
                # get price
                price = get_price(card)

                link = card.find("a", href=True)
                
                size_text = "Площа не знайдена"
                for span in card.find_all("span"):
                    text = span.get_text(strip=True)
                    if "м²" in text:
                        size_text = text
                        break
                
                title = extract_title(card)
                photo_url = extract_main_photo(card)
                location, _ = extract_location_and_date(card)
                size_int = int(float(size_text.split()[0]))
                price_per_squere = round(price / size_int) if price and size_int else None
                if price < 20000:
                    continue
                ad = {
                    "Заголовок": title if title else "Заголовок не знайдено",
                    "Фото": photo_url if photo_url else "",
                    "Ціна": price if price else "Ціна не знайдена",
                    "Посилання": f"https://www.olx.ua{link['href']}" if link else "Посилання не знайдено",
                    "Площа": size_text,
                    "Вартість одного квадрату": price_per_squere if price_per_squere else None,
                }

                all_ads.append(ad)

            if not found_yesterday:
                break

            page_num += 1
            time.sleep(random.uniform(67, 133))

            ###
            # if page_num == 3:
            #     break
            ###

        browser.close()

    return all_ads


if __name__ == "__main__":
    ads = []
    ads = getch_olx_data()
    print(f"\nЗнайдено {len(ads)} оголошень:")
    for ad in ads:
        print(ad)
    send_html_email("Test olx", to_email, from_email, email_app_password, ads)
