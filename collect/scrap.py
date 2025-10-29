i# ...existing code...
"""
Selenium scraper + AI classifier.
- Requirements: selenium, webdriver-manager, beautifulsoup4, openai, requests
- Set environment variable OPENAI_API_KEY before running (PowerShell: $env:OPENAI_API_KEY="sk-...")
"""
import os
import time
import json
import re
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from bs4 import BeautifulSoup
import openai
import requests

# List of target sites (unchanged)
ethiopian_news_websites = [
    {"name": "Ethiopian News Agency (ENA)", "url": "https://www.ena.et"},
    {"name": "Fana Broadcasting Corporate", "url": "https://www.fbc.com.et"},
    {"name": "Addis Standard", "url": "https://addisstandard.com"},
    {"name": "The Reporter", "url": "https://www.thereporterethiopia.com"},
    {"name": "Borkena", "url": "https://borkena.com"},
    {"name": "Ezega News", "url": "https://www.ezega.com/News"},
    {"name": "Walta Media and Communication", "url": "https://www.waltainfo.com"},
    {"name": "Ethiopian Monitor", "url": "https://ethiopianmonitor.com"},
    {"name": "Capital Newspaper", "url": "https://www.capitalethiopia.com"},
    {"name": "Addis Fortune", "url": "https://addisfortune.net"}
]

# Common CSS selectors to find article links on listing/home pages
COMMON_LINK_SELECTORS = [
    "article a[href]",
    "h1 a[href]",
    "h2 a[href]",
    "h3 a[href]",
    "a[href*='/news/']",
    "a[href*='article']",
    "a[href*='story']",
    "main a[href]",
    "section a[href]",
    ".post a[href]",
    ".entry a[href]"
]

# Common selectors to extract article title and body on article pages
TITLE_SELECTORS = ["h1", ".entry-title", ".article-title", ".post-title"]
BODY_SELECTORS = [
    "article",
    ".entry-content",
    ".post-content",
    ".article-body",
    ".content-body",
    "#content"
]

# categories for AI classification
CATEGORIES = ["sports", "politics", "business", "technology", "culture", "health", "science", "entertainment", "other"]

def create_driver(headless=True):
    opts = Options()
    if headless:
        # use new headless flag for recent Chrome; change if your Chrome is older
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    # set a common user-agent
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver

def normalize_url(base, href):
    if not href:
        return None
    href = href.strip()
    # ignore javascript, mailto
    if href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("#"):
        return None
    return urljoin(base, href)




def collect_article_links(driver, base_url, limit=50, max_pages=3):
    """Enhanced version that scrapes multiple pages"""
    links = []
    seen = set()
    current_page = 1
    
    try:
        # Start with homepage
        driver.get(base_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)
        
        while len(links) < limit and current_page <= max_pages:
            print(f"Scraping page {current_page}...")
            
            # Scroll to load more content (for modern websites)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Extract links from current page
            page_html = driver.page_source
            soup = BeautifulSoup(page_html, "html.parser")
            
            for sel in COMMON_LINK_SELECTORS:
                for a in soup.select(sel):
                    href = a.get("href") or a.get("data-href")
                    full = normalize_url(base_url, href)
                    
                    if (not full or 
                        urlparse(full).netloc != urlparse(base_url).netloc or 
                        full in seen or
                        len(full) < 20):  # Filter out very short URLs (usually not articles)
                        continue
                    
                    title = (a.get_text(strip=True) or "").strip()
                    # Only keep links that look like articles
                    if len(title) > 10:  # Minimum title length
                        seen.add(full)
                        links.append({"url": full, "text": title, "page": current_page})
                        
                        if len(links) >= limit:
                            return links
            
            # Try to go to next page
            next_page_found = False
            
            # Method 1: Try common "Next" buttons
            next_selectors = [
                "a.pagination-next",
                "a.next",
                "a[aria-label*='next']",
                "a[title*='next']",
                "a:contains('Next')",
                "a:contains('›')",
                "a:contains('»')"
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if next_btn.is_displayed():
                        driver.execute_script("arguments[0].click();", next_btn)
                        next_page_found = True
                        time.sleep(3)
                        break
                except:
                    continue
            
            # Method 2: If no next button, try URL pattern
            if not next_page_found:
                current_page += 1
                next_url = f"{base_url}page/{current_page}/"  # Common pattern
                try:
                    driver.get(next_url)
                    time.sleep(3)
                except:
                    break  # No more pages
            else:
                current_page += 1
                
    except Exception as e:
        print(f"Error: {e}")
    
    return links




def scrape_and_clean_articles(driver, links):
    """Visit multiple URLs and return cleaned content"""
    articles_data = []
    
    for url in links:
        try:
            print(f"Scraping: {url}")
            
            # 1. Navigate to URL
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)
            
            # 2. Get HTML and convert to BeautifulSoup
            page_html = driver.page_source
            soup = BeautifulSoup(page_html, "html.parser")
            
            # 3. Clean the HTML
            clean_soup = clean_html(soup)
            
            # 4. Extract article content
            article_content = extract_article_content(clean_soup)
            
            # 5. Store results
            articles_data.append({
                "url": url,
                "content": article_content,
                "title": extract_title(clean_soup)
            })
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            continue
    
    return articles_data

