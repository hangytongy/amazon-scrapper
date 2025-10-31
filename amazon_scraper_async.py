import asyncio
import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://www.amazon.sg"
HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    ),
    "accept-language": "en-US,en;q=0.9"
}


def extract_text(soup, selector, attr=None, default=None, strip=True):
    element = soup.select_one(selector)
    if not element:
        return default
    if attr:
        return element.get(attr, default)
    text = element.text if element else default
    return text.strip() if (text and strip) else text


async def fetch(session: ClientSession, url: str):
    """Fetch a page asynchronously with retries."""
    for attempt in range(3):
        try:
            async with session.get(url, headers=HEADERS, timeout=30) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"⚠️ Non-200 response for {url}: {response.status}")
        except Exception as e:
            print(f"⚠️ Error fetching {url}: {e}")
        await asyncio.sleep(1)
    return None


async def scrape_product_details(session, url):
    """Scrape detailed product information and reviews asynchronously."""
    print(f"Fetching: {url}")
    html = await fetch(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    title = extract_text(soup, "#productTitle")
    rating = extract_text(soup, "#acrPopover", attr="title")
    rating = rating.replace(" out of 5 stars", "") if rating else None
    num_rating = extract_text(soup, "#acrCustomerReviewText")
    num_rating = num_rating.split()[0] if num_rating else None
    price = extract_text(soup, "span.a-price span.a-offscreen")
    image_url = extract_text(soup, "#landingImage", attr="src")
    description = extract_text(soup, "#feature-bullets")

    # Extract reviews
    reviews = []
    for review in soup.select("div.review"):
        reviews.append({
            "author": extract_text(review, "span.a-profile-name"),
            "rating": extract_text(review, "i.review-rating"),
            "title": extract_text(review, "a.review-title span:not([class])"),
            "content": extract_text(review, "span.review-text"),
            "date": extract_text(review, "span.review-date"),
            "verified": extract_text(review, "span.a-size-mini")
        })

    return {
        "title": title,
        "rating": rating,
        "num_ratings": num_rating,
        "price": price,
        "image": image_url,
        "desc": description,
        "reviews": reviews,
        "url": url,
    }


async def scrape_search_results(keyword, max_pages, progress_callback=None):
    """Scrape search result pages and product URLs asynchronously."""
    page = 1
    all_products = []
    keywords = keyword.replace(" ", "+")
    search_url = f"{BASE_URL}/s?k={keywords}&page={page}"

    async with aiohttp.ClientSession() as session:
        while page <= max_pages:
            print(f"\n🔍 Scraping page {page}: {search_url}")
            html = await fetch(session, search_url)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            containers = soup.find_all("div", {"role": "listitem", "data-asin": True})
            print(f"Found {len(containers)} product containers")

            product_urls = []
            for container in containers:
                link_tag = container.find("a", class_="a-link-normal", href=lambda h: h and "/dp/" in h)
                if link_tag:
                    href = link_tag["href"]
                    full_url = BASE_URL + href.split("?")[0]
                    product_urls.append(full_url)

            # Scrape all product details concurrently
            sem = asyncio.Semaphore(5)
            async def safe_scrape(url):
                async with sem:
                    return await scrape_product_details(session, url)

            tasks = [safe_scrape(url) for url in product_urls]
            results = await asyncio.gather(*tasks)
            for product in results:
                if product:
                    all_products.append(product)

            # Update progress bar (0–1)
            if progress_callback:
                progress_callback(min(page / max_pages, 1.0))

            # Move to next page
            next_page = soup.select_one("a.s-pagination-next")
            if next_page and next_page.get("href"):
                search_url = BASE_URL + next_page["href"]
                page += 1
                await asyncio.sleep(1)
            else:
                break

    return all_products






