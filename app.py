import streamlit as st
import asyncio
import nest_asyncio
import pandas as pd
from io import BytesIO
from amazon_scraper_async import scrape_search_results

nest_asyncio.apply()

# ---------- Streamlit App ----------
st.set_page_config(page_title="Amazon Scraper Async", page_icon="🛒", layout="centered")
st.title("🛒 Amazon Product Scraper (Async & Fast)")
st.markdown("Enter a keyword and number of pages to scrape from **Amazon.sg** asynchronously.")

keyword = st.text_input("🔍 Keyword", placeholder="e.g. Dyson vacuum")
max_pages = st.number_input("📄 Number of pages", min_value=1, max_value=10, value=1, step=1)

if st.button("Start Scraping 🚀"):
    if not keyword.strip():
        st.error("Please enter a keyword first.")
    else:
        st.info("Scraping started... please wait ⏳")
        progress_bar = st.progress(0.0)

        async def run_scraper():
            return await scrape_search_results(keyword, max_pages, lambda p: progress_bar.progress(p))

        loop = asyncio.get_event_loop()
        products = loop.run_until_complete(run_scraper())

        if not products:
            st.warning("No products found.")
        else:
            df = pd.DataFrame(products)
            df['num_ratings'] = df['num_ratings'].apply(lambda x: 0 if x is None else int(x.replace(",", "")))
            df = df.sort_values(by=['num_ratings', 'rating'], ascending=[False, False])
            st.success(f"✅ Scraped {len(df)} products successfully!")

            st.dataframe(df.head())

            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)

            st.download_button(
                label="📥 Download CSV",
                data=csv_buffer,
                file_name=f"{keyword.replace(' ', '_')}_amazon_products.csv",
                mime="text/csv"
            )

