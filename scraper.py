
import requests
import re
import json
import logging

from bs4 import BeautifulSoup
from urllib.parse import urlparse

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PricePulse.Scraper")


# ---------------- HEADERS ----------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Cache-Control": "no-cache",
}


# ---------------- CLEAN PRICE ----------------
def clean_price(value):
    if value is None:
        return None

    text = str(value)

    text = (
        text.replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace(",", "")
        .strip()
    )

    match = re.search(r"\d+(?:\.\d{1,2})?", text)

    if match:
        try:
            price = float(match.group())

            if 0 < price < 10000000:
                return price

        except ValueError:
            pass

    return None


# ---------------- SITE NAME ----------------
def get_site_name(domain):
    domain = domain.lower()

    sites = {
        "amazon": "Amazon",
        "amzn": "Amazon",
        "flipkart": "Flipkart",
        "myntra": "Myntra",
        "ajio": "Ajio",
        "nykaa": "Nykaa",
        "meesho": "Meesho",
        "snapdeal": "Snapdeal",
    }

    for key, name in sites.items():
        if key in domain:
            return name

    return domain.split(".")[0].capitalize() if domain else "Unknown"


# ---------------- JSON PRICE ----------------
def extract_json_price(soup):
    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):
        try:
            raw = script.string or script.get_text()
            data = json.loads(raw)

            items = data if isinstance(data, list) else [data]

            for item in items:
                if not isinstance(item, dict):
                    continue

                candidates = [item]

                if isinstance(item.get("@graph"), list):
                    candidates.extend(item["@graph"])

                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue

                    offers = candidate.get("offers")

                    if isinstance(offers, dict):
                        price = clean_price(offers.get("price"))

                        if price:
                            return price

                    elif isinstance(offers, list):
                        for offer in offers:
                            if isinstance(offer, dict):
                                price = clean_price(
                                    offer.get("price")
                                )

                                if price:
                                    return price

        except (
            json.JSONDecodeError,
            TypeError,
            AttributeError
        ):
            continue

    return None


# ---------------- META PRICE ----------------
def extract_meta_price(soup):
    meta_tags = [
        ("property", "product:price:amount"),
        ("property", "og:price:amount"),
        ("name", "price"),
        ("itemprop", "price"),
    ]

    for attribute, value in meta_tags:
        tag = soup.find(
            "meta",
            attrs={attribute: value}
        )

        if tag and tag.get("content"):
            price = clean_price(tag["content"])

            if price:
                return price

    return None


# ---------------- AMAZON PRICE ----------------
def extract_amazon_price(soup):
    selectors = [
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#corePrice_feature_div .a-price .a-offscreen",
        ".priceToPay .a-offscreen",
        ".apexPriceToPay .a-offscreen",
        "#priceblock_dealprice",
        "#priceblock_saleprice",
        "#priceblock_ourprice",
        ".a-price .a-offscreen",
    ]

    for selector in selectors:
        for element in soup.select(selector):
            price = clean_price(
                element.get_text(" ", strip=True)
            )

            if price and price > 10:
                return price

    return None


# ---------------- GENERAL PRICE ----------------
def extract_general_price(soup):
    selectors = [
        ".Nx9bqj",
        "[class*='30jeq3']",
        ".pdp-price",
        ".selling-price",
        "[itemprop='price']",
        ".price",
    ]

    for selector in selectors:
        for element in soup.select(selector):
            value = (
                element.get("content")
                or element.get_text(" ", strip=True)
            )

            price = clean_price(value)

            if price and price > 10:
                return price

    text = soup.get_text(" ", strip=True)

    matches = re.findall(
        r"₹\s*([\d,]+(?:\.\d{1,2})?)",
        text
    )

    values = []

    for match in matches:
        price = clean_price(match)

        if price and 10 < price < 500000:
            values.append(price)

    if values:
        return min(values)

    return None


# ---------------- ERROR RESULT ----------------
def error_result(
    message,
    site="Unknown",
    title="Product"
):
    return {
        "title": title,
        "price": 0,
        "site": site,
        "error": message,
    }


