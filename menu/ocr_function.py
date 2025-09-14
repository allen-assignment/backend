
import io
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

from .models import MenuCategory, MenuItem


PRICE_RE = re.compile(
    r"\$?\s*\d{1,3}(?:\.\d{1,2})?\s*(?:ea|each)?"
    r"(?:\s*\|\s*\$?\s*\d{1,3}(?:\.\d{1,2})?\s*(?:ea|each)?)*\s*$",
    re.I
)

DOLLAR_PRICE_RE = re.compile(r"\$\s*\d{1,3}(?:\.\d{1,2})?\s*$", re.I)
COMPLIMENTARY_RE = re.compile(r"\bcomplimentary\b", re.I)
FULL_PRICE_OR_COMP_RE = re.compile(
    r"^\s*(?:\$?\s*\d{1,3}(?:\.\d{1,2})?\s*(?:ea|each)?|complimentary)\s*$",
    re.I
)
INLINE_PRICE_RE = re.compile(
    r"(?:\$?\s*\d{1,3}(?:\.\d{1,2})?\s*(?:ea|each)?)\s*$",
    re.I)
TAG_SET = {"V","VE","VO","GF","GFO","DF","DFO","VG","VEO", "NFO"}

ICON_TAIL_RE = re.compile(
    u"[\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001F5FF\U0001F600-\U0001F64F"
    u"\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF\uFE0E\uFE0F]+$")
TRAILING_TOKEN_RE = re.compile(r"\s+([A-Za-z]{1,2}|[%\*\u00B0\u2122\u00AE\uFF05])$")
REPLACEMENT_CHAR_RE = re.compile(u"\uFFFD+")
GLOBAL_TITLE_RE = re.compile(
    r"^\s*(?:ROSSONERO|Menu\s*[-–—]\s*[A-Za-z]+\s*\d{4}|FRASER['’]S|KINGS\s+PARK)\s*$",
    re.I)


DIJON_RE = re.compile(r"^\s*dijon\s+a[iï]oli\s*$", re.I)
SHORT_DESC_HINT_RE = re.compile(
    r"(,|\(|\)|\baioli\b|\bmayo\b|\bmayonnaise\b|\bsauce\b|\bromesco\b|"
    r"\bdressing\b|\bpur[eé]e\b|\bcream\b|\bvinaigrette\b)", re.I
)

NAME_LIKE_RE = re.compile(
    r"^(?=.{2,60}$)(?!.*,\s)(?:[A-Z][A-Za-z'&+/.\-]+(?:\s+[A-Za-z'&+/.\-]+){0,8})(?:\([^)]+\))?\s*$"
)

def _looks_like_short_desc(t: str) -> bool:

    s = (t or "").strip()
    if not s or _is_header(s) or FULL_PRICE_OR_COMP_RE.match(s) or INLINE_PRICE_RE.search(s):
        return False
    letters = [c for c in s if c.isalpha()]
    lower_ratio = (sum(c.islower() for c in letters) / len(letters)) if letters else 1.0
    words = re.findall(r"[A-Za-z]+", s)

    return (len(words) <= 6) and (lower_ratio >= 0.6 or SHORT_DESC_HINT_RE.search(s) is not None)

def _strip_trailing_icons_and_noise(text: str) -> str:
    if not text:
        return text
    t = REPLACEMENT_CHAR_RE.sub("", text)
    t = ICON_TAIL_RE.sub("", t)

    while True:
        m = TRAILING_TOKEN_RE.search(t)
        if not m:
            break
        tok = (m.group(1) or "").upper()
        if tok in TAG_SET:
            break
        t = t[:m.start()].rstrip()
    t = re.sub(r"\(\s*[,/&|·.\-–—\s]*\)", "", t)
    m_endnum = re.search(r"\b(\d+(?:\.\d+)?)\s*$", t)
    if m_endnum:
        num = m_endnum.group(1)
        if "." not in num and 1 <= len(num) <= 2:
            t = t[:m_endnum.start()].rstrip()

    t = re.sub(r"\s{2,}", " ", t).strip(" .,-–—:;/|")
    return t


