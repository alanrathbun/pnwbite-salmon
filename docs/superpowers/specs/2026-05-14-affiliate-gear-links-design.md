# Affiliate gear links — design

**Date:** 2026-05-14
**Status:** Draft, pending approval

## Goal

Earn a commission on fishing gear that the salmon report already recommends, without compromising editorial integrity. The bait rules pick the gear; the affiliate layer only picks the *vendor link*.

## Scope (MVP)

In:

- Inline affiliate links on every gear bullet currently rendered in the `_species_block` technique panel.
- Two vendors: Amazon Associates and Sportsman's Warehouse (via AvantLink).
- Search-URL-based links (no curated SKU map).
- One-line FTC disclosure banner under the report header.
- Per-link tracking sub-tag = `<launch_key>__<species>` so vendor dashboards reveal which fishing recommendations drive clicks.
- Graceful degradation: if affiliate env vars are missing, the report falls back to plain gear bullets.

Out (defer to later phases if revenue justifies):

- Curated SKU mapping per gear keyword.
- Server-side click tracking, A/B testing, conversion analytics beyond what the vendor dashboards report.
- Showing prices, images, or reviews inline.
- Affiliate-link health monitoring (broken SKUs, dead-end searches).
- A separate "Shop the rig" button or shopping-list page.
- Affiliate links inside the Trip Planner results or top-picks rows (gear isn't surfaced there in the current design).
- Adding affiliate links to the `pikeminnow` companion app.

## User-facing behavior

Today the technique block renders gear like:

```
★ Spinner-and-eggs (back-trolling)
  - rod: medium-heavy 8'6"
  - line: 25 lb mono
  - flasher: hot pink size 4
  - bait: cured roe
```

After this change, each gear bullet gains two small inline link badges:

```
★ Spinner-and-eggs (back-trolling)
  - rod: medium-heavy 8'6" [amzn] [spwh]
  - line: 25 lb mono [amzn] [spwh]
  - flasher: hot pink size 4 [amzn] [spwh]
  - bait: cured roe [amzn] [spwh]
```

Clicking `[amzn]` opens an Amazon search results page for the gear keywords, with the affiliate tag attached. Clicking `[spwh]` opens a Sportsman's Warehouse search via AvantLink's redirect URL.

A single-line disclosure renders directly under the report header:

> *Gear links are affiliate links — we earn a small commission if you buy, at no cost to you.*

Each badge also gets a `title=` tooltip ("Search Amazon (affiliate link)" / "Search Sportsman's Warehouse (affiliate link)") for in-context disclosure on hover.

## Architecture

One new pure-Python module, two new render helpers, no schema changes.

### `engines/affiliate.py` (new)

Pure function. No I/O. Reads credentials from `os.environ`.

```python
@dataclass(frozen=True)
class AffiliateLink:
    vendor: str          # "amzn" | "spwh"
    url: str             # fully formed affiliate URL
    label: str           # short text shown in the badge ("amzn" / "spwh")
    title: str           # tooltip text for the link

def links_for(query: str, *, launch_key: str, species: str) -> list[AffiliateLink]:
    """Return zero, one, or two affiliate links for a gear query string.

    Caller is expected to pass a clean search phrase (e.g. "hot pink size
    4 flasher"). URL-encodes the query, appends a sub-tag for
    vendor-dashboard attribution.

    Missing credentials → that vendor is silently omitted. If both are
    missing, returns an empty list and the renderer falls back to plain
    gear text.
    """
```

Credentials read from env (read once at module load, cached):

- `AMAZON_AFFILIATE_TAG` — e.g. `pnwbite-20`
- `AVANTLINK_AFFILIATE_ID` — your AvantLink account ID
- `AVANTLINK_SPWH_MERCHANT_ID` — Sportsman's Warehouse merchant ID inside AvantLink

URL templates:

```python
AMAZON_URL = (
    "https://www.amazon.com/s"
    "?k={query}"
    "&tag={tag}"
    "&ascsubtag={subtag}"
)

# AvantLink wraps the destination URL. The destination is a Sportsman's
# Warehouse search page; AvantLink rewrites the click and forwards.
SPWH_URL = (
    "https://www.avantlink.com/click.php"
    "?tt=cl"
    "&merchant_id={merchant_id}"
    "&affiliate_id={affiliate_id}"
    "&url={target}"
    "&pat={subtag}"
)
SPWH_TARGET = "https://www.sportsmans.com/search?query={query}"
```

Sub-tag format: `f"{launch_key}__{species}"` (double underscore to avoid collisions with launch keys that contain a single underscore).

Query cleaning:

- Strip a leading `"<key>: "` prefix if present (so we search "hot pink size 4 flasher" not "flasher: hot pink size 4").
- URL-encode the result with `urllib.parse.quote_plus`.

### `render.py` `_gear_bullets(gear: dict, *, launch_key: str, species: str) -> str` (new helper)

Replaces the inline list comprehension currently in `_species_block`. For each `(key, value)` in `gear`:

- Compose `query = f"{value} {key}"` (e.g. `"hot pink size 4 flasher"`).
- Call `affiliate.links_for(query, launch_key=launch_key, species=species)`.
- Emit `<li>{key}: {value}{badges}</li>` where `badges` is either empty (no env vars set) or the concatenation of `<a>` tags below.

Badge HTML pattern (one `<a>` per vendor returned):

```html
<a class="aff aff-amzn" href="{url}" target="_blank"
   rel="sponsored nofollow noopener" title="{title}">amzn</a>
```

`rel="sponsored nofollow noopener"` is the Google + FTC-recommended combination for paid outbound links.

### `render.py` `_disclosure_banner() -> str` (new helper)

Returns a single `<aside class="aff-disclosure muted">...</aside>` placed inside `_header_bar` between the date picker and the score-legend `<details>`. Only renders when at least one vendor env var is set; otherwise returns empty string (so the test/dev environment doesn't show a misleading disclosure with no actual affiliate links present).

### CSS additions (in `_head` style block)

```css
.aff {
    display: inline-block;
    margin-left: 0.25rem;
    padding: 0 0.25rem;
    font-size: 0.7rem;
    line-height: 1.4;
    border: 1px solid var(--border);
    border-radius: 3px;
    color: var(--muted);
    text-decoration: none;
}
.aff:hover { color: var(--fg); background: var(--card-hover, #2a2a2a); }
.aff-amzn { /* future room for vendor-specific accent color */ }
.aff-spwh { /* future room for vendor-specific accent color */ }
.aff-disclosure {
    font-size: 0.75rem;
    margin: 0.25rem 0;
}
```

## Data flow

1. `build_report_data` populates `data["forecasts"][sp::launch]` with per-day entries; today's entry carries `techniques[0].gear`.
2. `render_html` calls `_launch_card` → `_species_block(sp, days, section_open)`.
3. `_species_block` now passes `launch_key` and `sp` into `_gear_bullets(gear, launch_key=..., species=...)`.
4. `_gear_bullets` iterates `gear` items; for each, calls `affiliate.links_for(query, launch_key=, species=)`.
5. `links_for` reads cached env vars; if any vendor is configured, builds the URL with `urllib.parse.urlencode`-style encoding and the sub-tag.
6. HTML is emitted; static file ships as today; Cloudflare caches as today.

No JS changes. No payload changes. Affiliate URLs are baked into the static HTML at cron time.

## Configuration

New env vars on Railway service `pnwbite-salmon`:

- `AMAZON_AFFILIATE_TAG` (e.g. `pnwbite-20`)
- `AVANTLINK_AFFILIATE_ID`
- `AVANTLINK_SPWH_MERCHANT_ID`

Locally: unset means affiliate links don't render. Set values are echoed nowhere in logs.

## Compliance

- FTC disclosure: in-context banner under the header (above the day-strip) plus tooltip on each badge. Both are present together — meets "clear and conspicuous near the affiliate content" guidance.
- Amazon Associates Operating Agreement: the `tag=` param is required; `ascsubtag` is allowed; the disclosure language ("we earn a small commission") matches the agreement's required wording.
- `rel="sponsored nofollow noopener"`: signals to search engines that the link is paid (Google's recommended attribute for affiliate links).

## Testing

### Unit (pure function)

- `links_for` with both env vars set → returns 2 links in `[amzn, spwh]` order.
- `links_for` with only `AMAZON_AFFILIATE_TAG` set → returns 1 link, amzn only.
- `links_for` with no env vars set → returns `[]`.
- Query containing spaces, ampersand, apostrophe, quotes → URLs are correctly percent-encoded (assert via `urllib.parse.parse_qs` round-trip).
- Sub-tag inclusion: assert `ascsubtag=brewster__chinook` and `pat=brewster__chinook` appear in URLs.
- `_gear_bullets` constructs `f"{value} {key}"` as the search phrase from a gear dict entry (e.g. `flasher: "hot pink size 4"` → query `"hot pink size 4 flasher"`).

### Render

- Snapshot-style test on `_species_block` output with both env vars set: every gear `<li>` has exactly two `<a class="aff">` children with `rel="sponsored nofollow noopener"`.
- With no env vars: zero `<a class="aff">` elements in output; gear bullets are plain `<li>` text.
- `_disclosure_banner` with at least one env var → returns the `<aside>`. With no env vars → empty string.

### Manual

- Generate report locally with `AMAZON_AFFILIATE_TAG=test-tag` and AvantLink vars set to dummy values. Open in browser, click each badge, confirm URLs are well-formed (Amazon search renders; AvantLink redirects to the SpWh search with the affiliate parameters intact).
- Run the regen on Railway after deploy, confirm the rendered HTML has affiliate badges and the disclosure banner.

## Failure modes

- **Env var missing in production**: that vendor's link is silently dropped. Acceptable — the report still renders fully without affiliate links.
- **Gear value contains special chars that break URL encoding**: `quote_plus` handles all ASCII and Unicode safely.
- **AvantLink merchant ID rotates / SpWh leaves AvantLink**: links would 404 or redirect to an error page. Mitigation deferred — vendor dashboards will show a click-to-conversion collapse and prompt manual investigation.
- **Amazon Associates account banned for ToS violation**: catastrophic, but we control the disclosure language and link structure so this is unlikely. Mitigation: keep the env var; unsetting it cleanly removes the feature.

## Decision log

- **Two vendors, not one**: Amazon's catalog covers nearly everything but at 3-4% commission; Sportsman's Warehouse pays 5-7% via AvantLink and is PNW-native. Showing both lets the user pick.
- **Search URLs, not curated SKUs**: bait rules already encode the gear name; manually mapping ~50 keywords to specific SKUs would create a maintenance debt that doesn't pay off until traffic is much higher.
- **Inline badges, not a "Shop the rig" button**: highest click-through rate, lowest visual cost. The badges are small and skippable.
- **Both vendor badges always shown, no routing logic**: simplest implementation, most transparent to the user. Trade-off: we lose the chance to nudge toward higher-commission vendor automatically; gain: no per-keyword vendor allowlist to maintain.
- **No bait-rule schema changes**: keeps the editorial layer (bait rules) decoupled from the monetization layer (affiliate links). If we ever want to change vendors, we change `affiliate.py` only.
- **Sub-tag granularity = launch + species**: enough resolution to see which fishing recommendations drive clicks, without going so fine-grained that vendor dashboards become a wall of one-click rows.