# ---------------- MAIN SCRAPER ----------------
def scrape_price(url):

    session = requests.Session()
    session.headers.update(HEADERS)

    site_name = "Unknown"

    try:
        url = url.strip()

        parsed = urlparse(url)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
        ):
            return error_result(
                "Please enter a valid product URL."
            )

        logger.info("PRICEPULSE: Starting scrape")
        logger.info("Requested URL: %s", url)

        # Connect timeout: 8 seconds
        # Read timeout: 15 seconds
        response = session.get(
            url,
            timeout=(8, 15),
            allow_redirects=True
        )

        logger.info("Final URL: %s", response.url)
        logger.info(
            "HTTP Status: %s",
            response.status_code
        )
        logger.info(
            "Response Server: %s",
            response.headers.get("Server")
        )

        final_url = response.url

        domain = urlparse(final_url).netloc.lower()
        domain = domain.removeprefix("www.")

        site_name = get_site_name(domain)

        # ---------------- STATUS CHECK ----------------
        if response.status_code == 429:
            return error_result(
                "Website is limiting automated requests. Try again later.",
                site_name
            )

        if response.status_code == 529:
            return error_result(
                "Website is temporarily unavailable or blocking automated requests.",
                site_name
            )

        if response.status_code in (500, 502, 503, 504):
            return error_result(
                f"Website server returned HTTP {response.status_code}. Try again later.",
                site_name
            )

        if response.status_code >= 400:
            return error_result(
                f"Website returned HTTP {response.status_code}.",
                site_name
            )

        # ---------------- PARSE HTML ----------------
        soup = BeautifulSoup(
            response.content,
            "lxml"
        )

        # ---------------- PRODUCT TITLE ----------------
        title = None

        og_title = soup.find(
            "meta",
            property="og:title"
        )

        if og_title and og_title.get("content"):
            title = og_title["content"].strip()

        if not title:
            title_tag = soup.find("title")

            if title_tag:
                title = title_tag.get_text(strip=True)

        amazon_title = soup.select_one("#productTitle")

        if amazon_title:
            title = amazon_title.get_text(
                " ",
                strip=True
            )

        if not title:
            title = "Product"

        title = title[:150]

        # ---------------- EXTRACT PRICE ----------------
        price = extract_json_price(soup)

        if not price:
            price = extract_meta_price(soup)

        if not price and "amazon" in domain:
            price = extract_amazon_price(soup)

        if not price:
            price = extract_general_price(soup)

        logger.info(
            "Extracted Product Title: %s",
            title
        )

        logger.info(
            "Extracted Product Price: %s",
            price
        )

        # ---------------- PRICE NOT FOUND ----------------
        if not price:
            page_text = soup.get_text(
                " ",
                strip=True
            ).lower()

            if (
                "captcha" in page_text
                or "robot check" in page_text
                or "enter the characters you see below" in page_text
            ):
                message = (
                    "Website security check blocked automated access."
                )

            else:
                message = (
                    "Product price was not found. "
                    "The website may hide prices from automated requests."
                )

            return error_result(
                message,
                site_name,
                title
            )

        # ---------------- SUCCESS ----------------
        return {
            "title": title,
            "price": price,
            "site": site_name,
        }

    except requests.exceptions.ConnectTimeout:
        logger.exception("PRICEPULSE: Connection timeout")

        return error_result(
            "Could not connect to the website within 8 seconds.",
            site_name
        )

    except requests.exceptions.ReadTimeout:
        logger.exception("PRICEPULSE: Read timeout")

        return error_result(
            "Website connected but did not respond within 15 seconds.",
            site_name
        )

    except requests.exceptions.Timeout:
        logger.exception("PRICEPULSE: Request timeout")

        return error_result(
            "Website request timed out. Please try again later.",
            site_name
        )

    except requests.exceptions.RequestException as error:
        logger.exception("PRICEPULSE: Request error")

        return error_result(
            f"Website connection failed: {error}",
            site_name
        )

    except Exception as error:
        logger.exception("PRICEPULSE: Unexpected error")

        return error_result(
            f"Unexpected error: {error}",
            site_name
        )

    finally:
        session.close()