def _is_header(text: str) -> bool:
    t = re.sub(r"[\s•·\-–—*]+$", "", text.strip())
    if DOLLAR_PRICE_RE.search(t) or PRICE_RE.search(t):
        return False
    patterns = [
        r"^\s*STARTERS?\s*$",
        r"^\s*SALADS?\s*$",
        r"^\s*PASTA\s*$",
        r"^\s*KIDS\s+MENU\b.*$",
        r"^\s*DESSERTS?\s*$",
        r"^\s*DRINKS?\s*$",
        r"^\s*TOPPINGS?\s*$",
        r"^\s*PIZZAS?\s*$",
        r"^\s*CLASSIC\s+PIZZAS?\s*$",
        r"^\s*SIGNATURE\s+PIZZAS?\b.*$",
        r"^\s*SIDES?\s*$",
        r"^\s*EXTRAS?\s*$",
        r"^\s*ADD\-?ONS?\s*$",
        r"^\s*MODIFICATIONS?\s*$",
        r"^\s*TO\s+START\s*$",
        r"^\s*ENTR[ÉE]ES?\s*$",
        r"^\s*MAINS?\s*$",
        r"^\s*CHARGRILLED\s*$",
        r"^\s*SIDES?\s*$",
        r"^\s*DIETARY\s+MODIFICATIONS?\s*$",
        r"^\s*BEVERAGES?\s*$",
    ]
    return any(re.compile(p, re.I).match(t) for p in patterns)


def _extract_tags(text: str):
    out = set()
    for w in re.split(r"[,\s/]+", text.upper()):
        w = w.strip("()[]*;:.+")
        if w in TAG_SET:
            out.add(w)
    return sorted(out)


def _price_to_decimal(price_str: str) -> Decimal:
    s = (price_str or "").replace("$", "")
    m = re.search(r"(\d{1,3}(?:\.\d{1,2})?)", s)
    try:
        return Decimal(m.group(1)) if m else Decimal("0.00")
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def analyze_layout(file_bytes: bytes):
    if not settings.DOC_ENDPOINT or not settings.DOC_KEY:
        raise RuntimeError("DOC_ENDPOINT / DOC_KEY is missing. Check your .env settings.")
    client = DocumentAnalysisClient(
        endpoint=settings.DOC_ENDPOINT,
        credential=AzureKeyCredential(settings.DOC_KEY),
    )
    poller = client.begin_analyze_document("prebuilt-layout", io.BytesIO(file_bytes))
    return poller.result()


def _looks_like_name(t: str) -> bool:
    t = (t or "").strip()
    if not t or _is_header(t) or FULL_PRICE_OR_COMP_RE.match(t):
        return False


    t_no_tags = re.sub(r"\b(" + "|".join(map(re.escape, TAG_SET)) + r")\b", "", t, flags=re.I)
    t_norm = re.sub(r"[&/+\u00B7•·]", " ", t_no_tags)  # & / + · • 等
    t_clean = _strip_trailing_icons_and_noise(t_norm).strip()
    if not t_clean:
        return False

    if NAME_LIKE_RE.match(t_clean):
        return True

    alpha = sum(c.isalpha() for c in t_clean)
    upper = sum(c.isupper() for c in t_clean if c.isalpha())
    is_all_capsish = (alpha >= 3 and upper / alpha >= 0.6)

    words = [w for w in re.split(r"\s+", t_clean) if w]
    few_words = 1 <= len(words) <= 8
    no_long_digits = not any(re.search(r"\d{3,}", w) for w in words)

    return bool(is_all_capsish and few_words and no_long_digits)


def _assign_prices_by_right(items, price_lines, x_margin=0.02, y_thresh=0.035):
    used = set()
    for it in items:
        if it["price"]:
            continue
        y_ref = 0.5 * (it["_y_top"] + it["_y_bot"])
        x_ref = it["_x_center"]
        j_best, dy_best = -1, 1e9
        for j, pl in enumerate(price_lines):
            if j in used:
                continue
            if pl["x"] <= x_ref + x_margin:
                continue
            dy = abs(pl["y"] - y_ref)
            if dy < dy_best and dy <= y_thresh:
                dy_best, j_best = dy, j
        if j_best >= 0:
            used.add(j_best)
            txt = price_lines[j_best]["text"]
            if COMPLIMENTARY_RE.search(txt):
                it["price"] = "0"
            else:
                m = PRICE_RE.search(txt)
                it["price"] = m.group(0).strip() if m else txt.strip()


