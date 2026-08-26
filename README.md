# Swift

Daily aggregator of Globe/Temco Swift classified listings (GC-1A, GC-1B,
and bare "Swift" mentions) from
[Barnstormers.com](https://www.barnstormers.com), published as a static
page (`docs/index.html`) meant to be embedded via `<iframe>` on
taildraggers.com.

Controller.com was evaluated (in the companion [Aeronca](https://github.com/taildraggers/aeronca)
repo) and dropped: its search results are only reachable through an internal
client-side widget (not a plain URL), which a headless browser can't drive
reliably for an unattended daily job.

Note: in the companion [Aviat](https://github.com/taildraggers/aviat),
[CubCrafters](https://github.com/taildraggers/cub-crafters),
[de Havilland](https://github.com/taildraggers/de-Havilland),
[Maule](https://github.com/taildraggers/maule),
[Van's RV](https://github.com/taildraggers/vans),
[RANS](https://github.com/taildraggers/rans),
[Luscombe](https://github.com/taildraggers/luscombe),
[Just Aircraft](https://github.com/taildraggers/just-aircraft),
[Kitfox](https://github.com/taildraggers/kitfox),
[Bellanca](https://github.com/taildraggers/bellanca),
[Stearman](https://github.com/taildraggers/stearman),
[Waco](https://github.com/taildraggers/waco), and
[Pitts](https://github.com/taildraggers/pitts) repos, Barnstormers'
single-manufacturer category pages turned out to include unrelated
listings mixed in with no distinguishing HTML markup. This repo is built
with the same fix from day one: `scraper/barnstormers.py` filters by
title against a small allowlist (see `TARGET_MODEL_PHRASES` in
`scraper/barnstormers.py`) before publishing.

"Swift" is an ordinary English word (unlike "Pitts", "Waco", or
"Stearman"), so there's a real risk of an unrelated ad using it in a
generic sense slipping past a bare substring check. The aircraft was built
by two different manufacturers across its history - Globe Aircraft
Company originally, then Temco after Globe folded - and both names appear
in ads, so requiring "Globe" or "Temco" alongside "Swift" would wrongly
exclude plenty of genuine listings that just say "Swift" on its own (the
same problem seen in the companion Stearman repo). Instead, the two
factory model codes (`GC-1A`, `GC-1B`) are trusted only when "Swift" is
also in the title, and a bare "Swift" mention with no code stated is
trusted on its own since this category page is scoped to the aircraft
already - the same bare-brand policy used in the companion Stearman/Waco/
Pitts repos. Titles that read as parts, accessories, services, or raffles
are still dropped regardless. Every surviving listing's title is rewritten
to a canonical **`YEAR SWIFT MODEL`** form when the ad states a model year
and a specific model (e.g. `1946 Swift GC-1A`), `YEAR Swift` when only the
model is missing, `SWIFT MODEL` when only the year is missing, or plain
**`Swift`** when neither is stated.

**Gear note:** the factory Globe/Temco Swift (GC-1A and GC-1B alike) is a
conventional tailwheel-gear design with no tricycle-gear variant ever
built - so, as with the companion Pitts and Waco repos, no categorical
gear exclusion is needed here. The standard text-based tricycle/nosewheel
safety net used in those repos is still applied to every listing as a
general precaution, since one-off homebuilt tricycle-gear conversions do
turn up occasionally.

## How it works

- `scraper/barnstormers.py` searches Barnstormers.com's Swift category for
  listings, follows pagination, then keeps only the ones whose URL slug
  matches the Swift allowlist (Barnstormers builds each listing's URL slug
  directly from the ad's own title, so this runs before any detail page is
  fetched). For the matches, it visits each listing's detail page to pull
  out the price, location, and posted date (falling back to regex
  heuristics over the visible text since the site doesn't expose
  structured data). The title is derived from the listing URL's own SEO
  slug, since every detail page shares one generic `<title>`/`<h1>`; the
  final parsed title is checked against the allowlist again as a safety
  net. Pagination is built directly from Barnstormers' known
  `?seocategory=<url-encoded-path>&page=<n>` URL pattern rather than
  discovered by following a "Next" link, since this category's pager
  renders as page-number buttons with no "Next" text or `rel="next"`
  attribute to find (a lesson learned the hard way in the companion Van's
  RV repo, where the link-following approach silently stopped after
  page 1).
- `main.py` runs the scraper, de-duplicates results, sorts them
  newest-posted-first, and renders them into `docs/index.html` titled
  **"Other Swift Ads on the Web"**, with one row per listing: Title
  (linked to the original ad), Price, Location, Date Posted, and Site
  Posted On. Below phone width, each row collapses into a card (title +
  price on one line, location/date/site on a smaller line below) instead
  of a horizontally-scrolling table. Below the table, a "Search More Swift
  Listings" section links out to Trade-A-Plane, Controller, and ASO -
  sites that block automated scraping, but are still worth sending
  visitors to directly via a pre-filled search. Links use
  `rel="noopener noreferrer"` and the page sets a `no-referrer` meta
  policy, so none of these sites see that the click came from
  taildraggers.com.
- `.github/workflows/daily-scrape.yml` runs the whole thing once a day (13:00 UTC),
  commits the regenerated `docs/index.html` if it changed, and can also be triggered
  manually from the Actions tab (`workflow_dispatch`).

## One-time setup: enable GitHub Pages

This repo publishes `docs/index.html` as a plain static file — GitHub Pages just needs
to be pointed at it once:

1. Go to **Settings → Pages** in this repository.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Branch: `main`, folder: `/docs`. Save.
4. GitHub will publish the page at `https://taildraggers.github.io/swift/`
   (may take a minute or two the first time).

Also check **Settings → Actions → General**:
- **Actions permissions**: "Allow all actions and reusable workflows".
- **Workflow permissions**: "Read and write permissions" (needed so the daily
  job can commit the regenerated page back to the repo).

## Embedding on taildraggers.com

```html
<iframe
  src="https://taildraggers.github.io/swift/"
  title="Other Swift Ads on the Web"
  style="width: 100%; height: 800px; border: 0;"
  loading="lazy">
</iframe>
```

The page also posts its rendered height to the parent window on load/resize
(`{ type: "taildraggers:resize", height }`) so it can be auto-sized instead
of using a fixed guessed height - add a matching `message` listener on the
embedding page to pick this up.

## Running locally

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
python main.py
```

This writes/overwrites `docs/index.html`.

## Notes

- If Barnstormers changes its markup or is briefly unreachable, the run logs will
  show a `[warn]`/`[error]` line pointing at what broke rather than failing silently.
- The scraper identifies itself with a browser-like `User-Agent` and adds a short
  delay between requests to be polite to the site.
- Only one Barnstormers category is currently configured
  (`category-22191-Swift.html`). If listings turn out to be split across
  additional categories, add more URLs to `CATEGORY_URLS` in
  `scraper/barnstormers.py`.
