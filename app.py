import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
from PIL import Image, ImageOps
import io
import base64
import urllib.parse
import re
from datetime import datetime

# ==========================================
# KONFIGURATION AUS STREAMLIT SECRETS
# ==========================================
if "GROQ_API_KEY" not in st.secrets:
    st.error("❌ Kein GROQ_API_KEY in .streamlit/secrets.toml gefunden!")
    st.stop()

GROQ_API_KEY = st.secrets["GROQ_API_KEY"].strip()

st.set_page_config(page_title="PriceBot Scanner", page_icon="🔍", layout="centered")

# ==========================================
# SESSION-STATE INITIALISIERUNG (Privater Verlauf pro Nutzer)
# ==========================================
if "history" not in st.session_state:
    st.session_state["history"] = []

# ==========================================
# MOBILE-FIRST STYLING (CSS)
# ==========================================
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 3rem !important;
            max-width: 520px;
        }
        
        .product-card {
            background: #1e1e24;
            border: 1px solid #2e2e38;
            border-radius: 16px;
            overflow: hidden;
            margin-bottom: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
            display: flex;
            flex-direction: column;
            transition: transform 0.15s ease;
        }
        .product-card:active {
            transform: scale(0.96);
            border-color: #0064d2;
        }
        .card-img {
            width: 100%;
            height: 140px;
            object-fit: cover;
            display: block;
            background: #111;
        }
        .card-body {
            padding: 10px 12px 10px 12px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .card-title {
            color: #ffffff;
            font-size: 13px;
            font-weight: 600;
            line-height: 1.3;
            margin-bottom: 4px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .card-date {
            color: #888;
            font-size: 10px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "<h2 style='text-align: center; margin-bottom: 0px;'>📸 eBay Sold Scanner</h2>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: #888; font-size: 13px; margin-bottom: 15px;'>Mache ein Foto, um die letzten Verkaufspreise zu prüfen</p>",
    unsafe_allow_html=True,
)


# ==========================================
# LOKALE HISTORIE-FUNKTIONEN (Nur im Browser/Session)
# ==========================================
def create_thumbnail_b64(raw_bytes, max_dim=240) -> str:
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return ""


def add_to_history(query, url, thumb_b64=""):
    history = st.session_state["history"]
    if history and history[0].get("query") == query:
        return
    new_entry = {
        "query": query,
        "url": url,
        "time": datetime.now().strftime("%d.%m. %H:%M"),
        "thumb": thumb_b64,
    }
    history.insert(0, new_entry)


def delete_history_item(index):
    if 0 <= index < len(st.session_state["history"]):
        st.session_state["history"].pop(index)


def clear_entire_history():
    st.session_state["history"] = []


# ==========================================
# BILD- & KI-FUNKTIONEN (Groq Qwen 3.8)
# ==========================================
def optimize_image_bytes(raw_bytes, max_dimension=800) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_dimension, max_dimension))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def identify_product_groq(image_bytes: bytes, status_box):
    client = Groq(api_key=GROQ_API_KEY)
    status_box.update(label="🤖 KI analysiert Produkt...", state="running")

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Identifiziere das Produkt auf diesem Foto präzise für eine eBay-Suche. "
        "Gib NUR 3 bis 6 treffende Suchbegriffe aus (z.B. Titel, Edition, Format wie DVD/Box). "
        "Keine Sätze, keine Artikel, keine Anführungszeichen, keine Klammern."
    )

    response = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                    },
                ],
            }
        ],
        max_tokens=40,
    )

    result = response.choices[0].message.content or ""
    return re.sub(r"[\(\)'\"]", "", result).strip()


# ==========================================
# KAMERA-BEREICH
# ==========================================
img_file = st.camera_input("Foto aufnehmen", label_visibility="collapsed")

