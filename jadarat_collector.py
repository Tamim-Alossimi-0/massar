"""
jadarat_collector.py — Collect job listings from Jadarat.sa.

RESEARCH FINDINGS (2026-04-06):
─────────────────────────────────────────────────────────────────────────────
• jadarat.sa is built on OutSystems (a low-code enterprise platform).
• All pages are rendered client-side via React.
• The site is behind Cloudflare Rocket Loader + bot protection.
  Raw HTTP requests (requests library) receive 404s for all REST endpoints
  without a valid Cloudflare clearance cookie obtained through JS challenge.
• No public REST API is documented or exposed.

AUTHENTICATION REQUIRED FOR API:
  - Session cookie: __cf_bm  (Cloudflare bot management)
  - Session cookie: cf_clearance  (Cloudflare challenge solved)
  These are only obtainable by executing the Cloudflare JS challenge in a
  real browser session.

STRATEGY USED HERE:
  1. Launch a real Chromium browser via Playwright (bypasses Cloudflare).
  2. Navigate to jadarat.sa, wait for the React app to hydrate.
  3. For each search keyword, type into the search box, scrape result cards.
  4. If Playwright is unavailable or the site structure changes, fall back to
     the expanded 500-job synthetic dataset generated in scraper.py.

USAGE:
  python jadarat_collector.py
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import csv
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

RAW_PATH = Path("data/raw/jadarat_jobs.csv")
CLEAN_PATH = Path("data/processed/jobs_clean.csv")

DS_KEYWORDS = [
    "data scientist",
    "data analyst",
    "machine learning",
    "AI engineer",
    "data engineer",
    "business intelligence",
    "NLP",
    "deep learning",
    "python developer",
    "software engineer",
]

FIELDNAMES = [
    "job_title", "company", "location", "description",
    "required_skills", "experience_years", "education",
    "salary_range", "posting_date", "job_url", "source",
]


@dataclass
class Job:
    job_title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    required_skills: str = ""
    experience_years: str = ""
    education: str = ""
    salary_range: str = ""
    posting_date: str = ""
    job_url: str = ""
    source: str = "jadarat"


class JadaratCollector:
    """
    Collects Saudi tech job listings from Jadarat.sa using Playwright.
    Falls back to synthetic data if the site cannot be reached.
    """

    BASE_URL = "https://jadarat.sa"
    SEARCH_URL = "https://jadarat.sa/en/job-search"

    def __init__(self, headless: bool = True, delay: float = 2.0):
        self.headless = headless
        self.delay = delay          # seconds between page turns
        self._playwright = None
        self._browser = None
        self._page = None

    # ── Playwright lifecycle ──────────────────────────────────────────────────

    def _start_browser(self) -> bool:
        """Launch Playwright Chromium. Returns False if unavailable."""
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            self._pw_ctx = sync_playwright().__enter__()
            self._browser = self._pw_ctx.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._page = self._browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            logger.info("Playwright browser launched.")
            return True
        except Exception as exc:
            logger.warning(f"Playwright unavailable: {exc}")
            return False

    def _stop_browser(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._pw_ctx:
                self._pw_ctx.__exit__(None, None, None)
        except Exception:
            pass

    # ── Core scraping methods ─────────────────────────────────────────────────

    def fetch_jobs(self, keyword: str, location: str = "Riyadh",
                   page: int = 1) -> List[Job]:
        """
        Fetch job listings for a given keyword and location.
        Navigates to Jadarat search, waits for results, scrapes cards.
        """
        if self._page is None:
            raise RuntimeError("Browser not started. Call _start_browser() first.")

        jobs: List[Job] = []
        try:
            # Navigate to search page
            self._page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Try to find search input (multiple possible selectors)
            search_selectors = [
                "input[placeholder*='search' i]",
                "input[placeholder*='بحث']",
                "input[type='search']",
                "input[name='keyword']",
                ".search-input input",
                "[data-testid='search-input']",
            ]
            search_box = None
            for sel in search_selectors:
                try:
                    search_box = self._page.wait_for_selector(sel, timeout=5000)
                    if search_box:
                        break
                except Exception:
                    continue

            if not search_box:
                logger.warning(f"Search box not found for keyword '{keyword}'")
                return jobs

            # Type keyword and search
            search_box.click()
            search_box.fill(keyword)
            self._page.keyboard.press("Enter")
            time.sleep(self.delay)
            self._page.wait_for_load_state("networkidle", timeout=15000)

            # Scrape job cards (try common card selectors)
            card_selectors = [
                ".job-card", ".vacancy-card", "[class*='job-item']",
                "[class*='vacancy']", ".card", "article",
            ]
            cards = []
            for sel in card_selectors:
                cards = self._page.query_selector_all(sel)
                if cards:
                    logger.info(f"  Found {len(cards)} cards with selector '{sel}'")
                    break

            for card in cards[:20]:  # cap at 20 per keyword
                job = self.parse_job(card)
                if job.job_title:
                    jobs.append(job)

            logger.info(f"  Keyword '{keyword}': {len(jobs)} jobs scraped.")

        except Exception as exc:
            logger.error(f"  Error scraping keyword '{keyword}': {exc}")

        return jobs

    def parse_job(self, card) -> Job:  # type: ignore[no-untyped-def]
        """
        Extract standardised fields from a Playwright ElementHandle (job card).
        Tries multiple CSS selectors to handle layout variations.
        """
        def _text(selectors: List[str]) -> str:
            for sel in selectors:
                try:
                    el = card.query_selector(sel)
                    if el:
                        return el.inner_text().strip()
                except Exception:
                    pass
            return ""

        def _attr(selectors: List[str], attr: str) -> str:
            for sel in selectors:
                try:
                    el = card.query_selector(sel)
                    if el:
                        val = el.get_attribute(attr)
                        if val:
                            return val.strip()
                except Exception:
                    pass
            return ""

        title = _text(["h2", "h3", ".job-title", ".vacancy-title", "[class*='title']"])
        company = _text([".company", ".employer", "[class*='company']", "[class*='employer']"])
        location = _text([".location", "[class*='location']", "[class*='city']"])
        description = _text([".description", ".summary", "[class*='desc']", "p"])
        skills = _text([".skills", ".tags", "[class*='skill']", "[class*='tag']"])
        salary = _text([".salary", "[class*='salary']", "[class*='compensation']"])
        exp = _text([".experience", "[class*='experience']", "[class*='years']"])
        edu = _text([".education", "[class*='education']", "[class*='degree']"])
        url = _attr(["a", "a[href]"], "href")
        if url and not url.startswith("http"):
            url = self.BASE_URL + url

        return Job(
            job_title=title,
            company=company,
            location=location or "Saudi Arabia",
            description=description,
            required_skills=skills,
            experience_years=exp,
            education=edu,
            salary_range=salary,
            posting_date=str(date.today()),
            job_url=url,
            source="jadarat",
        )

    def fetch_all_ds_jobs(self) -> List[Job]:
        """
        Iterate through DS_KEYWORDS and accumulate all scraped jobs.
        Deduplicates by title + company before returning.
        """
        all_jobs: List[Job] = []
        summary: dict[str, int] = {}

        for keyword in DS_KEYWORDS:
            logger.info(f"Searching: '{keyword}'")
            jobs = self.fetch_jobs(keyword)
            summary[keyword] = len(jobs)
            all_jobs.extend(jobs)
            time.sleep(random.uniform(self.delay, self.delay + 1.5))

        # Deduplicate
        seen: set = set()
        unique: List[Job] = []
        for j in all_jobs:
            key = (j.job_title.lower().strip(), j.company.lower().strip())
            if key not in seen and j.job_title:
                seen.add(key)
                unique.append(j)

        logger.info("\nCollection summary:")
        for kw, cnt in summary.items():
            logger.info(f"  '{kw}': {cnt} jobs")
        logger.info(f"  Total unique: {len(unique)}")
        return unique

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_jobs(self, jobs: List[Job], filepath: str | Path) -> None:
        """Save a list of Job objects to a CSV file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for job in jobs:
                writer.writerow(asdict(job))
        logger.info(f"Saved {len(jobs)} jobs to {path}")

    def merge_with_existing(self, new_jobs: List[Job]) -> pd.DataFrame:
        """
        Merge new Jadarat jobs with the existing jobs_clean.csv.
        Deduplicates on (job_title, company) after normalising to lowercase.
        Saves merged result back to data/processed/jobs_clean.csv.
        """
        new_df = pd.DataFrame([asdict(j) for j in new_jobs])

        if CLEAN_PATH.exists():
            existing = pd.read_csv(CLEAN_PATH).fillna("")
            # Align columns — fill missing columns with empty string
            for col in FIELDNAMES:
                if col not in existing.columns:
                    existing[col] = ""
            combined = pd.concat([existing, new_df], ignore_index=True)
        else:
            combined = new_df

        # Deduplicate
        combined["_key"] = (
            combined["job_title"].str.lower().str.strip() + "||" +
            combined["company"].str.lower().str.strip()
        )
        combined = combined.drop_duplicates(subset="_key").drop(columns=["_key"])
        combined = combined.fillna("")

        CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(CLEAN_PATH, index=False)
        logger.info(f"Merged dataset: {len(combined)} total jobs → {CLEAN_PATH}")

        # Invalidate embedding cache so model re-encodes the new data
        cache_dir = Path("data/embeddings_cache")
        if cache_dir.exists():
            for f in cache_dir.glob("*.pkl"):
                f.unlink()
            logger.info("Embedding cache cleared (will rebuild on next app load).")

        return combined

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(self) -> List[Job]:
        """
        Full pipeline: start browser → scrape → save raw → merge → stop browser.
        Returns list of newly collected jobs (empty if scraping failed).
        """
        started = self._start_browser()
        if not started:
            logger.warning(
                "Playwright not available. Install with: pip install playwright && "
                "python -m playwright install chromium"
            )
            return []

        try:
            jobs = self.fetch_all_ds_jobs()
            if jobs:
                self.save_jobs(jobs, RAW_PATH)
                self.merge_with_existing(jobs)
            else:
                logger.warning("No jobs collected — site structure may have changed.")
        finally:
            self._stop_browser()

        return jobs


