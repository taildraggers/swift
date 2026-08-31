"""Shared helpers used by the Aeronca listing scrapers.

Barnstormers.com sits behind Cloudflare bot protection that treats plain
`requests`/`curl` HTTP clients differently from a real browser, silently
returning near-empty pages. A real headless browser clears this, so
fetching is done through Playwright/Chromium instead of a plain HTTP client.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

PAGE_TIMEOUT_MS = 30_000
CHALLENGE_MAX_WAIT_MS = 25_000
CHALLENGE_POLL_MS = 1_000
REQUEST_DELAY_SECONDS = 1.0
CHALLENGE_TITLE_MARKERS = ("just a moment", "attention required", "checking your browser")

_playwright = None
_browser = None
_context = None


def _get_context():
    global _playwright, _browser, _context
    if _context is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        _context = _browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="en-US",
        )
        _context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
    return _context


def close_browser() -> None:
    """Shut down the shared Playwright browser, if one was started."""
    global _playwright, _browser, _context
    if _browser is not None:
        _browser.close()
    if _playwright is not None:
        _playwright.stop()
    _playwright = _browser = _context = None


def fetch(url: str) -> Optional[str]:
    """Load a URL in a real browser and return the rendered HTML, or None on failure."""
    page = _get_context().new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        # If Cloudflare's JS challenge fires, poll until it clears (or give up).
        waited = 0
        while waited < CHALLENGE_MAX_WAIT_MS:
            title = (page.title() or "").lower()
            if not any(marker in title for marker in CHALLENGE_TITLE_MARKERS):
                break
            page.wait_for_timeout(CHALLENGE_POLL_MS)
            waited += CHALLENGE_POLL_MS
        else:
            print(f"  [warn] {url} -> Cloudflare challenge did not clear after {waited}ms")
        # Let any client-side rendering (SPA search results, etc.) finish.
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        return page.content()
    except Exception as exc:  # Playwright raises its own error types
        print(f"  [warn] {url} -> {exc}")
        return None
    finally:
        page.close()
        time.sleep(REQUEST_DELAY_SECONDS)


PRICE_RE = re.compile(
    r"\$\s?\d{1,3}(?:\.\d{1,2})?\s?[kKmM]\b"  # e.g. $275K, $85K, $1.2M
    r"|\$\s?[\d,]{3,12}(?:\.\d{2})?"  # e.g. $149,500
)
_PRICE_SUFFIX_RE = re.compile(r"\$\s?(\d{1,3}(?:\.\d{1,2})?)\s?([kKmM])\b")
_PRICE_SUFFIX_MULTIPLIERS = {"k": 1_000, "m": 1_000_000}
STATE_ABBRS = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT "
    "NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC"
).split()
LOCATION_RE = re.compile(
    r"\b([A-Z][a-zA-Z.'\-]+(?:\s[A-Z][a-zA-Z.'\-]+)*),\s(" + "|".join(STATE_ABBRS) + r")\b"
)
DATE_LABEL_RE = re.compile(
    r"(?:Date Posted|Date Listed|Posted|Listed)[:\s]+"
    r"([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)


def extract_price(text: str) -> str:
    m = PRICE_RE.search(text)
    if not m:
        return "Contact for price"
    raw = m.group(0).strip()
    # "$275K" means $275,000, not two hundred seventy-five dollars - expand
    # the abbreviated K/M suffix into the full number instead of truncating it.
    suffix_match = _PRICE_SUFFIX_RE.fullmatch(raw)
    if suffix_match:
        value = float(suffix_match.group(1)) * _PRICE_SUFFIX_MULTIPLIERS[suffix_match.group(2).lower()]
        return f"${value:,.0f}"
    return raw


def extract_location(text: str) -> str:
    m = LOCATION_RE.search(text)
    return f"{m.group(1)}, {m.group(2)}" if m else "Unknown"


def extract_date(text: str) -> str:
    m = DATE_LABEL_RE.search(text)
    return m.group(1).strip() if m else ""


_DATE_POSTED_FORMATS = ("%B %d %Y", "%m/%d/%Y", "%m/%d/%y")


def parse_listing_date(date_posted: str) -> dt.date | None:
    """Parse the free-form 'Date Posted' string extract_date() produces
    (e.g. 'August 16, 2026' or '8/16/2026') into a comparable date, or None
    if it's missing/unparseable."""
    if not date_posted:
        return None
    cleaned = date_posted.replace(",", "").strip()
    for fmt in _DATE_POSTED_FORMATS:
        try:
            return dt.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def extract_jsonld_objects(soup: BeautifulSoup) -> list[dict]:
    """Pull every schema.org JSON-LD object out of a page, if any are present."""
    objects: list[dict] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        if isinstance(data, list):
            objects.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            objects.append(data)
    return objects


YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
LABELED_YEAR_RE = re.compile(r"\byear\W{0,6}(19\d{2}|20\d{2})\b", re.IGNORECASE)

# Words that mark a listing as parts/accessories/services/raffles rather than
# a whole aircraft for sale. Matched as whole words/phrases against the ad's
# title only (not the full ad body, where they're too likely to appear as
# incidental description text).
EXCLUDE_KEYWORDS = [
    "parts", "part", "wing", "wings", "wingtip", "wingtips", "wheel", "wheels", "wheeltire", "wheeltires", "float", "floats",
    "strut", "struts", "gear leg", "gear legs", "landing gear",
    "engine mount", "engine mounts", "prop", "props", "propeller",
    "propellers", "cowl", "cowling", "cowlings", "fairing", "fairings",
    "tail cone", "elevator",
    "rudder", "aileron", "ailerons", "flap", "flaps", "tank", "tanks",
    "cooler", "coolers", "oil cooler", "oil coolers",
    "spinner", "spinners", "hinge", "hinges", "cushion", "cushions",
    "seat", "seats", "door", "doors", "window", "windows", "carburetor",
    "magneto", "magnetos", "battery", "starter", "alternator",
    "instrument", "instruments", "avionics", "radio", "gps", "camshaft",
    "cylinder", "cylinders", "crankshaft", "gasket", "gaskets", "bracket",
    "brackets", "bushing", "spring", "springs", "housing", "mount",
    "mounts", "kit", "kits", "manual", "manuals", "logbook", "logbooks",
    "decal", "decals", "poster", "ski", "skis", "brake", "brakes",
    "tire", "tires", "tube", "tubes", "empennage", "fuselage", "cabin",
    "canopy", "windshield", "exhaust", "muffler", "harness", "wiring",
    "panel", "yoke", "control column", "controls", "cable", "cables",
    "throttle", "hardware", "hose", "hoses", "fitting", "fittings",
    "bearing", "bearings", "tailwheel", "upholstery", "sump", "dipstick",
    "connecting rods", "stc", "governor", "governors", "winter front", "winter fronts",
    "spray boom", "spray booms", "hopper", "hoppers", "spreader", "spreaders",
    "nozzle", "nozzles", "valve", "valves", "shock", "shocks", "rubber",
    "intake", "intakes",
    "raffle", "win a", "win an", "enter to win", "rental", "ferry pilot",
    "ferry service",
    "flight training", "instruction", "insurance", "financing", "wanted",
    "wtb", "consignment", "appraisal", "logistics",
]


def extract_listing_year(title: str, page_text: str = "") -> str | None:
    """Pull a 4-digit model year from the title, falling back to a labeled
    'Year: 19xx' field in the ad body if the title doesn't state one."""
    match = YEAR_RE.search(title)
    if match:
        return match.group(1)
    if page_text:
        match = LABELED_YEAR_RE.search(page_text)
        if match:
            return match.group(1)
    return None


def is_non_aircraft_ad(title: str) -> bool:
    """True if the title looks like a parts/accessory/service/raffle ad
    rather than a whole aircraft for sale."""
    # Any run of non-alphanumeric characters becomes a single space, not
    # just hyphens/underscores - otherwise a keyword directly followed by
    # punctuation (e.g. "cowl, engine mount") slips past the check below,
    # since " cowl " with a trailing space would never match "cowl,".
    normalized = re.sub(r"[^a-z0-9]+", " ", title.lower())
    normalized = " " + normalized.strip() + " "
    return any((" " + keyword + " ") in normalized for keyword in EXCLUDE_KEYWORDS)


def format_aircraft_title(title: str, page_text: str, extract_model) -> str | None:
    """Build a canonical 'YEAR MAKE MODEL' title (or just 'MAKE MODEL' if no
    model year could be found), or return None if this listing isn't a
    clean, identifiable whole-aircraft-for-sale ad.

    extract_model(title) must return an (make, model) tuple, or None if no
    recognized model is present in the title. A missing model is still
    disqualifying - a missing year is not, since plenty of genuine ads
    simply don't state one in the title.
    """
    if is_non_aircraft_ad(title):
        return None
    result = extract_model(title)
    if not result:
        return None
    make, model = result
    year = extract_listing_year(title, page_text)
    if year:
        return f"{year} {make} {model}"
    return f"{make} {model}"


@dataclass
class Listing:
    title: str
    price: str
    location: str
    date_posted: str
    site: str
    url: str

    def key(self) -> tuple:
        return (self.site, self.url)
