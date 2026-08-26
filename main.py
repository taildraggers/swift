"""Scrape Swift listings from Barnstormers.com and render them into
docs/index.html for embedding via <iframe> on taildraggers.com.
"""
from __future__ import annotations

import datetime as dt
import html
import os

from scraper import barnstormers
from scraper.common import Listing, close_browser, parse_listing_date

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "docs", "index.html")
PAGE_TITLE = "Other Swift Ads on the Web"

# Sites that block automated scraping, but are still worth sending visitors
# to directly via a pre-filled search link.
EXTERNAL_SEARCH_LINKS = [
    (
        "Trade-A-Plane",
        "https://www.trade-a-plane.com/filtered/search?s-type=aircraft&s-keyword-search=swift&s-original-search=swift",
    ),
    ("Controller", "https://www.controller.com/listings?keywords=swift"),
    ("ASO", "https://aso.com/search?q=Swift"),
]


def collect_listings() -> list[Listing]:
    listings: list[Listing] = []
    try:
        for scraper in (barnstormers,):
            try:
                listings.extend(scraper.scrape())
            except Exception as exc:  # one site failing shouldn't kill the whole run
                print(f"[error] {scraper.SITE_NAME} scrape failed: {exc}")
    finally:
        close_browser()

    seen = set()
    unique: list[Listing] = []
    for listing in listings:
        if listing.key() in seen:
            continue
        seen.add(listing.key())
        unique.append(listing)
    # Newest posted first; listings with no parseable post date sort last,
    # alphabetically among themselves.
    def _sort_key(listing: Listing):
        posted = parse_listing_date(listing.date_posted)
        if posted is None:
            return (1, 0, listing.title.lower())
        return (0, -posted.toordinal(), listing.title.lower())

    unique.sort(key=_sort_key)
    return unique


