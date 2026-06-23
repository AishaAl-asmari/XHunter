import tkinter as tk
import requests
import threading
import time
import os
import tempfile
from datetime import datetime, timedelta, timezone

from openai import OpenAI
from PIL import Image, ImageTk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib
import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader


# =========================
# ARABIC FIX FOR MATPLOTLIB
# =========================
matplotlib.rcParams["font.family"] = "Arial Unicode MS"

def ar(text):
    return get_display(arabic_reshaper.reshape(text))


# =========================
# API KEYS
# =========================
# Keys are loaded from environment variables instead of being hardcoded,
# so this file is safe to publish publicly (e.g. on GitHub) without
# exposing real credentials. Set these before running the program:
#
#   Windows (PowerShell):
#     setx X_BEARER_TOKEN "your_token_here"
#     setx OPENAI_API_KEY "your_key_here"
#
#   macOS / Linux:
#     export X_BEARER_TOKEN="your_token_here"
#     export OPENAI_API_KEY="your_key_here"
BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")




if not BEARER_TOKEN:
    print("Missing X_BEARER_TOKEN")

if not OPENAI_API_KEY:
    print("Missing OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================
# GLOBAL VARIABLES
# =========================
running = False
seen_ids = set()

high_count = 0
medium_count = 0
low_count = 0
total_posts = 0

feed_empty_label = None

category_counts = {
    "تهديدات أمنية": 0,
    "تهديدات السلامة العامة": 0,
    "إشاعات ومعلومات مضللة": 0,
    "مخاطر السمعة التجارية": 0,
    "مخاطر سياسية واجتماعية": 0,
    "تهديدات سيبرانية": 0
}

category_icons = {
    "تهديدات أمنية": "🚨",
    "تهديدات السلامة العامة": "🔥",
    "إشاعات ومعلومات مضللة": "📰",
    "مخاطر السمعة التجارية": "🏢",
    "مخاطر سياسية واجتماعية": "👥",
    "تهديدات سيبرانية": "🛡️"
}

category_colors = {
    "تهديدات أمنية": "#B33A3A",
    "تهديدات السلامة العامة": "#C9892F",
    "إشاعات ومعلومات مضللة": "#8FA6C9",
    "مخاطر السمعة التجارية": "#5BC8E8",
    "مخاطر سياسية واجتماعية": "#7C9CD6",
    "تهديدات سيبرانية": "#A9B8D6"
}

RISK_LABELS_AR = {
    "High": "عالي",
    "Medium": "متوسط",
    "Low": "منخفض"
}

post_registry = {}
post_counter = 0


# =========================
# LANGUAGE TOGGLE
# =========================
current_language = "ar"

TRANSLATIONS = {
    "ar": {
        "subtitle": "لوحة استخبارات التهديدات اللحظية",
        "status_label": "الحالة",
        "date_label": "التاريخ",
        "time_label": "الوقت",
        "stopped": "متوقف",
        "active": "نشط",
        "saved": "تم الحفظ",
        "total_title": "إجمالي المنشورات",
        "total_subtitle": "إجمالي المنشورات المجمّعة",
        "high_title": "مخاطر عالية",
        "medium_title": "مخاطر متوسطة",
        "low_title": "مخاطر منخفضة",
        "risk_subtitle": "من إجمالي المنشورات",
        "bar_header": "📈  نظرة عامة على مستويات الخطر",
        "pie_header": "📈  توزيع فئات التهديد",
        "feed_header": "📡  سجل المخاطر اللحظي",
        "start": "▶ تشغيل",
        "stop": "⏹ إيقاف",
        "clear": "🗑 تفريغ",
        "report": "📄  إصدار تقرير PDF",
        "language_button": "العربية",
        "saudi_button": "منشورات داخل السعودية",
        "extracting_saudi": "جاري استخراج منشورات السعودية...",
        "empty_feed": "📡  لا توجد منشورات بعد — اضغط تشغيل لبدء المراقبة",
        "analyzing": "🤖 الذكاء الاصطناعي يحلل منشوراً جديداً...",
        "risk_chart_title": "مستويات الخطر",
        "count": "العدد",
        "category_chart_title": "فئات التهديد",
        "no_data": "لا توجد بيانات بعد",
        "risk_high": "عالي",
        "risk_medium": "متوسط",
        "risk_low": "منخفض",
        "popup_title": "تفاصيل المنشور",
        "risk_word": "الخطورة",
        "confidence": "🤖 نسبة الثقة",
        "original_post": "المنشور الأصلي",
        "ai_analysis": "🤖 تحليل الذكاء الاصطناعي",
    },
    "en": {
        "subtitle": "Real-Time Threat Intelligence Dashboard",
        "status_label": "Status",
        "date_label": "Date",
        "time_label": "Time",
        "stopped": "Stopped",
        "active": "Active",
        "saved": "Saved",
        "total_title": "Total Posts",
        "total_subtitle": "Total collected posts",
        "high_title": "High Risks",
        "medium_title": "Medium Risks",
        "low_title": "Low Risks",
        "risk_subtitle": "from total posts",
        "bar_header": "📈  Risk Level Overview",
        "pie_header": "📈  Threat Category Distribution",
        "feed_header": "📡  Live Risk Feed",
        "start": "▶ Start",
        "stop": "⏹ Stop",
        "clear": "🗑 Clear",
        "report": "📄  Generate PDF Report",
        "language_button": "English",
        "saudi_button": "inside Posts",
        "extracting_saudi": "Extracting Saudi Arabia posts...",
        "empty_feed": "📡  No posts yet — press Start to begin monitoring",
        "analyzing": "🤖 AI is analyzing a new post...",
        "risk_chart_title": "Risk Levels",
        "count": "Count",
        "category_chart_title": "Threat Categories",
        "no_data": "No data yet",
        "risk_high": "High",
        "risk_medium": "Medium",
        "risk_low": "Low",
        "popup_title": "Post Details",
        "risk_word": "Risk",
        "confidence": "🤖 Confidence",
        "original_post": "Original Post",
        "ai_analysis": "🤖 AI Analysis",
    }
}

RISK_LABELS_EN = {
    "High": "High",
    "Medium": "Medium",
    "Low": "Low"
}

CATEGORY_LABELS_EN = {
    "تهديدات أمنية": "Security Threats",
    "تهديدات السلامة العامة": "Public Safety Threats",
    "إشاعات ومعلومات مضللة": "Misinformation & Fake News",
    "مخاطر السمعة التجارية": "Brand Reputation Risks",
    "مخاطر سياسية واجتماعية": "Political & Social Risks",
    "تهديدات سيبرانية": "Cybersecurity Threats"
}

widget_refs = {}


def tr(key):
    return TRANSLATIONS[current_language].get(key, key)


def risk_text(risk):
    if current_language == "ar":
        return RISK_LABELS_AR.get(risk, risk)
    return RISK_LABELS_EN.get(risk, risk)


def category_text(category):
    """Categories are always stored in Arabic (the AI always returns the
    Arabic label), so this translates them for display when the UI
    language is set to English."""
    if current_language == "en":
        return CATEGORY_LABELS_EN.get(category, category)
    return category


def toggle_language():
    global current_language
    current_language = "en" if current_language == "ar" else "ar"
    apply_language()


def apply_language():
    if "subtitle" in widget_refs:
        widget_refs["subtitle"].config(text=tr("subtitle"))
    if "lang_btn" in widget_refs:
        widget_refs["lang_btn"].config(text=tr("language_button"))

    for key, value in {
        "status_caption": "status_label",
        "date_caption": "date_label",
        "time_caption": "time_label",
        "total_title": "total_title",
        "total_subtitle": "total_subtitle",
        "high_title": "high_title",
        "medium_title": "medium_title",
        "low_title": "low_title",
        "high_subtitle": "risk_subtitle",
        "medium_subtitle": "risk_subtitle",
        "low_subtitle": "risk_subtitle",
        "bar_header": "bar_header",
        "pie_header": "pie_header",
        "feed_header": "feed_header",
        "start_btn": "start",
        "saudi_btn": "saudi_button",
        "stop_btn": "stop",
        "clear_btn": "clear",
        "report_btn": "report",
    }.items():
        if key in widget_refs:
            widget_refs[key].config(text=tr(value))

    if "status_label" in globals():
        current_status = status_label.cget("text")
        if current_status in ("متوقف", "Stopped"):
            status_label.config(text=tr("stopped"))
        elif current_status in ("نشط", "Active"):
            status_label.config(text=tr("active"))
        elif current_status in ("تم الحفظ", "Saved"):
            status_label.config(text=tr("saved"))

    # Existing feed rows were drawn with the risk badge text fixed in
    # whatever language was active at the time, and don't update on
    # their own. Re-render every stored post (and the empty-state message,
    # if needed) so the whole feed matches the newly selected language.
    global feed_empty_label

    for widget in feed_frame.winfo_children():
        widget.destroy()
    feed_empty_label = None

    if post_registry:
        for post in post_registry.values():
            if post["risk"] != "Low":
                add_feed_row(post)
        if len(feed_frame.winfo_children()) == 0:
            show_empty_feed_message()
    else:
        show_empty_feed_message()

    update_dashboard()


# =========================
# LOAD KEYWORDS
# =========================
def load_keywords():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    keywords_file = os.path.join(base_dir, "keywords.txt")

    if not os.path.exists(keywords_file):
        print("keywords.txt not found")
        return []

    with open(keywords_file, "r", encoding="utf-8") as f:
        return [k.strip() for k in f if k.strip()]


# =========================
# GET TWEETS
# =========================
def get_tweets(saudi_only=False):
    keywords = load_keywords()

    url = "https://api.twitter.com/2/tweets/search/recent"

    ten_hours_ago = datetime.now(timezone.utc) - timedelta(hours=10)

    if saudi_only:
        # Important: X only returns posts with location/geo metadata for this filter.
        query = "place_country:SA -is:retweet"
    else:
        if not keywords:
            return [], {}
        query = " OR ".join(keywords)

    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }

    params = {
        "query": query,
        "max_results": 50 if saudi_only else 20,
        "tweet.fields": "created_at,geo,lang",
        "expansions": "author_id,geo.place_id",
        "user.fields": "username",
        "place.fields": "country,country_code,full_name",
        "start_time": ten_hours_ago.isoformat()
    }

    response = requests.get(url, headers=headers, params=params)

    print("STATUS:", response.status_code)
    print("QUERY:", query)

    if response.status_code != 200:
        print(response.text)
        return [], {}

    data = response.json()
    users = {}

    if "includes" in data and "users" in data["includes"]:
        for user in data["includes"]["users"]:
            users[user["id"]] = user["username"]

    return data.get("data", []), users

