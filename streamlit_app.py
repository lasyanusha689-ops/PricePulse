
import streamlit as st
import sqlite3
import pandas as pd
import logging
from datetime import datetime
from scraper import scrape_price

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("PricePulse")

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="PricePulse",
    page_icon="💰",
    layout="wide"
)

DB_NAME = "prices.db"

# ---------------- LANGUAGE ----------------
language = st.sidebar.selectbox(
    "🌐 Language",
    ["English", "ಕನ್ನಡ"]
)


def t(english, kannada):
    return kannada if language == "ಕನ್ನಡ" else english


# ---------------- CLEAR URL CALLBACK ----------------
def clear_url():
    st.session_state["url_input"] = ""


# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            price REAL,
            site TEXT,
            added TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            price REAL,
            date TEXT
        )
    """)

    conn.commit()
    return conn


# ---------------- GET PRODUCTS ----------------
def get_products():
    conn = get_db()

    df = pd.read_sql_query(
        "SELECT * FROM products ORDER BY id DESC",
        conn
    )

    conn.close()
    return df


# ---------------- ADD PRODUCT ----------------
def add_product(url):
    try:
        logger.info("PRICEPULSE: Starting product scrape")
        logger.info("PRICEPULSE: Requested URL: %s", url)

        result = scrape_price(url)

        logger.info("PRICEPULSE: Scraper result: %s", result)

        if not result or not result.get("price"):
            error = (
                result.get("error", "Price could not be found.")
                if result
                else "Scraper returned no result."
            )

            logger.warning("PRICEPULSE: Scraping failed: %s", error)
            return False, error

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO products (title, url, price, site, added)
               VALUES (?, ?, ?, ?, ?)""",
            (
                result["title"],
                url,
                result["price"],
                result["site"],
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        )

        product_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO history (product_id, price, date)
               VALUES (?, ?, ?)""",
            (
                product_id,
                result["price"],
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        )

        conn.commit()
        conn.close()

        logger.info("PRICEPULSE: Product saved successfully")

        return True, result

    except Exception:
        logger.exception("PRICEPULSE: ADD PRODUCT ERROR")
        return False, "An unexpected error occurred while adding the product. Check app logs."


# ---------------- DELETE PRODUCT ----------------
def delete_product(product_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM history WHERE product_id=?",
        (product_id,)
    )

    cursor.execute(
        "DELETE FROM products WHERE id=?",
        (product_id,)
    )

    conn.commit()
    conn.close()


# ---------------- REFRESH PRODUCT ----------------
def refresh_product(product_id, url):
    try:
        logger.info("PRICEPULSE: Refreshing product ID: %s", product_id)
        logger.info("PRICEPULSE: Refresh URL: %s", url)

        result = scrape_price(url)

        logger.info("PRICEPULSE: Refresh result: %s", result)

        if not result or not result.get("price"):
            error = (
                result.get("error", "Price could not be found.")
                if result
                else "Scraper returned no result."
            )

            return False, error

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """UPDATE products
               SET price=?, title=?, site=?
               WHERE id=?""",
            (
                result["price"],
                result["title"],
                result["site"],
                product_id
            )
        )

        cursor.execute(
            """INSERT INTO history (product_id, price, date)
               VALUES (?, ?, ?)""",
            (
                product_id,
                result["price"],
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        )

        conn.commit()
        conn.close()

        logger.info("PRICEPULSE: Product refreshed successfully")

        return True, result

    except Exception:
        logger.exception("PRICEPULSE: REFRESH ERROR")
        return False, "An unexpected error occurred while refreshing. Check app logs."


# ---------------- GET HISTORY ----------------
def get_history(product_id):
    conn = get_db()

    df = pd.read_sql_query(
        """SELECT price, date
           FROM history
           WHERE product_id=?
           ORDER BY id""",
        conn,
        params=(product_id,)
    )

    conn.close()
    return df


# ---------------- HEADER ----------------
st.title("💰 PricePulse")

st.caption(t(
    "Track product prices and compare price history.",
    "ಉತ್ಪನ್ನಗಳ ಬೆಲೆ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ ಮತ್ತು ಹೋಲಿಸಿ."
))

st.divider()


# ---------------- TRACK PRODUCT ----------------
st.subheader(t(
    "🔎 Track a Product",
    "🔎 ಉತ್ಪನ್ನ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ"
))

url = st.text_input(
    t("Paste Product URL", "ಉತ್ಪನ್ನದ URL ಹಾಕಿ"),
    key="url_input",
    placeholder="https://..."
)


# ---------------- TRACK PRICE BUTTON ----------------
if st.button(
    t("🚀 Track Price", "🚀 ಬೆಲೆ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ"),
    use_container_width=True
):
    if not url.strip():
        st.warning(t(
            "Please paste a product URL first.",
            "ದಯವಿಟ್ಟು ಮೊದಲು Product URL ಹಾಕಿ."
        ))

    elif not url.strip().lower().startswith(("http://", "https://")):
        st.warning(t(
            "Please enter a valid URL.",
            "ದಯವಿಟ್ಟು ಸರಿಯಾದ URL ಹಾಕಿ."
        ))

    else:
        with st.spinner(t(
            "Fetching product price...",
            "ಉತ್ಪನ್ನದ ಬೆಲೆ ಹುಡುಕಲಾಗುತ್ತಿದೆ..."
        )):
            success, result = add_product(url.strip())

        if success:
            st.success(t(
                f"Product added successfully! Price: ₹{result['price']}",
                f"ಉತ್ಪನ್ನ ಸೇರಿಸಲಾಗಿದೆ! ಬೆಲೆ: ₹{result['price']}"
            ))
            st.rerun()

        else:
            st.error(t(
                f"Could not fetch price: {result}",
                "ಉತ್ಪನ್ನದ ಬೆಲೆ ಪಡೆಯಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಬೇರೆ ಲಿಂಕ್ ಪ್ರಯತ್ನಿಸಿ."
            ))


# ---------------- CLEAR URL BUTTON ----------------
st.button(
    t("🧹 Clear URL", "🧹 URL ಕ್ಲಿಯರ್ ಮಾಡಿ"),
    on_click=clear_url,
    use_container_width=True
)

st.divider()


# ---------------- MANUAL ADD ----------------
with st.expander(t(
    "➕ Add Product Manually",
    "➕ ಉತ್ಪನ್ನವನ್ನು ಕೈಯಾರೆ ಸೇರಿಸಿ"
)):
    manual_title = st.text_input(
        t("Product Name", "ಉತ್ಪನ್ನದ ಹೆಸರು"),
        key="manual_title"
    )

    manual_price = st.number_input(
        t("Price (₹)", "ಬೆಲೆ (₹)"),
        min_value=0.0,
        step=1.0,
        key="manual_price"
    )

    manual_url = st.text_input(
        t("Product URL (optional)", "Product URL (ಐಚ್ಛಿಕ)"),
        key="manual_url"
    )

    manual_site = st.text_input(
        t("Website", "ವೆಬ್‌ಸೈಟ್"),
        key="manual_site"
    )

    if st.button(t(
        "Save Product",
        "ಉತ್ಪನ್ನ ಉಳಿಸಿ"
    )):
        if not manual_title.strip() or manual_price <= 0:
            st.warning(t(
                "Enter product name and a valid price.",
                "ಉತ್ಪನ್ನದ ಹೆಸರು ಮತ್ತು ಸರಿಯಾದ ಬೆಲೆ ಹಾಕಿ."
            ))

        else:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                """INSERT INTO products (title, url, price, site, added)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    manual_title.strip(),
                    manual_url.strip(),
                    manual_price,
                    manual_site.strip() or "Manual",
                    datetime.now().strftime("%Y-%m-%d %H:%M")
                )
            )

            product_id = cursor.lastrowid

            cursor.execute(
                """INSERT INTO history (product_id, price, date)
                   VALUES (?, ?, ?)""",
                (
                    product_id,
                    manual_price,
                    datetime.now().strftime("%Y-%m-%d %H:%M")
                )
            )

            conn.commit()
            conn.close()

            st.success(t(
                "Product added successfully!",
                "ಉತ್ಪನ್ನ ಸೇರಿಸಲಾಗಿದೆ!"
            ))

            st.rerun()


