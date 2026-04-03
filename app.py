import hashlib
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment, FeatureNotFound
from flask import Flask, render_template_string, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

# ---------------------------------------------------------------------------
# HTML шаблон
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""
<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Footprint Analyzer</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg:   #080c12;
  --s1:   #0d1117;
  --s2:   #111820;
  --bdr:  #1d2535;
  --txt:  #c9d4e8;
  --muted:#6b7d99;
  --acc:  #3b82f6;
  --grn:  #22c55e;
  --ylw:  #f59e0b;
  --red:  #ef4444;
  --mono: 'JetBrains Mono', monospace;
  --sans: 'Inter', sans-serif;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--txt); font-family: var(--sans); font-size: 15px; line-height: 1.65; }
a { color: var(--acc); text-decoration: none; }

.wrap    { max-width: 1480px; margin: 0 auto; padding: 28px 20px; }
.hero    { margin-bottom: 32px; }
.hero h1 { font-size: 30px; font-weight: 800; letter-spacing: -.4px; }
.hero p  { color: var(--muted); margin-top: 8px; font-size: 14px; }

.card  { background: var(--s1); border: 1px solid var(--bdr); border-radius: 16px; padding: 22px; margin-bottom: 18px; }
.g2    { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.g4    { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; }
@media(max-width:900px){ .g2,.g4{ grid-template-columns:1fr; } }

.field { margin-bottom: 14px; }
label  { display: block; font-weight: 700; color: var(--muted); font-size: 12px; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 8px; }
input[type="url"], input[type="file"] {
  width: 100%; padding: 12px 14px; border-radius: 12px;
  border: 1px solid var(--bdr); background: var(--bg);
  color: var(--txt); font-family: var(--mono); font-size: 13px;
}
input[type="url"]:focus { outline: none; border-color: var(--acc); }

.btn {
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
  border: none; color: #fff;
  padding: 12px 24px; border-radius: 12px;
  font-family: var(--sans); font-weight: 700; font-size: 14px; cursor: pointer;
  transition: transform .15s ease, opacity .15s ease;
}
.btn:hover { transform: translateY(-1px); opacity: .96; }

.error {
  background: #2d0a0a; border: 1px solid #7f1d1d; color: #fca5a5;
  padding: 14px 16px; border-radius: 12px; margin-bottom: 18px;
  font-family: var(--mono); font-size: 13px;
}

.stat { background: var(--s2); border: 1px solid var(--bdr); border-radius: 14px; padding: 16px; }
.stat .lbl { font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.stat .val { font-size: 30px; font-weight: 800; margin-top: 4px; }
.c-red   { color: var(--red); }
.c-ylw   { color: var(--ylw); }
.c-grn   { color: var(--grn); }
.c-acc   { color: var(--acc); }
.c-txt   { color: var(--txt); }

.sec  { font-size: 19px; font-weight: 800; margin-bottom: 16px; }
.sub  { font-size: 14px; font-weight: 700; color: var(--muted); margin-bottom: 10px; }
.div  { height: 1px; background: var(--bdr); margin: 16px 0; }
.muted{ color: var(--muted); }

.chips { display: flex; flex-wrap: wrap; gap: 7px; }
.chip  {
  border-radius: 999px; padding: 5px 11px; font-size: 12px; font-family: var(--mono);
  border: 1px solid var(--bdr); background: var(--s2);
}
.chip-r { background: #2d0a0a; border-color: #7f1d1d; color: #fca5a5; }
.chip-y { background: #2d1a00; border-color: #92400e; color: #fcd34d; }
.chip-b { background: #0c1a3d; border-color: #1d4ed8; color: #93c5fd; }
.chip-g { background: #052e0c; border-color: #166534; color: #86efac; }

.issue { border-left: 3px solid var(--bdr); padding-left: 16px; margin-bottom: 24px; }
.issue.crit { border-left-color: var(--red); }
.issue.warn { border-left-color: var(--ylw); }
.issue.info { border-left-color: var(--acc); }
.issue.noise{ border-left-color: #374151; }

.badge {
  display: inline-block; font-size: 11px; font-weight: 700;
  padding: 3px 9px; border-radius: 999px; margin-bottom: 10px;
  text-transform: uppercase; letter-spacing: .06em;
}
.badge-r { background: #2d0a0a; color: var(--red); border: 1px solid #7f1d1d; }
.badge-y { background: #2d1a00; color: var(--ylw); border: 1px solid #92400e; }
.badge-b { background: #0c1a3d; color: #93c5fd; border: 1px solid #1d4ed8; }
.badge-g { background: #052e0c; color: var(--grn); border: 1px solid #166534; }

.paragraph { white-space: pre-wrap; line-height: 1.7; color: var(--txt); font-size: 14px; }
pre {
  white-space: pre-wrap; word-break: break-word;
  background: var(--bg); border: 1px solid var(--bdr);
  padding: 12px 14px; border-radius: 12px; overflow: auto;
  font-family: var(--mono); font-size: 12px; color: #94a3b8;
}
ul.steps { margin: 10px 0 0 18px; }
ul.steps li { margin-bottom: 7px; font-size: 14px; }

.bar-wrap { height: 6px; background: var(--bdr); border-radius: 999px; margin-top: 8px; overflow: hidden; }
.bar-fill  { height: 100%; border-radius: 999px; transition: width .4s; }
</style>
</head>
<body>
<div class="wrap">

  <div class="hero">
    <h1>Footprint Analyzer</h1>
    <p>Порівняння двох сайтів по HTML-відбитках: тема, JS, CSS, id, класи, форми, мета, посилання.</p>
  </div>

  {% if error %}<div class="error">⚠ {{ error }}</div>{% endif %}

  <form method="post" action="/" enctype="multipart/form-data" class="card">
    <div class="g2" style="margin-bottom:16px;">
      <div>
        <h2 style="margin-bottom:12px;">Сайт A</h2>
        <div class="field">
          <label>URL A</label>
          <input type="url" name="url_a" placeholder="https://site-a.com" value="{{ form.url_a }}">
        </div>
        <div class="field">
          <label>або HTML файл A</label>
          <input type="file" name="file_a" accept=".html,.htm,.txt">
        </div>
      </div>
      <div>
        <h2 style="margin-bottom:12px;">Сайт B</h2>
        <div class="field">
          <label>URL B</label>
          <input type="url" name="url_b" placeholder="https://site-b.com" value="{{ form.url_b }}">
        </div>
        <div class="field">
          <label>або HTML файл B</label>
          <input type="file" name="file_b" accept=".html,.htm,.txt">
        </div>
      </div>
    </div>
    <button class="btn" type="submit">▶ Запустити аналіз</button>
  </form>

  {% if result %}

  <div class="card">
    <div class="sec">Підсумок</div>
    <div class="g4">
      <div class="stat">
        <div class="lbl">Загальна схожість</div>
        <div class="val {% if result.similarity >= 60 %}c-red{% elif result.similarity >= 35 %}c-ylw{% else %}c-grn{% endif %}">
          {{ result.similarity }}%
        </div>
        <div class="bar-wrap">
          <div class="bar-fill" style="width:{{ result.similarity }}%;
            background:{% if result.similarity >= 60 %}var(--red){% elif result.similarity >= 35 %}var(--ylw){% else %}var(--grn){% endif %};"></div>
        </div>
      </div>
      <div class="stat">
        <div class="lbl">Ризик шаблону</div>
        <div class="val {% if result.template_risk >= 60 %}c-red{% elif result.template_risk >= 30 %}c-ylw{% else %}c-grn{% endif %}">
          {{ result.template_risk }}%
        </div>
        <div class="bar-wrap">
          <div class="bar-fill" style="width:{{ result.template_risk }}%;
            background:{% if result.template_risk >= 60 %}var(--red){% elif result.template_risk >= 30 %}var(--ylw){% else %}var(--grn){% endif %};"></div>
        </div>
      </div>
      <div class="stat">
        <div class="lbl">Реальних проблем</div>
        <div class="val {% if result.real_issue_count >= 3 %}c-red{% elif result.real_issue_count >= 1 %}c-ylw{% else %}c-grn{% endif %}">
          {{ result.real_issue_count }}
        </div>
      </div>
      <div class="stat">
        <div class="lbl">Шум / типовий WP</div>
        <div class="val c-txt">{{ result.noise_count }}</div>
      </div>
    </div>
  </div>

  <div class="g2">
    <div class="card"><div class="sub">Джерело A</div><div class="muted" style="font-family:var(--mono);font-size:13px;">{{ result.label_a }}</div></div>
    <div class="card"><div class="sub">Джерело B</div><div class="muted" style="font-family:var(--mono);font-size:13px;">{{ result.label_b }}</div></div>
  </div>

  <div class="card">
    <div class="sec">Висновок</div>
    <div class="paragraph">{{ result.human_summary }}</div>
  </div>

  <div class="g2">
    <div class="card">
      <div class="sec">Що реально палиться</div>
      {% if result.real_issues %}
        {% for iss in result.real_issues %}
        <div class="issue {{ iss.css_class }}">
          <div class="sub">{{ iss.title }}</div>
          <span class="badge {{ iss.badge_class }}">{{ iss.level }}</span>
          <div class="paragraph" style="margin-bottom:10px;">{{ iss.explanation }}</div>
          {% if iss.matches %}
          <div class="chips" style="margin-bottom:12px;">
            {% for m in iss.matches %}<span class="chip chip-r">{{ m }}</span>{% endfor %}
          </div>
          {% endif %}
          {% if iss.preview_a or iss.preview_b %}
          <div class="g2" style="margin-bottom:12px;">
            {% if iss.preview_a %}<div><div class="sub">Фрагмент A</div><pre>{{ iss.preview_a }}</pre></div>{% endif %}
            {% if iss.preview_b %}<div><div class="sub">Фрагмент B</div><pre>{{ iss.preview_b }}</pre></div>{% endif %}
          </div>
          {% endif %}
          {% if iss.steps %}
          <div class="div"></div>
          <div class="sub">Що робити</div>
          <ul class="steps">{% for s in iss.steps %}<li>{{ s }}</li>{% endfor %}</ul>
          {% endif %}
        </div>
        {% endfor %}
      {% else %}
        <div class="muted">Сильних кастомних збігів не знайдено.</div>
      {% endif %}
    </div>

    <div class="card">
      <div class="sec">Шум — можна ігнорувати</div>
      {% if result.noise_issues %}
        {% for iss in result.noise_issues %}
        <div class="issue noise">
          <div class="sub">{{ iss.title }}</div>
          <span class="badge badge-b">{{ iss.level }}</span>
          <div class="paragraph" style="margin-bottom:10px;">{{ iss.explanation }}</div>
          {% if iss.matches %}
          <div class="chips">
            {% for m in iss.matches %}<span class="chip chip-b">{{ m }}</span>{% endfor %}
          </div>
          {% endif %}
        </div>
        {% endfor %}
      {% else %}
        <div class="muted">Шумових збігів майже немає.</div>
      {% endif %}
    </div>
  </div>

  <div class="g2">
    <div class="card">
      <div class="sec">Порядок виправлень</div>
      <ul class="steps">{% for item in result.fix_priority %}<li>{{ item }}</li>{% endfor %}</ul>
    </div>
    <div class="card">
      <div class="sec">Найважливіші збіги</div>
      <ul class="steps">{% for item in result.top_matches %}<li>{{ item }}</li>{% endfor %}</ul>
    </div>
  </div>

  <div class="card">
    <div class="sec">Сирий зріз відбитків</div>
    <div class="g2">
      <div><div class="sub">A</div><pre>{{ result.short_a }}</pre></div>
      <div><div class="sub">B</div><pre>{{ result.short_b }}</pre></div>
    </div>
  </div>

  {% endif %}
</div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Фільтри шуму
# ---------------------------------------------------------------------------

NOISE_ID_PATTERNS = [
    "wp-", "global-styles", "classic-theme-styles", "emoji", "jet-",
    "cookie", "cky-", "fast-vid", "menu-item-", "cn-", "wp-block-library",
    "wpadminbar", "respond", "yoast", "schema"
]

NOISE_COMMENTS = [
    "yoast seo", "this site is optimized with the yoast seo plugin",
    "schema.org", "begin: cookieyes", "end: cookieyes",
]

NOISE_META_PREFIXES = [
    "og:type=website",
    "twitter:card=summary_large_image",
    "robots=index, follow",
    "robots=index,follow",
    "author=wordpress",
]

NOISE_CLASS_EXACT = {
    "container", "row", "col", "active", "open", "show", "hidden", "visible",
    "wrapper", "content", "section", "title", "subtitle", "text", "btn", "button",
    "image", "icon", "menu", "nav", "navbar", "header", "footer", "main",
    "left", "right", "top", "bottom", "grid", "flex", "block", "inline",
    "center", "card", "item", "items", "link", "links", "list", "form",
    "input", "label", "field", "fields", "faq", "page", "site", "inner",
    "outer", "entry", "widget", "sidebar", "overlay", "modal", "popup",
    "close", "open", "logo", "search", "toggle", "wrap", "box",
    "current-menu-item", "current_page_item", "page_item", "menu-item",
    "menu-item-home", "menu-item-object-page", "menu-item-type-post_type",
    "page-template", "page", "home", "wp-singular", "new-header",
    "yoast-schema-graph"
}

NOISE_CLASS_PATTERNS = [
    "wp-", "elementor", "jet-", "swiper-", "slick-", "owl-",
    "fa-", "fas ", "far ", "fab ", "fi-",
    "col-", "row-", "container-", "grid-", "flex-",
    "justify-", "items-", "text-", "bg-", "border-", "rounded-",
    "mt-", "mb-", "ml-", "mr-", "mx-", "my-",
    "pt-", "pb-", "pl-", "pr-", "px-", "py-",
    "w-", "h-", "min-", "max-",
    "lg:", "md:", "sm:", "xl:", "2xl:", "3xl:",
    "rtl", "ltr", "sr-only", "screen-reader",
    "woocommerce", "cky-", "cookie", "cn-",
    "vc_", "wpb_", "fusion-", "avada-",
    "menu-item-", "page-id-", "page-item-", "page-template-",
]

NOISE_PLUGIN_CLASSES = {
    "menu-items-left", "logo", "header", "content"
}

# ---------------------------------------------------------------------------
# Утиліти
# ---------------------------------------------------------------------------

def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())

def normalize_urlish(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    p = urlparse(value)
    if p.scheme and p.netloc:
        return "%s%s" % (p.netloc.lower(), p.path.rstrip("/") or "/")
    return value.lower()

def short_hash(text: str) -> str:
    text = normalize_text(text)
    if not text:
        return ""
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:14]

def safe_preview(text: str, size: int = 650) -> str:
    text = normalize_text(text)
    if len(text) > size:
        return text[:size] + " …"
    return text

def safe_set(value) -> set:
    if value is None:
        return set()
    if isinstance(value, set):
        return value
    if isinstance(value, (list, tuple)):
        return set(value)
    return {str(value)}

def is_noise_id(value: str) -> bool:
    v = value.lower()
    return any(x in v for x in NOISE_ID_PATTERNS)

def is_noise_comment(value: str) -> bool:
    v = value.lower()
    return any(x in v for x in NOISE_COMMENTS)

def is_noise_meta(value: str) -> bool:
    v = value.lower().strip()
    if any(v.startswith(x) for x in NOISE_META_PREFIXES):
        return True
    if v.startswith("generator=wordpress"):
        return True
    return False

def is_noise_class(value: str) -> bool:
    v = value.lower().strip()
    if not v or len(v) <= 2:
        return True
    if v in NOISE_CLASS_EXACT:
        return True
    if v in NOISE_PLUGIN_CLASSES:
        return True
    if re.fullmatch(r"[a-z]-\d+", v):
        return True
    return any(p in v for p in NOISE_CLASS_PATTERNS)

def make_soup(html: str):
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")
    except Exception:
        return BeautifulSoup(html, "html.parser")

def _is_wp_core_inline_css(key, data):
    preview = data["inline_css_map"].get(key, "")[:700].lower()
    wp_markers = [
        "wp--preset",
        "wp--style",
        "wp-img-auto-sizes-contain-inline-css",
        "contain-intrinsic-size",
        "img:is([sizes=auto i]",
        "global-styles-inline-css",
        "classic-theme-styles-inline-css",
    ]
    return any(marker in preview for marker in wp_markers)

def _is_wp_core_inline_js(key, data):
    preview = data["inline_js_map"].get(key, "")[:1200].lower()
    js_markers = [
        "wp-emoji-settings",
        "window._wpemojisettings",
        "this file is auto-generated",
        "supporttests",
        "sessionstorage.setitem",
        "wpemoji",
    ]
    return any(marker in preview for marker in js_markers)

def _has_theme_match(fp_a: dict, fp_b: dict) -> bool:
    return bool((fp_a["direct_theme"] & fp_b["direct_theme"]) or (fp_a["theme_assets"] & fp_b["theme_assets"]))

# ---------------------------------------------------------------------------
# Читання вводу
# ---------------------------------------------------------------------------

def read_uploaded_file(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None
    raw = file_storage.read()
    return raw.decode("utf-8", errors="ignore"), file_storage.filename

def _detect_charset(raw: bytes) -> str:
    m = re.search(rb'charset=["\']?([a-zA-Z0-9_\-]+)', raw[:4096])
    return m.group(1).decode("ascii", errors="ignore") if m else "utf-8"

def fetch_url(url: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "uk,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = requests.get(url, timeout=30, headers=headers, allow_redirects=True)
    resp.raise_for_status()
    if resp.encoding and resp.encoding.lower() in ("iso-8859-1", "latin-1"):
        detected = _detect_charset(resp.content)
        resp.encoding = detected or "utf-8"
    resp.encoding = resp.encoding or "utf-8"
    return resp.text, resp.url

def get_input_side(url_value: str, file_storage, side_name: str):
    if (url_value or "").strip():
        html_text, final_url = fetch_url(url_value.strip())
        return html_text, "%s: %s" % (side_name, final_url), final_url
    file_text, filename = read_uploaded_file(file_storage)
    if file_text:
        return file_text, "%s: %s" % (side_name, filename), None
    raise ValueError("Для %s потрібно вказати URL або завантажити HTML файл." % side_name)

# ---------------------------------------------------------------------------
# Екстрактори
# ---------------------------------------------------------------------------

def extract_ids(soup) -> set:
    out = set()
    for tag in soup.find_all(True):
        v = tag.get("id")
        if v:
            out.add(normalize_text(v).lower())
    return out

def extract_classes(soup) -> set:
    out = set()
    for tag in soup.find_all(True):
        for c in tag.get("class", []):
            c = normalize_text(c).lower()
            if c:
                out.add(c)
    return out

def extract_theme_hints(html: str, soup):
    direct_theme = set()
    theme_assets = set()
    plugin_comments = set()
    cms_generators = set()

    low = html.lower()

    for m in re.findall(r"/wp-content/themes/([a-z0-9_\-]+)/", low):
        direct_theme.add("wp-theme:%s" % m)

    for m in re.finditer(r"/wp-content/plugins/([a-z0-9_\-]+)/", low):
        cms_generators.add("wp-plugin:%s" % m.group(1))

    generator = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
    if generator and generator.get("content"):
        content = normalize_text(generator.get("content"))
        low_c = content.lower()
        if "wordpress" in low_c:
            cms_generators.add("generator:%s" % content)
        elif content:
            direct_theme.add("generator:%s" % content)

    for tag in soup.find_all(["script", "link"]):
        src = (tag.get("src") or tag.get("href") or "").lower()
        if "/themes/" in src and src.startswith("http"):
            theme_assets.add("asset:%s" % normalize_urlish(src))

    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        text = normalize_text(str(c))
        if text:
            plugin_comments.add(text[:160])

    return {
        "direct_theme": direct_theme,
        "theme_assets": theme_assets,
        "plugin_comments": plugin_comments,
        "cms_generators": cms_generators,
    }

def extract_important_meta(soup) -> set:
    out = set()
    allowed = {
        "description", "og:site_name", "twitter:card",
        "robots", "theme-color", "og:type", "author",
    }
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or meta.get("http-equiv") or "").strip().lower()
        content = normalize_text(meta.get("content") or "")
        if name and content and name in allowed:
            out.add("%s=%s" % (name, safe_preview(content, 120)))
    return out

def extract_comments(html: str) -> set:
    out = set()
    for m in re.findall(r"<!--(.*?)-->", html, flags=re.S):
        text = normalize_text(m)
        if text and len(text) > 4:
            out.add(safe_preview(text, 160))
    return out

def extract_forms(soup):
    forms = set()
    signatures = set()
    for form in soup.find_all("form"):
        action = normalize_urlish(form.get("action") or "[empty]")
        method = (form.get("method") or "get").lower()
        types = sorted({
            (inp.get("type") or inp.name or "input").lower()
            for inp in form.find_all(["input", "textarea", "select", "button"])
        })
        names = sorted({
            inp.get("name", "").lower()
            for inp in form.find_all(["input", "textarea", "select"])
            if inp.get("name")
        })
        forms.add("%s %s :: %s" % (method, action, ",".join(types)))
        if names:
            signatures.add("fields:%s" % ",".join(names[:30]))
    return forms, signatures

def extract_internal_paths(soup, base_url=None) -> set:
    out = set()
    base_netloc = urlparse(base_url).netloc.lower() if base_url else ""
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full = urljoin(base_url, href) if base_url else href
        p = urlparse(full)
        if base_netloc and p.netloc and p.netloc.lower() != base_netloc:
            continue
        if p.path:
            out.add(p.path.rstrip("/") or "/")
    return out

def extract_asset_domains(soup, base_url=None) -> set:
    out = set()
    base_netloc = urlparse(base_url).netloc.lower() if base_url else ""
    for tag in soup.find_all(["script", "link", "img", "iframe"]):
        src = tag.get("src") or tag.get("href")
        if not src:
            continue
        full = urljoin(base_url, src) if base_url else src
        p = urlparse(full)
        if p.netloc and p.netloc.lower() != base_netloc:
            out.add(p.netloc.lower())
    return out

def extract_inline_blocks(soup, kind: str) -> dict:
    mapping = {}
    tag_name = "script" if kind == "js" else "style"
    for tag in soup.find_all(tag_name):
        if tag.get("src"):
            continue
        text = normalize_text(tag.get_text(" ", strip=True))
        if len(text) < 40:
            continue
        h = short_hash(text[:2000])
        key = "inline-%s:%s" % (kind, h)
        if key not in mapping:
            mapping[key] = safe_preview(text, 700)
    return mapping

def extract_dom_patterns(soup) -> set:
    tags = Counter(tag.name.lower() for tag in soup.find_all(True))
    return {"%s:%s" % (k, v) for k, v in tags.most_common(25)}

def extract_schema_types(html: str) -> set:
    out = set()
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                t = data.get("@type")
                if t:
                    out.add(str(t))
            elif isinstance(data, list):
                for item in data:
                    t = (item or {}).get("@type")
                    if t:
                        out.add(str(t))
        except Exception:
            pass
    return out

def extract_og_image_paths(html: str) -> set:
    out = set()
    for m in re.findall(r'og:image.*?content=["\']([^"\']+)', html, re.I):
        p = urlparse(m)
        if p.path:
            out.add(p.path)
    return out

# ---------------------------------------------------------------------------
# Головний екстрактор відбитків
# ---------------------------------------------------------------------------

def extract_fingerprints(html: str, label: str, base_url=None) -> dict:
    soup = make_soup(html)
    forms, form_signatures = extract_forms(soup)
    inline_js_map = extract_inline_blocks(soup, "js")
    inline_css_map = extract_inline_blocks(soup, "css")
    theme_data = extract_theme_hints(html, soup)

    fp = {
        "direct_theme": theme_data["direct_theme"],
        "theme_assets": theme_data["theme_assets"],
        "plugin_comments": theme_data["plugin_comments"],
        "cms_generators": theme_data["cms_generators"],
        "important_meta": extract_important_meta(soup),
        "comments": extract_comments(html),
        "ids": extract_ids(soup),
        "classes": extract_classes(soup),
        "forms": forms,
        "form_signatures": form_signatures,
        "internal_paths": extract_internal_paths(soup, base_url),
        "asset_domains": extract_asset_domains(soup, base_url),
        "inline_scripts": set(inline_js_map.keys()),
        "inline_styles": set(inline_css_map.keys()),
        "dom_patterns": extract_dom_patterns(soup),
        "schema_types": extract_schema_types(html),
        "og_image_paths": extract_og_image_paths(html),
        "inline_css_map": inline_css_map,
        "inline_js_map": inline_js_map,
    }

    short_summary = {
        "direct_theme": sorted(fp["direct_theme"])[:10],
        "theme_assets": sorted(fp["theme_assets"])[:10],
        "cms_generators": sorted(fp["cms_generators"])[:10],
        "plugin_comments": sorted(fp["plugin_comments"])[:8],
        "important_meta": sorted(fp["important_meta"])[:10],
        "schema_types": sorted(fp["schema_types"])[:10],
        "ids": sorted(fp["ids"])[:20],
        "classes": sorted(fp["classes"])[:30],
        "form_signatures": sorted(fp["form_signatures"])[:10],
        "asset_domains": sorted(fp["asset_domains"])[:10],
    }

    return {
        "label": label,
        "fingerprints": fp,
        "inline_js_map": inline_js_map,
        "inline_css_map": inline_css_map,
        "short_summary": json.dumps(short_summary, ensure_ascii=False, indent=2),
    }

# ---------------------------------------------------------------------------
# Скоринг
# ---------------------------------------------------------------------------

def similarity_score(fp_a: dict, fp_b: dict) -> int:
    weights = {
        "direct_theme": 10,
        "theme_assets": 7,
        "inline_scripts": 2,
        "inline_styles": 3,
        "important_meta": 2,
        "form_signatures": 5,
        "ids": 2,
        "classes": 1,
        "comments": 3,
        "asset_domains": 1,
        "internal_paths": 1,
        "dom_patterns": 1,
        "schema_types": 1,
        "og_image_paths": 3,
    }
    inter = union = 0
    for key, w in weights.items():
        a = safe_set(fp_a.get(key))
        b = safe_set(fp_b.get(key))
        inter += len(a & b) * w
        union += len(a | b) * w
    if union == 0:
        return 0
    return int(round((inter / float(union)) * 100))

def template_risk(fp_a: dict, fp_b: dict) -> int:
    score = 0

    if fp_a["direct_theme"] & fp_b["direct_theme"]:
        score += 40
    if fp_a["theme_assets"] & fp_b["theme_assets"]:
        score += 20

    common_js = fp_a["inline_scripts"] & fp_b["inline_scripts"]
    custom_js = [k for k in common_js if not _is_wp_core_inline_js(k, {"inline_js_map": fp_a.get("inline_js_map", {})})]
    if custom_js:
        score += 15

    common_css = fp_a["inline_styles"] & fp_b["inline_styles"]
    custom_css = [k for k in common_css if not _is_wp_core_inline_css(k, {"inline_css_map": fp_a.get("inline_css_map", {})})]
    if custom_css:
        score += 10

    if fp_a["form_signatures"] & fp_b["form_signatures"]:
        score += 10
    if fp_a["og_image_paths"] & fp_b["og_image_paths"]:
        score += 10

    custom_ids = [x for x in (fp_a["ids"] & fp_b["ids"]) if not is_noise_id(x)]
    if len(custom_ids) >= 3:
        score += 5

    custom_classes = [x for x in (fp_a["classes"] & fp_b["classes"]) if not is_noise_class(x)]
    if len(custom_classes) >= 8:
        score += 5

    real_comments = [x for x in (fp_a["comments"] & fp_b["comments"]) if not is_noise_comment(x)]
    if len(real_comments) >= 2:
        score += 5

    return min(score, 100)

# ---------------------------------------------------------------------------
# Будування issue-об'єктів
# ---------------------------------------------------------------------------

_LEVEL_CSS = {
    "Критично": ("crit", "badge-r"),
    "Увага": ("warn", "badge-y"),
    "Низький ризик": ("info", "badge-b"),
}

def make_issue(title: str, level: str, explanation: str,
               matches: list, steps: list,
               preview_a: str = "", preview_b: str = "") -> dict:
    css_class, badge_class = _LEVEL_CSS.get(level, ("info", "badge-b"))
    return {
        "title": title,
        "level": level,
        "css_class": css_class,
        "badge_class": badge_class,
        "explanation": explanation,
        "matches": matches,
        "steps": steps,
        "preview_a": preview_a,
        "preview_b": preview_b,
    }

# ---------------------------------------------------------------------------
# Формування real / noise issues
# ---------------------------------------------------------------------------

def build_issues(a_data: dict, b_data: dict):
    fp_a = a_data["fingerprints"]
    fp_b = b_data["fingerprints"]
    real = []
    noise = []

    common_theme = sorted(fp_a["direct_theme"] & fp_b["direct_theme"])
    common_assets = sorted(fp_a["theme_assets"] & fp_b["theme_assets"])
    if common_theme or common_assets:
        real.append(make_issue(
            "Однакова тема або theme-assets",
            "Критично",
            "Прямий збіг назви WordPress-теми або публічних шляхів до її файлів. Це найсильніший сигнал спільного шаблону.",
            (common_theme + common_assets)[:16],
            [
                "Перейменуй тему на одному із сайтів: нова папка + новий Theme Name у style.css.",
                "Перевір, щоб у HTML більше не фігурував /wp-content/themes/<назва>.",
                "Виноси публічні CSS/JS у нейтральну структуру.",
            ],
        ))

    common_gen = sorted(fp_a["cms_generators"] & fp_b["cms_generators"])
    if common_gen:
        noise.append(make_issue(
            "Однаковий CMS generator або плагіни",
            "Низький ризик",
            "Збіг WordPress-generator або wp-plugin шляхів. Це лише CMS або плагін, а не доказ однакової теми.",
            common_gen[:12],
            [],
        ))

    common_js = sorted(fp_a["inline_scripts"] & fp_b["inline_scripts"])
    if common_js:
        custom_js = [k for k in common_js if not _is_wp_core_inline_js(k, a_data)]
        wp_js = [k for k in common_js if _is_wp_core_inline_js(k, a_data)]

        if custom_js:
            key = custom_js[0]
            real.append(make_issue(
                "Однаковий кастомний inline JavaScript",
                "Критично",
                "Знайдено однакові фрагменти JavaScript прямо в HTML. Це схоже на кастомний код з одного шаблону.",
                custom_js[:10],
                [
                    "Знайди <script> у header.php, footer.php, functions.php або template-part.",
                    "Винось код у зовнішній .js файл з унікальним іменем.",
                    "Змінюй назви змінних, порядок ініціалізації та структуру функцій.",
                    "Дані налаштувань передавай через wp_localize_script, а не window.*.",
                ],
                a_data["inline_js_map"].get(key, ""),
                b_data["inline_js_map"].get(key, ""),
            ))

        if wp_js:
            noise.append(make_issue(
                "Стандартний WordPress core inline JavaScript",
                "Низький ризик",
                "Це WordPress core inline JS, наприклад emoji/settings script. Такий збіг не є доказом спільного шаблону.",
                wp_js[:10],
                [],
            ))

    common_css = sorted(fp_a["inline_styles"] & fp_b["inline_styles"])
    if common_css:
        custom_css = [k for k in common_css if not _is_wp_core_inline_css(k, a_data)]
        wp_css = [k for k in common_css if _is_wp_core_inline_css(k, a_data)]

        if custom_css:
            key = custom_css[0]
            real.append(make_issue(
                "Однаковий кастомний inline CSS",
                "Увага",
                "Знайдено однакові блоки <style> у HTML, які не схожі на стандартний WordPress core або global styles.",
                custom_css[:10],
                [
                    "Знайди <style> у шаблонах, ACF-блоках або widget areas.",
                    "Виноси стилі у зовнішній .css файл.",
                    "Перейменуй CSS-класи і додай project-prefix.",
                    "Перевір hero, faq, menu, popup, footer і кастомні блоки.",
                ],
                a_data["inline_css_map"].get(key, ""),
                b_data["inline_css_map"].get(key, ""),
            ))

        if wp_css:
            noise.append(make_issue(
                "Стандартний WordPress core inline CSS",
                "Низький ризик",
                "Це стандартний inline CSS від WordPress core або global styles, включно з auto sizes для зображень. Такі збіги не є доказом однакової теми чи шаблону.",
                wp_css[:10],
                [],
            ))

    common_og = sorted(fp_a["og_image_paths"] & fp_b["og_image_paths"])
    if common_og:
        real.append(make_issue(
            "Однакові шляхи og:image",
            "Критично",
            "og:image вказує на однаковий шлях до файлу без урахування домену. Це сильний сигнал спільної файлової структури або копії медіа.",
            common_og[:10],
            [
                "Заміни og:image на унікальні зображення для кожного сайту.",
                "Переконайся, що медіа-папки різні.",
                "Налаштуй окремі OG-зображення для кожного проекту.",
            ],
        ))

    common_meta = sorted(fp_a["important_meta"] & fp_b["important_meta"])
    real_meta = [x for x in common_meta if not is_noise_meta(x)]
    noise_meta = [x for x in common_meta if is_noise_meta(x)]

    if real_meta:
        real.append(make_issue(
            "Однакові важливі meta-теги",
            "Увага",
            "Збігаються конкретні значення meta, наприклад description, og:site_name або theme-color.",
            real_meta[:14],
            [
                "Зроби унікальні description і og-мета для кожного сайту.",
                "Перевір og:site_name, twitter:card, theme-color та інші брендові поля.",
            ],
        ))

    if noise_meta:
        noise.append(make_issue(
            "Типові SEO/CMS meta",
            "Низький ризик",
            "Стандартні SEO або CMS meta-значення, які часто збігаються на багатьох WordPress-сайтах.",
            noise_meta[:14],
            [],
        ))

    common_ids = sorted(fp_a["ids"] & fp_b["ids"])
    real_ids = [x for x in common_ids if not is_noise_id(x)]
    noise_ids = [x for x in common_ids if is_noise_id(x)]

    if real_ids:
        real.append(make_issue(
            "Однакові кастомні DOM id",
            "Увага",
            "Збігаються нестандартні id, які зазвичай створюються розробником, а не WordPress.",
            real_ids[:24],
            [
                "Перейменуй ці id на унікальні для кожного проекту.",
                "Якщо id не критичний для JS, заміни його на data-атрибут.",
                "Онови JS, що звертається до цих id.",
            ],
        ))

    if noise_ids:
        noise.append(make_issue(
            "Системні WordPress/plugin id",
            "Низький ризик",
            "Службові id WordPress або плагінів. Їх перейменування майже нічого не дає.",
            noise_ids[:24],
            [],
        ))

    common_cls = sorted(fp_a["classes"] & fp_b["classes"])
    real_cls = [x for x in common_cls if not is_noise_class(x)]
    noise_cls = [x for x in common_cls if is_noise_class(x)]

    if real_cls:
        level = "Увага" if len(real_cls) >= 8 else "Низький ризик"
        real.append(make_issue(
            "Однакові кастомні CSS класи",
            level,
            "Збігаються кастомні класи, не utility і не framework. Їх бажано перейменувати, якщо хочеш менше схожості між сайтами.",
            real_cls[:40],
            [
                "Додай project-specific prefix, наприклад siteA-, gcc- або brand-.",
                "Перейменуй класи секцій, меню, FAQ, hero, footer, карток і кастомних блоків.",
                "Онови HTML, CSS і JS після перейменування.",
                "За потреби автоматизуй це пошуком і заміною.",
            ],
        ))

    if noise_cls:
        noise.append(make_issue(
            "Framework / utility / типові WP класи",
            "Низький ризик",
            "Tailwind, Bootstrap, Elementor, WooCommerce, а також типові WordPress-класи. Їх перейменування зазвичай не потрібне.",
            noise_cls[:40],
            [],
        ))

    common_comm = sorted(fp_a["comments"] & fp_b["comments"])
    real_comm = [x for x in common_comm if not is_noise_comment(x)]
    noise_comm = [x for x in common_comm if is_noise_comment(x)]

    if real_comm:
        real.append(make_issue(
            "Однакові HTML-коментарі",
            "Увага",
            "Знайдено однакові ручні або шаблонні коментарі. Це часто сліди скопійованих блоків.",
            real_comm[:15],
            [
                "Знайди ці тексти через пошук по проекту.",
                "Видали коментарі з production HTML, особливо в header, footer, faq і tables.",
            ],
        ))

    if noise_comm:
        noise.append(make_issue(
            "Yoast / plugin коментарі",
            "Низький ризик",
            "Стандартні коментарі від Yoast SEO або інших плагінів. Ознакою шаблону не є.",
            noise_comm[:10],
            [],
        ))

    common_forms = sorted(fp_a["form_signatures"] & fp_b["form_signatures"])
    if common_forms:
        real.append(make_issue(
            "Однакові signatures форм",
            "Увага",
            "Форми мають однаковий набір полів. Якщо форми кастомні, це помітний сигнал спільного шаблону.",
            common_forms[:10],
            [
                "Зміни name-атрибути полів або порядок полів.",
                "Зміни action endpoint або логіку submit.",
                "Для різних проектів використовуй окремі шаблони форм.",
            ],
        ))

    common_schema = sorted(fp_a["schema_types"] & fp_b["schema_types"])
    if common_schema:
        noise.append(make_issue(
            "Однакові Schema.org типи",
            "Низький ризик",
            "Збіг JSON-LD @type, наприклад WebPage або LocalBusiness, це слабкий сигнал і часто стандартна розмітка.",
            common_schema[:10],
            [],
        ))

    common_paths = sorted(fp_a["internal_paths"] & fp_b["internal_paths"])
    trivial = {"/", "/ar", "/en", "/ru", "/ua", "/uk"}
    meaningful = [x for x in common_paths if x not in trivial]
    banal = [x for x in common_paths if x in trivial]

    if meaningful:
        real.append(make_issue(
            "Однакові внутрішні шляхи",
            "Низький ризик",
            "Повторюються змістовні slug/path, а не лише базові / або /en.",
            meaningful[:20],
            [
                "Переглянь naming slug/path для ключових сторінок.",
                "Не копіюй повністю однакову структуру URL без потреби.",
            ],
        ))

    if banal:
        noise.append(make_issue(
            "Тривіальні базові шляхи",
            "Низький ризик",
            "Базові шляхи /, /ar, /en збігаються на багатьох сайтах. Це слабкий сигнал.",
            banal[:10],
            [],
        ))

    return real, noise

# ---------------------------------------------------------------------------
# Текстовий висновок
# ---------------------------------------------------------------------------

def build_human_summary(a_data: dict, b_data: dict, real_issues: list, noise_issues: list) -> str:
    fp_a = a_data["fingerprints"]
    fp_b = b_data["fingerprints"]

    theme_match = _has_theme_match(fp_a, fp_b)
    js_hits = [x for x in sorted(fp_a["inline_scripts"] & fp_b["inline_scripts"]) if not _is_wp_core_inline_js(x, a_data)]
    css_hits = [x for x in sorted(fp_a["inline_styles"] & fp_b["inline_styles"]) if not _is_wp_core_inline_css(x, a_data)]
    og_hits = sorted(fp_a["og_image_paths"] & fp_b["og_image_paths"])
    real_comments = [x for x in sorted(fp_a["comments"] & fp_b["comments"]) if not is_noise_comment(x)]
    custom_ids = [x for x in sorted(fp_a["ids"] & fp_b["ids"]) if not is_noise_id(x)]
    custom_classes = [x for x in sorted(fp_a["classes"] & fp_b["classes"]) if not is_noise_class(x)]

    lines = []
    n = 1

    if theme_match:
        common_theme = sorted((fp_a["direct_theme"] | fp_a["theme_assets"]) & (fp_b["direct_theme"] | fp_b["theme_assets"]))
        lines.append("%d. Є прямий збіг теми або theme-assets: %s." % (n, ", ".join(common_theme[:4])))
        n += 1
    else:
        lines.append("%d. Прямого збігу WordPress-теми немає: назви тем або theme-assets різні." % n)
        n += 1

    if js_hits:
        lines.append("%d. Є однаковий кастомний inline JavaScript — це схоже на спільний шаблонний код." % n)
        n += 1

    if css_hits:
        lines.append("%d. Є однаковий кастомний inline CSS — це сильний сигнал спільних блоків або шаблонів." % n)
        n += 1

    if real_comments:
        lines.append("%d. Однакові HTML-коментарі: %s — це сліди скопійованих блоків." % (n, " | ".join(real_comments[:4])))
        n += 1

    if custom_ids:
        lines.append("%d. Однакові кастомні id: %s — структура секцій дуже схожа." % (n, ", ".join(custom_ids[:8])))
        n += 1

    if custom_classes:
        lines.append("%d. Дублюються кастомні CSS класи: %s — їх бажано перейменувати." % (n, ", ".join(custom_classes[:10])))
        n += 1

    if og_hits:
        lines.append("%d. Однакові og:image шляхи: %s — це може вказувати на спільну файлову структуру або копію медіа." % (n, ", ".join(og_hits[:3])))
        n += 1

    if noise_issues:
        lines.append("%d. Частина збігів — це шум: WordPress generator, core inline JS/CSS, plugin paths, utility-класи або системні id. Їх не треба прирівнювати до реальних кастомних збігів." % n)
        n += 1

    if not lines:
        lines.append("Сильних кастомних збігів практично немає. Більшість знайденого схоже на типовий шум або слабкі сигнали.")

    return "\n\n".join(lines)

def build_fix_priority(real_issues: list) -> list:
    if not real_issues:
        return ["Критичних кастомних збігів мало. Перевір тільки коментарі, meta і ручні блоки для чистоти."]
    return ["%d. %s — %s" % (i, iss["title"], iss["level"]) for i, iss in enumerate(real_issues[:8], 1)]

def build_top_matches(a_data: dict, b_data: dict) -> list:
    fp_a = a_data["fingerprints"]
    fp_b = b_data["fingerprints"]
    lines = []

    theme = sorted((fp_a["direct_theme"] & fp_b["direct_theme"]) | (fp_a["theme_assets"] & fp_b["theme_assets"]))
    if theme:
        lines.append("theme/assets: %s" % ", ".join(theme[:8]))

    js = [x for x in sorted(fp_a["inline_scripts"] & fp_b["inline_scripts"]) if not _is_wp_core_inline_js(x, a_data)]
    if js:
        lines.append("inline js: %s" % ", ".join(js[:8]))

    css = [x for x in sorted(fp_a["inline_styles"] & fp_b["inline_styles"]) if not _is_wp_core_inline_css(x, a_data)]
    if css:
        lines.append("inline css: %s" % ", ".join(css[:8]))

    og = sorted(fp_a["og_image_paths"] & fp_b["og_image_paths"])
    if og:
        lines.append("og:image paths: %s" % ", ".join(og[:6]))

    ids = [x for x in sorted(fp_a["ids"] & fp_b["ids"]) if not is_noise_id(x)]
    if ids:
        lines.append("custom ids: %s" % ", ".join(ids[:10]))

    cls = [x for x in sorted(fp_a["classes"] & fp_b["classes"]) if not is_noise_class(x)]
    if cls:
        lines.append("custom classes: %s" % ", ".join(cls[:15]))

    comm = [x for x in sorted(fp_a["comments"] & fp_b["comments"]) if not is_noise_comment(x)]
    if comm:
        lines.append("html comments: %s" % " | ".join(comm[:6]))

    return lines or ["Сильних кастомних збігів не знайдено."]

# ---------------------------------------------------------------------------
# Flask маршрут
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    result = None
    form = {"url_a": "", "url_b": ""}

    if request.method == "POST":
        form["url_a"] = request.form.get("url_a", "")
        form["url_b"] = request.form.get("url_b", "")
        try:
            html_a, label_a, base_a = get_input_side(form["url_a"], request.files.get("file_a"), "A")
            html_b, label_b, base_b = get_input_side(form["url_b"], request.files.get("file_b"), "B")

            a_data = extract_fingerprints(html_a, label_a, base_a)
            b_data = extract_fingerprints(html_b, label_b, base_b)

            real_issues, noise_issues = build_issues(a_data, b_data)

            result = {
                "label_a": a_data["label"],
                "label_b": b_data["label"],
                "similarity": similarity_score(a_data["fingerprints"], b_data["fingerprints"]),
                "template_risk": template_risk(a_data["fingerprints"], b_data["fingerprints"]),
                "real_issues": real_issues,
                "noise_issues": noise_issues,
                "real_issue_count": len(real_issues),
                "noise_count": len(noise_issues),
                "human_summary": build_human_summary(a_data, b_data, real_issues, noise_issues),
                "fix_priority": build_fix_priority(real_issues),
                "top_matches": build_top_matches(a_data, b_data),
                "short_a": a_data["short_summary"],
                "short_b": b_data["short_summary"],
            }

        except requests.exceptions.Timeout:
            error = "Таймаут при завантаженні сторінки. Спробуй ще раз або завантаж HTML вручну."
        except requests.exceptions.ConnectionError as exc:
            error = "Не вдалося підключитися: %s" % exc
        except requests.exceptions.HTTPError as exc:
            error = "HTTP помилка: %s" % exc
        except requests.exceptions.RequestException as exc:
            error = "Помилка при завантаженні сторінки: %s" % exc
        except Exception as exc:
            error = str(exc)

    return render_template_string(HTML_TEMPLATE, error=error, result=result, form=form)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
