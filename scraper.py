
import requests
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def clean_price(text):
    if not text:
        return None

    text = str(text)
    text = text.replace("₹", "").replace("Rs.", "").replace("Rs", "")
    text = text.replace(",", "").strip()

    match = re.search(r"\d+(?:\.\d{1,2})?", text)

    if match:
        try:
            price = float(match.group())
            if price > 0:
                return price
        except ValueError:
            pass

    return None


def get_site_name(domain):
    domain = domain.lower()

    if "amazon" in domain or "amzn" in domain:
        return "Amazon"
    elif "flipkart" in domain:
        return "Flipkart"
    elif "myntra" in domain:
        return "Myntra"
    elif "ajio" in domain:
        return "Ajio"
    elif "nykaa" in domain:
        return "Nykaa"
    elif "meesho" in domain:
        return "Meesho"
    elif "snapdeal" in domain:
        return "Snapdeal"

    return domain.split(".")[0].capitalize() if domain else "Unknown"


def extract_json_price(soup):
    for script in soup.find_all("script", type="application/ld+json"):
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
                                price = clean_price(offer.get("price"))
                                if price:
                                    return price

        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    return None


def extract_meta_price(soup):
    meta_tags = [
        ("property", "product:price:amount"),
        ("property", "og:price:amount"),
        ("name", "price"),
        ("itemprop", "price"),
    ]

    for attribute, value in meta_tags:
        tag = soup.find("meta", attrs={attribute: value})

        if tag and tag.get("content"):
            price = clean_price(tag["content"])

            if price:
                return price

    return None


def extract_amazon_price(soup):
    selectors = [
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#corePrice_feature_div .a-price .a-offscreen",
        "#priceblock_dealprice",
        "#priceblock_saleprice",
        "#priceblock_ourprice",
        ".priceToPay .a-offscreen",
        ".apexPriceToPay .a-offscreen",
        ".a-price .a-offscreen",
        ".a-price-whole",
    ]

    for selector in selectors:
        elements = soup.select(selector)

        for element in elements:
            price = clean_price(element.get_text(" ", strip=True))

            if price and price > 10:
                return price

    return None


def extract_general_price(soup):
    selectors = [
        ".Nx9bqj",
        "._30jeq3",
        ".pdp-price",
        ".selling-price",
        ".price",
        "[itemprop='price']",
    ]

    for selector in selectors:
        elements = soup.select(selector)

        for element in elements:
            value = element.get("content") or element.get_text(" ", strip=True)
            price = clean_price(value)

            if price and price > 10:
                return price

    # Fallback: scan visible page text for rupee prices
    text = soup.get_text(" ", strip=True)

    matches = re.findall(r"₹\s*([\d,]+(?:\.\d{1,2})?)", text)

    values = []

    for match in matches:
        price = clean_price(match)

        if price and 10 < price < 500000:
            values.append(price)

    if values:
        return min(values)

    return None


def scrape_price(url):
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return {
                "title": "Product",
                "price": 0,
                "site": "Unknown",
                "error": "Please enter a valid product URL."
            }

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
            allow_redirects=True
            )

        final_url = response.url
        domain = urlparse(final_url).netloc.lower().replace("www.", "")
        site_name = get_site_name(domain)

        if response.status_code >= 400:
            return {
                "title": "Product",
                "price": 0,
                "site": site_name,
                "error": f"Website returned HTTP {response.status_code}."
            }

        soup = BeautifulSoup(response.content, "lxml")

        # Product title
        title = None

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()

        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

        amazon_title = soup.select_one("#productTitle")
        if amazon_title:
            title = amazon_title.get_text(" ", strip=True)

        if not title:
            title = "Product"

        title = title[:150]

        # Price extraction
        price = extract_json_price(soup)

        if not price:
            price = extract_meta_price(soup)

        if not price and "amazon" in domain:
            price = extract_amazon_price(soup)

        if not price:
            price = extract_general_price(soup)

        # Detect likely Amazon blocking
        page_text = soup.get_text(" ", strip=True).lower()

        if not price:
            if (
                "captcha" in page_text
                or "robot check" in page_text
                or "enter the characters you see below" in page_text
            ):
                error = (
                    "Amazon blocked automated price access. "
                    "Try another product link later."
                )
            else:
                error = (
                    "Price was not found on this page. "
                    "This website may hide its price from automated requests."
                )

            return {
                "title": title,
                "price": 0,
                "site": site_name,
                "error": error
            }

        return {
            "title": title,
            "price": price,
            "site": site_name
        }

    except requests.exceptions.Timeout:
        return {
            "title": "Product",
            "price": 0,
            "site": "Unknown",
            "error": "The website took too long to respond. Try again."
        }

    except requests.exceptions.RequestException as e:
        return {
            "title": "Product",
            "price": 0,
            "site": "Unknown",
            "error": f"Website connection failed: {e}"
        }

    except Exception as e:
        return {
            "title": "Product",
            "price": 0,
            "site": "Unknown",
            "error": f"Unexpected error: {e}"
        }