def clean_html(soup):
    """Remove unnecessary elements from BeautifulSoup object"""
    
    elements_to_remove = [
        'script', 'style', 'nav', 'header', 'footer', 'aside', 
        'iframe', 'form', 'button'
    ]
    
    # Remove by tag name
    for tag_name in elements_to_remove:
        for element in soup.find_all(tag_name):
            element.decompose()
    
    # Remove by class
    garbage_classes = [
        'ad', 'advertisement', 'social', 'share', 'comments',
        'menu', 'navbar', 'sidebar', 'popup', 'newsletter',
        'related', 'recommended'
    ]
    
    for class_name in garbage_classes:
        for element in soup.find_all(class_=class_name):
            element.decompose()
    
    return soup

def extract_title(soup):
    """Extract article title"""
    title_selectors = ['h1', '.entry-title', '.article-title', '.post-title']
    
    for selector in title_selectors:
        title_elem = soup.select_one(selector)
        if title_elem:
            return title_elem.get_text(strip=True)
    
    # Fallback to page title
    if soup.title:
        return soup.title.get_text(strip=True)
    
    return "No title found"

"""

def extract_article_from_page(driver, url, wait_seconds=8):
    Visit article page and try to extract title, author, date, and body text.
    out = {"url": url, "title": None, "author": None, "date": None, "text": ""}
    try:
        driver.get(url)
        WebDriverWait(driver, wait_seconds).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # title
        for sel in TITLE_SELECTORS:
            t = soup.select_one(sel)
            if t and t.get_text(strip=True):
                out["title"] = t.get_text(strip=True)
                break
        if not out["title"]:
            # fallback to <title> tag
            if soup.title and soup.title.string:
                out["title"] = soup.title.string.strip()
        # author/date heuristics
        author = soup.select_one("[rel=author]") or soup.select_one(".author") or soup.select_one(".byline")
        if author:
            out["author"] = author.get_text(strip=True)
        date = soup.select_one("time") or soup.select_one(".date") or soup.select_one(".published")
        if date:
            out["date"] = date.get_text(strip=True)
        # body extraction
        paragraphs = []
        for sel in BODY_SELECTORS:
            node = soup.select_one(sel)
            if node:
                # collect text only from paragraphs to avoid menus/ads
                for p in node.find_all(["p", "div"]):
                    text = p.get_text(separator=" ", strip=True)
                    if len(text) > 50:  # threshold to avoid nav items
                        paragraphs.append(text)
                if paragraphs:
                    break
        if not paragraphs:
            # fallback: find long <p> in whole page
            for p in soup.find_all("p"):
                text = p.get_text(separator=" ", strip=True)
                if len(text) > 80:
                    paragraphs.append(text)
        out["text"] = "\n\n".join(paragraphs).strip()
        # final sanity: if text is empty, try a broader extraction
        if not out["text"]:
            out["text"] = soup.get_text(separator="\n", strip=True)[:10000]
        # cleanup whitespace
        out["text"] = re.sub(r"\s+\n", "\n", out["text"]).strip()
    except Exception as e:
        out["error"] = str(e)
    return out"""

def classify_with_openai(article_data,  categories=CATEGORIES):
    """Call OpenAI ChatCompletion to classify the article into one category.
    Returns the chosen category (lowercase) or 'other' on failure.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"category": "other", "explanation": "OPENAI_API_KEY not set"}
    openai.api_key = api_key
    prompt = (
        "You are an assistant that assigns a single best category to a news article. "
        f"Categories: {', '.join(categories)}.\n\n"
        "Return only a JSON object with keys: category (one of the categories), reason (short)."
        "\n\nArticle title:\n" + (title or "") + "\n\nArticle text:\n" + (text[:4000] or "")
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=150
        )
        content = resp.choices[0].message["content"].strip()
        # try to parse a JSON object in the response
        # we will look for a JSON object inside the content
        m = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if m:
            obj_text = m.group(0)
            try:
                obj = json.loads(obj_text)
                cat = obj.get("category", "").lower()
                reason = obj.get("reason", "")
                if cat in categories:
                    return {"category": cat, "explanation": reason}
            except Exception:
                pass
        # fallback: try to find category name in text
        for c in categories:
            if re.search(r"\b" + re.escape(c) + r"\b", content, flags=re.IGNORECASE):
                return {"category": c, "explanation": content}
        return {"category": "other", "explanation": content}
    except Exception as e:
        return {"category": "other", "explanation": f"openai error: {e}"}



if __name__ == "__main__":
    # example run
    # Set headless=False during development to see the browser
    data = scrape_all(ethiopian_news_websites, headless=True, per_site_limit=6, use_ai=True)
    out_file = os.path.join(os.path.dirname(__file__), "..", "scraped_classified.json")
    # normalize path
    out_file = os.path.abspath(out_file)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved", out_file)
# ...existing code...