def _parse_stream(lines):
    items = []
    price_only = []
    current_category = "UNCATEGORIZED"
    cur = None

    for line in sorted(lines, key=lambda l: l["y"]):
        t = (line["text"] or "").strip()

        if re.fullmatch(r"\d{1,2}", t) and int(t) <= 5 and line.get("x", 0) < 0.75:
            continue

        if GLOBAL_TITLE_RE.match(t):
            continue

        if line["type"] == "CATEGORY":
            if cur:
                items.append(cur)
                cur = None
            current_category = re.sub(r'[:.]+$', '', t)
            continue

        if DIJON_RE.match(t):
            if cur:
                cur["description"] = (
                        (cur.get("description") + " " if cur.get("description") else "") + "Dijon aioli"
                ).strip()

                cur["_y_bot"] = line["y"]

            continue

        if FULL_PRICE_OR_COMP_RE.match(t):
            price_only.append(line)
            continue

        if line["type"] == "ITEM_WITH_PRICE" and INLINE_PRICE_RE.search(t):
            m = INLINE_PRICE_RE.search(t)
            price = m.group(0).strip()
            price = re.sub(r"(?i)\s*(?:ea|each)\b[)\]\}.,;:•·*–—-]*$", "", price).strip()
            left_text  = t[:m.start()].strip(" .-–—")
            right_desc = t[m.end():].strip(" .-–—") or None

            if not left_text and cur:
                cur["price"] = price
                if right_desc:
                    cur["description"] = ((cur.get("description") or "") + " " + right_desc).strip()
                continue

            if left_text and ('$' not in price):
                mnum = re.search(r"\d+(?:\.\d+)?", price)
                val = float(mnum.group(0)) if mnum else 99.0
                if val <= 9.0:
                    if cur:
                        items.append(cur)
                    name = _strip_trailing_icons_and_noise(t)
                    tags = _extract_tags(name)
                    if tags:
                        name = re.sub(r"\b(" + "|".join(map(re.escape, TAG_SET)) + r")\b", "", name, flags=re.I)
                        name = _strip_trailing_icons_and_noise(name)
                    cur = {
                        "category": current_category,
                        "name": name,
                        "price": "",
                        "description": None,
                        "tags": sorted(set(tags)),
                        "_y_top": line["y"], "_y_bot": line["y"], "_x_center": line["x"],
                    }
                    continue


            name = _strip_trailing_icons_and_noise(left_text)
            desc = right_desc
            tags = _extract_tags(name)
            if tags:
                name = re.sub(r"\b(" + "|".join(map(re.escape, TAG_SET)) + r")\b", "", name, flags=re.I)
                name = _strip_trailing_icons_and_noise(name)

            if cur:
                items.append(cur)

            cur = {
                "category": current_category,
                "name": name,
                "price": price,
                "description": right_desc,
                "tags": sorted(set(tags)),
                "_y_top": line["y"], "_y_bot": line["y"], "_x_center": line["x"],
            }
            continue



        if _looks_like_name(t):
            if cur:
                items.append(cur)
            name = _strip_trailing_icons_and_noise(t)
            tags = _extract_tags(name)
            if tags:
                name = re.sub(r"\b(" + "|".join(map(re.escape, TAG_SET)) + r")\b", "", name, flags=re.I)
                name = _strip_trailing_icons_and_noise(name)

            cur = {
                "category": current_category,
                "name": name,
                "price": "",
                "description": None,
                "tags": sorted(set(tags)),
                "_y_top": line["y"], "_y_bot": line["y"], "_x_center": line["x"],
            }
            continue

        if cur:
            d = (cur["description"] or "")
            cur["description"] = (d + " " + t).strip() if d else t
            cur["_y_bot"] = line["y"]

    if cur:
        items.append(cur)

    _assign_prices_by_right(items, price_only)

    for it in items:
        it.pop("_y_top", None); it.pop("_y_bot", None); it.pop("_x_center", None)
        if it.get("description"):
            it["description"] = it["description"].strip() or None

    return items


def parse_to_items(result):
    lines = []
    for page in result.pages:
        w, h = float(page.width), float(page.height)
        for ln in page.lines:
            t = (ln.content or "").strip()
            if not t:
                continue
            poly = ln.polygon
            if not poly or len(poly) < 4:
                continue

            xs = [p.x / w for p in poly]
            ys = [p.y / h for p in poly]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)

            if cy < 0.12 and GLOBAL_TITLE_RE.match(t) and not _is_header(t):
                continue
            if _is_header(t):
                typ = "CATEGORY"
            elif INLINE_PRICE_RE.search(t) or FULL_PRICE_OR_COMP_RE.match(t):
                typ = "ITEM_WITH_PRICE"
            else:
                typ = "DESCRIPTION"

            lines.append({"text": t, "x": cx, "y": cy, "type": typ})

    if not lines:
        return []
    return _parse_stream(lines)


def preview_items(items):
    from pprint import pprint
    pprint(items)
    return items



