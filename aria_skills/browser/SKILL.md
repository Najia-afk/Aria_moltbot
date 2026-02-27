# aria-browser — Headless Browser Skill

**Layer:** 2 (Infrastructure) | **Category:** Browser | **Status:** Active

## Purpose

Headless browser access via the `aria-browser` (browserless/chromium) service. Navigate, snapshot, screenshot, and scrape web pages without needing a local browser binary.

## Configuration (env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSERLESS_URL` | `http://aria-browser:3000` | Browserless service URL |
| `BROWSERLESS_INTERNAL_PORT` | `3000` | Internal container port (used for URL construction) |

## Tools

| Tool | Description |
|------|-------------|
| `navigate(url, wait_for?, timeout?)` | Fetch full page HTML, title, and HTTP status |
| `snapshot(url, selectors?)` | Structured page extract: title, headings, links, meta, text |
| `screenshot(url, full_page?)` | Capture PNG as base64 |
| `scrape(url, elements[])` | Extract specific elements by CSS selector |

## Usage

```python
# Via run_skill.py
python3 aria_mind/skills/run_skill.py browser navigate '{"url": "https://example.com"}'
python3 aria_mind/skills/run_skill.py browser snapshot '{"url": "https://example.com"}'

# Via aria agent tools
aria-browser.navigate({"url": "https://example.com"})
aria-browser.scrape({"url": "https://example.com", "elements": [{"selector": "h1"}]})
```

## Dependencies

- `httpx` — HTTP client for browserless API
- `aria-browser` Docker service (browserless/chromium v2)

## Notes

- Upgraded from `browserless/chrome` v1 → `ghcr.io/browserless/chromium` v2 in S-50
- Service URL always resolved from env vars — never hardcoded
- Use `navigate` for full HTML; use `snapshot` for structured content (lower token cost)