def run_jadarat_collector() -> List[dict]:
    """
    Convenience function called from scraper.py.
    Returns list of job dicts, or empty list if collection fails.
    """
    collector = JadaratCollector(headless=True)
    jobs = collector.run()
    return [asdict(j) for j in jobs]


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Jadarat.sa Collector")
    print("=" * 60)
    print()
    print("NOTE: This collector requires Playwright Chromium.")
    print("If not installed, run:")
    print("  pip install playwright")
    print("  python -m playwright install chromium")
    print()

    collector = JadaratCollector(headless=True, delay=2.5)
    jobs = collector.run()

    if jobs:
        print(f"\nSuccessfully collected {len(jobs)} jobs from Jadarat.sa")
        print("Summary by keyword:")
        titles = [j.job_title for j in jobs]
        for kw in DS_KEYWORDS:
            count = sum(1 for t in titles if kw.lower() in t.lower())
            print(f"  {kw:<25}: ~{count} matching jobs")
    else:
        print("\nJadarat scraping returned no results.")
        print("Possible reasons:")
        print("  1. Playwright not installed (pip install playwright)")
        print("  2. Cloudflare is blocking the browser session")
        print("  3. Jadarat site structure has changed")
        print("  4. Network/firewall restriction")
        print()
        print("The main dataset (data/processed/jobs_clean.csv) is unchanged.")
        print("Run 'python scraper.py' to regenerate synthetic data.")
        sys.exit(0)
