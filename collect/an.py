# ...existing code...
"""
Selenium scraper + AI classifier for Ethiopian News.
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

# Ethiopian-focused categories for AI classification
ETHIOPIAN_CATEGORIES = [
    "politics",                    # Government, elections, political parties
    "economy_business",           # Economy, trade, business, investment
    "regional_conflicts",         # Amhara, Tigray, Oromia conflicts
    "agriculture",                # Farming, crops, food security
    "infrastructure",             # Roads, dams, construction projects
    "education_health",           # Schools, universities, healthcare
    "culture_tourism",            # Heritage, tourism, arts
    "sports",                     # Football, athletics, sports events
    "international_relations",    # Diplomacy, foreign affairs
    "social_issues"               # Poverty, unemployment, social welfare
]

# Ethiopian regions for regional classification
ETHIOPIAN_REGIONS = [
    "addis_ababa", "oromia", "amhara", "tigray", "snnpr", "afar", 
    "somali", "benishangul_gumuz", "gambela", "sidama", "south_west",
    "dire_dawa", "harari", "multiple_regions", "national", "international"
]

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

def extract_article_data(driver, url):
    """Extract article content, title, author, and date"""
    article_data = {
        "url": url,
        "title": "",
        "author": "",
        "date": "",
        "content": "",
        "error": None
    }
    
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)
        
        page_html = driver.page_source
        soup = BeautifulSoup(page_html, "html.parser")
        
        # Extract title
        for selector in TITLE_SELECTORS:
            title_elem = soup.select_one(selector)
            if title_elem and title_elem.get_text(strip=True):
                article_data["title"] = title_elem.get_text(strip=True)
                break
        
        # Extract author
        author_selectors = ['.author', '.byline', '[rel="author"]', '.post-author']
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                article_data["author"] = author_elem.get_text(strip=True)
                break
        
        # Extract date
        date_selectors = ['time', '.date', '.published', '.post-date', '.article-date']
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                if date_elem.get('datetime'):
                    article_data["date"] = date_elem.get('datetime')
                else:
                    article_data["date"] = date_elem.get_text(strip=True)
                break
        
        # Extract content
        content_parts = []
        for selector in BODY_SELECTORS:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Get all paragraphs from the content element
                paragraphs = content_elem.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 50:
                        content_parts.append(text)
                if content_parts:
                    break
        
        # If no structured content found, try to get all substantial paragraphs
        if not content_parts:
            all_paragraphs = soup.find_all('p')
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 80:
                    content_parts.append(text)
        
        article_data["content"] = "\n\n".join(content_parts)
        
    except Exception as e:
        article_data["error"] = str(e)
    
    return article_data

def classify_ethiopian_news_with_openai(title, content, categories=ETHIOPIAN_CATEGORIES, regions=ETHIOPIAN_REGIONS):
    """Call OpenAI to classify Ethiopian news articles by category and region"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "category": "unknown", 
            "region": "unknown", 
            "explanation": "OPENAI_API_KEY not set",
            "confidence": 0
        }
    
    openai.api_key = api_key
    
    prompt = f"""
    You are an expert classifier of Ethiopian news articles. Analyze the following article and classify it.

    CATEGORIES (choose ONE):
    {', '.join(categories)}

    REGIONS (choose ONE or MULTIPLE if relevant):
    {', '.join(regions)}

    Return ONLY a JSON object with these keys:
    - "category" (string): the main category from the list above
    - "region" (array): list of relevant regions from the list above
    - "explanation" (string): brief explanation of your classification
    - "confidence" (number): your confidence level from 0.0 to 1.0

    Article Title: {title or 'No title'}
    Article Content: {content[:3000] or 'No content'}

    Focus on Ethiopian context. For example:
    - Politics: government, elections, political parties
    - Regional conflicts: Amhara, Tigray, Oromia issues
    - Economy: Ethiopian economy, trade, business
    - Agriculture: farming, crops (coffee, teff), food security
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500
        )
        
        content_text = response.choices[0].message["content"].strip()
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', content_text, re.DOTALL)
        if json_match:
            classification = json.loads(json_match.group())
            
            # Validate category
            if classification.get("category") not in categories:
                classification["category"] = "unknown"
            
            # Validate regions
            if isinstance(classification.get("region"), list):
                valid_regions = [r for r in classification["region"] if r in regions]
                classification["region"] = valid_regions if valid_regions else ["national"]
            else:
                classification["region"] = ["national"]
            
            return classification
        else:
            return {
                "category": "unknown", 
                "region": ["national"], 
                "explanation": "Could not parse AI response",
                "confidence": 0
            }
            
    except Exception as e:
        return {
            "category": "unknown", 
            "region": ["national"], 
            "explanation": f"OpenAI error: {str(e)}",
            "confidence": 0
        }

def simple_ethiopian_keyword_classify(title, content):
    """Fallback classifier using Ethiopian-specific keywords"""
    text = f"{title} {content}".lower()
    
    # Category classification
    politics_keywords = ['election', 'parliament', 'prime minister', 'government', 'political', 'party', 'democracy']
    economy_keywords = ['economy', 'business', 'investment', 'trade', 'market', 'gdp', 'inflation']
    conflict_keywords = ['conflict', 'war', 'fighting', 'clash', 'tension', 'violence', 'peace']
    agriculture_keywords = ['agriculture', 'farm', 'crop', 'teff', 'coffee', 'harvest', 'food security']
    regional_keywords = ['amhara', 'tigray', 'oromia', 'afar', 'somali', 'snnpr', 'regional']
    
    if any(keyword in text for keyword in politics_keywords):
        category = "politics"
    elif any(keyword in text for keyword in economy_keywords):
        category = "economy_business"
    elif any(keyword in text for keyword in conflict_keywords):
        category = "regional_conflicts"
    elif any(keyword in text for keyword in agriculture_keywords):
        category = "agriculture"
    elif any(keyword in text for keyword in regional_keywords):
        category = "regional_conflicts"
    else:
        category = "social_issues"
    
    # Region detection
    regions = []
    region_mapping = {
        "amhara": ["amhara", "bahir dar", "gondar"],
        "tigray": ["tigray", "mekelle", "axum"],
        "oromia": ["oromia", "addis ababa", "jimma", "harar"],
        "afar": ["afar", "semera"],
        "somali": ["somali", "jijiga"],
        "snnpr": ["snnpr", "hawassa", "wolayta"]
    }
    
    for region, keywords in region_mapping.items():
        if any(keyword in text for keyword in keywords):
            regions.append(region)
    
    if not regions:
        regions = ["national"]
    
    return {
        "category": category,
        "region": regions,
        "explanation": "Keyword-based classification",
        "confidence": 0.6
    }

def scrape_all_ethiopian_news(sites, headless=True, articles_per_site=15, use_ai=True):
    """Main function to scrape and classify Ethiopian news"""
    driver = create_driver(headless=headless)
    all_articles = []
    
    try:
        for site in sites:
            print(f"🔍 Collecting articles from {site['name']}...")
            
            # Collect article links
            links = collect_article_links(driver, site["url"], limit=articles_per_site)
            print(f"   Found {len(links)} articles to scrape")
            
            site_articles = []
            for i, link in enumerate(links):
                print(f"   📖 Scraping article {i+1}/{len(links)}")
                
                # Extract article data
                article_data = extract_article_data(driver, link["url"])
                
                if article_data["error"]:
                    print(f"   ❌ Error: {article_data['error']}")
                    continue
                
                # Classify article
                if use_ai:
                    classification = classify_ethiopian_news_with_openai(
                        article_data["title"], 
                        article_data["content"]
                    )
                else:
                    classification = simple_ethiopian_keyword_classify(
                        article_data["title"], 
                        article_data["content"]
                    )
                
                # Combine all data
                final_article = {
                    **article_data,
                    **classification,
                    "source": site["name"],
                    "source_url": site["url"],
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                site_articles.append(final_article)
                time.sleep(1)  # Be polite
            
            print(f"   ✅ Successfully processed {len(site_articles)} articles from {site['name']}")
            all_articles.extend(site_articles)
            
            time.sleep(2)  # Be polite between sites
            
    finally:
        driver.quit()
    
    return all_articles

def save_results(articles, filename="ethiopian_news_classified.json"):
    """Save classified articles to JSON file"""
    output_file = os.path.join(os.path.dirname(__file__), "..", filename)
    output_file = os.path.abspath(output_file)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Saved {len(articles)} articles to {output_file}")
    
    # Print summary
    category_count = {}
    region_count = {}
    
    for article in articles:
        cat = article.get("category", "unknown")
        category_count[cat] = category_count.get(cat, 0) + 1
        
        for region in article.get("region", []):
            region_count[region] = region_count.get(region, 0) + 1
    
    print("\n📊 Classification Summary:")
    print("Categories:")
    for cat, count in category_count.items():
        print(f"  {cat}: {count} articles")
    
    print("\nRegions:")
    for region, count in region_count.items():
        print(f"  {region}: {count} mentions")

if __name__ == "__main__":
    
    
    # Scrape and classify articles
    articles = scrape_all_ethiopian_news(
        ethiopian_news_websites, 
        headless=True, 
        articles_per_site=10, 
        use_ai=True
    )
    
    # Save results
    save_results(articles)

