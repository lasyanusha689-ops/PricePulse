import streamlit as st
import sqlite3, requests, re, datetime, json, urllib.parse
from bs4 import BeautifulSoup
import pandas as pd

st.set_page_config(page_title="PricePulse", page_icon="💰", layout="wide")

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect('prices.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS products
    (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, url TEXT, price REAL, site TEXT, added TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS history
    (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, price REAL, date TEXT)''')
    conn.commit()
    return conn

def clean_price(text):
    if not text:
        return 0
    text = str(text).replace('Rs.','').replace('Rs','').replace(',','').strip()
    m = re.search(r'(\d+\.\d+|\d+)', text)
    if m:
        try:
            v = float(m.group(1))
            if v < 10:
                return 0
            return v
        except:
            return 0
    return 0

def guess_title_from_url(url):
    try:
        path = urllib.parse.urlparse(url).path
        parts = [p for p in path.split('/') if p]
        if parts:
            slug = parts[0]
            slug = slug.replace('-', ' ').replace('_', ' ')
            slug = re.sub(r'[^a-zA-Z ]', '', slug)
            slug = slug.strip().title()
            if len(slug) > 3:
                return slug[:80]
    except:
        pass
    return "Product"

def scrape_via_jina(url):
    try:
        jina_url = "https://r.jina.ai/" + url
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/plain'}
        r = requests.get(jina_url, headers=headers, timeout=20)
        if r.status_code == 200 and len(r.text) > 500:
            text = r.text
            bad_words = ['hey', 'check out', 'get upto', 'get up to', 'off on', 'first order', 'download', 'share', 'meesho']
            title = ""
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            for l in lines:
                low = l.lower()
                if len(l) > 10 and len(l) < 100 and 'http' not in low:
                    if any(b in low for b in bad_words):
                        continue
                    title = l[:80]
                    break
            if not title or 'hey' in title.lower():
                title = guess_title_from_url(url)
            all_prices = re.findall(r'Rs\.?\s?([\d,]+\.?\d*)', text)
            valid = []
            for p in all_prices:
                v = clean_price(p)
                if 50 < v < 10000:
                    valid.append(v)
            price = min(valid) if valid else 0
            return title, price
    except Exception as e:
        print("Jina fail:", e)
    return "", 0

def scrape(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept-Language': 'en-IN,en;q=0.9'}
    try:
        r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        html = r.text
        if "Attention Required" not in html and len(html) > 1000:
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict) and 'offers' in item:
                            o = item['offers']
                            if isinstance(o, dict) and 'price' in o:
                                p = clean_price(str(o['price']))
                                if p > 10:
                                    t1 = soup.find('title')
                                    title = t1.get_text().strip()[:80] if t1 else guess_title_from_url(url)
                                    return title, p
                except:
                    continue
            p = 0
            for tag, attrs in [('span', {'class': 'a-price-whole'}),('div', {'class': '_30jeq3'}),('span', {'class': '_30jeq3'})]:
                el = soup.find(tag, attrs)
                if el:
                    p = clean_price(el.get_text())
                    if p > 10:
                        break
            if p == 0:
                text = soup.get_text()
                prices = re.findall(r'Rs\.?\s?([\d,]+\.?\d*)', text)
                for pr in prices:
                    v = clean_price(pr)
                    if 10 < v < 500000:
                        p = v
                        break
            if p > 10:
                t1 = soup.find('title')
                title = t1.get_text().strip()[:80] if t1 else guess_title_from_url(url)
                return title, p
    except Exception as e:
        print("Direct fail:", e)
    j_title, j_price = scrape_via_jina(url)
    if j_price > 10:
        return j_title, j_price
    return guess_title_from_url(url), 0

def get_site(url):
    low = url.lower()
    if "flipkart" in low: return "Flipkart"
    if "myntra" in low: return "Myntra"
    if "nykaa" in low: return "Nykaa"
    if "ajio" in low: return "Ajio"
    if "meesho" in low: return "Meesho"
    if "amazon" in low: return "Amazon"
    return "Other"

# ---------- UI ----------
lang = st.sidebar.selectbox("Language / ಭಾಷೆ", ["English", "ಕನ್ನಡ"])
EN = lang == "English"

def T(en, kn):
    return en if EN else kn

st.title("💰 PricePulse")
st.markdown(f"### {T('Never Pay More. Track. Compare. Save.', 'ಯಾವಾಗಲೂ ಬೆಸ್ಟ್ ಪ್ರೈಸ್ ಗೆ ತಗೊಳ್ಳಿ.')}")
st.caption("Amazon / Flipkart / Myntra / Nykaa / Ajio / Meesho")

# Add Product
st.subheader(T("🔗 Track Product (Auto)", "🔗 ಪ್ರಾಡಕ್ಟ್ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ (ಆಟೋ)"))
url = st.text_input(T("Paste product link...", "ಲಿಂಕ್ ಇಲ್ಲಿ ಹಾಕಿ..."), key="url_input")
if st.button(T("Track Price (Auto)", "ಆಟೋ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ"), type="primary"):
    if url:
        with st.spinner(T("Auto tracking... Please wait 15 sec, trying bypass...", "ಆಟೋ ಟ್ರ್ಯಾಕ್... 15 ಸೆಕೆಂಡ್ ಕಾಯಿರಿ...")):
            title, price = scrape(url)
            if price == 0:
                st.warning(T("Site blocked Auto. Name auto-filled! Just enter the price and click Add Manually.", "ಸೈಟ್ ಆಟೋ ಬ್ಲಾಕ್ ಮಾಡಿದೆ. ಹೆಸರು ತಾನೇ ಬಂತು! ಬೆಲೆ ಮಾತ್ರ ಹಾಕಿ, ಕೈಯಾರೆ ಸೇರಿಸಿ ಒತ್ತಿ."))
                st.session_state['mTitle'] = title
            else:
                conn = get_db()
                now = datetime.datetime.now().strftime('%d-%m %H:%M')
                site = get_site(url)
                cur = conn.cursor()
                cur.execute("INSERT INTO products (title,url,price,site,added) VALUES (?,?,?,?,?)", (title, url, price, site, now))
                pid = cur.lastrowid
                cur.execute("INSERT INTO history (product_id,price,date) VALUES (?,?,?)", (pid, price, now))
                conn.commit(); conn.close()
                st.success(f"Auto Added: {title} - Rs.{price}")
                st.rerun()
    else:
        st.error(T("Please paste a link", "ದಯವಿಟ್ಟು ಲಿಂಕ್ ಹಾಕಿ"))

# Manual
st.subheader(T("✍️ Add Manually", "✍️ ಕೈಯಾರೆ ಸೇರಿಸಿ"))
c1, c2, c3 = st.columns([2,1,1])
with c1:
    mTitle = st.text_input(T("Product name - ex: iPhone 17 Mist Blue", "ಪ್ರಾಡಕ್ಟ್ ಹೆಸರು - ಉದಾ: iPhone 17 Mist Blue"), key="mTitle")
with c2:
    mPrice = st.number_input(T("Price", "ಬೆಲೆ"), min_value=0, step=1, key="mPrice")
with c3:
    st.write("")
    st.write("")
    if st.button(T("+ Add Manually", "+ ಕೈಯಾರೆ ಸೇರಿಸಿ")):
        if mTitle and mPrice > 0:
            conn = get_db()
            now = datetime.datetime.now().strftime('%d-%m %H:%M')
            cur = conn.cursor()
            cur.execute("INSERT INTO products (title,url,price,site,added) VALUES (?,?,?,?,?)", (mTitle, url if url else "Manual", mPrice, "Manual", now))
            pid = cur.lastrowid
            cur.execute("INSERT INTO history (product_id,price,date) VALUES (?,?,?)", (pid, mPrice, now))
            conn.commit(); conn.close()
            st.success(f"Manually added: {mTitle} - Rs.{mPrice}")
            st.rerun()
        else:
            st.error(T("Please enter Name + Price", "ಹೆಸರು + ಬೆಲೆ ಹಾಕಿ"))

st.divider()

# List
conn = get_db()
rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
conn.close()

if rows:
    total = len(rows)
    prices = [r[3] for r in rows]
    col1, col2, col3 = st.columns(3)
    col1.metric(T("Tracked Items", "ಟ್ರ್ಯಾಕ್ ಮಾಡಿದ ವಸ್ತುಗಳು"), total)
    col2.metric(T("Avg Price", "ಸರಾಸರಿ ಬೆಲೆ"), f"Rs {int(sum(prices)/total)}")
    col3.metric(T("Lowest Price", "ಕಡಿಮೆ ಬೆಲೆ"), f"Rs {int(min(prices))}")

    # Chart
    st.subheader(T("📊 Price Comparison", "📊 ಬೆಲೆ ಹೋಲಿಕೆ"))
    df = pd.DataFrame([{"Product": r[1][:25], "Price": r[3]} for r in rows])
    st.bar_chart(df.set_index("Product"))

    st.subheader(T("📋 My Track List", "📋 ನನ್ನ ಟ್ರ್ಯಾಕ್ ಪಟ್ಟಿ"))
    for r in rows:
        pid, title, purl, price, site, added = r
        with st.expander(f"{title} - Rs.{price} | {site}"):
            st.write(f"**{T('Updated:', 'ಅಪ್ಡೇಟ್:')}** {added}")
            st.write(f"**Link:** {purl}")
            b1, b2, b3 = st.columns(3)
            if b1.button(T("🔄 Refresh", "🔄 ರಿಫ್ರೆಶ್"), key=f"ref_{pid}"):
                with st.spinner(T("Re-checking price...", "ಬೆಲೆ ಮತ್ತೆ ಚೆಕ್ ಮಾಡುತ್ತಿದ್ದೇವೆ...")):
                    t2, p2 = scrape(purl)
                    if p2 == 0:
                        st.error(T("Auto failed, site blocked. Use Manual Add!", "ಆಟೋ ಆಗಲಿಲ್ಲ, ಸೈಟ್ ಬ್ಲಾಕ್ ಮಾಡಿದೆ."))
                    else:
                        conn = get_db()
                        now = datetime.datetime.now().strftime('%d-%m %H:%M')
                        conn.execute("UPDATE products SET price=?, added=? WHERE id=?", (p2, now, pid))
                        conn.execute("INSERT INTO history (product_id,price,date) VALUES (?,?,?)", (pid, p2, now))
                        conn.commit(); conn.close()
                        st.success(f"Updated Price: Rs.{p2}")
                        st.rerun()
            if b2.button(T("📈 History", "📈 ಇತಿಹಾಸ"), key=f"hist_{pid}"):
                conn = get_db()
                hrows = conn.execute("SELECT price,date FROM history WHERE product_id=? ORDER BY id", (pid,)).fetchall()
                conn.close()
                hdf = pd.DataFrame(hrows, columns=["Price", "Date"])
                st.line_chart(hdf.set_index("Date"))
            if b3.button(T("🗑️ Delete", "🗑️ ಡಿಲೀಟ್"), key=f"del_{pid}"):
                conn = get_db()
                conn.execute("DELETE FROM products WHERE id=?", (pid,))
                conn.execute("DELETE FROM history WHERE product_id=?", (pid,))
                conn.commit(); conn.close()
                st.rerun()
else:
    st.info(T("Nothing tracked yet", "ಇನ್ನೂ ಏನೂ ಟ್ರ್ಯಾಕ್ ಮಾಡಿಲ್ಲ"))