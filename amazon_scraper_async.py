import streamlit as st
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
import nest_asyncio


BASE_URL = "https://www.amazon.sg"
HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    ),
    "accept-language": "en-US,en;q=0.9",
}


# ---------- Helper Functions ----------
def extract_text(soup, selector, attr=None, default=None, strip=True):
    element = soup.select_one(selector)
    if not element:
        return default
    if attr:
        return element.get(attr, default)
    text = element.text if element else default
    return text.strip() if (text and strip) else text


async def fetch(session, url):
    """Fetch a page asynchronously."""
    try:
        async with session.get(url, headers=HEADERS, timeout=10) as response:
            if response.status != 200:
                return None
            return await response.text()
    except Exception:
        return None


async def scrape_product_detail(session, url):
    """Scrape details for a single product asynchronously."""
    html = await fetch(session, url)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")

    title = extract_text(soup, "#productTitle")
    rating = extract_text(soup, "#acrPopover", attr="title")
    if rating:
        rating = rating.replace(" out of 5 stars", "")
    num_rating = extract_text(soup, "#acrCustomerReviewText")
    num_rating = num_rating.split()[0] if num_rating else None
    price = extract_text(soup, "span.a-price span.a-offscreen")
    image_url = extract_text(soup, "#landingImage", attr="src")
    description = extract_text(soup, "#feature-bullets")

    return {
        "title": title,
        "rating": rating,
        "num_ratings": num_rating,
        "price": price,
        "image": image_url,
        "description": description,
        "url": url,
    }


async def scrape_search_page(session, keyword, page):
    """Scrape one search page asynchronously for product URLs."""
    keywords = keyword.replace(" ", "+")
    url = f"{BASE_URL}/s?k={keywords}&page={page}"
    html = await fetch(session, url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    containers = soup.find_all("div", {"role": "listitem", "data-asin": True})

    urls = []
    for container in containers:
        link_tag = container.find("a", class_="a-link-normal", href=lambda h: h and "/dp/" in h)
        if link_tag:
            href = link_tag["href"]
            full_url = BASE_URL + href.split("?")[0]
            urls.append(full_url)
    return urls


async def scrape_search_results(keyword, max_pages, progress_callback=None):
    """Main async scrape pipeline for multiple pages."""
    async with aiohttp.ClientSession() as session:
        # Step 1: gather all product URLs
        search_tasks = [scrape_search_page(session, keyword, p) for p in range(1, max_pages + 1)]
        search_results = await asyncio.gather(*search_tasks)
        product_urls = [url for sublist in search_results for url in sublist]

        total = len(product_urls)
        st.info(f"🔗 Found {total} product URLs across {max_pages} pages.")

        # Step 2: scrape details concurrently
        detail_tasks = []
        for i, url in enumerate(product_urls):
            detail_tasks.append(scrape_product_detail(session, url))

        results = []
        completed = 0
        for task in asyncio.as_completed(detail_tasks):
            result = await task
            if result:
                results.append(result)
            completed += 1
            if progress_callback:
                progress_callback(completed / total)

        return results