if img_file:
    raw_img_bytes = img_file.getvalue()
    compressed_bytes = optimize_image_bytes(raw_img_bytes)

    if (
        "detected_query" not in st.session_state
        or st.session_state.get("last_img") != img_file.file_id
    ):
        st.session_state["last_img"] = img_file.file_id

        with st.status("🔍 Erkenne Gegenstand...", expanded=False) as status:
            try:
                query_text = identify_product_groq(compressed_bytes, status_box=status)
                st.session_state["detected_query"] = query_text
                status.update(
                    label=f"✅ {query_text}",
                    state="complete",
                )
            except Exception as e:
                status.update(label="❌ Erkennung fehlgeschlagen", state="error")
                st.error(f"Fehler: {e}")
                st.session_state["detected_query"] = ""

    current_query = st.text_input(
        "Suchbegriff:",
        value=st.session_state.get("detected_query", ""),
        help="Hier kannst du den Begriff noch kurz nachbessern",
    )

    if current_query:
        clean_query = re.sub(r"[^\w\s\-]", "", current_query).strip()
        encoded_query = urllib.parse.quote(clean_query)
        ebay_url = f"https://www.ebay.de/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_sop=13"

        thumb_b64 = create_thumbnail_b64(raw_img_bytes)
        add_to_history(clean_query, ebay_url, thumb_b64=thumb_b64)

        # ----------------------------------------------------
        # BUTTON ZUM DIREKTEN ÖFFNEN DER EBAY-APP
        # ----------------------------------------------------
        st.markdown(
            f"""
            <a href="{ebay_url}" target="_blank" rel="noopener noreferrer" style="text-decoration: none; display: block;">
                <button style="
                    width: 100%; 
                    height: 54px; 
                    background: linear-gradient(135deg, #0064d2 0%, #0094ff 100%); 
                    color: white; 
                    border: none; 
                    border-radius: 14px; 
                    font-size: 17px; 
                    font-weight: 700; 
                    cursor: pointer;
                    margin-top: 6px;
                    margin-bottom: 10px;
                    box-shadow: 0 4px 16px rgba(0, 100, 210, 0.4);
                ">
                    🛍️ In eBay-App ansehen
                </button>
            </a>
            """,
            unsafe_allow_html=True,
        )

        # Kopier-Buttons
        safe_query_js = clean_query.replace("'", "\\'").replace('"', '\\"')
        copy_buttons_html = f"""
            <div style="display: flex; gap: 8px; margin-bottom: 14px;">
                <button onclick="
                    const btn = this;
                    navigator.clipboard.writeText('{safe_query_js}').then(() => {{
                        btn.innerHTML = '✅ Text kopiert!';
                        setTimeout(() => btn.innerHTML = '📋 Suchtext', 2000);
                    }});
                " style="
                    flex: 1; height: 42px; background-color: #262730; color: #fff;
                    border: 1px solid #4e5159; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer;
                ">
                    📋 Suchtext
                </button>

                <button onclick="
                    const btn = this;
                    navigator.clipboard.writeText('{ebay_url}').then(() => {{
                        btn.innerHTML = '✅ Link kopiert!';
                        setTimeout(() => btn.innerHTML = '🔗 eBay-Link', 2000);
                    }});
                " style="
                    flex: 1; height: 42px; background-color: #262730; color: #fff;
                    border: 1px solid #4e5159; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer;
                ">
                    🔗 eBay-Link
                </button>
            </div>
            """
        components.html(copy_buttons_html, height=52)

# ==========================================
# VISUELLER VERLAUF (Nur für diesen Nutzer)
# ==========================================
st.markdown(
    "<h4 style='margin-top: 15px; margin-bottom: 10px;'>📜 Bisher gescannt</h4>",
    unsafe_allow_html=True,
)

all_history = st.session_state["history"]

if all_history:
    if "show_all_history" not in st.session_state:
        st.session_state["show_all_history"] = False

    limit = 20
    visible_items = (
        all_history if st.session_state["show_all_history"] else all_history[:limit]
    )

    for i in range(0, len(visible_items), 2):
        col1, col2 = st.columns(2)

        with col1:
            item = visible_items[i]
            img_src = (
                f"data:image/jpeg;base64,{item['thumb']}"
                if item.get("thumb")
                else "https://via.placeholder.com/200?text=📦"
            )
            st.markdown(
                f"""
                <a href="{item['url']}" target="_blank" rel="noopener noreferrer" style="text-decoration: none; display: block;">
                    <div class="product-card">
                        <img src="{img_src}" class="card-img" />
                        <div class="card-body">
                            <div class="card-title">{item['query']}</div>
                            <div class="card-date">{item.get('time', '')}</div>
                        </div>
                    </div>
                </a>
                """,
                unsafe_allow_html=True,
            )
            if st.button("🗑️ Löschen", key=f"del_{i}", use_container_width=True):
                delete_history_item(i)
                st.rerun()

        with col2:
            if i + 1 < len(visible_items):
                item_r = visible_items[i + 1]
                img_src_r = (
                    f"data:image/jpeg;base64,{item_r['thumb']}"
                    if item_r.get("thumb")
                    else "https://via.placeholder.com/200?text=📦"
                )
                st.markdown(
                    f"""
                    <a href="{item_r['url']}" target="_blank" rel="noopener noreferrer" style="text-decoration: none; display: block;">
                        <div class="product-card">
                            <img src="{img_src_r}" class="card-img" />
                            <div class="card-body">
                                <div class="card-title">{item_r['query']}</div>
                                <div class="card-date">{item_r.get('time', '')}</div>
                            </div>
                        </div>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("🗑️ Löschen", key=f"del_{i+1}", use_container_width=True):
                    delete_history_item(i + 1)
                    st.rerun()

    st.write("")
    col_expand, col_clear = st.columns([1, 1])

    with col_expand:
        if len(all_history) > limit:
            if not st.session_state["show_all_history"]:
                if st.button(
                    f"➕ Mehr ({len(all_history) - limit})", use_container_width=True
                ):
                    st.session_state["show_all_history"] = True
                    st.rerun()
            else:
                if st.button("➖ Weniger", use_container_width=True):
                    st.session_state["show_all_history"] = False
                    st.rerun()

    with col_clear:
        if st.button("⚠️ Alles leeren", use_container_width=True):
            clear_entire_history()
            st.rerun()
else:
    st.markdown(
        "<p style='color: #666; font-size: 13px;'>Noch keine Artikel gescannt.</p>",
        unsafe_allow_html=True,
    )
