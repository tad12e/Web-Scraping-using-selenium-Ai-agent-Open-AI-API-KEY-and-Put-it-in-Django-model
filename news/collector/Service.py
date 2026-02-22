# news/collector/Service.py

from urllib.parse import urlparse

from django.utils import timezone
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .models import Article, Source


BASE_URL = "https://www.thereporterethiopia.com/"
BLOCKED_PATHS = {
    "",
    "/",
    "/business",
    "/business/",
    "/politics",
    "/politics/",
    "/news",
    "/news/",
    "/category",
    "/category/",
}


def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )

    return webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )


def is_article_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and "thereporterethiopia.com" not in parsed.netloc:
        return False

    path = parsed.path.strip()
    if path in BLOCKED_PATHS:
        return False

    # Require deeper paths to avoid category pages.
    clean_path = path.strip("/")
    if clean_path.count("/") < 1:
        return False

    # Skip common non-article paths.
    segments = clean_path.split("/")
    if segments[0] in {"tag", "author", "page", "category", "wp-content"}:
        return False

    return True


def get_article_links(driver, max_pages=10):
    all_links = []

    for page in range(1, max_pages + 1):
        page_url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
        driver.get(page_url)
        wait = WebDriverWait(driver, 25)

        try:
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href]")))
        except TimeoutException:
            print(f"Timeout loading page: {page_url}")
            continue

        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
        page_links = []

        for a in anchors:
            href = a.get_attribute("href")
            if not href:
                continue
            if is_article_url(href):
                page_links.append(href)

        # Keep order and remove duplicates from this page.
        page_links = list(dict.fromkeys(page_links))
        print(f"Page {page}: found {len(page_links)} candidate article links")
        all_links.extend(page_links)

    # Keep order and remove duplicates globally.
    return list(dict.fromkeys(all_links))


def scrape_article(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))

    title = driver.find_element(By.TAG_NAME, "h1").text.strip()

    paragraphs = []
    for selector in ["div.entry-content p", "article p", ".post-content p", ".td-post-content p"]:
        paragraphs = driver.find_elements(By.CSS_SELECTOR, selector)
        if paragraphs:
            break

    content = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])

    return {
        "title": title or "Untitled",
        "content": content or "",
        "url": url,
        "published_at": timezone.now(),
        "category": "General",
        "region": "Global",
    }


def get_or_create_source():
    domain = urlparse(BASE_URL).netloc
    source, _ = Source.objects.get_or_create(
        base_url=f"https://{domain}/",
        defaults={"name": "The Reporter Ethiopia"},
    )
    return source


def save_new_article(source, data):
    # Only create when URL is new; skip if already scraped.
    article, created = Article.objects.get_or_create(
        url=data["url"],
        defaults={
            "source": source,
            "title": data["title"],
            "content": data["content"],
            "published_at": data["published_at"],
            "category": data["category"],
            "region": data["region"],
        },
    )
    return article, created


def run_scraper(limit=100, max_pages=10):
    driver = get_driver()
    try:
        source = get_or_create_source()
        links = get_article_links(driver, max_pages=max_pages)
        print(f"Total unique candidate links: {len(links)}")

        new_saved = 0
        skipped_existing = 0

        for link in links:
            if new_saved >= limit:
                break

            try:
                data = scrape_article(driver, link)
                article, created = save_new_article(source, data)
                if created:
                    new_saved += 1
                    print(f"NEW: {article.title} | {article.url}")
                else:
                    skipped_existing += 1
            except Exception as e:
                print(f"Failed on {link}: {e}")

        print(f"Saved new articles: {new_saved}")
        print(f"Skipped already-scraped: {skipped_existing}")
    finally:
        driver.quit()