# =========================
# AI ANALYSIS
# =========================
def analyze(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
You are a threat intelligence analyst reviewing posts from X.

Classify the post into:
High, Medium, or Low.

HIGH:
Direct credible threat, attack plan, violence, hacking plan, leak threat, terrorism, or urgent public safety emergency.

MEDIUM:
Risk-relevant information, news, warning, scam, protest, vulnerability, crime report, or brand risk.

LOW:
Metaphor, joke, emotion, poetry, casual talk, sports, lyrics, or no real threat.

Choose one Arabic category exactly:
تهديدات أمنية
تهديدات السلامة العامة
إشاعات ومعلومات مضللة
مخاطر السمعة التجارية
مخاطر سياسية واجتماعية
تهديدات سيبرانية

Return only this format:
Risk: High
Category: تهديدات السلامة العامة
Confidence: 92
Reasoning: شرح قصير بالعربي
"""
            },
            {
                "role": "user",
                "content": text
            }
        ]
    )

    result = response.choices[0].message.content.strip()

    risk = "Low"
    category = "تهديدات أمنية"
    confidence = 85
    reasoning = ""

    for line in result.splitlines():
        if line.startswith("Risk:"):
            risk = line.replace("Risk:", "").strip()
        elif line.startswith("Category:"):
            category = line.replace("Category:", "").strip()
        elif line.startswith("Confidence:"):
            raw = line.replace("Confidence:", "").strip().replace("%", "")
            try:
                confidence = int(raw)
            except ValueError:
                confidence = 85
        elif line.startswith("Reasoning:"):
            reasoning = line.replace("Reasoning:", "").strip()

    if not reasoning:
        reasoning = "لم يتم توفير شرح تفصيلي لهذا التصنيف."

    return risk, category, confidence, reasoning


# =========================
# UPDATE DASHBOARD
# =========================
def update_dashboard():
    total_label.config(text=str(total_posts))
    high_label.config(text=str(high_count))
    medium_label.config(text=str(medium_count))
    low_label.config(text=str(low_count))

    update_bar_chart()
    update_pie_chart()


# =========================
# BAR CHART
# =========================
def update_bar_chart():
    bar_ax.clear()

    labels = [
        tr("risk_high"),
        tr("risk_medium"),
        tr("risk_low")
    ]

    values = [high_count, medium_count, low_count]
    colors = ["#B33A3A", "#C9892F", "#3E8E6E"]

    bar_fig.patch.set_facecolor("#15213A")
    bar_ax.set_facecolor("#15213A")

    bars = bar_ax.bar(labels, values, color=colors)

    bar_ax.set_title(tr("risk_chart_title"), color="white", fontsize=14, fontweight="bold")
    bar_ax.set_ylabel(tr("count"), color="white")
    bar_ax.tick_params(colors="white")

    for spine in bar_ax.spines.values():
        spine.set_color("#2A3A55")

    bar_ax.grid(axis="y", color="#1C2B45", linestyle="--", alpha=0.5)

    max_value = max(values) if max(values) > 0 else 1
    bar_ax.set_ylim(0, max_value + 1)

    for bar in bars:
        height = bar.get_height()
        bar_ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + 0.05,
            str(height),
            ha="center",
            va="bottom",
            color="white",
            fontweight="bold"
        )

    bar_fig.subplots_adjust(bottom=0.25)
    bar_canvas.draw()


# =========================
# PIE CHART
# =========================
def update_pie_chart():
    pie_ax.clear()

    pie_fig.patch.set_facecolor("#15213A")
    pie_ax.set_facecolor("#15213A")

    labels = []
    values = []
    colors = []

    for category, count in category_counts.items():
        if count > 0:
            labels.append(category_text(category))
            values.append(count)
            colors.append(category_colors.get(category, "#5BC8E8"))

    if values:
        pie_ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            colors=colors,
            textprops={"color": "white", "fontsize": 8}
        )
        pie_ax.set_title(tr("category_chart_title"), color="white", fontsize=14, fontweight="bold")
    else:
        pie_ax.text(
            0.5,
            0.5,
            tr("no_data"),
            ha="center",
            va="center",
            color="white",
            fontsize=12
        )
        pie_ax.set_title(tr("category_chart_title"), color="white", fontsize=14, fontweight="bold")
        pie_ax.set_xlim(0, 1)
        pie_ax.set_ylim(0, 1)

    pie_fig.subplots_adjust(bottom=0.15)
    pie_canvas.draw()


# =========================
# FEED FUNCTIONS
# =========================
def show_empty_feed_message():
    global feed_empty_label

    feed_empty_label = tk.Label(
        feed_frame,
        text=tr("empty_feed"),
        bg="#15213A",
        fg="#5B6B8C",
        font=("Segoe UI", 10),
        pady=40
    )
    feed_empty_label.pack(fill="both", expand=True)


def show_analyzing_row():
    global feed_empty_label

    if feed_empty_label is not None:
        feed_empty_label.destroy()
        feed_empty_label = None

    row = tk.Frame(feed_frame, bg="#15213A")
    row.pack(fill="x", padx=10, pady=4)

    spinner = tk.Label(
        row,
        text="◐",
        bg="#15213A",
        fg="#5BC8E8",
        font=("Segoe UI", 11, "bold")
    )
    spinner.pack(side="left", padx=(8, 8), pady=6)

    tk.Label(
        row,
        text=tr("analyzing"),
        bg="#15213A",
        fg="#8FA6C9",
        font=("Segoe UI", 9, "italic")
    ).pack(side="left", pady=6)

    spin_frames = ["◐", "◓", "◑", "◒"]
    spin_state = {"i": 0, "active": True}

    def animate():
        if not spin_state["active"]:
            return

        spin_state["i"] = (spin_state["i"] + 1) % len(spin_frames)

        try:
            spinner.config(text=spin_frames[spin_state["i"]])
            window.after(140, animate)
        except tk.TclError:
            pass

    animate()

    return row, spin_state


def open_detail_popup(post):
    popup = tk.Toplevel(window)
    popup.title(tr("popup_title"))
    popup.geometry("560x420")
    popup.configure(bg="#15213A")
    popup.resizable(False, False)

    risk_color = {
        "High": "#B33A3A",
        "Medium": "#C9892F",
        "Low": "#3E8E6E"
    }.get(post["risk"], "#5BC8E8")

    header_row = tk.Frame(popup, bg="#15213A")
    header_row.pack(fill="x", padx=20, pady=(18, 10))

    tk.Label(
        header_row,
        text=f"{risk_text(post['risk'])} {tr('risk_word')}",
        bg=risk_color,
        fg="white",
        font=("Segoe UI", 10, "bold"),
        padx=12,
        pady=5
    ).pack(side="left")

    tk.Label(
        header_row,
        text=f"{tr('confidence')} {post['confidence']}%",
        bg="#0B1220",
        fg="#5BC8E8",
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=5
    ).pack(side="left", padx=(10, 0))

    tk.Button(
        header_row,
        text="✕",
        command=popup.destroy,
        bg="#15213A",
        fg="#8FA6C9",
        relief="flat",
        font=("Segoe UI", 11, "bold"),
        cursor="hand2"
    ).pack(side="right")

    tk.Label(
        popup,
        text=tr("original_post"),
        bg="#15213A",
        fg="#8FA6C9",
        font=("Segoe UI", 9, "bold")
    ).pack(anchor="e", padx=20)

    tk.Label(
        popup,
        text=post["text"],
        bg="#0B1220",
        fg="white",
        font=("Segoe UI", 11),
        wraplength=500,
        justify="right",
        padx=14,
        pady=12
    ).pack(fill="x", padx=20, pady=(4, 4))

    tk.Label(
        popup,
        text=f"👤 @{post['username']}  ·  {category_icons.get(post['category'], '⚠️')} {category_text(post['category'])}",
        bg="#15213A",
        fg=category_colors.get(post["category"], "#5BC8E8"),
        font=("Segoe UI", 9, "bold")
    ).pack(anchor="e", padx=20, pady=(0, 16))

    tk.Label(
        popup,
        text=tr("ai_analysis"),
        bg="#15213A",
        fg="#8FA6C9",
        font=("Segoe UI", 9, "bold")
    ).pack(anchor="e", padx=20)

    tk.Label(
        popup,
        text=post["reasoning"],
        bg="#0F1B30",
        fg="#C9D4E8",
        font=("Segoe UI", 10),
        wraplength=500,
        justify="right",
        padx=14,
        pady=12
    ).pack(fill="x", padx=20, pady=(4, 16))


def add_feed_row(post):
    global feed_empty_label

    if feed_empty_label is not None:
        feed_empty_label.destroy()
        feed_empty_label = None

    risk_color = {
        "High": "#B33A3A",
        "Medium": "#C9892F",
        "Low": "#3E8E6E"
    }.get(post["risk"], "#5BC8E8")

    row = tk.Frame(feed_frame, bg="#15213A", cursor="hand2")
    row.pack(fill="x", padx=10, pady=4)

    divider = tk.Frame(feed_frame, bg="#1C2B45", height=1)
    divider.pack(fill="x", padx=10)

    badge = tk.Label(
        row,
        text=risk_text(post["risk"]),
        bg=risk_color,
        fg="white",
        font=("Segoe UI", 8, "bold"),
        padx=8,
        pady=3,
        cursor="hand2"
    )
    badge.pack(side="left", padx=(2, 10), pady=4)

    text_block = tk.Frame(row, bg="#15213A", cursor="hand2")
    text_block.pack(side="left", fill="x", expand=True, pady=4)

    text_label = tk.Label(
        text_block,
        text=post["text"],
        bg="#15213A",
        fg="white",
        wraplength=750,
        justify="left",
        font=("Segoe UI", 10),
        cursor="hand2"
    )
    text_label.pack(anchor="w")

    meta_row = tk.Frame(text_block, bg="#15213A", cursor="hand2")
    meta_row.pack(anchor="w", pady=(2, 0))

    tk.Label(
        meta_row,
        text=f"👤 @{post['username']}  ·  {category_icons.get(post['category'], '⚠️')} {category_text(post['category'])}",
        bg="#15213A",
        fg=category_colors.get(post["category"], "#5BC8E8"),
        font=("Segoe UI", 8, "bold"),
        cursor="hand2"
    ).pack(side="left")

    tk.Label(
        meta_row,
        text=f"   🤖 {post['confidence']}%",
        bg="#15213A",
        fg="#5BC8E8",
        font=("Segoe UI", 8, "bold"),
        cursor="hand2"
    ).pack(side="left")

    tk.Label(
        row,
        text=f"🕒 {post['time']}",
        bg="#15213A",
        fg="#8FA6C9",
        font=("Segoe UI", 8),
        cursor="hand2"
    ).pack(side="right", padx=(10, 4))

    for widget in (row, badge, text_block, text_label, meta_row):
        widget.bind("<Button-1>", lambda e, p=post: open_detail_popup(p))


def display(username, time_, text, risk, category, confidence, reasoning):
    global high_count, medium_count, low_count, total_posts, post_counter

    analyzing_row, spin_state = show_analyzing_row()

    def finalize():
        global high_count, medium_count, low_count, total_posts, post_counter

        spin_state["active"] = False

        try:
            analyzing_row.destroy()
        except tk.TclError:
            pass

        total_posts += 1

        if risk == "High":
            high_count += 1
        elif risk == "Medium":
            medium_count += 1
        else:
            low_count += 1

        if category in category_counts:
            category_counts[category] += 1

        update_dashboard()

        post_counter += 1

        post = {
            "id": f"post_{post_counter}",
            "username": username,
            "time": time_,
            "text": text,
            "risk": risk,
            "category": category,
            "confidence": confidence,
            "reasoning": reasoning
        }

        post_registry[post["id"]] = post

        if risk != "Low":
            add_feed_row(post)
        elif len(feed_frame.winfo_children()) == 0:
            show_empty_feed_message()

    window.after(900, finalize)


# =========================
# REPORT
# =========================
def generate_report():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    filename = os.path.join(
        base_dir,
        f"X_Hunter_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )

    logo_path = os.path.join(base_dir, "logo.png")

    temp_dir = tempfile.gettempdir()
    bar_chart_path = os.path.join(temp_dir, "risk_bar_chart.png")
    pie_chart_path = os.path.join(temp_dir, "category_pie_chart.png")

    bar_fig.savefig(bar_chart_path, facecolor="#15213A", bbox_inches="tight")
    pie_fig.savefig(pie_chart_path, facecolor="#15213A", bbox_inches="tight")

    pdf = pdf_canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    y = height - 60

    if os.path.exists(logo_path):
        pdf.drawImage(
            ImageReader(logo_path),
            45,
            height - 120,
            width=70,
            height=70,
            preserveAspectRatio=True,
            mask="auto"
        )
        title_x = 130
    else:
        title_x = 50

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(title_x, y, "X Hunter Risk Intelligence Report")

    y -= 30
    pdf.setFont("Helvetica", 11)
    pdf.drawString(title_x, y, f"Generated Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 18
    pdf.drawString(title_x, y, "Platform: X / Twitter")
    y -= 18
    pdf.drawString(title_x, y, "System: AI-Powered Risk Intelligence Platform")

    y -= 45
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Dashboard Statistics")

    y -= 25
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Total Posts Analyzed: {total_posts}")
    y -= 18
    pdf.drawString(50, y, f"High Risks: {high_count}")
    y -= 18
    pdf.drawString(50, y, f"Medium Risks: {medium_count}")
    y -= 18
    pdf.drawString(50, y, f"Low Risks: {low_count}")

    y -= 40
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Risk Level Chart")

    y -= 210
    pdf.drawImage(ImageReader(bar_chart_path), 50, y, width=480, height=190)

    y -= 40
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Threat Categories Chart")

    y -= 210
    pdf.drawImage(ImageReader(pie_chart_path), 50, y, width=480, height=190)

    pdf.showPage()

    y = height - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Threat Categories Summary")

    y -= 40
    pdf.setFont("Helvetica", 11)

    category_labels_en = {
        "تهديدات أمنية": "Security Threats",
        "تهديدات السلامة العامة": "Public Safety Threats",
        "إشاعات ومعلومات مضللة": "Misinformation & Fake News",
        "مخاطر السمعة التجارية": "Brand Reputation Risks",
        "مخاطر سياسية واجتماعية": "Political & Social Risks",
        "تهديدات سيبرانية": "Cybersecurity Threats"
    }

    for category, count in category_counts.items():
        label = category_labels_en.get(category, category)
        pdf.drawString(50, y, f"{label}: {count}")
        y -= 22

    y -= 25
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Executive Summary")

    y -= 25
    pdf.setFont("Helvetica", 10)

    summary_lines = [
        "This report summarizes risks detected from X posts using AI analysis.",
        "The system classifies posts based on risk level and threat category.",
        "The dashboard supports real-time monitoring and decision-making.",
        "High and medium risks should be reviewed by analysts."
    ]

    for line in summary_lines:
        pdf.drawString(50, y, line)
        y -= 18

    pdf.save()

    status_label.config(text=tr("saved"), fg="#3E8E6E")
    print("Saved to:", filename)

    if os.name == "posix":
        os.system(f'open "{filename}"')


# =========================
# CLEAR DASHBOARD
# =========================
def clear_dashboard():
    global high_count, medium_count, low_count, total_posts, category_counts
    global seen_ids, post_registry, post_counter, feed_empty_label

    high_count = 0
    medium_count = 0
    low_count = 0
    total_posts = 0

    seen_ids = set()
    post_registry = {}
    post_counter = 0

    category_counts = {
        "تهديدات أمنية": 0,
        "تهديدات السلامة العامة": 0,
        "إشاعات ومعلومات مضللة": 0,
        "مخاطر السمعة التجارية": 0,
        "مخاطر سياسية واجتماعية": 0,
        "تهديدات سيبرانية": 0
    }

    for widget in feed_frame.winfo_children():
        widget.destroy()

    feed_empty_label = None
    show_empty_feed_message()

    update_dashboard()
    status_label.config(text=tr("stopped"), fg="#B33A3A")


# =========================
# MONITOR
# =========================
def process_tweets_batch(saudi_only=False):
    tweets, users = get_tweets(saudi_only=saudi_only)

    for tweet in tweets:
        if tweet["id"] in seen_ids:
            continue

        seen_ids.add(tweet["id"])

        text = tweet["text"]
        risk, category, confidence, reasoning = analyze(text)

        username = users.get(tweet.get("author_id"), "unknown")
        time_ = tweet.get("created_at", datetime.now(timezone.utc).isoformat())

        window.after(
            0,
            display,
            username,
            time_,
            text,
            risk,
            category,
            confidence,
            reasoning
        )


def monitor():
    global running

    while running:
        process_tweets_batch(saudi_only=False)
        time.sleep(20)


def extract_saudi_posts():
    status_label.config(text=tr("extracting_saudi"), fg="#5BC8E8")
    threading.Thread(target=lambda: process_tweets_batch(saudi_only=True), daemon=True).start()

# =========================
# START / STOP
# =========================
def start():
    global running

    if not running:
        running = True
        status_label.config(text=tr("active"), fg="#3E8E6E")
        threading.Thread(target=monitor, daemon=True).start()


def stop():
    global running

    running = False
    status_label.config(text=tr("stopped"), fg="#B33A3A")


# =========================
# WINDOW
# =========================
window = tk.Tk()
window.title("X Hunter")
window.geometry("1250x950")
window.configure(bg="#0B1220")


# =========================
# HEADER
# =========================
header = tk.Frame(window, bg="#0B1220", height=95)
header.pack(fill="x")
header.pack_propagate(False)

base_dir = os.path.dirname(os.path.abspath(__file__))


def load_logo_with_transparent_background(path, size):
    img = Image.open(path).convert("RGBA")
    img.thumbnail(size)

    pixels = img.getdata()
    new_pixels = []
    threshold = 235

    for r, g, b, a in pixels:
        if r >= threshold and g >= threshold and b >= threshold:
            new_pixels.append((r, g, b, 0))
        else:
            new_pixels.append((r, g, b, a))

    img.putdata(new_pixels)
    return img


logo_path = os.path.join(base_dir, "logo.png")

if os.path.exists(logo_path):
    logo_image = load_logo_with_transparent_background(logo_path, (58, 58))
    logo_photo = ImageTk.PhotoImage(logo_image)

    logo_label = tk.Label(header, image=logo_photo, bg="#0B1220")
    logo_label.image = logo_photo
    logo_label.pack(side="left", padx=(20, 12), pady=10)
else:
    tk.Label(
        header,
        text="🛡️",
        bg="#0B1220",
        fg="#5BC8E8",
        font=("Segoe UI Emoji", 26)
    ).pack(side="left", padx=(20, 12), pady=15)

title_frame = tk.Frame(header, bg="#0B1220")
title_frame.pack(side="left", pady=22)

tk.Label(
    title_frame,
    text="X HUNTER",
    bg="#0B1220",
    fg="#5BC8E8",
    font=("Segoe UI", 19, "bold")
).pack(anchor="w")

subtitle_label = tk.Label(
    title_frame,
    text=tr("subtitle"),
    bg="#0B1220",
    fg="#8FA6C9",
    font=("Segoe UI", 10)
)
subtitle_label.pack(anchor="w")
widget_refs["subtitle"] = subtitle_label


# =========================
# HEADER PILLS
# =========================
pills_frame = tk.Frame(header, bg="#0B1220")
pills_frame.pack(side="right", padx=20, pady=18)

def create_pill(parent, icon, icon_color, label, value, value_color, caption_key=None):
    pill = tk.Frame(parent, bg="#15213A", bd=1, relief="solid", padx=14, pady=8)
    pill.pack(side="left", padx=6)

    row = tk.Frame(pill, bg="#15213A")
    row.pack(anchor="w")

    tk.Label(
        row,
        text=icon,
        bg="#15213A",
        fg=icon_color,
        font=("Segoe UI", 10, "bold")
    ).pack(side="left")

    caption_label = tk.Label(
        row,
        text=label,
        bg="#15213A",
        fg="#8FA6C9",
        font=("Segoe UI", 8, "bold")
    )
    caption_label.pack(side="left", padx=(4, 0))
    if caption_key:
        widget_refs[caption_key] = caption_label

    value_label = tk.Label(
        pill,
        text=value,
        bg="#15213A",
        fg=value_color,
        font=("Segoe UI", 11, "bold")
    )
    value_label.pack(anchor="w")

    return value_label


status_label = create_pill(pills_frame, "●", "#3E8E6E", tr("status_label"), tr("stopped"), "#B33A3A", "status_caption")
date_label = create_pill(pills_frame, "📅", "#8FA6C9", tr("date_label"), datetime.now().strftime("%Y-%m-%d"), "white", "date_caption")
time_label = create_pill(pills_frame, "🕒", "#8FA6C9", tr("time_label"), datetime.now().strftime("%H:%M:%S"), "white", "time_caption")


def update_clock():
    date_label.config(text=datetime.now().strftime("%Y-%m-%d"))
    time_label.config(text=datetime.now().strftime("%H:%M:%S"))
    window.after(1000, update_clock)


# =========================
# KPI CARDS
# =========================
cards_frame = tk.Frame(window, bg="#0B1220")
cards_frame.pack(fill="x", padx=20, pady=10)


def create_card(parent, icon, icon_color, title, subtitle, title_key=None, subtitle_key=None):
    card = tk.Frame(parent, bg="#15213A", bd=1, relief="solid", width=280, height=95)
    card.pack(side="left", padx=8)
    card.pack_propagate(False)

    top_row = tk.Frame(card, bg="#15213A")
    top_row.pack(anchor="w", padx=14, pady=(12, 0), fill="x")

    tk.Label(
        top_row,
        text=icon,
        bg=icon_color,
        fg="white",
        font=("Segoe UI", 12, "bold"),
        width=2,
        height=1
    ).pack(side="left")

    title_label = tk.Label(
        top_row,
        text=title,
        bg="#15213A",
        fg="#8FA6C9",
        font=("Segoe UI", 9, "bold")
    )
    title_label.pack(side="left", padx=(10, 0))
    if title_key:
        widget_refs[title_key] = title_label

    value_label = tk.Label(
        card,
        text="0",
        bg="#15213A",
        fg="white",
        font=("Segoe UI", 24, "bold")
    )
    value_label.pack(anchor="w", padx=14, pady=(4, 0))

    subtitle_label = tk.Label(
        card,
        text=subtitle,
        bg="#15213A",
        fg="#8FA6C9",
        font=("Segoe UI", 8)
    )
    subtitle_label.pack(anchor="w", padx=14)
    if subtitle_key:
        widget_refs[subtitle_key] = subtitle_label

    return value_label


total_label = create_card(cards_frame, "📊", "#5BC8E8", tr("total_title"), tr("total_subtitle"), "total_title", "total_subtitle")
high_label = create_card(cards_frame, "🚨", "#B33A3A", tr("high_title"), tr("risk_subtitle"), "high_title", "high_subtitle")
medium_label = create_card(cards_frame, "⚠️", "#C9892F", tr("medium_title"), tr("risk_subtitle"), "medium_title", "medium_subtitle")
low_label = create_card(cards_frame, "✅", "#3E8E6E", tr("low_title"), tr("risk_subtitle"), "low_title", "low_subtitle")


# =========================
# MAIN CONTENT
# =========================
main_frame = tk.Frame(window, bg="#0B1220")
main_frame.pack(fill="both", expand=True, padx=20)


# =========================
# CHARTS
# =========================
charts_frame = tk.Frame(main_frame, bg="#0B1220")
charts_frame.pack(fill="x", pady=8)

bar_frame = tk.Frame(charts_frame, bg="#15213A", bd=1, relief="solid")
bar_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

bar_header_label = tk.Label(
    bar_frame,
    text=tr("bar_header"),
    bg="#15213A",
    fg="#5BC8E8",
    font=("Segoe UI", 10, "bold")
)
bar_header_label.pack(anchor="w", padx=14, pady=(10, 0))
widget_refs["bar_header"] = bar_header_label

pie_frame = tk.Frame(charts_frame, bg="#15213A", bd=1, relief="solid")
pie_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))

pie_header_label = tk.Label(
    pie_frame,
    text=tr("pie_header"),
    bg="#15213A",
    fg="#5BC8E8",
    font=("Segoe UI", 10, "bold")
)
pie_header_label.pack(anchor="w", padx=14, pady=(10, 0))
widget_refs["pie_header"] = pie_header_label

bar_fig = Figure(figsize=(5.6, 2.1), dpi=100)
bar_ax = bar_fig.add_subplot(111)
bar_canvas = FigureCanvasTkAgg(bar_fig, master=bar_frame)
bar_canvas.get_tk_widget().pack(fill="both", expand=True)

pie_fig = Figure(figsize=(5.6, 2.1), dpi=100)
pie_ax = pie_fig.add_subplot(111)
pie_canvas = FigureCanvasTkAgg(pie_fig, master=pie_frame)
pie_canvas.get_tk_widget().pack(fill="both", expand=True)


# =========================
# LIVE FEED HEADER
# =========================
feed_header = tk.Frame(main_frame, bg="#0B1220")
feed_header.pack(fill="x", pady=(10, 6))

feed_header_label = tk.Label(
    feed_header,
    text=tr("feed_header"),
    bg="#0B1220",
    fg="#5BC8E8",
    font=("Segoe UI", 12, "bold")
)
feed_header_label.pack(side="left")
widget_refs["feed_header"] = feed_header_label

control_buttons = tk.Frame(feed_header, bg="#0B1220")
control_buttons.pack(side="right")

start_btn = tk.Button(
    control_buttons,
    text=tr("start"),
    command=start,
    bg="#3E8E6E",
    fg="green",
    activebackground="#4FA383",
    activeforeground="white",
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    cursor="hand2",
    padx=12,
    pady=4
)
start_btn.pack(side="left", padx=4)
widget_refs["start_btn"] = start_btn

stop_btn = tk.Button(
    control_buttons,
    text=tr("stop"),
    command=stop,
    bg="#B33A3A",
    fg="red",
    activebackground="#C24F4F",
    activeforeground="white",
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    cursor="hand2",
    padx=12,
    pady=4
)
stop_btn.pack(side="left", padx=4)
widget_refs["stop_btn"] = stop_btn

clear_btn = tk.Button(
    control_buttons,
    text=tr("clear"),
    command=clear_dashboard,
    bg="#2A3A55",
    fg="white",
    activebackground="#3D5A99",
    activeforeground="white",
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    cursor="hand2",
    padx=12,
    pady=4
)
clear_btn.pack(side="left", padx=4)
widget_refs["clear_btn"] = clear_btn


saudi_btn = tk.Button(
    control_buttons,
    text=tr("saudi_button"),
    command=extract_saudi_posts,
    bg="#5BC8E8",
    fg="#0B1220",
    activebackground="#8FD9F0",
    activeforeground="#0B1220",
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    cursor="hand2",
    padx=12,
    pady=4
)
saudi_btn.pack(side="left", padx=4)
widget_refs["saudi_btn"] = saudi_btn


lang_btn = tk.Button(
    control_buttons,
    text=tr("language_button"),
    command=toggle_language,
    bg="#3E8E6E",
    fg="black",
    activebackground="#4FA383",
    activeforeground="white",
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    cursor="hand2",
    padx=12,
    pady=4
)
lang_btn.pack(side="left", padx=4)
widget_refs["lang_btn"] = lang_btn

# =========================
# LIVE FEED LIST
# =========================
feed_card = tk.Frame(main_frame, bg="#15213A", bd=1, relief="solid")
feed_card.pack(fill="both", expand=True)

feed_container = tk.Frame(feed_card, bg="#15213A")
feed_container.pack(fill="both", expand=True, padx=4, pady=4)

canvas = tk.Canvas(feed_container, bg="#15213A", highlightthickness=0)
scrollbar = tk.Scrollbar(feed_container, orient="vertical", command=canvas.yview)

feed_frame = tk.Frame(canvas, bg="#15213A")

feed_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=feed_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

show_empty_feed_message()


# =========================
# PDF BUTTON
# =========================
pdf_button_frame = tk.Frame(window, bg="#0B1220")
pdf_button_frame.pack(fill="x", pady=14)

report_btn = tk.Button(
    pdf_button_frame,
    text=tr("report"),
    command=generate_report,
    bg="#0B1220",
    fg="#5BC8E8",
    activebackground="#15213A",
    activeforeground="#5BC8E8",
    font=("Segoe UI", 10, "bold"),
    relief="solid",
    bd=1,
    highlightbackground="#5BC8E8",
    cursor="hand2",
    padx=30,
    pady=8
)
report_btn.pack()
widget_refs["report_btn"] = report_btn


# =========================
# RUN
# =========================
update_dashboard()
update_clock()

window.mainloop()