st.divider()


# ---------------- TRACKED PRODUCTS ----------------
st.subheader(t(
    "📦 Tracked Products",
    "📦 ಟ್ರ್ಯಾಕ್ ಮಾಡುತ್ತಿರುವ ಉತ್ಪನ್ನಗಳು"
))

products = get_products()

if products.empty:
    st.info(t(
        "No products tracked yet. Add a product URL above.",
        "ಇನ್ನೂ ಉತ್ಪನ್ನಗಳನ್ನು ಟ್ರ್ಯಾಕ್ ಮಾಡಿಲ್ಲ. ಮೇಲಿನಿಂದ URL ಸೇರಿಸಿ."
    ))

else:
    st.metric(
        t("Total Products", "ಒಟ್ಟು ಉತ್ಪನ್ನಗಳು"),
        len(products)
    )

    for _, product in products.iterrows():
        pid = int(product["id"])

        with st.container(border=True):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"### {product['title']}")
                st.write(f"**Website:** {product['site']}")
                st.write(f"**Current Price:** ₹{product['price']}")

                if product["url"]:
                    st.markdown(f"[🔗 Open Product]({product['url']})")

                st.caption(f"Added: {product['added']}")

            with col2:
                if st.button(
                    t("🔄 Refresh Price", "🔄 ಬೆಲೆ ಅಪ್‌ಡೇಟ್"),
                    key=f"refresh_{pid}",
                    use_container_width=True
                ):
                    if product["url"]:
                        with st.spinner(t(
                            "Refreshing price...",
                            "ಬೆಲೆ ಅಪ್‌ಡೇಟ್ ಆಗುತ್ತಿದೆ..."
                        )):
                            success, result = refresh_product(
                                pid,
                                product["url"]
                            )

                        if success:
                            st.success(t(
                                f"Price updated: ₹{result['price']}",
                                f"ಬೆಲೆ ಅಪ್‌ಡೇಟ್ ಆಗಿದೆ: ₹{result['price']}"
                            ))
                        else:
                            st.error(t(
                                f"Could not refresh price: {result}",
                                "ಬೆಲೆ ಅಪ್‌ಡೇಟ್ ಆಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."
                            ))

                        st.rerun()

                    else:
                        st.warning(t(
                            "This product has no URL.",
                            "ಈ ಉತ್ಪನ್ನಕ್ಕೆ URL ಇಲ್ಲ."
                        ))

                if st.button(
                    t("🗑️ Delete", "🗑️ ಡಿಲೀಟ್"),
                    key=f"delete_{pid}",
                    use_container_width=True
                ):
                    delete_product(pid)
                    st.rerun()

            # ---------------- HISTORY ----------------
            history = get_history(pid)

            if not history.empty:
                with st.expander(t(
                    "📈 Price History",
                    "📈 ಬೆಲೆ ಇತಿಹಾಸ"
                )):
                    chart_data = history.copy()

                    chart_data["date"] = pd.to_datetime(
                        chart_data["date"],
                        errors="coerce"
                    )

                    chart_data = chart_data.dropna(subset=["date"])
                    chart_data = chart_data.set_index("date")

                    st.line_chart(chart_data["price"])


# ---------------- COMPARISON ----------------
st.divider()

st.subheader(t(
    "📊 Price Comparison",
    "📊 ಬೆಲೆ ಹೋಲಿಕೆ"
))

products = get_products()

if len(products) >= 2:
    comparison = products[["title", "price", "site"]].copy()

    comparison.columns = [
        "Product",
        "Price (₹)",
        "Website"
    ]

    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True
    )

    st.bar_chart(
        comparison.set_index("Product")["Price (₹)"]
    )

else:
    st.info(t(
        "Add at least 2 products to compare prices.",
        "ಬೆಲೆ ಹೋಲಿಸಲು ಕನಿಷ್ಠ 2 ಉತ್ಪನ್ನಗಳನ್ನು ಸೇರಿಸಿ."
    ))


# ---------------- FOOTER ----------------
st.divider()

st.caption("💚 PricePulse | Smart Price Tracking")