def render_html(listings: list[Listing]) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    rows = []
    for listing in listings:
        rows.append(
            "\n        <tr>"
            f'<td><a href="{html.escape(listing.url)}" target="_blank" '
            f'rel="noopener noreferrer">{html.escape(listing.title)}</a></td>'
            f"<td>{html.escape(listing.price or 'Contact for price')}</td>"
            f"<td>{html.escape(listing.location or 'Unknown')}</td>"
            f"<td>{html.escape(listing.date_posted or '-')}</td>"
            f"<td>{html.escape(listing.site)}</td>"
            "</tr>"
        )

    rows_html = "".join(rows) if rows else (
        '\n        <tr><td colspan="5" class="empty">'
        "No listings found in the latest run.</td></tr>"
    )

    resource_links_html = "".join(
        f'\n      <a class="resource-link" href="{html.escape(url)}" '
        f'target="_blank" rel="noopener noreferrer">'
        f"<span>{html.escape(name)}</span><span class=\"resource-arrow\">&rarr;</span></a>"
        for name, url in EXTERNAL_SEARCH_LINKS
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{html.escape(PAGE_TITLE)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          margin: 0; padding: 1rem; background: #fff; color: #1a1a1a; }}
  h1 {{ font-size: 1.25rem; margin: 0 0 0.75rem; }}
  .updated {{ font-size: 0.8rem; color: #666; margin-bottom: 0.25rem; }}
  .disclaimer {{ font-size: 0.75rem; font-style: italic; color: #888; margin-bottom: 1rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid #e2e2e2; vertical-align: top; }}
  th {{ background: #f5f5f5; position: sticky; top: 0; }}
  tr:hover {{ background: #fafafa; }}
  a {{ color: #0b5fa5; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .empty {{ text-align: center; color: #888; padding: 1.5rem; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #14161a; color: #e6e6e6; }}
    th {{ background: #1e2125; }}
    th, td {{ border-bottom-color: #2a2d31; }}
    tr:hover {{ background: #1a1c20; }}
    a {{ color: #6cb2f2; }}
    .updated {{ color: #9aa0a6; }}
    .disclaimer {{ color: #7a7f85; }}
  }}
  /* Below phone width, each row becomes a card: title + price on one line,
     location / date / site on a second line. Wider viewports (tablets,
     desktop embeds) keep the table exactly as it is above. */
  @media (max-width: 600px) {{
    table {{ display: block; }}
    thead {{ display: none; }}
    tbody {{ display: flex; flex-direction: column; gap: 0.6rem; }}
    tr {{ display: flex; flex-wrap: wrap; align-items: baseline; row-gap: 0.3rem;
          column-gap: 0.5rem; border: 1px solid #e2e2e2; border-radius: 8px;
          padding: 0.7rem 0.8rem; }}
    tr:hover {{ background: none; }}
    td {{ display: block; border: none; padding: 0; }}
    td:nth-child(1) {{ flex: 1 1 auto; min-width: 0; order: 1; font-weight: 600; font-size: 0.92rem; }}
    td:nth-child(2) {{ flex: 0 0 auto; order: 2; margin-left: auto; font-weight: 600;
                        font-variant-numeric: tabular-nums; white-space: nowrap; }}
    td:nth-child(3) {{ order: 3; flex-basis: 100%; font-size: 0.78rem; color: #666; }}
    td:nth-child(4) {{ order: 4; font-size: 0.78rem; color: #666; }}
    td:nth-child(4)::before {{ content: "\\00B7\\0020"; }}
    td:nth-child(5) {{ order: 5; font-size: 0.78rem; color: #666; }}
    td:nth-child(5)::before {{ content: "\\00B7\\0020"; }}
    td.empty {{ font-weight: 400; font-size: 0.9rem; }}
  }}
  @media (prefers-color-scheme: dark) and (max-width: 600px) {{
    tr {{ border-color: #2a2d31; }}
    td:nth-child(3), td:nth-child(4), td:nth-child(5) {{ color: #9aa0a6; }}
  }}
  .more-resources {{ margin-top: 1.5rem; padding-top: 1.1rem; border-top: 1px solid #e2e2e2; }}
  .more-resources h2 {{ font-size: 0.95rem; margin: 0 0 0.3rem; }}
  .more-resources p {{ font-size: 0.78rem; color: #666; margin: 0 0 0.75rem; }}
  .resource-links {{ display: flex; flex-wrap: wrap; gap: 0.6rem; }}
  .resource-link {{
    display: inline-flex; align-items: center; gap: 0.45rem;
    padding: 0.55rem 0.95rem; border: 1px solid #e2e2e2; border-radius: 999px;
    font-size: 0.85rem; font-weight: 600; color: #0b5fa5; text-decoration: none;
    background: #f5f5f5; transition: background 0.15s ease, border-color 0.15s ease;
  }}
  .resource-link:hover {{ background: #eaf2fa; border-color: #0b5fa5; text-decoration: none; }}
  .resource-arrow {{ opacity: 0.55; }}
  @media (prefers-color-scheme: dark) {{
    .more-resources {{ border-top-color: #2a2d31; }}
    .more-resources p {{ color: #9aa0a6; }}
    .resource-link {{ background: #1e2125; border-color: #2a2d31; color: #6cb2f2; }}
    .resource-link:hover {{ background: #202632; border-color: #6cb2f2; }}
  }}
</style>
</head>
<body>
  <h1>{html.escape(PAGE_TITLE)}</h1>
  <div class="updated">Updated {html.escape(now)} &middot; {len(listings)} listing(s)</div>
  <div class="disclaimer">External listings are provided for informational purposes. Taildraggers.com is not affiliated with or endorsed by the originating listing sites. Listing information remains the responsibility of the original publisher. Clicking an external listing will take you to the source website.</div>
  <table>
    <thead>
      <tr><th>Title</th><th>Price</th><th>Location</th><th>Date Posted</th><th>Site Posted On</th></tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
  <div class="more-resources">
    <h2>Search More Swift Listings</h2>
    <p>View additional Swift Aircraft listings at these fine sites:</p>
    <div class="resource-links">{resource_links_html}
    </div>
  </div>
<script>
  // Reports this page's rendered height to the parent window so an iframe
  // embed can size itself to fit, instead of using a fixed guessed height.
  // Requires a matching listener on the embedding page - see the repo README.
  (function () {{
    if (window.parent === window) return;
    var lastHeight = 0;
    function postHeight() {{
      var h = document.documentElement.scrollHeight;
      if (h !== lastHeight) {{
        lastHeight = h;
        window.parent.postMessage({{ type: "taildraggers:resize", height: h }}, "*");
      }}
    }}
    window.addEventListener("load", postHeight);
    window.addEventListener("resize", postHeight);
    if (window.ResizeObserver) {{
      new ResizeObserver(postHeight).observe(document.body);
    }}
    postHeight();
  }})();
</script>
</body>
</html>
"""


def main() -> None:
    listings = collect_listings()
    print(f"[main] total unique listings: {len(listings)}")
    html_doc = render_html(listings)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"[main] wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
