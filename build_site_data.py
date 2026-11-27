import os
import sys
import re
import json
import urllib.parse
from collections import OrderedDict, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = r"C:\Users\avremi-c\.gemini\antigravity\scratch\reb_yoel_archive"
CACHE_DIR = os.path.join(BASE_DIR, "raw_cache")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ==============================================================================
# Hebrew Year Parsing (5550 - 5787) & Gematria
# ==============================================================================
UNITS = {"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9}
TENS = {"י": 10, "כ": 20, "ך": 20, "ל": 30, "מ": 40, "ם": 40, "נ": 50, "ן": 50, "ס": 60, "ע": 70, "פ": 80, "ף": 80, "צ": 90, "ץ": 90}
HUNDREDS = {"ק": 100, "ר": 200, "ש": 300, "ת": 400}

def gematria(letters):
    total = 0
    for ch in letters:
        if ch in HUNDREDS:
            total += HUNDREDS[ch]
        elif ch in TENS:
            total += TENS[ch]
        elif ch in UNITS:
            total += UNITS[ch]
        else:
            return None
    return total

def num_to_heb_letters(rem):
    out = []
    while rem >= 400:
        out.append("ת")
        rem -= 400
    for v, ch in [(300, "ש"), (200, "ר"), (100, "ק")]:
        if rem >= v:
            out.append(ch)
            rem -= v
    if rem == 15:
        out.extend(["ט", "ו"])
        rem = 0
    elif rem == 16:
        out.extend(["ט", "ז"])
        rem = 0
    else:
        for v, ch in [(90, "צ"), (80, "פ"), (70, "ע"), (60, "ס"), (50, "נ"), (40, "מ"), (30, "ל"), (20, "כ"), (10, "י")]:
            if rem >= v:
                out.append(ch)
                rem -= v
        for v, ch in [(9, "ט"), (8, "ח"), (7, "ז"), (6, "ו"), (5, "ה"), (4, "ד"), (3, "ג"), (2, "ב"), (1, "א")]:
            if rem >= v:
                out.append(ch)
                rem -= v
    if not out:
        return ""
    if len(out) == 1:
        return out[0] + "'"
    return "".join(out[:-1]) + '"' + out[-1]

def num_to_hebrew_year(n):
    if n < 5500 or n > 5800:
        return str(n)
    return num_to_heb_letters(n - 5000)

def canon_heb_num(raw):
    clean = re.sub(r'["\'״׳”’\s]', "", raw or "")
    val = gematria(clean)
    if val and 1 <= val <= 100:
        return num_to_heb_letters(val).rstrip("'")
    return raw.strip()

HEB_YEAR_MAP = {}
for y in range(5550, 5788):
    hy = num_to_hebrew_year(y)
    plain = hy.replace('"', "").replace("'", "")
    HEB_YEAR_MAP[plain] = (y, hy)
HEB_YEAR_MAP.update({
    "תנשא": (5751, 'תשנ"א'),
    "תשדמ": (5744, 'תשמ"ד'),
    "עטרת": (5679, 'תרע"ט'),
    "עתר": (5670, 'תר"ע'),
    "תערב": (5672, 'תרע"ב'),
    "תערג": (5673, 'תרע"ג'),
    "תערד": (5674, 'תרע"ד'),
    "תערה": (5675, 'תרע"ה'),
    "תערו": (5676, 'תרע"ו'),
    "תערז": (5677, 'תרע"ז'),
    "תעח": (5678, 'תרע"ח'),
    "תרסו": (5666, 'תרס"ו'),
    "תש": (5700, 'ת"ש'),
})

YEAR_TOKEN_RE = re.compile(
    r'(?<![א-ת])(?:ה[\'"׳]?)?(תק[א-ת"\'״׳]{1,3}|תר[א-ת"\'״׳]{1,3}|תש[א-ת"\'״׳]{0,3}|תנש["\'״׳]?א|עטר["\'״׳]?ת|עת["\'״׳]?ר|תער["\'״׳]?[בגדהוז]|ת"ש|ת׳׳ש|ת\'\'ש)(?![א-ת])'
)
NUM_YEAR_RE = re.compile(r'\b(57\d{2}|56\d{2})\b')

def year_to_decade(yn):
    if not yn:
        return None
    if yn < 5660: return 'תק"ס–תרנ"ט'
    if yn < 5680: return 'תר"ס–תרע"ט'
    if yn < 5711: return 'תר"פ–תש"י'
    if yn < 5731: return 'תשי"א–תש"ל'
    if yn < 5740: return 'תשל"א–תשל"ט'
    if yn < 5750: return 'תש"מ–תשמ"ט'
    if yn < 5760: return 'תש"נ–תשנ"ט'
    if yn < 5770: return 'תש"ס–תשס"ט'
    return 'תש"ע–תשפ"א'

def extract_years(*texts):
    found = OrderedDict()
    blob = " ".join(t for t in texts if t)
    norm_blob = blob.replace("''", '"').replace("״", '"').replace("׳", "'").replace("”", '"').replace("’", "'")
    for m in YEAR_TOKEN_RE.finditer(norm_blob):
        clean = m.group(1).replace('"', "").replace("'", "")
        if clean in HEB_YEAR_MAP:
            yn, hy = HEB_YEAR_MAP[clean]
            found[hy] = yn
    for m in NUM_YEAR_RE.finditer(norm_blob):
        yn = int(m.group(1))
        if 5600 <= yn <= 5787:
            found[num_to_hebrew_year(yn)] = yn
    if re.search(r'(?:המשך|תער"ב|מאמרי)\s+ע"ב|ע"ב\s*[-–]', norm_blob):
        found['תרע"ב'] = 5672
    if re.search(r'(?:המשך|מאמרי)\s+ס"ו|ס"ו\s*[-–]|ס"ו\s+שיעור', norm_blob):
        found['תרס"ו'] = 5666
    years_list = list(found.keys())
    decs = list(OrderedDict.fromkeys(year_to_decade(yn) for yn in found.values() if year_to_decade(yn)))
    primary_yn = max(found.values()) if found else 0
    return years_list, primary_yn, decs

# ==============================================================================
# Parsha -> Chumash & Holidays -> Month
# ==============================================================================
PARSHIYOS = [
    ("בראשית", "ספר בראשית", ["בראשית", "bereishis", "bereshit", "berieshis"]),
    ("נח", "ספר בראשית", ["פרשת נח", "נוח", "noach", "parshas noach"]),
    ("לך לך", "ספר בראשית", ["לך לך", "lech lecha", "lechlecha", "lech l"]),
    ("וירא", "ספר בראשית", ["וירא", "vayeira", "vayera"]),
    ("חיי שרה", "ספר בראשית", ["חיי שרה", "chayei sara", "chayeisara"]),
    ("תולדות", "ספר בראשית", ["תולדות", "toldos", "toldot", "toldas"]),
    ("ויצא", "ספר בראשית", ["ויצא", "vayeitzei", "vayetzei", "vayetz"]),
    ("וישלח", "ספר בראשית", ["וישלח", "vayishlach"]),
    ("וישב", "ספר בראשית", ["וישב", "vayeshev", "vayeishev"]),
    ("מקץ", "ספר בראשית", ["מקץ", "mikeitz", "miketz"]),
    ("ויגש", "ספר בראשית", ["ויגש", "vayigash", "vaygash"]),
    ("ויחי", "ספר בראשית", ["ויחי", "vayechi"]),
    ("שמות", "ספר שמות", ["ואלה שמות", "פרשת שמות", "shemos", "shmos", "shimos"]),
    ("וארא", "ספר שמות", ["וארא", "vaeira", "vaera", "va'era"]),
    ("בא", "ספר שמות", ["פרשת בא", "parshas bo", "bo --", "bo 57", "bo7"]),
    ("בשלח", "ספר שמות", ["בשלח", "beshalach"]),
    ("יתרו", "ספר שמות", ["יתרו", "yisro", "yitro"]),
    ("משפטים", "ספר שמות", ["משפטים", "mishpatim", "mishpotim"]),
    ("תרומה", "ספר שמות", ["תרומה", "terumah", "trumah", "trumoh"]),
    ("תצוה", "ספר שמות", ["תצוה", "תצווה", "tetzaveh", "tetsaveh"]),
    ("כי תשא", "ספר שמות", ["כי תשא", "ki sisa", "ki tisa", "kisisa"]),
    ("ויקהל", "ספר שמות", ["ויקהל", "vayakhel"]),
    ("פקודי", "ספר שמות", ["פקודי", "pekudei", "pikudei"]),
    ("ויקרא", "ספר ויקרא", ["פרשת ויקרא", "vayikra"]),
    ("צו", "ספר ויקרא", ["פרשת צו", "parshas tzav", "tzav --", "tzav 57"]),
    ("שמיני", "ספר ויקרא", ["שמיני", "shemini", "shmini"]),
    ("תזריע", "ספר ויקרא", ["תזריע", "tazria", "tazriah"]),
    ("מצורע", "ספר ויקרא", ["מצורע", "מצרע", "metzora"]),
    ("אחרי מות", "ספר ויקרא", ["אחרי מות", "פרשת אחרי", "acharei"]),
    ("קדושים", "ספר ויקרא", ["קדושים", "קדשים", "kedoshim"]),
    ("אמור", "ספר ויקרא", ["אמור", "emor"]),
    ("בהר", "ספר ויקרא", ["בהר", "behar"]),
    ("בחוקותי", "ספר ויקרא", ["בחוקותי", "בחקתי", "בחוקתי", "bechukosai", "bechukotai", "bichukosay"]),
    ("במדבר", "ספר במדבר", ["פרשת במדבר", "bamidbar"]),
    ("נשא", "ספר במדבר", ["פרשת נשא", "naso", "noso"]),
    ("בהעלותך", "ספר במדבר", ["בהעלותך", "בהעלתך", "behaalosecha", "beha'alosecha", "behalotcha"]),
    ("שלח", "ספר במדבר", ["שלח לך", "פרשת שלח", "shelach", "shlach"]),
    ("קרח", "ספר במדבר", ["קרח", "קורח", "korach"]),
    ("חוקת", "ספר במדבר", ["חוקת", "חקת", "chukas", "chukat"]),
    ("בלק", "ספר במדבר", ["בלק", "balak"]),
    ("פנחס", "ספר במדבר", ["פנחס", "פינחס", "pinchas"]),
    ("מטות", "ספר במדבר", ["מטות", "matos", "matot", "mattos"]),
    ("מסעי", "ספר במדבר", ["מסעי", "masei"]),
    ("דברים", "ספר דברים", ["פרשת דברים", "devarim", "devorim", "divarim"]),
    ("ואתחנן", "ספר דברים", ["ואתחנן", "vaeschanan", "va'eschanan", "vaetchanan", "voeschanon"]),
    ("עקב", "ספר דברים", ["עקב", "eikev", "ekev"]),
    ("ראה", "ספר דברים", ["פרשת ראה", "reeh", "reei", "re'eh"]),
    ("שופטים", "ספר דברים", ["שופטים", "shoftim"]),
    ("כי תצא", "ספר דברים", ["כי תצא", "ki seitzei", "ki seitze", "kiseitzei", "kiteitzei"]),
    ("כי תבוא", "ספר דברים", ["כי תבוא", "כי תבא", "ki savo", "kisavo"]),
    ("נצבים", "ספר דברים", ["נצבים", "ניצבים", "nitzavim", "nitavim"]),
    ("וילך", "ספר דברים", ["וילך", "vayeilech", "vaylach"]),
    ("האזינו", "ספר דברים", ["האזינו", "haazinu", "ha'azinu", "ha'ahzinu"]),
    ("וזאת הברכה", "ספר דברים", ["וזאת הברכה", "זאת הברכה", "vezos haberacha", "ve'zos ha'beracha", "vzos"]),
]
PARSHA_TO_CHUMASH = {p[0]: p[1] for p in PARSHIYOS}

HOLIDAYS = [
    ("ראש השנה", "תשרי", ["ראש השנה", 'ר"ה', "תקעו", "rosh hashana", "rosh hashonah", "rosh hasonah"]),
    ("יום כיפור", "תשרי", ["יום כיפור", 'יו"כ', 'יוה"כ', "yom kippur", "yom kipur"]),
    ("סוכות ושמיני עצרת", "תשרי", ["סוכות", "בסוכות", "לולב", "שמיני עצרת", "שמחת תורה", "sukkos", "sukkot", "sukkas", "sokkus", "simchas torah", "st57"]),
    ("חודש חשון", "חשון", ["mar cheshvan", "כ' מרחשון", "כ' חשון", "ר\"ח חשון"]),
    ('י"ט כסלו', "כסלו", ['י"ט כסלו', "יט כסלו", "פדה בשלום", "19 kislev", "19 kislav", "yud tes kislev", "podoh bsholom", "pada b"]),
    ("חנוכה", "כסלו", ["חנוכה", "נר חנוכה", "chanukah", "chanuka", "hanukkah", "chanika", "24 kislev"]),
    ('כ"ד טבת', "טבת", ['כ"ד טבת', "כד טבת", "24 teves"]),
    ('יו"ד שבט', "שבט", ["י' שבט", 'י" שבט', 'יו"ד שבט', "י שבט", "באתי לגני", "yud shvat", "10 shvat", "10 shevat", "basi lgani", "basi legan"]),
    ('ט"ו בשבט', "שבט", ['ט"ו בשבט', "טו בשבט", "15 shevat", "15 shvat"]),
    ('ז\' אדר', "אדר", ["7 adar", "ז' אדר", "ז אדר"]),
    ("פרשת החודש", "אדר", ["פרשת החודש"]),
    ("פורים", "אדר", ["פורים", "בלילה ההוא", "עמלק", "זכור", "purim", "balayla hahu", "balaylah"]),
    ("פסח", "ניסן", ["פסח", "מצה", "היא שעמדה", "כי ישאלך", "פסח שני", "שבת הגדול", "pesach", "passover", "shabbos hagodol", "shabbos hagadol", "achroin shel pesach", "acharon shel pesach"]),
    ('י"א ניסן', "ניסן", ['י"א ניסן', "יא ניסן", "11 nissan", "yud alef nissan", "yud alef nisan", "yud nissan", "yud nisan"]),
    ('ל"ג בעומר', "אייר", ['ל"ג בעומר', "לג בעומר", "רשב\"י", "rashbi", "lag baomer", "lag b_omer", "lag buomer", "lah buomer"]),
    ("שבועות", "סיון", ["שבועות", "מתן תורה", "בחודש השלישי", "shavuos", "shavuot", "bachodesh hashlishi"]),
    ('י"ב-י"ג תמוז', "תמוז", ['י"ב תמוז', "יב תמוז", 'י"ג תמוז', "יג תמוז", "12 tammuz", "12 de tamuz", "13 tammuz", "12th & 13th"]),
    ("ג' תמוז", "תמוז", ["ג' תמוז", "ג תמוז", "3 tammuz", "gimmel tammuz"]),
    ("בין המצרים ותשעה באב", "אב", ["בין המצרים", "ימי המצרים", "תשעה באב", "ט' באב", "17 tammuz", "tisha bav", "bein hametzarim", "menachem av"]),
    ('ט"ו באב', "אב", ['ט"ו באב', "טו באב", "15 av"]),
    ('ח"י אלול', "אלול", ['ח"י אלול', "חי אלול", "18 elul", "chai elul"]),
    ("חודש אלול", "אלול", ["חודש אלול", "י\"א אלול"]),
    ("ו' אב (יארצייט ר' יואל)", "אב", ["ו' מנחם אב", "ו׳ מנחם אב", "יארצייט של ר' יואל", "סעודת שלושים"]),
]
HOLIDAY_TO_MONTH = {h[0]: h[1] for h in HOLIDAYS}
HEB_MONTHS = ["תשרי", "חשון", "כסלו", "טבת", "שבט", "אדר", "ניסן", "אייר", "סיון", "תמוז", "אב", "אלול"]

def detect_parsha_or_holiday(*texts):
    blob = (
        " ".join(t for t in texts if t)
        .lower()
        .replace("''", '"')
        .replace("״", '"')
        .replace("”", '"')
        .replace("׳", "'")
        .replace("’", "'")
    )
    for name, _, keys in PARSHIYOS:
        for k in keys:
            if k in blob:
                return name
    for name, _, keys in HOLIDAYS:
        for k in keys:
            if k in blob:
                return name
    return ""

# ==============================================================================
# Clean 6-Level Hierarchy Taxonomy
# ==============================================================================
CAT_ORDER = [
    "ספרים",
    "פרשיות השבוע",
    "ענינא דיומא",
    "חזרות והתוועדויות",
    "סוגיות בחסידות",
    "ניגונים",
    "ספרים וכתבים (PDF)",
]

CAT_INFO = {
    "ספרים": {
        "icon": "📚",
        "title": "ספרים (ספרי רבותינו נשיאינו)",
        "desc": "דפדוף לפי אדמו\"ר ← ספר ← חלק / פרק ← שיחה / מאמר ← סדרת שיעורים ברצף",
        "nextLabel": "אדמו\"ר",
    },
    "פרשיות השבוע": {
        "icon": "📖",
        "title": "פרשיות השבוע (חומש)",
        "desc": "שיעורים, וורטים, שיחות ומאמרים מסודרים לפי חומש ופרשת השבוע",
        "nextLabel": "חומש",
    },
    "ענינא דיומא": {
        "icon": "🗓️",
        "title": "מועדי השנה וענינא דיומא",
        "desc": "תשרי, י\"ט כסלו, חנוכה, יו\"ד שבט, פורים, פסח, שבועות ותמוז-אב לפי חודשים",
        "nextLabel": "חודש",
    },
    "חזרות והתוועדויות": {
        "icon": "🔄",
        "title": "חזרות והתוועדויות",
        "desc": "הקלטות חזרה אותנטיות מהתוועדויות הרבי לפי שנים, והתוועדויות ר' יואל",
        "nextLabel": "מסגרת",
    },
    "סוגיות בחסידות": {
        "icon": "💡",
        "title": "סוגיות ומושגים בחסידות",
        "desc": "שיעורי עומק ביסודות החסידות, י\"ג עיקרים, אחדות ה', גאולה ומשיח ובמשנת רבינו",
        "nextLabel": "מדור / סדרה",
    },
    "ניגונים": {
        "icon": "🎵",
        "title": "ניגוני חב\"ד מר' יואל",
        "desc": "ניגוני דביקות ושמחה שניגן ולימד ר' יואל כהן בהתוועדויות",
        "nextLabel": "קבוצת ניגונים",
    },
    "ספרים וכתבים (PDF)": {
        "icon": "📄",
        "title": "ספרים, כתבים וחוברות לימוד (PDF)",
        "desc": "ספר הערכים חב\"ד, שער היחוד והאמונה, מחשבת החסידות, דפי מקורות ורישומי חזרות",
        "nextLabel": "סדרה / סוג ספר",
    },
}

REBBE_ZAKEN = 'כ"ק אדמו"ר הזקן'
REBBE_ZZ = 'כ"ק אדמו"ר הצמח צדק'
REBBE_RASHAB = 'כ"ק אדמו"ר הרש"ב'
REBBE_RAYYATZ = 'כ"ק אדמו"ר מוהריי"צ'
REBBE_LUBAVITCH = 'כ"ק אדמו"ר'

REBBE_ORDER = [
    REBBE_ZAKEN,
    REBBE_ZZ,
    REBBE_RASHAB,
    REBBE_RAYYATZ,
    REBBE_LUBAVITCH,
]

REBBE_INFO = {
    REBBE_ZAKEN: {
        "title": REBBE_ZAKEN,
        "sub": "בעל התניא והשו\"ע",
        "desc": "תניא על כל חלקיו (ליקוטי אמרים, שעהיוה\"א, אגרת התשובה, אגרת הקודש), תורה אור ולקוטי תורה",
    },
    REBBE_ZZ: {
        "title": REBBE_ZZ,
        "sub": "בעל הדרך מצותיך",
        "desc": "סדרות שיעורים מפורטות בספר דרך מצוותיך לפי מצוות",
    },
    REBBE_RASHAB: {
        "title": REBBE_RASHAB,
        "sub": "בעל המשך תרס\"ו והמשך תער\"ב",
        "desc": "המשך תרס\"ו (ס\"ו), המשך תער\"ב (ע\"ב), ספרי המאמרים (תרמ\"ג–עטר\"ת) וקונטרסים",
    },
    REBBE_RAYYATZ: {
        "title": REBBE_RAYYATZ,
        "sub": "ספרי המאמרים, באתי לגני וקונטרסים",
        "desc": "ספרי המאמרים (תרפ\"ה–תש\"י), מאמרי באתי לגני וקונטרסים",
    },
    REBBE_LUBAVITCH: {
        "title": REBBE_LUBAVITCH,
        "sub": "הרבי מליובאוויטש",
        "desc": "ליקוטי שיחות, ספר המאמרים מלוקט, מאמרים בלתי מוגה, קונטרסים, הדרנים, ספר השיחות ורשימות",
    },
}

BOOKS_BY_REBBE = {
    REBBE_ZAKEN: [
        'תניא — לקוטי אמרים',
        'תניא — שער היחוד והאמונה',
        'תניא — אגרת התשובה',
        'תניא — אגרת הקודש וקונטרס אחרון',
        'תורה אור',
        'לקוטי תורה',
    ],
    REBBE_ZZ: [
        'דרך מצותיך',
    ],
    REBBE_RASHAB: [
        'המשך תרס"ו (ס"ו)',
        'המשך תער"ב (ע"ב)',
        'ספרי המאמרים וקונטרסים',
    ],
    REBBE_RAYYATZ: [
        'ספרי המאמרים וקונטרסים',
    ],
    REBBE_LUBAVITCH: [
        'ליקוטי שיחות',
        'ספר המאמרים מלוקט',
        'מאמרים (בלתי מוגה ותורת מנחם)',
        'קונטרסים',
        'הדרנים',
        'ספר השיחות ורשימות',
    ],
}

BOOK_INFO = {
    'תניא — לקוטי אמרים': ("פרק בתניא", "סדרה / שיעור", "ספר של בינונים — חלק ראשון של ספר התניא (שער עד פרק נ\"ג) באידיש ובעברית"),
    'תניא — שער היחוד והאמונה': ("פרק", "סדרה", "ביאורי אמונה, אחדות ה' וצמצום — לפי פרקים"),
    'תניא — אגרת התשובה': ("פרק", "סדרה", "מהות התשובה עילאה ותתאה — לפי פרקים"),
    'תניא — אגרת הקודש וקונטרס אחרון': ("סימן / פרק", "סדרה", "איגרות הקודש וביאורי קונטרס אחרון"),
    'תורה אור': ("חומש / שער", "פרשה ומאמר ד\"ה", "מאמרי בראשית, שמות, חנוכה ופורים"),
    'לקוטי תורה': ("חומש / שער", "פרשה ומאמר ד\"ה", "מאמרי ויקרא, במדבר, דברים, מועדים ושיר השירים"),
    'דרך מצותיך': ("מצוה", "סדרת שיעורים", "טעמי המצוות על דרך החסידות מאת כ\"ק אדמו\"ר הצמח צדק"),
    'המשך תרס"ו (ס"ו)': ("מאמר / סעיף", "פרטי המאמר", 'המשך המאמרים המפורסם "יו"ט של ר"ה תרס"ו" (תרס"ו–תרס"ח)'),
    'המשך תער"ב (ע"ב)': ("סימן / מאמר", "פרטי המאמר", 'המשך המאמרים "בשעה שהקדימו" (תרע"ב–תרע"ו)'),
    'ספרי המאמרים וקונטרסים': ("ספר המאמרים (שנה)", "מאמר ד\"ה", "ספרי המאמרים לפי שנים וקונטרסים"),
    'ליקוטי שיחות': ("חלק / כרך", "שיחה / פרשה", "שיעורי ר' יואל בליקוטי שיחות לפי חלקים ושיחות"),
    'ספר המאמרים מלוקט': ("חלק", "מאמר ד\"ה", "ספר המאמרים מלוקט לפי חלקים ומאמרים"),
    'מאמרים (בלתי מוגה ותורת מנחם)': ("מדור", "מאמר ד\"ה", "מאמרים בלתי מוגה, תשי\"ג ותורת מנחם"),
    'קונטרסים': ("קונטרס", "סעיף / חטיבה", "ענינה של תורת החסידות, בית רבינו שבבבל ועוד"),
    'הדרנים': ("סוג / שנה", "שיעור / קבוצה", "הדרנים על הרמב\"ם, הש\"ס ומשניות"),
    'ספר השיחות ורשימות': ("חלק / ספר", "שיחה / רשימה", "ספר השיחות תשמ\"ט וקונטרסי רשימות"),
}

# ==============================================================================
# Text & Part Order Helpers
# ==============================================================================
HEB_PARSHAS_ORD = {p[0]: i for i, p in enumerate(PARSHIYOS)}
HEB_MONTHS_ORD = {m: i for i, m in enumerate(HEB_MONTHS)}
CHUMASH_ORD = {"ספר בראשית": 1, "ספר שמות": 2, "ספר ויקרא": 3, "ספר במדבר": 4, "ספר דברים": 5, "ימים טובים — מועדים": 6, "חנוכה ופורים": 6, "שיר השירים": 7}

def normalize_ls_chelek(raw):
    c = canon_heb_num(raw)
    return f"חלק {c}" if c else raw

def extract_ls_chelek_from_text(text):
    """Extract normalized Likkutei Sichos chelek ('חלק ט', 'חלק י\"ט', etc.) from text, normalizing Unicode curly quotes."""
    if not text:
        return ""
    norm = text.replace("״", '"').replace("”", '"').replace("׳", "'").replace("’", "'")
    m = re.search(
        r'(?:לקו"ש|לקוטי\s+שיחות|ליקוטי\s+שיחות)\s*,?\s*(?:חלק|כרך|ח(?!\s+שיח))\s*["\']?\s*([א-ת]{1,2}(?:["\'][א-ת])?|[א-ת]|\d{1,2})["\']?(?=\s|,|;|$|[-–.])',
        norm,
    )
    if not m and any(k in norm for k in ['לקו"ש', "לקוטי שיחות", "ליקוטי שיחות"]):
        m = re.search(r'(?:^|\s)חלק\s+([א-ת]{1,2}(?:["\'][א-ת])?|[א-ת]|\d{1,2})["\']?(?=\s|,|;|$|[-–.])', norm)
    if not m:
        return ""
    val = m.group(1)
    if val.isdigit():
        return normalize_ls_chelek(num_to_heb_letters(int(val)))
    return normalize_ls_chelek(val)

def clean_tanya_perek(raw_seg):
    s = (raw_seg or "").strip()
    if any(k in s for k in ["שער", "הקדמה", "חינוך קטן", "דף השער"]):
        if "פרק א" in s:
            return "פרק א"
        if "חינוך קטן" in s:
            return "חינוך קטן"
        return "דף השער והקדמה"
    m = re.search(r'פרק(?:ים)?\s+([א-ת"\'״׳]{1,4})(?:\s*[-–]\s*([א-ת"\'״׳]{1,4}))?', s)
    if m:
        p1 = canon_heb_num(m.group(1))
        if m.group(2):
            p2 = canon_heb_num(m.group(2))
            return f"פרקים {p1}–{p2}"
        return f"פרק {p1}"
    return s

def extract_part_order(title, fn=""):
    """Extract numeric sort key so lessons inside a Series always sort 1, 2, 3..."""
    t = (title or "").strip()
    f = (fn or "").strip()
    # 0. Explicit JEM / Drive multi-part tape codes like '01-A', '001-B', '5666 01b', '(01)', '- 001-A'
    m = re.search(r'(?:_part_|#|Part\s*|חלק\s*|שיעור\s*)(\d+)\s*([ab])?', t, re.I)
    if not m:
        m = re.search(r'_part_(\d+)$', f, re.I)
    if not m:
        m = re.search(r'\b0*(\d{1,3})\s*[-_]?\s*([ab])(?:\b|[\s\]\[_-])', t, re.I)
    if not m:
        m = re.match(r'^0*(\d+)(?:\s*[-–]|$|\s*\|)', t)
    if not m:
        m = re.match(r'^0*(\d+)-', f)
    if not m:
        m = re.search(r'\((\d+)\)\s*$', t)
    if not m:
        m = re.search(r'(?:^|\s)0*(\d{1,3})\s*([a-c])?(?:\.[a-z0-9]+)*$', t, re.I)
    if m:
        n = int(m.group(1))
        # Avoid interpreting 4-digit Hebrew years (e.g. 5666, 5744) as small lesson numbers unless followed by part
        if 5500 <= n <= 5800:
            after = re.search(r'\b5[67]\d{2}\s+0*(\d+)\s*([a-c])?', t, re.I)
            if after:
                n = int(after.group(1))
                side = {'a': 0, 'b': 1, 'c': 2}.get((after.group(2) or '').lower(), 0)
                return n * 10 + side
        else:
            side = 0
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                side = {'a': 0, 'b': 1, 'c': 2}.get(m.group(2).lower(), 0)
            return n * 10 + side
    # 2. Check Hebrew letter parts (חלק א..י)
    m_heb = re.search(r'(?:חלק|שיעור)\s+([א-י])[\'׳]?(?:\s|$)', t)
    if m_heb and m_heb.group(1) in UNITS:
        return UNITS[m_heb.group(1)] * 10
    # 3. Check side A / B
    if re.search(r'(?:^|\s|_)a(?:\s|$|\.)', t, re.I):
        return 10
    if re.search(r'(?:^|\s|_)b(?:\s|$|\.)', t, re.I):
        return 11
    if "final" in t.lower():
        return 9999
    return 0

def strip_part_for_series_stem(title):
    s = (title or "").strip()
    s = re.sub(r'\s*[-–|]*\s*(?:חלק|שיעור|פרק)\s+[א-ת\d"\'׳״]+(?:\s+שנת\s+תש[א-ת"\'׳״]+)?\s*$', '', s)
    s = re.sub(r'\s*[-–|]*\s*(?:Part|Pt\.?)\s*\d+\s*$', '', s, flags=re.I)
    s = re.sub(r'\s*#\s*(?:\d+|Final)\b.*$', '', s, flags=re.I)
    s = re.sub(r'^\d+\s*\|\s*', '', s)
    return s.strip(" -–|")

# ==============================================================================
# Translators / Normalizers for Google Drive English Folders -> Hebrew
# ==============================================================================
MELUKAT_HEB = {
    "vatah-tetzaveh": "ואתה תצוה", "podoh-bsholom": "פדה בשלום", "hayisheves-bganim": "היושבת בגנים",
    "es-havaya-heamarta": "את ה' האמרת", "vhaya-eikev": "והי' עקב", "hachodesh-hazeh": "החודש הזה לכם",
    "basukos-teishvu": "בסוכות תשבו", "havaya-li-bozri": "ה' לי בעוזרי", "balayla-hahu": "בלילה ההוא",
    "lhavin-inyan-neros-chanukah": "להבין ענין נרות חנוכה", "tziyon-bamishpat-tipadeh": "ציון במשפט תפדה",
    "bhaaloscha-es-haneros": "בהעלותך את הנרות", "vatah-yigdal-na": "ועתה יגדל נא",
    "vchazakta-vhayisa-lish": "וחזקת והיית לאיש", "zeh-hayom-asah-hashem": "זה היום עשה ה'",
    "lhovin-inyan-tchiyas-hameisim": "להבין ענין תחיית המתים", "vnacha-alav": "ונחה עליו",
    "vatah-yisroel": "ועתה ישראל", "ani-ldodi": "אני לדודי", "lcha-amar-libi": "לך אמר לבי",
    "zeh-hayom-techilas-maasecha": "זה היום תחילת מעשיך", "kumi-ori": "קומי אורי",
    "yom-tov-shel-rosh-hashanah": "יום טוב של ראש השנה", "hasam-nafsheinu-bachaim": "השם נפשנו בחיים",
    "lhovin-inyan-pesach-sheni": "להבין ענין פסח שני", "basi-lgani": "באתי לגני", "matza-zu": "מצה זו",
    "vayigash-eilav-yehudah": "ויגש אליו יהודה", "hashomayim-kisi": "השמים כסאי",
    "shuva-yisroel": "שובה ישראל", "habayim-yashresh-yaakov": "הבאים ישרש",
    "ulakachtem-lachem": "ולקחתם לכם", "kol-yisroel": "כל ישראל",
    "vavraham-zakein": "ואברהם זקן", "vatah-brachamecha-harabim": "ועתה ברחמיך הרבים",
    "vyitein-lcha": "ויתן לך", "amar-rav-oishia": "אמר רב אושעיא", "rani-vsimchi": "רני ושמחי",
    "shir-hamaalos-ldovid": "שיר המעלות הנה מה טוב", "vhinei-perach-matei-aharon": "והנה פרח מטה אהרן",
    "yehi-hashem-elokeinu-imanu": "יהי ה' אלקינו עמנו",
}

GD_MAAMAR_TRANSLIT = [
    ("adon olam", "אדון עולם"),
    ("al kein karu", "על כן קראו לימים וכו'"),
    ("al shloshah", "על שלשה דברים"),
    ("ani ledodi", "אני לדודי"),
    ("b'sukkos", "בסוכות תשבו"),
    ("balaylah", "בלילה ההוא"),
    ("baruch sheasah", "ברוך שעשה נסים"),
    ("basi legan", "באתי לגני"),
    ("bayom hasheini", "ביום השני הקריב"),
    ("bereishis bara", "בראשית ברא"),
    ("besha’ah shalah", "בשעה שעלה משה"),
    ("bachodesh hashlishi", "בחודש השלישי"),
    ("bicha botchu", "בך בטחו"),
    ("eleh toldos", "אלה תולדות נח"),
    ("es havaya", "את ה' האמרת"),
    ("gal einai", "גל עיני"),
    ("gadol yihiye", "גדול יהי' כבוד הבית"),
    ("hachodesh hazeh", "החודש הזה לכם"),
    ("hasom nafsheinu", "השם נפשנו בחיים"),
    ("hashomayim kisei", "השמים כסאי"),
    ("havayah li", "הוי' לי בעוזרי"),
    ("hayosheves", "היושבת בגנים"),
    ("katz sam", "קץ שם לחושך"),
    ("ki ishalcha", "כי ישאלך בנך"),
    ("kidoshim tehyu", "קדושים תהיו"),
    ("kimei tzeischah", "כימי צאתך"),
    ("kol yisroel", "כל ישראל"),
    ("lecha dodi", "לכה דודי"),
    ("lehavin..chanukah", "להבין ענין נרות חנוכה"),
    ("lehavin..techiyas", "להבין ענין תחיית המתים"),
    ("lehavin..torah", "להבין ענין התורה"),
    ("margela", "מרגלא בפומי' דרבא"),
    ("matza zu", "מצה זו"),
    ("mayim rabbim", "מים רבים"),
    ("mizmar lisosda", "מזמור לתודה"),
    ("pada b", "פדה בשלום"),
    ("padah b", "פדה בשלום"),
    ("pasach eliyahu", "פתח אליהו"),
    ("shuva yisroel", "שובה ישראל"),
    ("shuvah yisroel", "שובה ישראל"),
    ("tanu... ner", "ת\"ר מצות נר חנוכה"),
    ("tefilah l", "תפלה למשה"),
    ("tiyon bimishpat", "ציון במשפט תפדה"),
    ("tzion bemishpat", "ציון במשפט תפדה"),
    ("tziyon bimishpot", "ציון במשפט תפדה"),
    ("ulkachtem", "ולקחתם לכם"),
    ("v'atah te'tzaveh", "ואתה תצוה"),
    ("v’atah te’tzaveh", "ואתה תצוה"),
    ("v'atah yigdal", "ועתה יגדל נא"),
    ("v’atah yigdal", "ועתה יגדל נא"),
    ("v'chazaktah", "וחזקת והיית לאיש"),
    ("v’chazaktah", "וחזקת והיית לאיש"),
    ("v'isha achas", "ואשה אחת"),
    ("vaeirah el avraham", "וארא אל אברהם"),
    ("vayedaber elokim", "וידבר אלקים"),
    ("vayoimer...avrohom", "ויאמר ה' אל אברם"),
    ("vayatzay yakov", "ויצא יעקב"),
    ("ve'dovid avdi", "ודוד עבדי"),
    ("ve'eleh hamishpotim", "ואלה המשפטים"),
    ("vehaya eikev", "והי' עקב"),
    ("vehinei parach", "והנה פרח מטה אהרן"),
    ("venachah alav", "ונחה עליו"),
    ("vi'atah birachemchah", "ועתה ברחמיך הרבים"),
    ("yehi..elkeinu", "יהי ה' אלקינו עמנו"),
    ("yivchar lanu", "יבחר לנו"),
    ("yom tov shel rosh hashana", "יום טוב של ראש השנה"),
    ("zeh hayom", "זה היום עשה ה'"),
    ("zos chukas", "זאת חוקת התורה"),
    ("b’yom ashtei asar", "ביום עשתי עשר יום"),
]

def translate_maamar_name(raw, years=None):
    low = (raw or "").lower()
    heb = ""
    for k, v in GD_MAAMAR_TRANSLIT:
        if k in low:
            heb = v
            break
    yrs = years or extract_years(raw)[0]
    yr_str = f" - {yrs[0]}" if yrs else ""
    if heb:
        return f"{heb}{yr_str}"
    cleaned = re.sub(r'\(\s*57\d{2}\s*-?\s*\)|\b57\d{2}\b', '', raw or '').strip(" -_")
    return f"{cleaned}{yr_str}" if yr_str and yr_str not in cleaned else (cleaned or raw)

GD_TZ_MITZVA_MAP = {
    "eved ivri": "דין עבד עברי",
    "mitzvas tzitzis": "ציצית",
    "achdus hashem": "אחדות ה'",
    "ahvas yisroel": "אהבת ישראל",
    "hamanas elukus": "האמנת אלקות",
    "miny melech": "מינוי מלך",
    "miyla": "מילה",
    "tiglachas mitzra": "תגלחת המצורע",
    "yiud upidyon oma ivriya": "יעוד ופדיון אמה העבריה",
    "zichiras amalak": "זכירת ומחיית עמלק",
}

GD_RASHAB_66_MAP = {
    "001": 'יו"ט של ר"ה — תחלת ההמשך',
    "010": "ואברהם זקן - ויתן לך",
    "019-024": "המשך החודש הזה (י\"ט–כ\"ד)",
    "027": "ושאבתם מים בששון",
    "028": "במדבר סיני",
    "034": "אז ישיר ישראל",
    "035": "כי מראש אמנה",
    "051": "כל השונה הלכות - אם בחקותי",
    "053": 'בשעה שהקדימו (תרס"ז)',
}

# ==============================================================================
# Build Unified Dataset
# ==============================================================================
def build():
    unified = []

    # --------------------------------------------------------------------------
    # 1. HEICHALAPP (Chassidus App - 3,661 tracks)
    # --------------------------------------------------------------------------
    ha = json.load(open(os.path.join(CACHE_DIR, "heichalapp.json"), encoding="utf-8"))
    for it in ha:
        fn = it.get("fileName") or ""
        fp = it.get("filePath") or ""
        if not fn or not fp:
            continue
        paths = it.get("paths", [])
        sefer_paths = [p for p in paths if p and p[0] == "ספרים"]
        chosen = sorted(sefer_paths, key=lambda p: -len(p))[0] if sefer_paths else (sorted(paths, key=lambda p: -len(p))[0] if paths else [])
        all_paths_str = " | ".join(" > ".join(p) for p in paths)
        title = it["title"]
        subtitle = it.get("subtitle") or ""
        sub_parts = [x for x in chosen if x != "ר' יואל כהן"]
        if subtitle:
            sub_parts.append(subtitle)
        sub = " › ".join(sub_parts)
        parsha = detect_parsha_or_holiday(title, sub, all_paths_str)
        years, yn, decs = extract_years(title, sub)

        # Extract tape key + teaching year from fileName for Series Grouping
        m_kahn = re.search(r'(?:reb_)?yoel_kahn_(.+)$', fn, re.I)
        tape_code = ""
        teach_yr_heb = ""
        if m_kahn:
            rest = re.sub(r'(?:_part_\d+|_[a-z]|-\d+)$', '', m_kahn.group(1), flags=re.I)
            m_ty = re.match(r'(57\d{2})_(.+)$', rest)
            if m_ty:
                teach_yr_heb = num_to_hebrew_year(int(m_ty.group(1)))
                tape_code = m_ty.group(2)
            else:
                tape_code = rest
        else:
            tape_code = re.sub(r'^\d+-|_part_\d+$', '', fn)

        cat = "ספרים"
        r = ""
        b = ""
        v = "כללי"
        sec = title
        ts = "" # Tanya cycle series label
        ser = ""
        gid_key = ""

        # Classify strictly from chosen/all_paths into clean (cat, r, b, v, sec, ts, ser)
        p = chosen
        if p and p[0] == "ספרים" and len(p) >= 3:
            raw_r = p[1]
            raw_b = p[2]
            if raw_r == 'אדמו"ר הזקן':
                r = REBBE_ZAKEN
                if raw_b == "תניא":
                    sub_tanya = p[3] if len(p) > 3 else ""
                    if "שער היחוד" in sub_tanya:
                        b = 'תניא — שער היחוד והאמונה'
                    elif "אגרת התשובה" in sub_tanya:
                        b = 'תניא — אגרת התשובה'
                    elif "אגרת הקודש" in sub_tanya:
                        b = 'תניא — אגרת הקודש וקונטרס אחרון'
                    else:
                        b = 'תניא — לקוטי אמרים'
                    raw_series = next((seg for seg in p if "Series" in seg or "סדרה" in seg), "")
                    m_sn = re.search(r'(\d+)', raw_series)
                    if m_sn:
                        ts = f"סדרה {m_sn.group(1)}" + (" (שיעורים בטלפון)" if "בטלפון" in raw_series else (" — סיכום" if "סיכום" in raw_series else ""))
                    else:
                        ts = raw_series or "סדרה כללית"
                    raw_perek = next((seg for seg in p[4:] if any(k in seg for k in ["פרק", "שער", "הקדמה", "חינוך"])), "")
                    v = clean_tanya_perek(raw_perek or title) or "כללי"
                    sec = ts
                    ser = f"{ts} (היכל מנחם)"
                    gid_key = f"ha_tn_{b}_{ts}_{v}"
                else:
                    # תורה אור - לקוטי תורה
                    chumash = next((seg for seg in p if seg.startswith("ספר ") or seg.startswith("ימים טובים")), "")
                    par_seg = p[p.index(chumash) + 1] if (chumash and p.index(chumash) + 1 < len(p)) else ""
                    maamar = p[p.index(chumash) + 2] if (chumash and p.index(chumash) + 2 < len(p)) else title
                    is_to = chumash in ("ספר בראשית", "ספר שמות") or any(k in all_paths_str for k in ["חנוכה", "פורים", "מגילת אסתר"])
                    b = 'תורה אור' if is_to else 'לקוטי תורה'
                    if chumash == "ימים טובים - שיר השירים":
                        v = "חנוכה ופורים" if is_to else ("שיר השירים" if "שיר השירים" in par_seg else "ימים טובים — מועדים")
                    else:
                        v = chumash or "כללי"
                    sec = f"{par_seg} › {maamar}" if (par_seg and maamar and maamar != par_seg) else (maamar or par_seg or title)
                    gid_key = f"ha_tolt_{' > '.join(p)}_{tape_code}"

            elif raw_r == 'אדמו"ר צמח צדק':
                r = REBBE_ZZ
                b = 'דרך מצותיך'
                v = p[3] if len(p) > 3 else "כללי"
                raw_ser = next((seg for seg in p if "Series" in seg or "סדרה" in seg), "")
                sec = v
                m_sn = re.search(r'(\d+)', raw_ser)
                ser = f"סדרה #{m_sn.group(1)} (היכל מנחם)" if m_sn else ("היכל מנחם")
                gid_key = f"ha_zz_{v}_{raw_ser or tape_code}"

            elif raw_r == 'אדמו"ר הרש"ב':
                r = REBBE_RASHAB
                if 'תרס"ו' in raw_b:
                    b = 'המשך תרס"ו (ס"ו)'
                    v = p[3] if len(p) > 3 else title
                    sec = p[4] if len(p) > 4 else v
                elif 'תער"ב' in raw_b:
                    b = 'המשך תער"ב (ע"ב)'
                    v = p[3] if len(p) > 3 else title
                    sec = p[4] if len(p) > 4 else v
                else:
                    b = 'ספרי המאמרים וקונטרסים'
                    v = raw_b
                    sec = p[3] if len(p) > 3 else title
                gid_key = f"ha_rsb_{b}_{v}_{sec}_{tape_code}"

            elif raw_r == 'אדמו"ר הריי"צ':
                r = REBBE_RAYYATZ
                b = 'ספרי המאמרים וקונטרסים'
                v = raw_b
                sec = p[3] if len(p) > 3 else title
                gid_key = f"ha_ryy_{v}_{sec}_{tape_code}"

            elif raw_r == 'אדמו"ר זי"ע':
                r = REBBE_LUBAVITCH
                if raw_b == 'לקוטי שיחות':
                    b = 'ליקוטי שיחות'
                    hlk = [x for x in paths if "לקוטי שיחות" in x and "חלקים" in x]
                    if hlk:
                        hp = hlk[0]
                        idx = hp.index("חלקים")
                        raw_vol = hp[idx + 1] if len(hp) > idx + 1 else "כללי"
                        v = normalize_ls_chelek(raw_vol[4:]) if raw_vol.startswith("חלק ") else raw_vol
                        sec = hp[idx + 2] if len(hp) > idx + 2 else (parsha or title)
                    else:
                        v = "שיחות לפי פרשה / מועד"
                        sec = parsha or title
                        for x in paths:
                            for seg in x:
                                m = re.match(r'חלק\s+([^\s-]+)(?:\s*-\s*(.+))?', seg)
                                if m:
                                    v = normalize_ls_chelek(m.group(1))
                                    sec = m.group(2).strip() if m.group(2) else (parsha or title)
                    gid_key = f"ha_ls_{v}_{sec}_{tape_code}"
                elif raw_b == 'ספר המאמרים מלוקט':
                    b = 'ספר המאמרים מלוקט'
                    mlk = [x for x in paths if "ספר המאמרים מלוקט" in x and "חלקים" in x]
                    if mlk:
                        hp = mlk[0]
                        idx = hp.index("חלקים")
                        v = hp[idx + 1] if len(hp) > idx + 1 else "כללי"
                        sec = hp[idx + 2] if len(hp) > idx + 2 else title
                    else:
                        v = "מאמרים מלוקטים — כללי"
                        sec = p[-1] if p else title
                    raw_ser = next((seg for seg in p if "Series" in seg or "Seires" in seg), "")
                    m_sn = re.search(r'(\d+)', raw_ser)
                    if m_sn:
                        ser = f"סדרה #{m_sn.group(1)} (היכל מנחם)"
                    gid_key = f"ha_mlk_{v}_{sec}_{raw_ser or tape_code}"
                elif raw_b in ('חזרות מהתוועדות רבינו', 'לקט חזרות מהתוועדות רבינו'):
                    cat = "חזרות והתוועדויות"
                    r = ""
                    b = 'חזרות על התוועדויות הרבי'
                    month = next((seg for seg in p if seg in HEB_MONTHS), "")
                    v = years[0] if years else (month or "שנים שונות")
                    sec = f"{month} — {parsha or title}" if (month and years) else (parsha or title)
                    gid_key = f"ha_chz_{v}_{month}_{parsha}_{tape_code}"
                elif raw_b == 'קונטרסים':
                    b = 'קונטרסים'
                    v = p[3] if len(p) > 3 else "קונטרסים"
                    raw_ser = next((seg for seg in p if "Series" in seg or "Seires" in seg), "")
                    sec = re.sub(r'\s*[-–#]*\s*\d+\s*$', '', title).strip()
                    m_sn = re.search(r'(\d+)', raw_ser)
                    ser = f"סדרה #{m_sn.group(1)} (היכל מנחם)" if m_sn else "היכל מנחם"
                    gid_key = f"ha_knt_{v}_{raw_ser or tape_code}"
                elif raw_b == 'הדרנים':
                    b = 'הדרנים'
                    v = p[3] if len(p) > 3 else "הדרנים"
                    sec = title
                    raw_ser = next((seg for seg in p if "Series" in seg), "")
                    gid_key = f"ha_hdr_{v}_{raw_ser or tape_code}"
                elif 'תורת מנחם' in raw_b:
                    b = 'מאמרים (בלתי מוגה ותורת מנחם)'
                    v = 'תורת מנחם — מאמרים'
                    sec = p[3] if len(p) > 3 else title
                    gid_key = f"ha_tm_{sec}_{tape_code}"
                else:
                    # ספר השיחות תשמ"ט / רשימות
                    b = 'ספר השיחות ורשימות'
                    v = raw_b
                    sec = p[3] if (len(p) > 3 and "ר' יואל" not in p[3]) else (parsha or title)
                    gid_key = f"ha_ss_{v}_{sec}_{tape_code}"
        else:
            # Non-ספרים categories in Heichal App
            top = p[0] if p else ""
            if top == "פרשיות":
                cat = "פרשיות השבוע"
                b = p[1] if len(p) > 1 and p[1].startswith("ספר ") else (PARSHA_TO_CHUMASH.get(parsha, "פרשיות כללי"))
                v = parsha or (p[2] if len(p) > 2 else "כללי")
                sec = strip_part_for_series_stem(title)
                gid_key = f"ha_par_{v}_{tape_code}"
            elif top == "ענינא דיומא":
                cat = "ענינא דיומא"
                b = next((seg for seg in p if seg in HEB_MONTHS), "") or HOLIDAY_TO_MONTH.get(parsha, "מועדי השנה")
                v = parsha or (p[2] if len(p) > 2 else "מועדים")
                sec = strip_part_for_series_stem(title)
                gid_key = f"ha_yd_{b}_{v}_{tape_code}"
            elif top == "התוועדות חסידים":
                cat = "חזרות והתוועדויות"
                b = 'התוועדויות חסידים וזיכרונות'
                v = next((seg for seg in p if seg in HEB_MONTHS), "") or HOLIDAY_TO_MONTH.get(parsha, "מועדי השנה")
                sec = parsha or (p[2] if len(p) > 2 else strip_part_for_series_stem(title))
                gid_key = f"ha_far_{v}_{sec}_{tape_code}"
            elif top == "נושאים":
                cat = "סוגיות בחסידות"
                b = 'מושגים וסוגיות בחסידות'
                v = p[1] if len(p) > 1 else "כללי"
                sec = strip_part_for_series_stem(title)
                gid_key = f"ha_top_{v}_{tape_code}"
            elif top == "ניגונים":
                cat = "ניגונים"
                b = p[2] if len(p) > 2 else "ניגוני חב\"ד"
                v = "ניגוני התוועדות"
                sec = title
                gid_key = f"ha_nig_{it['id']}"
            else:
                cat = "סוגיות בחסידות"
                b = 'מושגים וסוגיות בחסידות'
                v = "שונות"
                sec = title
                gid_key = f"ha_oth_{it['id']}"

        if not ser:
            ser = f"סדרה ({teach_yr_heb} — היכל מנחם)" if teach_yr_heb else "היכל מנחם"

        fname_enc = urllib.parse.quote(fn, safe="")
        mp3 = f"https://media.heichalapp.com/{fp}{fname_enc}.mp3"
        unified.append({
            "id": f"ha_{it['id']}",
            "t": title,
            "cat": cat,
            "r": r,
            "b": b,
            "v": v,
            "sec": sec,
            "ser": ser,
            "ts": ts,
            "gid": gid_key,
            "ord": extract_part_order(title, fn),
            "sub": sub,
            "l": ["yi"],
            "f": ["audio"],
            "y": years,
            "yn": yn,
            "decs": decs,
            "p": parsha,
            "d": int(it.get("duration") or 0),
            "src": "heichal",
            "au": mp3,
            "pg": f"https://chassidus-content.com/yi/player/{it['id']}",
        })

    # --------------------------------------------------------------------------
    # 2. PODCASTS (Anchor RSS Feeds)
    # --------------------------------------------------------------------------
    pods = json.load(open(os.path.join(CACHE_DIR, "podcasts.json"), encoding="utf-8"))
    tanya_pods = list(reversed([ep for ep in pods if ep["source"] == "podcast_tanya"]))
    other_pods = [ep for ep in pods if ep["source"] != "podcast_tanya"]
    for idx_pt, ep in enumerate(tanya_pods + other_pods, start=1):
        src = ep["source"]
        title = ep["title"]
        desc = ep.get("desc", "")
        years, yn, decs = extract_years(title, desc)
        parsha = detect_parsha_or_holiday(title, desc)
        cat, r, b, v, sec, ser, ts, gid_key, ord_n = "", "", "", "כללי", title, "", "", "", extract_part_order(title)
        langs = ["yi"]

        if src == "podcast_chazara":
            cat, b = "חזרות והתוועדויות", "חזרות על התוועדויות הרבי"
            v = years[0] if years else "שנים שונות"
            sec = parsha or title
            ser = "פודקאסט חזרות הרבי"
            gid_key = f"pod_chz_{ep['idx']}"
            sub = "חזרה של ר' יואל מהתוועדות הרבי"
        elif src == "podcast_tanya":
            cat, r, b = "ספרים", REBBE_ZAKEN, 'תניא — לקוטי אמרים'
            langs = ["he"]
            perek = clean_tanya_perek(title)
            v = perek if ("פרק" in perek or "שער" in perek or "הקדמה" in perek) else "כללי"
            ts = "פודקאסט תניא בעברית (56 שיעורים)"
            sec = ts
            ser = ts
            gid_key = f"pod_tanya_{v}"
            m_num = re.match(r'^0*(\d+)', title.strip())
            ord_n = int(m_num.group(1)) * 10 if m_num else idx_pt * 10
            sub = "שיעורי תניא בעברית"
        elif src == "podcast_fabrenguen":
            cat, b = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות"
            langs = ["he"]
            v = HOLIDAY_TO_MONTH.get(parsha, "") or (years[0] if years else "התוועדויות")
            stem = strip_part_for_series_stem(title)
            sec = parsha or stem
            ser = "פודקאסט התוועדויות בעברית"
            gid_key = f"pod_fab_{stem}"
            sub = "התוועדות בעברית"
        else:
            # study chassidus podcast
            langs = ["yi", "en"]
            stem = strip_part_for_series_stem(title)
            low_all = (title + " " + desc).lower()
            if "tanya" in low_all or "תניא" in low_all:
                cat, r, b = "ספרים", REBBE_ZAKEN, 'תניא — לקוטי אמרים'
                v = clean_tanya_perek(title) or "שיעורים כלליים"
                ts = "Study Chassidus (אנגלית)"
            elif "what is chassidus" in low_all or "inyana shel toras hachassidus" in low_all:
                cat, r, b = "ספרים", REBBE_LUBAVITCH, "קונטרסים"
                v = "קונטרס ענינה של תורת החסידות"
                stem = "קונטרס ענינה של תורת החסידות"
            elif "haumnom" in low_all:
                cat, r, b = "ספרים", REBBE_RASHAB, 'ספרי המאמרים וקונטרסים'
                v = 'ספר המאמרים תרמ"ג'
            elif any(k in low_all for k in ["basi legani", "zeh hayom", "veavdi", "vechozakta", "vechozokto", "vaera 5735"]):
                cat, r, b = "ספרים", REBBE_LUBAVITCH, 'ספר המאמרים מלוקט'
                v = "לפי מועדי השנה" if ("basi legani" in low_all or "zeh hayom" in low_all) else "מאמרים מלוקטים — כללי"
            elif "chanukah" in low_all:
                cat, b, v = "ענינא דיומא", "כסלו", "חנוכה"
            else:
                cat, b = "סוגיות בחסידות", "מושגים וסוגיות בחסידות"
                v = stem
            sec = stem
            ser = "Study Chassidus Podcast"
            gid_key = f"pod_stu_{stem}"
            sub = "Study Chassidus (שיעורים משוחזרים)"

        unified.append({
            "id": f"pod_{src}_{ep['idx']}",
            "t": title,
            "cat": cat, "r": r, "b": b, "v": v, "sec": sec, "ser": ser, "ts": ts,
            "gid": gid_key, "ord": ord_n,
            "sub": sub,
            "l": langs, "f": ["audio"], "y": years, "yn": yn, "decs": decs, "p": parsha,
            "d": int(ep.get("duration") or 0), "src": src,
            "au": ep["mp3"], "pg": ep.get("link") or "",
        })

    # --------------------------------------------------------------------------
    # 3. VIDEO.CHASIDUT.NET (364 videos)
    # --------------------------------------------------------------------------
    vc = json.load(open(os.path.join(CACHE_DIR, "video_chasidut.json"), encoding="utf-8"))
    for v_item in vc:
        title = v_item["title"]
        desc = v_item.get("desc", "")
        tags = v_item.get("tags", "")
        blob = f"{title} {desc} {tags}"
        langs = []
        if "לשון הקודש" in blob or "עברית" in blob:
            langs.append("he")
        if "אידיש" in blob or "יידיש" in blob or not langs:
            langs.append("yi")
        years, yn, decs = extract_years(title, desc)
        parsha = detect_parsha_or_holiday(title, desc, tags)
        stem = strip_part_for_series_stem(title)
        cat, r, b, vol, sec, ts = "", "", "", "כללי", stem, ""

        if "לקוטי שיחות" in blob or "ליקוטי שיחות" in blob or 'לקו"ש' in blob or "לקו”ש" in blob or "הדרן" in blob:
            cat, r = "ספרים", REBBE_LUBAVITCH
            if "הדרן" in blob:
                b = 'הדרנים'
                vol = "הדרנים על הרמב\"ם" if "רמב" in blob else "הדרנים"
            else:
                b = 'ליקוטי שיחות'
                vol = extract_ls_chelek_from_text(blob) or PARSHA_TO_CHUMASH.get(parsha, "שיחות שונות")
        elif "דרך מצוותיך" in blob or "דרך מצותיך" in blob:
            cat, r, b = "ספרים", REBBE_ZZ, "דרך מצותיך"
            vol = "מצות אחדות ה'" if "אחדות" in blob else stem
            sec = vol
        elif "קונטרס" in blob or "קונטרוס" in blob:
            cat, r, b = "ספרים", REBBE_LUBAVITCH, "קונטרסים"
            vol = "קונטרס ענינה של תורת החסידות" if "ענינה" in blob else stem
            sec = vol
        elif "תניא" in blob or "ספר של בינונים" in blob or "שער היחוד" in blob or "אגרת התשובה" in blob or "אגרת הקודש" in blob:
            cat, r = "ספרים", REBBE_ZAKEN
            if "שער היחוד" in blob: b = 'תניא — שער היחוד והאמונה'
            elif "אגרת התשובה" in blob: b = 'תניא — אגרת התשובה'
            elif "אגרת הקודש" in blob: b = 'תניא — אגרת הקודש וקונטרס אחרון'
            else: b = 'תניא — לקוטי אמרים'
            perek = clean_tanya_perek(blob)
            vol = perek if ("פרק" in perek or "שער" in perek or "חינוך" in perek) else "כללי"
            ts = "וידאו חסידות.נט"
            sec = ts
        elif "תורה אור" in blob:
            cat, r, b = "ספרים", REBBE_ZAKEN, 'תורה אור'
            vol = PARSHA_TO_CHUMASH.get(parsha, "חנוכה ופורים" if parsha in ("חנוכה", "פורים") else "כללי")
            sec = stem
        elif "לקוטי תורה" in blob or "ליקוטי תורה" in blob:
            cat, r, b = "ספרים", REBBE_ZAKEN, 'לקוטי תורה'
            vol = PARSHA_TO_CHUMASH.get(parsha, "ימים טובים — מועדים")
            sec = stem
        elif 'תרס"ו' in blob or 'ס"ו' in blob:
            cat, r, b = "ספרים", REBBE_RASHAB, 'המשך תרס"ו (ס"ו)'
            vol = stem
        elif 'תער"ב' in blob or 'ע"ב' in blob:
            cat, r, b = "ספרים", REBBE_RASHAB, 'המשך תער"ב (ע"ב)'
            vol = stem
        elif 'רש"ב' in blob:
            cat, r, b = "ספרים", REBBE_RASHAB, 'ספרי המאמרים וקונטרסים'
            vol = years[0] if years else "מאמרים"
        elif 'ריי"צ' in blob:
            cat, r, b = "ספרים", REBBE_RAYYATZ, 'ספרי המאמרים וקונטרסים'
            vol = years[0] if years else "מאמרים"
        elif "מאמר" in title or "ד\"ה" in title or "דה " in title:
            if yn and yn < 5680:
                cat, r, b = "ספרים", REBBE_RASHAB, 'ספרי המאמרים וקונטרסים'
                vol = f"ספר המאמרים {years[0]}" if years else "מאמרים"
                if "וידעת" in blob:
                    sec = 'וידעת - מאסקאווא (תרנ"ז)'
            elif (yn and yn < 5710) or ("באתי לגני" in blob and yn == 5710):
                cat, r, b = "ספרים", REBBE_RAYYATZ, 'ספרי המאמרים וקונטרסים'
                vol = f"ספר המאמרים {years[0]}" if years else "מאמרים"
            else:
                cat, r, b = "ספרים", REBBE_LUBAVITCH, 'ספר המאמרים מלוקט'
                vol = years[0] if years else (PARSHA_TO_CHUMASH.get(parsha, "מאמרים"))
        elif "התוועדות" in blob:
            cat, b = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות"
            vol = HOLIDAY_TO_MONTH.get(parsha, "") or (years[0] if years else "התוועדויות")
        elif parsha and parsha in PARSHA_TO_CHUMASH:
            cat, b = "פרשיות השבוע", PARSHA_TO_CHUMASH[parsha]
            vol = parsha
        elif parsha and parsha in HOLIDAY_TO_MONTH:
            cat, b = "ענינא דיומא", HOLIDAY_TO_MONTH[parsha]
            vol = parsha
        else:
            cat, b = "סוגיות בחסידות", "מושגים וסוגיות בחסידות"
            vol = stem

        unified.append({
            "id": f"vc_{v_item['id']}",
            "t": title,
            "cat": cat, "r": r, "b": b, "v": vol, "sec": sec,
            "ser": "סדרת וידאו (חסידות.נט)", "ts": ts,
            "gid": f"vc_{stem}", "ord": extract_part_order(title),
            "sub": (desc[:120] if desc else tags) or "וידאו חסידות.נט",
            "l": langs, "f": ["video"], "y": years, "yn": yn, "decs": decs, "p": parsha,
            "d": 0, "src": "video_chasidut", "vi": v_item.get("mp4") or "", "pg": v_item["url"],
        })

    # --------------------------------------------------------------------------
    # 4. MERKAZ ANASH + MONSEY
    # --------------------------------------------------------------------------
    merkaz = json.load(open(os.path.join(CACHE_DIR, "merkaz_anash.json"), encoding="utf-8"))
    monsey = json.load(open(os.path.join(CACHE_DIR, "monsey.json"), encoding="utf-8"))
    monsey_by_file = {}
    monsey_other = []
    for m in monsey:
        if m.get("isShortVort") and m.get("mp3"):
            monsey_by_file[m["mp3"].split("/")[-1].lower()] = m
        else:
            monsey_other.append(m)

    used_monsey_files = set()
    for idx, ma in enumerate(merkaz):
        mp3 = ma.get("mp3", "")
        fn = mp3.split("/")[-1].lower() if mp3 else ""
        paired = monsey_by_file.get(fn)
        if paired:
            used_monsey_files.add(fn)
        title = f"{paired['title']} — {ma['title']}" if (paired and paired.get("title")) else ma["title"]
        mekor = (paired.get("mekor") if paired else "") or ""
        sub_parts = ["Chassidus Perspective"] + ([mekor] if mekor else ([ma["hint"]] if ma.get("hint") else []))
        fmts = ([f for f, u in [("audio", mp3), ("video", ma.get("mp4")), ("pdf", ma.get("pdf"))] if u]) or ["video"]
        langs = ["yi", "en"] if ma.get("pdf") or ma.get("mp4") else ["yi"]
        years, yn, decs = extract_years(title, ma.get("slug", ""), ma.get("hint", ""))
        parsha = detect_parsha_or_holiday(title, ma.get("slug", ""), ma.get("hint", ""))

        norm_mekor = mekor.replace("״", '"').replace("”", '"').replace("׳", "'").replace("’", "'")
        if norm_mekor and ('לקו"ש' in norm_mekor or "לקוטי שיחות" in norm_mekor or "ליקוטי שיחות" in norm_mekor):
            cat, r, b = "ספרים", REBBE_LUBAVITCH, 'ליקוטי שיחות'
            vol = extract_ls_chelek_from_text(norm_mekor) or "שיחות לפי פרשה / מועד"
            sec = parsha or title
        elif parsha and parsha in PARSHA_TO_CHUMASH:
            cat, r, b, vol, sec = "פרשיות השבוע", "", PARSHA_TO_CHUMASH[parsha], parsha, title
        else:
            cat, r, b, vol, sec = "ענינא דיומא", "", HOLIDAY_TO_MONTH.get(parsha, "מועדי השנה"), parsha or "מועדים", title

        unified.append({
            "id": f"ma_{idx}", "t": title,
            "cat": cat, "r": r, "b": b, "v": vol, "sec": sec,
            "ser": "Chassidus Perspective (מרכז אנ\"ש)", "ts": "", "gid": f"ma_{idx}", "ord": 10,
            "sub": " • ".join(sub_parts), "l": langs, "f": fmts,
            "y": years, "yn": yn, "decs": decs, "p": parsha, "d": 0, "src": "merkaz_anash",
            "au": mp3, "vi": ma.get("mp4", ""), "pd": ma.get("pdf", ""), "pg": ma["url"],
        })

    for idx, m in enumerate(list(monsey_by_file.values()) + monsey_other):
        mp3 = m.get("mp3", "").replace("http://www.merkazanash.com", "https://merkazanash.com").replace("http://merkazanash.com", "https://merkazanash.com")
        mp4 = m.get("mp4", "").replace("http://www.merkazanash.com", "https://merkazanash.com").replace("http://merkazanash.com", "https://merkazanash.com")
        pdf = m.get("pdf", "").replace("http://www.merkazanash.com", "https://merkazanash.com").replace("http://merkazanash.com", "https://merkazanash.com")
        fn = mp3.split("/")[-1].lower() if mp3 else ""
        if m.get("isShortVort") and fn in used_monsey_files:
            continue
        title = m["title"]
        mekor = m.get("mekor") or ""
        fmts = [k for k, cond in [("audio", mp3), ("video", mp4 or m.get("youtube")), ("pdf", pdf)] if cond] or ["audio"]
        langs = ["yi", "en"] if pdf else ["yi", "he"]
        years, yn, decs = extract_years(title, m.get("slug", ""))
        parsha = detect_parsha_or_holiday(title, m.get("slug", ""))
        cat, r, b, vol, sec = "סוגיות בחסידות", "", "מושגים וסוגיות בחסידות", "שונות", title
        norm_title = title.replace("״", '"').replace("”", '"').replace("׳", "'").replace("’", "'")
        norm_mekor = mekor.replace("״", '"').replace("”", '"').replace("׳", "'").replace("’", "'")
        if norm_mekor and ('לקו"ש' in norm_mekor or "לקוטי שיחות" in norm_mekor or "ליקוטי שיחות" in norm_mekor):
            cat, r, b = "ספרים", REBBE_LUBAVITCH, 'ליקוטי שיחות'
            vol = extract_ls_chelek_from_text(norm_mekor) or "שיחות לפי פרשה / מועד"
            sec = parsha or title
        elif "אגרת התשובה" in norm_title or "שער היחוד" in norm_title:
            cat, r = "ספרים", REBBE_ZAKEN
            b = 'תניא — אגרת התשובה' if "אגרת התשובה" in norm_title else 'תניא — שער היחוד והאמונה'
            vol, sec = "כללי", title
        elif "likutei torah" in m.get("slug", "").replace("_", " ").lower() or "אני לדודי" in norm_title:
            cat, r, b, vol, sec = "ספרים", REBBE_ZAKEN, 'לקוטי תורה', 'שיר השירים / אלול', 'אני לדודי'
        elif "התוועדות" in norm_title:
            cat, b = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות"
            vol = HOLIDAY_TO_MONTH.get(parsha, "") or (years[0] if years else "התוועדויות")
            sec = parsha or title
        elif parsha and parsha in PARSHA_TO_CHUMASH:
            cat, b, vol, sec = "פרשיות השבוע", PARSHA_TO_CHUMASH[parsha], parsha, title
        elif parsha and parsha in HOLIDAY_TO_MONTH:
            cat, b, vol, sec = "ענינא דיומא", HOLIDAY_TO_MONTH[parsha], parsha, title
        elif "תשובה" in norm_title:
            vol = "מצות התשובה"

        unified.append({
            "id": f"mon_{idx}", "t": title,
            "cat": cat, "r": r, "b": b, "v": vol, "sec": sec,
            "ser": "היכל מנחם מאנסי", "ts": "", "gid": f"mon_{idx}", "ord": 10,
            "sub": mekor or "היכל מנחם מאנסי", "l": langs, "f": fmts,
            "y": years, "yn": yn, "decs": decs, "p": parsha, "d": 0, "src": "monsey",
            "au": mp3, "vi": mp4 or (f"yt:{m['youtube']}" if m.get("youtube") else ""), "pd": pdf, "pg": m["url"],
        })

    # --------------------------------------------------------------------------
    # 5. PROJECT MELUKAT
    # --------------------------------------------------------------------------
    mel = json.load(open(os.path.join(CACHE_DIR, "melukat.json"), encoding="utf-8"))
    for idx, pm in enumerate(mel):
        slug = pm.get("slug", "")
        base_slug = re.sub(r"-57\d{2}$", "", slug)
        heb_name = MELUKAT_HEB.get(base_slug, "")
        pretty_slug = slug.replace("-", " ").title()
        is_pdf = pm.get("isPdf", False)
        drive_id = pm.get("driveId", "")
        drive_preview = f"https://drive.google.com/file/d/{drive_id}/preview" if drive_id else ""
        years, yn, decs = extract_years(slug)
        parsha = detect_parsha_or_holiday(slug, heb_name)
        yr_he = f" - {years[0]}" if years else ""
        display_name = heb_name if heb_name else pretty_slug
        title = f"מאמר ד\"ה {display_name}{yr_he} — " + ("דפי לימוד וביאור (PDF)" if is_pdf else "דף המאמר (PDF) וקישור לשיעור")
        if is_pdf:
            cat, r, b, vol, sec = "ספרים וכתבים (PDF)", "", "דפי מאמרים מלוקט (Project Melukat PDF)", "דפי לימוד וביאור", f"{display_name}{yr_he}"
        else:
            cat, r, b, vol, sec = "ספרים", REBBE_LUBAVITCH, 'ספר המאמרים מלוקט', "מאמרים מלוקטים — כללי", f"{display_name}{yr_he}"
        unified.append({
            "id": f"pm_{idx}", "t": title,
            "cat": cat, "r": r, "b": b, "v": vol, "sec": sec,
            "ser": "Project Melukat", "ts": "", "gid": f"pm_{idx}", "ord": 10,
            "sub": f"ספר המאמרים מלוקט (Project Melukat — דף המאמר וקישור לשיעור) • {pretty_slug}",
            "l": ["he"] if is_pdf else ["he", "yi"], "f": ["pdf"] if drive_preview else [],
            "y": years, "yn": yn, "decs": decs, "p": parsha, "d": 0, "src": "melukat",
            "pd": drive_preview, "dr": "",
            "vi": "", "au": "", "pg": pm["url"],
        })

    # --------------------------------------------------------------------------
    # 6. YOUTUBE & SINUN770
    # --------------------------------------------------------------------------
    YT_MELUKAT_MAAMARIM = [
        ("pada beshalom", 'פדה בשלום (תשכ"ו)', "חלק ו'"),
        ("venacha alav", 'ונחה עליו (תשכ"ה)', "חלק ב'"),
        ("bachodesh hashlishi", 'בחודש השלישי (תשכ"ט)', "חלק ד'"),
        ("balaila hahu", 'בלילה ההוא (תשכ"ה)', "חלק ד'"),
        ("gadol ihie", 'גדול יהיה כבוד הבית (תשכ"ב)', "חלק ד'"),
        ("baruch sheasa", 'ברוך שעשה נסים (תשט"ו)', "חלק ה'"),
        ("patach eliahu", 'פתח אליהו (תשט"ו)', "חלק ה'"),
        ("lehavin inyan nerot", 'להבין ענין נרות חנוכה (תשכ"ו)', "חלק ו'"),
        ("margela bepumei", 'מרגלא בפומיה (תש"מ)', "מאמרים מלוקטים — כללי"),
        ("vele pikudei", 'ואלה פקודי', "מאמרים מלוקטים — כללי"),
        ("beyom ashtei asar", 'ביום עשתי עשר (תשל"א)', "חלק ג'"),
        ("vedavid avdi", 'ודויד עבדי (תשל"ב)', "חלק ו'"),
        ("bati legani", 'באתי לגני (תשל"ב)', "חלק ו'"),
        ("rani vessimcha", 'רוני ושמחי (תשכ"ז)', "חלק ד'"),
    ]
    yts = json.load(open(os.path.join(CACHE_DIR, "youtube.json"), encoding="utf-8"))
    for yt in yts:
        title = yt["title"]
        series = yt.get("series", "")
        blob = f"{title} {series}"
        low_blob = blob.lower()
        years, yn, decs = extract_years(title, series)
        parsha = detect_parsha_or_holiday(title)
        stem = strip_part_for_series_stem(title)
        gid_key = f"yt_{stem}"
        mlk_hit = next((m for m in YT_MELUKAT_MAAMARIM if m[0] in low_blob), None)
        if "תניא" in blob or "tanya" in low_blob:
            cat, r, b = "ספרים", REBBE_ZAKEN, 'תניא — לקוטי אמרים'
            vol = clean_tanya_perek(blob) or "כללי"
            sec, ts = "יוטיוב", "סדרת יוטיוב"
        elif "לקוטי תורה" in blob or "ליקוטי תורה" in blob:
            cat, r, b, vol, sec, ts = "ספרים", REBBE_ZAKEN, 'לקוטי תורה', 'שיר השירים / אלול', 'אני לדודי', ""
        elif "ayen bet" in low_blob:
            cat, r, b, vol, sec, ts = "ספרים", REBBE_RASHAB, 'המשך תער"ב (ע"ב)', 'כללי (ע"ב)', stem, ""
        elif mlk_hit:
            _, ma_sec, ma_vol = mlk_hit
            cat, r, b, vol, sec, ts = "ספרים", REBBE_LUBAVITCH, 'ספר המאמרים מלוקט', ma_vol, ma_sec, ""
            gid_key = f"yt_mlk_{ma_sec}"
        elif "התוועדות" in blob or "התועדות" in blob or "farbrengen" in low_blob:
            cat, r, b, vol, sec, ts = "חזרות והתוועדויות", "", "התוועדויות חסידים וזיכרונות", years[0] if years else "כללי", stem, ""
        elif parsha and parsha in PARSHA_TO_CHUMASH:
            cat, r, b, vol, sec, ts = "פרשיות השבוע", "", PARSHA_TO_CHUMASH[parsha], parsha, stem, ""
        elif parsha and parsha in HOLIDAY_TO_MONTH:
            cat, r, b, vol, sec, ts = "ענינא דיומא", "", HOLIDAY_TO_MONTH[parsha], parsha, stem, ""
        else:
            cat, r, b, vol, sec, ts = "סוגיות בחסידות", "", "מושגים וסוגיות בחסידות", series or "וידאו", stem, ""
        unified.append({
            "id": f"yt_{yt['videoId']}", "t": title,
            "cat": cat, "r": r, "b": b, "v": vol, "sec": sec,
            "ser": series or "יוטיוב / סינון 770", "ts": ts,
            "gid": gid_key, "ord": extract_part_order(title),
            "sub": series, "l": [yt.get("lang", "yi")], "f": ["video"],
            "y": years, "yn": yn, "decs": decs, "p": parsha, "d": 0, "src": "youtube",
            "vi": f"yt:{yt['videoId']}", "pg": yt.get("sinunUrl") or yt["url"],
        })

    # --------------------------------------------------------------------------
    # 7. OTZER HACHASSIDUS (public items)
    # --------------------------------------------------------------------------
    ot = json.load(open(os.path.join(CACHE_DIR, "otzer.json"), encoding="utf-8"))
    for o in ot:
        title = o["title"]
        langs = []
        lang_vals = " ".join(str(v) for v in (o.get("oz_lang") or {}).values())
        if "לשון הקודש" in lang_vals or "עברית" in lang_vals:
            langs.append("he")
        if "אידיש" in lang_vals or not langs:
            langs.append("yi")
        lit_vals = " ".join(list(v.values())[0] if isinstance(v, dict) else str(v) for v in (o.get("oz_litwork") or {}).values())
        top_vals = " ".join(list(v.values())[0] if isinstance(v, dict) else str(v) for v in (o.get("oz_topic") or {}).values())
        years, yn, decs = extract_years(title, lit_vals)
        parsha = detect_parsha_or_holiday(title, top_vals)
        stem = strip_part_for_series_stem(title)
        blob = f"{title} {lit_vals}"
        if "מלוקט" in blob:
            cat, r, b = "ספרים", REBBE_LUBAVITCH, 'ספר המאמרים מלוקט'
            vol = "לפי מועדי השנה" if not parsha else PARSHA_TO_CHUMASH.get(parsha, "כללי")
            sec = stem
        elif "קונטרס" in blob:
            cat, r, b, vol, sec = "ספרים", REBBE_LUBAVITCH, "קונטרסים", "קונטרס ענינה של תורת החסידות", "קונטרס ענינה של תורת החסידות"
        elif "תניא" in blob:
            cat, r, b, vol, sec = "ספרים", REBBE_ZAKEN, 'תניא — לקוטי אמרים', clean_tanya_perek(blob) or "כללי", "אוצר החסידות"
        elif "רש\"ב" in blob or 'תרס"ו' in blob or 'תער"ב' in blob:
            cat, r, b, vol, sec = "ספרים", REBBE_RASHAB, 'ספרי המאמרים וקונטרסים', years[0] if years else "מאמרים", stem
        elif "פרשה" in title or (parsha and parsha in PARSHA_TO_CHUMASH):
            cat, r, b, vol, sec = "פרשיות השבוע", "", PARSHA_TO_CHUMASH.get(parsha, "פרשיות כללי"), parsha or "כללי", stem
        else:
            cat, r, b, vol, sec = "ספרים", REBBE_LUBAVITCH, 'ספר המאמרים מלוקט', years[0] if years else "כללי", stem
        dur = 0
        if o.get("length"):
            pts = [int(x) for x in o["length"].split(":") if x.isdigit()]
            if len(pts) == 2: dur = pts[0]*60 + pts[1]
            elif len(pts) == 3: dur = pts[0]*3600 + pts[1]*60 + pts[2]
        pdf = o.get("attachment") or ""
        unified.append({
            "id": f"oz_{o['id']}", "t": title,
            "cat": cat, "r": r, "b": b, "v": vol, "sec": sec,
            "ser": "אוצר החסידות", "ts": "", "gid": f"oz_{stem}", "ord": extract_part_order(title),
            "sub": lit_vals or o.get("courtesy") or "אוצר החסידות",
            "l": langs, "f": ["audio", "pdf"] if pdf else ["audio"],
            "y": years, "yn": yn, "decs": decs, "p": parsha, "d": dur, "src": "otzer",
            "au": o.get("src", ""), "pd": pdf,
            "pg": "https://otzerhachassidus.com/%D7%9E%D7%92%D7%99%D7%93%D7%A9%D7%99%D7%A2%D7%95%D7%A8/%D7%94%D7%A8%D7%91-%D7%99%D7%95%D7%90%D7%9C-%D7%9B%D7%94%D7%9F/",
        })

    # --------------------------------------------------------------------------
    # 8. HEBREWBOOKS PRINTED SEFORIM
    # --------------------------------------------------------------------------
    printed_seforim = [
        ("hb_54885", "שער היחוד והאמונה משיעורי הרב יואל כהן", "ספרי עיון וחסידות", "שער היחוד והאמונה", "סיכומי שיעורי ר' יואל כהן על שער היחוד והאמונה בתניא", [], 0, "https://hebrewbooks.org/54885"),
        ("hb_30546", "ספר הערכים — חב\"ד חלק א' (תשל\"א)", "ספר הערכים — חב\"ד", "חלק א' (תשל\"א)", "אנציקלופדיה למושגי החסידות בעריכת הרב יואל כהן", ['תשל"א'], 5731, "https://hebrewbooks.org/30546"),
        ("hb_30545", "ספר הערכים — חב\"ד חלק ב' (תשל\"ג)", "ספר הערכים — חב\"ד", "חלק ב' (תשל\"ג)", "אנציקלופדיה למושגי החסידות בעריכת הרב יואל כהן", ['תשל"ג'], 5733, "https://hebrewbooks.org/30545"),
        ("hb_30575", "ספר הערכים — חב\"ד חלק ג' (תשל\"ה)", "ספר הערכים — חב\"ד", "חלק ג' (תשל\"ה)", "אנציקלופדיה למושגי החסידות בעריכת הרב יואל כהן", ['תשל"ה'], 5735, "https://hebrewbooks.org/30575"),
        ("hb_58852", "ספר הערכים — חב\"ד חלק ח'", "ספר הערכים — חב\"ד", "חלק ח'", "אנציקלופדיה למושגי החסידות בעריכת הרב יואל כהן", [], 0, "https://hebrewbooks.org/58852"),
        ("hb_60795", "ספר הערכים — חב\"ד חלק ט'", "ספר הערכים — חב\"ד", "חלק ט'", "אנציקלופדיה למושגי החסידות בעריכת הרב יואל כהן", [], 0, "https://hebrewbooks.org/60795"),
        ("hb_31639", "מחשבת החסידות — חלק א'", "ספרי עיון וחסידות", "מחשבת החסידות א'", "ביאורים יסודיים בתורת החסידות מאת הרב יואל כהן", [], 0, "https://hebrewbooks.org/31639"),
    ]
    for hid, title, vol, sec, sub, yrs, yn, url in printed_seforim:
        decs = [year_to_decade(yn)] if yn else []
        unified.append({
            "id": hid, "t": title,
            "cat": "ספרים וכתבים (PDF)", "r": "", "b": "ספרי ר' יואל (HebrewBooks)",
            "v": vol, "sec": sec, "ser": vol, "ts": "", "gid": f"hb_{vol}", "ord": 10,
            "sub": sub, "l": ["he"], "f": ["pdf"], "y": yrs, "yn": yn, "decs": decs, "p": "", "d": 0,
            "src": "hebrewbooks", "pd": url, "pg": url,
        })

    # --------------------------------------------------------------------------
    # 9. USER GOOGLE DRIVE (4,495+ deduplicated files mapped cleanly!)
    # --------------------------------------------------------------------------
    gd_path = os.path.join(CACHE_DIR, "user_gdrive.json")
    if os.path.exists(gd_path):
        gd_files = json.load(open(gd_path, encoding="utf-8"))
        folder_names_map = {}
        for f in gd_files:
            raw_title = f.get("title", "")
            low = raw_title.lower().strip()
            href_low = (f.get("href") or "").lower()
            if any(j in low for j in ["thumbs.db", "folder.jpg", "albumart", "desktop.ini", "copy folder log", ".lnk", ".tmp", ".db", ".ini", ".jpg"]):
                continue
            is_google_doc = "docs.google.com/document/d/" in href_low
            ext = low.rsplit(".", 1)[-1] if "." in low else ""
            if not is_google_doc and ext not in ("mp3", "wma", "m4a", "wmv", "pdf", "doc", "docx", "txt") and not low.endswith(")"):
                continue
            key = ("/".join(f["path"]), re.sub(r'(?:\.(?:wma|wav|mp3|m4a))+$', '', low))
            folder_names_map.setdefault(key, []).append((ext, low, f))

        dedup_gd = []
        for key, variants in folder_names_map.items():
            if len(variants) == 1:
                dedup_gd.append(variants[0][2])
            else:
                variants.sort(key=lambda v: (0 if v[0] == "mp3" and v[1].count(".mp3") == 1 else (1 if v[0] == "mp3" else 2), len(v[1])))
                dedup_gd.append(variants[0][2])

        for f in dedup_gd:
            raw_title = f["title"]
            clean_name = re.sub(r'(?:\.(?:wma|wav|mp3|m4a))+$', '', raw_title, flags=re.I)
            path = f.get("path", [])
            top = path[0] if path else ""
            sub_str = " › ".join(path[1:]) if len(path) > 1 else top
            blob = " ".join(path) + " " + clean_name
            low_blob = blob.lower()
            is_google_doc = "docs.google.com/document/d/" in (f.get("href") or "").lower()
            ext = raw_title.lower().rsplit(".", 1)[-1] if "." in raw_title else ""
            is_doc = is_google_doc or ext in ("pdf", "doc", "docx", "txt")
            is_vid = (not is_google_doc) and ext in ("wmv", "mp4")
            if ext == "wma":
                sub_str = f"{sub_str} (קובץ WMA להורדה)"
            years, yn, decs = extract_years(blob)
            parsha = detect_parsha_or_holiday(blob)

            langs = []
            if any(k in low_blob for k in ["hebrew", "עברית", "ivrit"]) or (is_doc and any("\u0590" <= c <= "\u05FF" for c in raw_title)):
                langs.append("he")
            if "english" in low_blob:
                langs.append("en")
            if not langs:
                langs.append("yi")

            cat, r, b, vol, sec, ts = "סוגיות בחסידות", "", "מושגים וסוגיות בחסידות", "שונות", clean_name, ""
            ser = f"Google Drive: {path[-1]}" if path else "Google Drive"
            gid_key = f"gd_dir_{'/'.join(path)}"
            ord_n = extract_part_order(clean_name)

            doc_title_override = 'וידעת מאסקאווא (תרנ"ז) — הערות' if f["id"] == "1087zR_Xj05ir_tvvwk0xJGSxDZBPJQW8ZX94v87Elfw" else ""
            if is_doc:
                cat = "ספרים וכתבים (PDF)"
                if "chazora" in low_blob:
                    b, vol, sec = "רישומי חזרות (Google Drive)", "רישומי חזרות (Chazora Notes)", doc_title_override or clean_name
                else:
                    b, vol, sec = "כתבים ומסמכים (Google Drive)", "כתבים ומסמכים (010-Text)", doc_title_override or clean_name
                gid_key = f"gd_doc_{f['id']}"
            elif top == "001-alter rebbe":
                cat, r = "ספרים", REBBE_ZAKEN
                p1 = (path[1] if len(path) > 1 else "").lower()
                if "likutei torah" in p1:
                    b = 'לקוטי תורה'
                    raw_m = (path[2] if len(path) > 2 else "").lower()
                    if "ani lidodi" in raw_m: vol, sec = "ספר דברים / שיר השירים", "אני לדודי"
                    elif "atam nitzavi" in raw_m: vol, sec = "ספר דברים", "אתם נצבים"
                    elif "ushavtem" in raw_m: vol, sec = "ימים טובים — מועדים", "ושאבתם מים בששון"
                    elif "sos osis" in raw_m: vol, sec = "ימים טובים — מועדים", "שוש אשיש"
                    elif "shchora" in raw_m: vol, sec = "שיר השירים", "שחורה אני"
                    else: vol, sec = "מועדים", path[2] if len(path) > 2 else clean_name
                else:
                    if "shaar hayichud" in p1: b = 'תניא — שער היחוד והאמונה'
                    elif "igeres hatishuva" in p1: b = 'תניא — אגרת התשובה'
                    elif "igeres hakodesh" in p1: b = 'תניא — אגרת הקודש וקונטרס אחרון'
                    else: b = 'תניא — לקוטי אמרים'
                    series_dir = path[2] if len(path) > 2 else "כללי"
                    ts = f"Drive {series_dir}"
                    if "[009]" in series_dir:
                        vol = "כל הפרקים (תניא בעברית 1–35)"
                        langs = ["he"]
                    elif "[001]PHONE" in series_dir:
                        vol = f"פרשת {parsha}" if (parsha and parsha in PARSHA_TO_CHUMASH) else (parsha or "שיעורים לפי פרשיות")
                    else:
                        m_ch = re.match(r'^0*(\d{1,2})(?:[ab\s-]|$)', clean_name, re.I)
                        if m_ch and 1 <= int(m_ch.group(1)) <= 53:
                            perek_heb = num_to_heb_letters(int(m_ch.group(1))).rstrip("'")
                            vol = f"פרק {perek_heb}"
                        elif "hakdama" in clean_name.lower() or "chnuch" in clean_name.lower():
                            vol = "דף השער והקדמה"
                        else:
                            vol = "פרקים שונים"
                    sec = ts
                    ser = f"{ts} › {path[3]}" if len(path) > 3 else ts
                    gid_key = f"gd_tn_{'/'.join(path)}_{vol}"
            elif top == "002-Tzemach tzedek":
                cat, r, b = "ספרים", REBBE_ZZ, 'דרך מצותיך'
                raw_mz = (path[1] if len(path) > 1 else "").lower()
                vol = GD_TZ_MITZVA_MAP.get(raw_mz, path[1] if len(path) > 1 else "כללי")
                sec = vol
                ser = f"Google Drive: {path[-1]}" if len(path) > 2 else "Google Drive"
            elif top == "003-Rebbe rashab":
                cat, r = "ספרים", REBBE_RASHAB
                p1 = path[1] if len(path) > 1 else ""
                if p1 == "5666":
                    b = 'המשך תרס"ו (ס"ו)'
                    p2 = path[2] if len(path) > 2 else ""
                    vol = next((heb for prefix, heb in GD_RASHAB_66_MAP.items() if p2.startswith(prefix)), p2 or "כללי")
                    sec = path[3] if len(path) > 3 else vol
                    ser = f"Google Drive: {path[-1]}"
                elif p1 == "5672":
                    b = 'המשך תער"ב (ע"ב)'
                    p2 = path[2] if len(path) > 2 else ""
                    if "49-88" in p2: vol, sec = 'סימנים מ"ט–פ"ח', f'מאמרי סוף תער"ב ({p2})'
                    elif "384-399" in p2: vol, sec = 'סימנים שפ"ד–שצ"ט', "384-399 (Drive)"
                    elif "109" in p2: vol, sec = "מצה זו", "מאמר ק\"ט — מצה זו"
                    else: vol, sec = p2 or "כללי", p2 or clean_name
                    ser = f"Google Drive: {path[-1]}"
                else:
                    b = 'ספרי המאמרים וקונטרסים'
                    ymap = {"5657": 'ספר המאמרים תרנ"ז', "5659": 'ספר המאמרים תרנ"ט', "5665": 'ספר המאמרים תרס"ה', "5669": 'ספר המאמרים תרס"ט', "5679": 'ספר המאמרים עטר"ת'}
                    vol = ymap.get(p1, years[0] if years else (p1 or "מאמרים"))
                    sec = path[2] if len(path) > 2 else vol
                    ser = f"Google Drive: {path[-1]}"
            elif top == "004-Friediker Rebbe":
                cat, r, b = "ספרים", REBBE_RAYYATZ, 'ספרי המאמרים וקונטרסים'
                p1 = path[1] if len(path) > 1 else ""
                if "5686" in p1:
                    vol, sec = 'ספר המאמרים תרפ"ו', "שובה ישראל"
                elif "5703" in p1:
                    vol, sec = 'ספר המאמרים תש"ג', "מאמרי תש\"ג"
                elif "5708" in p1:
                    vol = 'ספר המאמרים תש"ח'
                    p2 = (path[2] if len(path) > 2 else "").lower()
                    if "ki minase" in p2: sec = "כי מנסה"
                    elif "tzena" in p2: sec = "צאינה וראינה - אנכי הוי' אלקיך"
                    elif "vayach" in p2: sec = "ויחלום"
                    elif "tishray" in p2: sec = 'תשרי תש"ח'
                    else: sec = path[2] if len(path) > 2 else vol
                else:
                    vol, sec = "כללי", clean_name
                ser = f"Google Drive: {path[-1]}"
            elif top == "005-Rebbe":
                cat, r = "ספרים", REBBE_LUBAVITCH
                p1 = (path[1] if len(path) > 1 else "").lower()
                if p1 in ("melukot", "kuntrasim"):
                    b = 'ספר המאמרים מלוקט'
                    p2 = path[2] if len(path) > 2 else ""
                    m_vol = re.search(r'(\d)', p2)
                    vol_heb = num_to_heb_letters(int(m_vol.group(1))) if m_vol else ""
                    vol = f"מלוקט (מהדורת קה\"ת) — חלק {vol_heb}" if vol_heb else "ספר המאמרים מלוקט (Drive)"
                    if len(path) > 3:
                        sec = translate_maamar_name(path[3], years)
                        ser = f"Google Drive: {path[-1]}"
                    else:
                        # Files directly inside (Milukat 4-Ligirsa) etc.: group per Maamar name inside filename
                        sec = translate_maamar_name(re.sub(r'^\d+[-\s]*(?:[AB]\s+|(?:\d+\s*-\s*)?[AB]\s+)', '', clean_name, flags=re.I), years)
                        ser = f"Google Drive: {p2}"
                        gid_key = f"gd_lig_{p2}_{sec}"
                elif p1 == "bilty muga":
                    b = 'מאמרים (בלתי מוגה ותורת מנחם)'
                    vol = "מאמרים בלתי מוגה"
                    sec = translate_maamar_name(path[2] if len(path) > 2 else clean_name, years)
                    ser = f"Google Drive: {path[-1]}"
                elif p1 == "hadranim":
                    b = 'הדרנים'
                    p2 = path[2] if len(path) > 2 else ""
                    if "rambam" in p2.lower(): vol = 'הדרנים על הרמב"ם'
                    elif "brochos" in p2.lower(): vol = 'הדרנים על הש"ס'
                    elif "5746" in p2: vol = 'הדרנים — תשמ"ו'
                    else: vol = "הדרנים"
                    sec = path[2] if len(path) > 2 else clean_name
                    ser = f"Google Drive: {p2}"
                elif p1 == "rshimois":
                    b = 'ספר השיחות ורשימות'
                    vol = "רשימות"
                    sec = path[2] if len(path) > 2 else clean_name
                    ser = f"Google Drive: {sec}"
                else:
                    # sichois
                    p2 = path[2] if len(path) > 2 else ""
                    if "inayana shel" in p2.lower():
                        b, vol, sec = 'קונטרסים', 'קונטרס ענינה של תורת החסידות', 'קונטרס ענינה של תורת החסידות'
                        ser = f"Google Drive: {path[-1]}"
                    elif "kuntres" in p2.lower():
                        b = 'קונטרסים'
                        vol = "קונטרס בית רבינו שבבבל" if "beis rabynu" in p2.lower() else 'קונטרס תורה שבעל פה'
                        sec = vol
                        ser = f"Google Drive: {p2}"
                    else:
                        b = 'ליקוטי שיחות'
                        m_ls = re.search(r'(?:lkus|vol\.?|לקוש\s*ח?)[-\s]*(\d+|[א-ת]{1,2})', blob, re.I)
                        if m_ls:
                            val = m_ls.group(1)
                            vol = normalize_ls_chelek(num_to_heb_letters(int(val)) if val.isdigit() else val)
                        else:
                            vol = "שיחות לפי פרשה / מועד"
                        sec = parsha if parsha else p2 or clean_name
                        ser = f"Google Drive: {path[-1]}"
            elif top == "006-chzoroh":
                cat, b = "חזרות והתוועדויות", "חזרות על התוועדויות הרבי"
                p1 = path[1] if len(path) > 1 else ""
                if p1.lower() == "other":
                    yr_str = "שנים שונות"
                else:
                    yr_str = num_to_hebrew_year(int(p1)) if p1.isdigit() else (years[0] if years else p1 or "שנים שונות")
                vol = yr_str
                # Group A/B sides of the same Chazara tape (e.g. '1.wav' & '1 b.wav')
                tape_stem = re.sub(r'(?:[\s_-]+[ab]|_side_[ab]|\s*\([ab]\))$', '', clean_name, flags=re.I).strip()
                sec = f"{vol} — {parsha or tape_stem}"
                ser = f"Google Drive חזרות {vol}"
                gid_key = f"gd_chz_{'/'.join(path)}_{tape_stem.lower()}"
            elif top == "008-speeches":
                p1 = (path[1] if len(path) > 1 else "").lower()
                low_fn = clean_name.lower()
                if "bimishnas" in p1:
                    cat, b, vol, sec = "סוגיות בחסידות", "במשנת רבינו", "שיעורי במשנת רבינו", "סדרת במשנת רבינו (115 שיעורים)"
                    ser = "סדרת במשנת רבינו (Google Drive)"
                    m_bm = re.match(r'^0*(\d+)', clean_name)
                    if m_bm: ord_n = int(m_bm.group(1)) * 10
                elif "musogim" in p1:
                    cat, b, vol, sec = "סוגיות בחסידות", "מושגים וסוגיות בחסידות", "מושגים בחסידות", clean_name
                    ser = "מושגים בחסידות (Google Drive)"
                elif "parshos" in p1 or (parsha and parsha in PARSHA_TO_CHUMASH):
                    par_name = parsha or "כללי"
                    cat, b, vol = "פרשיות השבוע", PARSHA_TO_CHUMASH.get(parsha, "פרשיות כללי"), par_name
                    sec = f"שיעורים על פרשת {par_name}" if parsha else clean_name
                    ser = "פרשת השבוע (Google Drive)"
                    gid_key = f"gd_par_{par_name}_{path[1] if len(path) > 1 else ''}"
                elif "igeres" in low_fn:
                    cat, r, b, vol, sec = "ספרים", REBBE_ZAKEN, 'תניא — אגרת התשובה', "כללי", "אגרת התשובה"
                elif "siyum" in p1 or "rambam" in low_fn:
                    cat, b, vol, sec = "סוגיות בחסידות", "מושגים וסוגיות בחסידות", "סיום הרמב\"ם", "סיום הרמב\"ם (טורונטו)"
                elif "taammei" in p1 or "taamaei" in low_fn:
                    cat, b, vol, sec = "סוגיות בחסידות", "מושגים וסוגיות בחסידות", "טעמי המצוות", "טעמי המצוות"
                elif "kinus" in p1 or "kinus hashluchim" in low_fn or "shlichus" in low_fn:
                    cat, b, vol, sec = "סוגיות בחסידות", "מושגים וסוגיות בחסידות", "כינוס השלוחים וענייני שליחות", clean_name
                elif "logical of existence" in low_fn:
                    cat, b, vol, sec = "סוגיות בחסידות", "מושגים וסוגיות בחסידות", "אמונת ה' וקיום המצוות", clean_name
                elif parsha and parsha in HOLIDAY_TO_MONTH:
                    cat = "ענינא דיומא"
                    b = HOLIDAY_TO_MONTH[parsha]
                    vol = parsha
                    sec = clean_name
                elif "after simchas torah" in p1 or "v_yaakov" in low_fn:
                    cat, b, vol, sec = "ענינא דיומא", "תשרי", "סוכות ושמיני עצרת", "ויעקב הלך לדרכו"
                elif any(k in p1 for k in ["adar", "chanukah", "pesach", "lag", "cheshvan", "menachem", "achroin", "simchas", "shevat", "shavuos", "tammuz", "rosh", "sivan", "nisan", "av"]):
                    cat = "ענינא דיומא"
                    if "adar" in p1: b, vol = "אדר", "ז' אדר" if "7 adar" in low_fn else "חודש אדר"
                    elif "cheshvan" in p1: b, vol = "חשון", "חודש חשון"
                    elif "chanukah" in p1: b, vol = "כסלו", "חנוכה"
                    elif "shevat" in p1: b, vol = "שבט", "חודש שבט"
                    elif any(k in p1 for k in ["pesach", "achroin", "nisan"]): b, vol = "ניסן", "אחרון של פסח" if "achr" in p1 else ("פסח" if "pesach" in p1 else 'י"א ניסן')
                    elif "sivan" in p1 or "shavuos" in p1: b, vol = "סיון", "שבועות וחודש סיון"
                    elif "tammuz" in p1: b, vol = "תמוז", "ימי תמוז"
                    else: b, vol = "אב", "כ' מנחם אב" if "20" in low_fn or "chaf" in p1 else "חודש אב"
                    sec = clean_name
                elif "10 kislev" in low_fn:
                    cat, b, vol, sec = "ענינא דיומא", "כסלו", "י' כסלו", "י' כסלו"
                elif low_fn == "elul":
                    cat, b, vol, sec = "ענינא דיומא", "אלול", "חודש אלול", "חודש אלול"
                elif "shabbos mevorchim nissan" in low_fn:
                    cat, b, vol, sec = "ענינא דיומא", "ניסן", "שבת מברכים ניסן", clean_name
                elif "shabbos mevorchim sivan" in low_fn or "12 sivan" in low_fn:
                    cat, b, vol, sec = "ענינא דיומא", "סיון", "שבועות וחודש סיון", clean_name
                elif "hachozrim" in p1:
                    cat, b, vol, sec = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות", "זכרונות חוזרים", "זכרונות חוזרים"
                elif "pigishah" in p1:
                    cat, b, vol, sec = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות", "שיחות וזכרונות", clean_name
                elif "nitul" in low_fn:
                    cat, b, vol, sec = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות", "סיפורי חסידים וזכרונות", clean_name
                elif "texes" in p1 or "yuston" in low_fn:
                    cat, b, vol, sec = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות", 'יוסטון — תשנ"ה', "יוסטון (תשנ\"ה)"
                elif "vthh" in p1 or "tishray" in p1:
                    cat, b, vol, sec = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות", 'תשרי תשס"ט (ועד התלמידים)', "כינוס תשרי תשס\"ט"
                elif "shonos" in p1 or "5765" in low_fn or "yom iuyn" in low_fn:
                    cat, b, vol, sec = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות", 'כינוסים וימי עיון (תשס"ה)', clean_name
                else:
                    cat, b = "חזרות והתוועדויות", "התוועדויות חסידים וזיכרונות"
                    vol = years[0] if years else "התוועדויות ושיחות"
                    sec = clean_name
            elif top == "009-Nosim BiYahdus":
                cat, b = "סוגיות בחסידות", "מושגים וסוגיות בחסידות"
                raw_tp = (path[1] if len(path) > 1 else "").lower()
                vol = {"13 ikrim": 'י"ג עיקרים', "achdus hashem": "אחדות ה'", "yisroel": "ישראל"}.get(raw_tp, path[1] if len(path) > 1 else "כללי")
                sec = vol
                ser = f"{vol} (Google Drive)"
                m_nb = re.search(r'(\d+)$', clean_name)
                if m_nb: ord_n = int(m_nb.group(1)) * 10
            elif top == "012-Nigunim":
                cat, b, vol, sec = "ניגונים", "ניגוני חב\"ד (Google Drive)", "ניגונים", clean_name
            else:
                cat, b, vol, sec = "סוגיות בחסידות", "מושגים וסוגיות בחסידות", top or "שונות", clean_name

            GD_MUSOGIM_HEB = {
                "1 yisoday hachasidus b": "יסודות החסידות — חלק ב'",
                "chidus hachasiduss a": "חידוש החסידות (ענינה של תורת החסידות) — חלק א'",
                "chidus hachasiduss b": "חידוש החסידות (ענינה של תורת החסידות) — חלק ב'",
                "choyvas haodam baolmoi a": "חובת האדם בעולמו — חלק א'",
                "choyvas haodam baolmoi  b": "חובת האדם בעולמו — חלק ב'",
                "chukim umishptim a": "חוקים ומשפטים — חלק א'",
                "chukim umishptim b": "חוקים ומשפטים — חלק ב'",
                "emunas hashem  b": "אמונת ה' — חלק ב'",
                "kal yehudey bietzem tal' hbast a 1": "כל יהודי בעצם תלמיד הבעש\"ט — חלק א'",
                "kal yehudey bietzem tal' hbast  b 1": "כל יהודי בעצם תלמיד הבעש\"ט — חלק ב'",
                "yichuda iloah a": "ייחודא עילאה — חלק א'",
                "yichuda iloah b": "ייחודא עילאה — חלק ב'",
            }
            ctx_label = path[-1] if path else ""
            musogim_heb = GD_MUSOGIM_HEB.get(clean_name.strip().lower(), "")
            if doc_title_override:
                disp_title = doc_title_override
            elif clean_name.lower() == "new text document.txt":
                yr_doc = num_to_hebrew_year(int(path[1])) if len(path) > 1 and path[1].isdigit() else (path[1] if len(path) > 1 else "")
                disp_title = f"רשימת וציוני חזרות — {yr_doc}" if yr_doc else "רשימת וציוני חזרות"
            elif musogim_heb:
                disp_title = musogim_heb
            elif len(clean_name) <= 14 or re.match(r'^[\d\sA-Ba-b_-]+$', clean_name):
                disp_title = f"{ctx_label} — {clean_name}" if ctx_label else clean_name
            else:
                disp_title = clean_name

            if is_google_doc:
                preview_url = f"https://docs.google.com/document/d/{f['id']}/preview"
                dl_url = f"https://docs.google.com/document/d/{f['id']}/export?format=pdf"
                view_url = f.get("href") or f"https://docs.google.com/document/d/{f['id']}/edit"
            else:
                rk_q = f"?resourcekey={f['rkey']}" if f.get("rkey") else ""
                rk_amp = f"&resourcekey={f['rkey']}" if f.get("rkey") else ""
                preview_url = f"https://drive.google.com/file/d/{f['id']}/preview{rk_q}"
                dl_url = f"https://drive.google.com/uc?export=download&id={f['id']}{rk_amp}"
                view_url = f.get("href") or f"https://drive.google.com/file/d/{f['id']}/view{rk_q}"

            unified.append({
                "id": f"gd_{f['id']}", "t": disp_title,
                "cat": cat, "r": r, "b": b, "v": vol, "sec": sec, "ser": ser, "ts": ts,
                "gid": gid_key, "ord": ord_n,
                "sub": f"Drive: {sub_str}", "l": langs,
                "f": ["pdf"] if is_doc else (["video"] if is_vid else ["audio"]),
                "y": years, "yn": yn, "decs": decs, "p": parsha, "d": 0, "src": "gdrive",
                "pd": preview_url if is_doc else "",
                "dr": preview_url if (not is_doc) else "",
                "dl": dl_url, "pg": view_url,
            })

    # --------------------------------------------------------------------------
    # Auto-number anonymous multi-series under same (cat, r, b, v, sec)
    # --------------------------------------------------------------------------
    by_parent = defaultdict(list)
    for it in unified:
        by_parent[(it["cat"], it["r"], it["b"], it["v"], it["sec"])].append(it)

    for pkey, items_in_sec in by_parent.items():
        # Distinct gids in this parent
        distinct_gids = list(OrderedDict.fromkeys(x["gid"] for x in items_in_sec))
        if len(distinct_gids) > 1:
            # Ensure tracks sharing same parent with generic ser='היכל מנחם' get clear distinct Hebrew series numbers
            generic_gids = [g for g in distinct_gids if any(x["gid"] == g and x["ser"] == "היכל מנחם" for x in items_in_sec)]
            if len(generic_gids) > 1:
                for idx_g, g in enumerate(generic_gids, start=1):
                    heb_l = num_to_heb_letters(idx_g)
                    for x in items_in_sec:
                        if x["gid"] == g:
                            x["ser"] = f"סדרה {heb_l} (היכל מנחם)"

    # --------------------------------------------------------------------------
    # Canonical Maamar Tagging (`ma`, `mas`, `mo`) for books with multi-maamar series
    # --------------------------------------------------------------------------
    HEMSHECH_66_ORDER = [
        'יו"ט של ר"ה',
        'זה היום',
        'שובה ישראל',
        'ביום השמיני עצרת',
        'ויכולו השמים',
        'אלה תולדות נח',
        "ויאמר ה' לך לך",
        'ואברהם זקן',
        'ויתן לך',
        'ויצא',
        'תחילת ההמשך — שיעורים ללא ציון מאמר',
        'החודש הזה',
        "ויולך ה'",
        'זאת חוקת',
        'כי עמך מקור חיים',
        'אדם כי יקריב',
        'אדם כי יהיה בעור',
        'המשך החודש הזה — כללי',
        'ושאבתם מים בששון',
        'במדבר סיני',
        'אז ישיר ישראל',
        'כי מראש אמנה',
        'כי המצוה',
        "כי תבואו וגו' ושבתה",
        'קדושים תהיו',
        'כל השונה הלכות',
        'אם בחוקותי תלכו',
        'בשעה שהקדימו (תרס"ז)',
        "אנכי ה' אלקיך (תרס\"ז)",
        'פנים בפנים (תרס"ז)',
        'אין עומדין (תרס"ז)',
        'תקעו בחודש (תרס"ז)',
        'בסוכות תשבו - ביום השמיני (תרס"ז)',
        'היושבת בגנים (תרס"ז)',
        'ומקנה רב',
        "קדש ישראל לה' (תרס\"ח)",
        'לפני "באתי לגני" (תשל"א)',
    ]
    H66_IDX = {name: i + 1 for i, name in enumerate(HEMSHECH_66_ORDER)}

    def canon_h66_maamar(raw_name):
        s = raw_name.strip()
        low_s = s.lower()
        exact_map = {
            "זאת חקת": "זאת חוקת",
            "אדם כי יהי' בעור": "אדם כי יהיה בעור",
            "כי ידעתיו, ואברהם זקן": "ואברהם זקן",
            "כי תבאו וגו' ושבתה": "כי תבואו וגו' ושבתה",
            "אם בחקותי תלכו": "אם בחוקותי תלכו",
            "בשעה שהקדימו - תרס\"ז": 'בשעה שהקדימו (תרס"ז)',
            "תקעו בחודש - תרס\"ז": 'תקעו בחודש (תרס"ז)',
            "בסוכות תשבו - ביום השמיני - תרס\"ז": 'בסוכות תשבו - ביום השמיני (תרס"ז)',
            "היושבת בגנים - תרס\"ז": 'היושבת בגנים (תרס"ז)',
            "קדש ישראל לה' - תרס\"ח": "קדש ישראל לה' (תרס\"ח)",
            "כל השונה הלכות - תרס\"ז": "כל השונה הלכות",
        }
        if s in exact_map:
            return exact_map[s]
        if "beshah" in low_s or "bsha" in low_s:
            return 'בשעה שהקדימו (תרס"ז)'
        if "anochi" in low_s:
            return "אנכי ה' אלקיך (תרס\"ז)"
        if "panim" in low_s or "punim" in low_s:
            return 'פנים בפנים (תרס"ז)'
        if "omdin" in low_s:
            return 'אין עומדין (תרס"ז)'
        if "hachodesh" in low_s or "המשך החודש" in s:
            return 'החודש הזה'
        if "vayolech" in low_s:
            return "ויולך ה'"
        if "chukas" in low_s or "chokat" in low_s or "chukat" in low_s:
            return 'זאת חוקת'
        if "imcha" in low_s or "emech" in low_s:
            return 'כי עמך מקור חיים'
        if "yakriv" in low_s or "adom ke ya" in low_s:
            return 'אדם כי יקריב'
        if "ihie beor" in low_s or "ki yihye" in low_s:
            return 'אדם כי יהיה בעור'
        if "veshav" in low_s or "vishav" in low_s:
            return 'ושאבתם מים בששון'
        if "bamidbar" in low_s:
            return 'במדבר סיני'
        if "yashir" in low_s:
            return 'אז ישיר ישראל'
        if "merosh" in low_s:
            return 'כי מראש אמנה'
        if "hashone" in low_s or "hasone" in low_s:
            return 'כל השונה הלכות'
        if "yut rh" in low_s or "yom tov" in low_s:
            return 'יו"ט של ר"ה'
        return s

    for it in unified:
        bk = it.get("b", "")
        t = it.get("t", "")
        src = it.get("src", "")
        gid = it.get("gid", "")

        if bk == 'המשך תרס"ו (ס"ו)':
            ma = ""
            mas = None
            if src == "heichal":
                stem = re.sub(r'\s*-\s*\d+\s*$', '', t).strip()
                if stem == "החודש הזה, ויולך":
                    ma, mas = "החודש הזה", ["החודש הזה", "ויולך ה'"]
                elif stem == "ויולך ה' - זאת חקת":
                    ma, mas = "ויולך ה'", ["ויולך ה'", "זאת חוקת"]
                elif stem == "ואברהם זקן - ויתן לך":
                    ma, mas = "ואברהם זקן", ["ואברהם זקן", "ויתן לך"]
                else:
                    ma = canon_h66_maamar(stem)
            elif src == "gdrive":
                if "019-024 Hachodesh [4]" in gid or "Hemshech Hachodesh-JEM" in gid or "019-024 Hachodesh [3]" in gid:
                    m_tp = re.search(r'(?:—|- 00 -)\s*0*(\d{1,3})\s*(?:[-_\s]?[ABab]|\[|$)', t)
                    if not m_tp:
                        m_tp = re.match(r'^0*(\d{1,3})-[ABab]', t)
                    tp = int(m_tp.group(1)) if m_tp else 0
                    if 1 <= tp <= 7:
                        ma = 'החודש הזה'
                    elif 8 <= tp <= 14:
                        ma = "ויולך ה'"
                    elif tp == 15:
                        ma = 'זאת חוקת'
                    elif 16 <= tp <= 25:
                        ma = 'כי עמך מקור חיים'
                    elif 26 <= tp <= 31:
                        ma = 'כל השונה הלכות'
                    else:
                        ma = 'המשך החודש הזה — כללי'
                elif "001 (Yom-tov)-49" in gid:
                    lt = t.lower()
                    if "yom tov" in lt:
                        ma = 'יו"ט של ר"ה'
                    elif "vaichulu" in lt:
                        ma = 'ויכולו השמים'
                    elif "noach" in lt:
                        ma = 'אלה תולדות נח'
                    elif "vayolech" in lt or "vayoilech" in lt:
                        ma = "ויולך ה'"
                    elif "ki imcha" in lt:
                        ma = 'כי עמך מקור חיים'
                    elif "veshavsa" in lt:
                        ma, mas = 'אדם כי יהיה בעור', ['אדם כי יהיה בעור', 'ושאבתם מים בששון']
                    elif "adam ihie beor" in lt:
                        ma = 'אדם כי יהיה בעור'
                    elif "bamidbar" in lt:
                        ma = 'במדבר סיני'
                    elif "az yashir" in lt:
                        ma = 'אז ישיר ישראל'
                    elif "ki hamitzvah" in lt or "ki hamizvah" in lt:
                        ma = 'כי המצוה'
                    elif "umikne" in lt:
                        ma = 'ומקנה רב'
                    elif "bati legani" in lt:
                        ma = 'לפני "באתי לגני" (תשל"א)'
                    else:
                        ma = 'תחילת ההמשך — שיעורים ללא ציון מאמר'
                elif "010-11vavraham" in gid:
                    ma, mas = "ואברהם זקן", ["ואברהם זקן", "ויתן לך"]
                elif "010-Viavarahom" in gid:
                    ma = "ואברהם זקן"
                elif "001-Yut RH" in gid:
                    ma = 'יו"ט של ר"ה'
                elif "019-024 Hachodesh [1(-old)]" in gid or ("019-Hachodesh" in gid and not ("hachodesh" in t.lower() or "pg 16" in t.lower())):
                    ma = 'המשך החודש הזה — כללי'
                elif "053-56 Bshoah" in gid:
                    ma = canon_h66_maamar(it.get("ser", "") or t)
                else:
                    # Standard single-maamar folder inside 5666
                    vname = it.get("v", "")
                    if vname in H66_IDX:
                        ma = vname
                    elif vname == 'המשך החודש הזה (י"ט–כ"ד)':
                        sec_n = canon_h66_maamar(it.get("sec", "") or it.get("ser", ""))
                        if sec_n in H66_IDX:
                            ma = sec_n
                        elif "doc" in gid:
                            ma = 'המשך החודש הזה — כללי'
                        else:
                            ma = 'החודש הזה'
                    else:
                        ma = canon_h66_maamar(it.get("ser", "").replace("Google Drive: ", "") or vname)
            if ma:
                it["ma"] = ma
                if mas:
                    it["mas"] = mas
                if ma in H66_IDX:
                    it["mo"] = H66_IDX[ma]
            vname = it.get("v", "")
            v_head = vname.split(" — ")[0].split(" - ")[0].replace(' (י"ט–כ"ד)', "").strip()
            v_canon = canon_h66_maamar(v_head)
            if v_canon in H66_IDX:
                it["vo"] = H66_IDX[v_canon]
            elif it.get("mo"):
                it["vo"] = it["mo"]

        elif bk == 'המשך תער"ב (ע"ב)':
            h72_ord = {
                'סימנים מ"ט–פ"ח': 1, 'מצה זו': 2, 'שופטים': 3, 'כי תצא': 4, 'כי תבא': 5,
                'אתם נצבים': 6, 'ביום השמיני עצרת': 7, 'ויגש - העת"ר': 8, 'יהודה אתה - העת"ר': 9,
                'ואלה שמות העת"ר': 10, 'ואלה שמות העת"ר - וידבר אלקים העת"ר': 10,
                'וידבר אלקים העת"ר': 11, 'ועתה ישראל': 12, 'סימנים שפ"ד–שצ"ט': 13, 'כללי (ע"ב)': 14,
            }
            if src == "heichal":
                it["ma"] = re.sub(r'\s*-\s*\d+\s*$', '', t).strip()
            else:
                it["ma"] = it.get("v") or "כללי"
            if it["ma"] in h72_ord:
                it["mo"] = h72_ord[it["ma"]]
            vname = it.get("v", "")
            if vname in h72_ord:
                it["vo"] = h72_ord[vname]

        elif bk == 'דרך מצותיך':
            dm_ord = {
                'מילה': 1, 'ציצית': 2, 'זכירת ומחיית עמלק': 3, 'יעוד ופדיון אמה העבריה': 4,
                'תגלחת המצורע': 5, 'האמנת אלקות': 6, 'השבתת חמץ ואכילת מצה': 7,
                'דין עבד עברי': 8, 'מינוי מלך': 9, "אחדות ה'": 10, "מצות אחדות ה'": 10,
                'אהבת ישראל': 11, 'שרש מצות התפלה': 12,
            }
            vname = it.get("v", "")
            if vname in dm_ord:
                it["vo"] = dm_ord[vname]

        elif bk in ('תורה אור', 'לקוטי תורה'):
            chumash_vo = {
                'ספר בראשית': 1, 'ספר שמות': 2, 'חנוכה ופורים': 3,
                'ספר ויקרא': 1, 'ספר במדבר': 2, 'ספר דברים': 3,
                'ספר דברים / שיר השירים': 4, 'ימים טובים — מועדים': 5,
                'שיר השירים': 6, 'שיר השירים / אלול': 7,
            }
            vname = it.get("v", "")
            if vname in chumash_vo:
                it["vo"] = chumash_vo[vname]

        elif bk == 'ספרי המאמרים וקונטרסים':
            vname = it.get("v", "")
            if 'קונטרסים ב' in vname:
                it["vo"] = 57005
            elif it.get("yn"):
                it["vo"] = it["yn"] * 10
            if src == "heichal":
                stem = re.sub(r'\s*-\s*\d+\s*$', '', t).strip()
                if stem == "כל המאריך באחד, אהללה ה' בחיי":
                    it["ma"] = 'כל המאריך באחד (ת"ש)'
                    it["mas"] = ['כל המאריך באחד (ת"ש)', "אהללה ה' בחיי (ת\"ש)"]
                else:
                    it["ma"] = f"{stem} ({vname.replace('ספר המאמרים ', '')})" if "ספר המאמרים " in vname else stem
            elif src == "podcast_study":
                lt = t.lower()
                if "haumnom" in lt: it["ma"] = 'האומנם ישב (תרמ"ג)'
                elif "vaera 5735" in lt: it["ma"] = 'וארא (תשל"ה)'
                elif "veavdi" in lt: it["ma"] = 'ודויד עבדי (תשל"ב)'
                elif "vechozakta" in lt or "vechozokto" in lt: it["ma"] = 'וחזקת (תשכ"ח)'
                elif "zeh hayom" in lt: it["ma"] = 'זה היום (תשי"א)'
            elif src == "video_chasidut":
                if "וידעת" in t:
                    it["ma"] = 'וידעת - מאסקאווא (תרנ"ז)'
                elif "באתי לגני" in t:
                    it["ma"] = 'באתי לגני - תש"י (תש"י)'
            elif src == "gdrive":
                lt = t.lower()
                if "veyada" in lt:
                    it["ma"] = 'וידעת - מאסקאווא (תרנ"ז)'
                elif vname == 'ספר המאמרים תרנ"ז' and it.get("sec") == "001":
                    it["ma"] = 'מאמרי תרנ"ז (סדרה ב\')'
                elif "5665 rosh hashana" in lt:
                    it["ma"] = 'ראש השנה (תרס"ה)'
                elif "5665 [001] shavuos" in lt:
                    it["ma"] = 'חג השבועות א\' (תרס"ה)'
                elif "5665 [002] shavuos" in lt:
                    it["ma"] = 'חג השבועות ב\' (תרס"ה)'
                elif vname == 'ספר המאמרים תש"ח' and it.get("sec") == "5708":
                    it["ma"] = 'מאמרי תש"ח — כללי'
                elif "vechol" in lt or "וכל העם" in t:
                    it["ma"] = 'וכל העם (תרס"ה)'
                elif "תדמיוני" in t:
                    it["ma"] = 'ואל מי תדמיוני (תרס"ה)'
                elif "נשא את ראש" in t:
                    it["ma"] = 'נשא את ראש (תרס"ה)'
                elif "tzena" in lt:
                    it["ma"] = 'צאינה וראינה (תש"ח)'
                elif "ki minase" in lt:
                    it["ma"] = 'כי מנסה (תש"ח)'
                elif "vayach" in lt:
                    it["ma"] = 'ויחלום (תש"ח)'
                elif "shuva" in lt:
                    it["ma"] = 'שובה ישראל (תרפ"ו)'
                else:
                    raw_s = it.get("sec") or it.get("v") or "כללי"
                    it["ma"] = f"{raw_s} ({vname.replace('ספר המאמרים ', '')})" if "ספר המאמרים " in vname and vname not in raw_s else raw_s
            if it.get("ma") and it.get("yn"):
                m_off = 50
                lt_m = it["ma"]
                if any(k in lt_m for k in ["ר\"ה", "ראש השנה", "תשרי", "לולב", "שמיני"]): m_off = 10
                elif any(k in lt_m for k in ["שובה", "אלה", "ויגש", "ויחלום"]): m_off = 20
                elif any(k in lt_m for k in ["באתי", "שבט", "אדר", "פורים", "זכור"]): m_off = 30
                elif any(k in lt_m for k in ["החודש", "פסח", "מצה"]): m_off = 40
                elif any(k in lt_m for k in ["שבועות", "הר סיני", "במדבר", "נשא", "צאינה"]): m_off = 60
                it["mo"] = it["yn"] * 100 + m_off

    # Sort unified cleanly so tracks within each gid are in exact ascending order!
    source_priority = {
        "hebrewbooks": 0, "podcast_tanya": 1, "podcast_fabrenguen": 2, "otzer": 3,
        "merkaz_anash": 4, "monsey": 5, "melukat": 6, "podcast_study": 7,
        "podcast_chazara": 8, "video_chasidut": 9, "youtube": 10, "heichal": 11, "gdrive": 12,
    }
    unified.sort(key=lambda x: (source_priority.get(x["src"], 99), x["gid"], x["ord"], x["t"]))

    sources_meta = {
        "heichal": {"name": "היכל מנחם (Chassidus App)", "url": "https://chassidus.com/rebyoel/"},
        "gdrive": {"name": "Google Drive — אוסף ר' יואל", "url": "https://drive.google.com/drive/folders/0B7BtXyKG9O_rQmdKOUd2U0owYk0?resourcekey=0-EZQ3wdHgQEgeD14j3cKLUQ&usp=drive_link"},
        "podcast_chazara": {"name": "פודקאסט חזרות הרבי", "url": "https://anchor.fm/s/da801cec/podcast/rss"},
        "podcast_tanya": {"name": "פודקאסט שיעורי תניא בעברית", "url": "https://anchor.fm/s/d53b97d4/podcast/rss"},
        "podcast_study": {"name": "Study Chassidus Podcast", "url": "https://anchor.fm/s/45ba83a4/podcast/rss"},
        "podcast_fabrenguen": {"name": "פודקאסט התוועדויות בעברית", "url": "https://anchor.fm/s/67553a2c/podcast/rss"},
        "video_chasidut": {"name": "וידאו חסידות.נט", "url": "http://video.chasidut.net/videos/load/hachozer"},
        "merkaz_anash": {"name": "מרכז אנ\"ש (Chassidus Perspective)", "url": "https://merkazanash.com/videos"},
        "monsey": {"name": "היכל מנחם מאנסי", "url": "https://heichalmenachemmonsey.org/cat/rabbunim/yoel-kahn/"},
        "melukat": {"name": "Project Melukat", "url": "https://projectmelukat.org/"},
        "youtube": {"name": "יוטיוב / סינון 770", "url": "https://sinun770.org/author/UCHNCfybOXvA1N3P1B1Eyg-A/"},
        "otzer": {"name": "אוצר החסידות", "url": "https://otzerhachassidus.com/%D7%9E%D7%92%D7%99%D7%93%D7%A9%D7%99%D7%A2%D7%95%D7%A8/%D7%94%D7%A8%D7%91-%D7%99%D7%95%D7%90%D7%9C-%D7%9B%D7%94%D7%9F/"},
        "hebrewbooks": {"name": "HebrewBooks (ספרים מודפסים)", "url": "https://hebrewbooks.org/54885"},
    }

    payload = {
        "meta": {
            "totalCount": len(unified),
            "seriesCount": len(set(x["gid"] for x in unified)),
            "multiSeriesCount": sum(1 for k, g in defaultdict(int, ((x["gid"], 0) for x in unified)).items()),
            "sources": sources_meta,
            "catOrder": CAT_ORDER,
            "catInfo": CAT_INFO,
            "rebbeOrder": REBBE_ORDER,
            "rebbeInfo": REBBE_INFO,
            "booksByRebbe": BOOKS_BY_REBBE,
            "bookInfo": BOOK_INFO,
        },
        "items": unified,
    }
    # Compute exact multiSeriesCount
    gid_cnt = defaultdict(int)
    for x in unified:
        gid_cnt[x["gid"]] += 1
    payload["meta"]["multiSeriesCount"] = sum(1 for c in gid_cnt.values() if c >= 2)

    js_path = os.path.join(DATA_DIR, "shiurim_data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.SHIURIM_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    size_mb = os.path.getsize(js_path) / (1024 * 1024)
    print(f"BUILT {js_path}: {len(unified)} items in {len(gid_cnt)} groups ({payload['meta']['multiSeriesCount']} multi-lesson series) ({size_mb:.2f} MB)")
    for c in CAT_ORDER:
        cnt = sum(1 for x in unified if x["cat"] == c)
        print(f"  CAT {c}: {cnt}")
    for rb in REBBE_ORDER:
        cnt = sum(1 for x in unified if x["r"] == rb)
        print(f"    REBBE {rb}: {cnt}")

if __name__ == "__main__":
    build()
