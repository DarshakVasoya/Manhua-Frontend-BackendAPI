import re
import os
from pymongo import MongoClient
from datetime import datetime, UTC
from urllib.parse import quote

BASE_URL = "https://manhwagalaxy.org"
SITEMAP_DIR = "sitemaps"
SITEMAP_INDEX_PATH = "sitemap-index.xml"
MAX_URLS_PER_FILE = 49000

MONGO_URI = os.getenv("MONGO_URI", "mongodb://darshak:DarshakVasoya1310%40@165.232.60.4:27017/admin?authSource=admin")
client = MongoClient(MONGO_URI)
db = client["admin"]
collection = db["manhwa"]

STATIC_PAGES = [
    {"loc": f"{BASE_URL}/", "changefreq": "hourly", "priority": "1.0"},
    {"loc": f"{BASE_URL}/privacy", "changefreq": "yearly", "priority": "0.3"},
    {"loc": f"{BASE_URL}/terms", "changefreq": "yearly", "priority": "0.3"},
    {"loc": f"{BASE_URL}/dmca", "changefreq": "yearly", "priority": "0.3"},
    {"loc": f"{BASE_URL}/about", "changefreq": "yearly", "priority": "0.3"},
    {"loc": f"{BASE_URL}/contact", "changefreq": "yearly", "priority": "0.3"},
]

def get_categories():
    genres = collection.distinct("genres")
    return [g for g in genres if g]

def get_manga():
    return list(collection.find({}, {"name": 1, "chapters": 1, "updated_at": 1, "posted_on": 1, "_id": 0}))

def escape_xml(text):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("'", "&apos;")
                .replace('"', "&quot;"))

def build_url_entry(loc, lastmod, changefreq, priority):
    # Validate lastmod format (YYYY-MM-DD)
    def valid_date(date_str):
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_str)))
    now = datetime.now(UTC).strftime('%Y-%m-%d')
    if not valid_date(lastmod):
        lastmod = now
    # Only URL-encode loc for safe XML and web use
    safe_loc = quote(loc, safe=':/?=&%')
    return f"<url><loc>{safe_loc}</loc><lastmod>{lastmod}</lastmod><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"

def generate_all_urls():
    urls = []
    # Static pages
    now = datetime.now(UTC).strftime('%Y-%m-%d')
    for page in STATIC_PAGES:
        # Use current time for home page, else yearly for static
        if page['loc'] == f"{BASE_URL}/":
            urls.append(build_url_entry(page['loc'], now, page['changefreq'], page['priority']))
        else:
            urls.append(build_url_entry(page['loc'], now, page['changefreq'], page['priority']))
    # Categories
    for slug in get_categories():
        safe_slug = slug.replace('&', '-')
        loc = f"{BASE_URL}/category/{escape_xml(safe_slug)}"
        urls.append(build_url_entry(loc, now, "hourly", "0.9"))
    # Manga details and chapters
    for manga in get_manga():
        name = manga.get("name")
        if not name:
            continue
        name_slug = escape_xml(name.replace(" ", "-").replace('&', '-').lower())
        # Use posted_on for details page
        manga_lastmod = manga.get("posted_on")
        if manga_lastmod:
            if isinstance(manga_lastmod, str):
                # Extract date part and validate
                date_part = manga_lastmod[:10]
                if re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
                    manga_lastmod = date_part
                else:
                    manga_lastmod = now
            elif hasattr(manga_lastmod, 'strftime'):
                manga_lastmod = manga_lastmod.strftime('%Y-%m-%d')
            else:
                manga_lastmod = now
        else:
            manga_lastmod = now
        loc = f"{BASE_URL}/details/{name_slug}"
        urls.append(build_url_entry(loc, manga_lastmod, "weekly", "0.8"))
        chapters = manga.get("chapters", [])
        for chapter in chapters:
            chapternum = chapter.get("chapternum")
            chapter_lastmod = chapter.get("updated_at") or manga_lastmod
            if isinstance(chapter_lastmod, str):
                date_part = chapter_lastmod[:10]
                if re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
                    chapter_lastmod = date_part
                else:
                    chapter_lastmod = manga_lastmod
            elif hasattr(chapter_lastmod, 'strftime'):
                chapter_lastmod = chapter_lastmod.strftime('%Y-%m-%d')
            else:
                chapter_lastmod = manga_lastmod
            if chapternum:
                try:
                    chapter_number = int(chapternum.split()[-1])
                except Exception:
                    continue
                chapter_loc = f"{BASE_URL}/details/{name_slug}/chapters/{chapter_number}"
                urls.append(build_url_entry(chapter_loc, chapter_lastmod, "never", "0.6"))
    return urls

def write_sitemap_files(urls):
    import glob
    if not os.path.exists(SITEMAP_DIR):
        os.makedirs(SITEMAP_DIR)
    # Remove old sitemap files
    for old_file in glob.glob(os.path.join(SITEMAP_DIR, "sitemap-*.xml")):
        os.remove(old_file)
    sitemap_files = []
    for i in range(0, len(urls), MAX_URLS_PER_FILE):
        part_urls = urls[i:i+MAX_URLS_PER_FILE]
        filename = f"sitemap-{i//MAX_URLS_PER_FILE+1}.xml"
        filepath = os.path.join(SITEMAP_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n")
            f.write("\n".join(part_urls))
            f.write("\n</urlset>")
        sitemap_files.append(filepath)
    return sitemap_files

def write_sitemap_index(sitemap_files):
    index_entries = []
    lastmod = datetime.now(UTC).strftime('%Y-%m-%d')
    for filepath in sitemap_files:
        filename = os.path.basename(filepath)
        loc = f"{BASE_URL}/sitemaps/{filename}"
        safe_loc = quote(loc, safe=':/?=&%')
        index_entries.append(f"<sitemap><loc>{safe_loc}</loc><lastmod>{lastmod}</lastmod></sitemap>")
    with open(SITEMAP_INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n")
        f.write("\n".join(index_entries))
        f.write("\n</sitemapindex>")
    print(f"Sitemap index generated at {SITEMAP_INDEX_PATH} ({len(sitemap_files)} files)")

def main():
    urls = generate_all_urls()
    sitemap_files = write_sitemap_files(urls)
    write_sitemap_index(sitemap_files)

if __name__ == "__main__":
    main()
