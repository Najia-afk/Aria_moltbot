# aria_skills/browser/__init__.py
"""
Browser Skill — headless Chrome via aria-browser (browserless/chrome).

Provides Aria with web browsing capabilities through the internal
aria-browser service. All web access MUST go through this skill
(per AGENTS.md browser policy).

Endpoints used:
  POST /content    — full page HTML
  POST /scrape     — extract elements by CSS selector
  POST /screenshot — PNG screenshot (base64)

The browser URL is resolved from env:
  BROWSERLESS_URL > config.browser_url > http://aria-browser:${BROWSERLESS_INTERNAL_PORT:-3000}
"""
import base64
import os
import logging
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger("aria.skills.browser")


@SkillRegistry.register
class BrowserSkill(BaseSkill):
    """
    Headless browser for web access via browserless/chrome REST API.

    Methods:
        navigate(url)    — fetch full page HTML + title + status
        snapshot(url)    — structured page summary (title, headings, links, text)
        screenshot(url)  — PNG screenshot as base64
        scrape(url, elements) — extract elements by CSS selector
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._client: "httpx.AsyncClient" | None = None
        self._browser_url: str = ""

    @property
    def name(self) -> str:
        return "browser"

    @property
    def canonical_name(self) -> str:
        return "aria-browser"

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def initialize(self) -> bool:
        if not HAS_HTTPX:
            self.logger.error("httpx not installed — browser skill unavailable")
            self._status = SkillStatus.UNAVAILABLE
            return False

        # Resolve browser URL: env > skill config > default
        port = os.environ.get("BROWSERLESS_INTERNAL_PORT", "3000")
        default_url = f"http://aria-browser:{port}"
        self._browser_url = (
            os.environ.get("BROWSERLESS_URL")
            or self.config.config.get("browser_url")
            or default_url
        )

        # Optional token auth
        token = os.environ.get("BROWSERLESS_TOKEN", "")
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Basic {token}"

        self._client = httpx.AsyncClient(
            base_url=self._browser_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers=headers,
        )

        # Quick connectivity check
        try:
            resp = await self._client.get("/")
            if resp.status_code < 500:
                self._status = SkillStatus.AVAILABLE
                self.logger.info(
                    "Browser skill ready → %s (status %d)",
                    self._browser_url, resp.status_code,
                )
                return True
        except Exception as e:
            self.logger.warning("Browser connectivity check failed: %s", e)

        # Service might not be up yet — mark available anyway (lazy check)
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Browser skill initialized (connectivity check deferred)")
        return True

    async def health_check(self) -> SkillStatus:
        if not self._client:
            return SkillStatus.UNAVAILABLE
        try:
            resp = await self._client.get("/")
            if resp.status_code < 500:
                self._status = SkillStatus.AVAILABLE
            else:
                self._status = SkillStatus.ERROR
        except Exception:
            self._status = SkillStatus.ERROR
        return self._status

    async def cleanup(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Tools ──────────────────────────────────────────────────────────

    @logged_method()
    async def navigate(self, url: str, wait_for: str | None = None, timeout: int = 30000) -> SkillResult:
        """
        Navigate to a URL and return the full page HTML, title, and status.

        Uses the browserless /content endpoint which renders the page with
        headless Chrome and returns the resulting HTML.
        """
        if not self._client:
            return SkillResult.fail("Browser skill not initialized")

        payload: dict[str, Any] = {"url": url}
        if wait_for:
            payload["waitForSelector"] = {"selector": wait_for, "timeout": timeout}
        else:
            payload["gotoOptions"] = {"waitUntil": "networkidle2", "timeout": timeout}

        try:
            resp = await self._client.post("/content", json=payload)
            html = resp.text

            # Extract title from HTML
            title = ""
            if "<title>" in html.lower():
                start = html.lower().index("<title>") + 7
                end = html.lower().index("</title>", start) if "</title>" in html.lower() else start + 200
                title = html[start:end].strip()

            # Truncate if very large (keep useful portion)
            max_len = 8000
            truncated = len(html) > max_len
            content_preview = html[:max_len] if truncated else html

            return SkillResult.ok({
                "url": url,
                "title": title,
                "status_code": resp.status_code,
                "html": content_preview,
                "total_length": len(html),
                "truncated": truncated,
            })
        except httpx.TimeoutException:
            return SkillResult.fail(f"Timeout navigating to {url} (>{timeout}ms)")
        except httpx.ConnectError as e:
            return SkillResult.fail(f"Cannot reach browser service at {self._browser_url}: {e}")
        except Exception as e:
            return SkillResult.fail(f"Navigation failed: {e}")

    @logged_method()
    async def snapshot(self, url: str, selectors: list[str] | None = None) -> SkillResult:
        """
        Take a structured snapshot of a web page.

        Extracts title, headings, links, meta, and visible text using the
        browserless /scrape endpoint with default selectors.
        """
        if not self._client:
            return SkillResult.fail("Browser skill not initialized")

        # Default selectors for a comprehensive page snapshot
        if not selectors:
            selectors = ["title", "h1", "h2", "h3", "p", "a[href]", "meta[name]", "meta[property]", "img[alt]"]

        elements = [{"selector": s} for s in selectors]

        try:
            resp = await self._client.post("/scrape", json={
                "url": url,
                "elements": elements,
                "gotoOptions": {"waitUntil": "networkidle2", "timeout": 30000},
            })

            if resp.status_code != 200:
                return SkillResult.fail(
                    f"Scrape returned HTTP {resp.status_code}: {resp.text[:500]}"
                )

            data = resp.json()

            # Build a structured summary
            snapshot: dict[str, Any] = {"url": url, "elements": {}}
            for item in data.get("data", []):
                sel = item.get("selector", "?")
                results = item.get("results", [])
                elements_data = []
                for r in results[:20]:  # Cap to avoid massive payloads
                    entry: dict[str, str] = {}
                    if r.get("text"):
                        entry["text"] = r["text"][:500]
                    if r.get("html") and r["html"] != r.get("text"):
                        entry["html"] = r["html"][:500]
                    if r.get("attributes"):
                        attrs = {a["name"]: a["value"] for a in r["attributes"] if a.get("value")}
                        if attrs:
                            entry["attributes"] = attrs
                    if entry:
                        elements_data.append(entry)
                if elements_data:
                    snapshot["elements"][sel] = elements_data

            # Count visible content
            total_items = sum(len(v) for v in snapshot["elements"].values())
            snapshot["total_elements"] = total_items

            return SkillResult.ok(snapshot)

        except httpx.TimeoutException:
            return SkillResult.fail(f"Timeout snapshotting {url}")
        except httpx.ConnectError as e:
            return SkillResult.fail(f"Cannot reach browser service: {e}")
        except Exception as e:
            return SkillResult.fail(f"Snapshot failed: {e}")

    @logged_method()
    async def screenshot(self, url: str, full_page: bool = False) -> SkillResult:
        """
        Capture a PNG screenshot of a web page.

        Returns base64-encoded image data. The frontend or other skills
        can decode and display/save it.
        """
        if not self._client:
            return SkillResult.fail("Browser skill not initialized")

        try:
            payload: dict[str, Any] = {
                "url": url,
                "options": {
                    "fullPage": full_page,
                    "type": "png",
                },
                "gotoOptions": {"waitUntil": "networkidle2", "timeout": 30000},
            }

            resp = await self._client.post("/screenshot", json=payload)

            if resp.status_code != 200:
                return SkillResult.fail(
                    f"Screenshot returned HTTP {resp.status_code}: {resp.text[:500]}"
                )

            img_b64 = base64.b64encode(resp.content).decode("utf-8")
            return SkillResult.ok({
                "url": url,
                "image_base64": img_b64,
                "size_bytes": len(resp.content),
                "format": "png",
                "full_page": full_page,
            })

        except httpx.TimeoutException:
            return SkillResult.fail(f"Timeout taking screenshot of {url}")
        except httpx.ConnectError as e:
            return SkillResult.fail(f"Cannot reach browser service: {e}")
        except Exception as e:
            return SkillResult.fail(f"Screenshot failed: {e}")

    @logged_method()
    async def scrape(self, url: str, elements: list[dict[str, str]] | None = None) -> SkillResult:
        """
        Extract specific elements from a web page by CSS selector.

        Args:
            url: Page URL to scrape
            elements: List of dicts with 'selector' key, e.g.
                      [{"selector": "h1"}, {"selector": ".price"}]
        """
        if not self._client:
            return SkillResult.fail("Browser skill not initialized")

        if not elements:
            return SkillResult.fail("No elements/selectors provided")

        try:
            resp = await self._client.post("/scrape", json={
                "url": url,
                "elements": elements,
                "gotoOptions": {"waitUntil": "networkidle2", "timeout": 30000},
            })

            if resp.status_code != 200:
                return SkillResult.fail(
                    f"Scrape returned HTTP {resp.status_code}: {resp.text[:500]}"
                )

            data = resp.json()
            results: dict[str, list] = {}
            for item in data.get("data", []):
                sel = item.get("selector", "?")
                sel_results = []
                for r in item.get("results", [])[:50]:
                    entry: dict[str, Any] = {}
                    if r.get("text"):
                        entry["text"] = r["text"][:1000]
                    if r.get("html"):
                        entry["html"] = r["html"][:1000]
                    if r.get("attributes"):
                        entry["attributes"] = {
                            a["name"]: a["value"]
                            for a in r["attributes"]
                            if a.get("value")
                        }
                    if entry:
                        sel_results.append(entry)
                results[sel] = sel_results

            total = sum(len(v) for v in results.values())
            return SkillResult.ok({
                "url": url,
                "results": results,
                "total_matches": total,
            })

        except httpx.TimeoutException:
            return SkillResult.fail(f"Timeout scraping {url}")
        except httpx.ConnectError as e:
            return SkillResult.fail(f"Cannot reach browser service: {e}")
        except Exception as e:
            return SkillResult.fail(f"Scrape failed: {e}")
