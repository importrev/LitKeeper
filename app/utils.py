import os
import requests
from bs4 import BeautifulSoup
import time
import random
from PIL import Image, ImageDraw, ImageFont
import ebooklib.epub as epub
import uuid
from urllib.parse import quote
import re
import hashlib
import traceback
from datetime import datetime
from lxml import html          # <‑‑ added for XPath extraction

# --------------------------------------------------------------------------
# Environment variables – logging / telegram
# --------------------------------------------------------------------------
ENABLE_ACTION_LOG = os.getenv('ENABLE_ACTION_LOG', 'true').lower() == 'true'
ENABLE_ERROR_LOG  = os.getenv('ENABLE_ERROR_LOG',  'true').lower() == 'true'
ENABLE_URL_LOG    = os.getenv('ENABLE_URL_LOG',    'true').lower() == 'true'

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID')
ENABLE_TELEGRAM    = all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID])

# --------------------------------------------------------------------------
# Helper / logging functions
# --------------------------------------------------------------------------
def log_action(message):
    """Log an action to log.txt with timestamp."""
    if not ENABLE_ACTION_LOG:
        return
    log_dir = os.path.join(os.path.dirname(__file__), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"{timestamp} - {message}\n")

def log_error(error_message, url=None):
    """Log an error message to error_log.txt with timestamp and optional URL."""
    if not ENABLE_ERROR_LOG:
        return
    log_dir = os.path.join(os.path.dirname(__file__), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "error_log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"{timestamp} - {error_message}"
    if url and url not in error_message:
        message += f"\nURL: {url}"
    message += "\n" + "-"*50 + "\n"
    with open(log_file, "a") as f:
        f.write(message)
    log_action(f"Error logged: {error_message}")

def sanitize_filename(filename):
    """Keep only alphanumerics, space, dot, underscore, hyphen."""
    return re.sub(r'[^a-zA-Z0-9._ -]', '', filename)

def log_url(url):
    """Log URL to url_log.txt with timestamp."""
    if not ENABLE_URL_LOG:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = os.path.join(os.path.dirname(__file__), "data", "logs", "url_log.txt")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a") as f:
        f.write(f"{timestamp} - {url}\n")
    log_action("URL logged to url_log.txt")

def send_telegram_message(message, is_error=False):
    """Send a message to Telegram chat."""
    if not ENABLE_TELEGRAM:
        return
    try:
        icon = "❌" if is_error else "✅"
        formatted_message = f"{icon} {message}"
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": formatted_message, "parse_mode": "HTML"}
        response = requests.post(url, json=data)
        response.raise_for_status()
        if response.status_code == 200:
            log_action(f"Telegram notification sent: {message}")
        else:
            log_error(f"Failed to send Telegram notification. Status code: {response.status_code}")
    except Exception as e:
        log_error(f"Error sending Telegram notification: {str(e)}")

def get_random_user_agent():
    """Return a random User‑Agent string."""
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    ]
    return random.choice(USER_AGENTS)

def get_session():
    """Create and return a session with default headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    log_action("Created new requests session")
    return session

# --------------------------------------------------------------------------
# Story download – now also extracts the description for each chapter
# --------------------------------------------------------------------------
def download_story(url):
    """
    Download and extract the full story content and metadata from a Literotica URL.
    Returns:
        story_content (str)
        story_title (str)
        story_author (str)
        story_category (str | None)
        story_tags (list[str])
        chapter_titles (list[str])
        chapter_descriptions (list[str]) – description extracted from the first page of each chapter
    """
    try:
        session = get_session()
        story_content = ""
        current_page = 1
        story_title = "Unknown Title"
        story_author = "Unknown Author"
        story_category = None
        story_tags = []

        chapter_urls = [url]
        processed_urls = set()
        series_title = None
        chapter_titles = []
        chapter_contents = []
        chapter_descriptions = []   # <‑‑ new list

        while chapter_urls:
            current_url = chapter_urls.pop(0)
            if current_url in processed_urls:
                continue
            processed_urls.add(current_url)
            current_chapter = len(chapter_contents) + 1
            current_chapter_content = ""
            log_action(f"Processing chapter {current_chapter} from URL: {current_url}")
            log_url(current_url)

            while current_url:
                try:
                    log_action(f"Fetching page {current_page} of chapter {current_chapter}")
                    response = session.get(current_url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")
                    log_action("Successfully parsed page content")

                    # ------------------------------------------------------------------
                    #  First‑page metadata (title, author, description, category, tags)
                    # ------------------------------------------------------------------
                    if current_page == 1:
                        title_tag   = soup.find("h1", class_="headline")
                        author_tag  = soup.find("a", class_="y_eU")
                        current_title = title_tag.text.strip() if title_tag else "Unknown Chapter"

                        if current_chapter == 1:
                            story_title  = current_title
                            story_author = author_tag.text.strip() if author_tag else story_author
                            log_action(f"Extracted story metadata - Title: {story_title}, Author: {story_author}")

                            # Category
                            breadcrumb = soup.find("div", id="BreadCrumbComponent")
                            if breadcrumb:
                                category_links = breadcrumb.find_all("a", class_="h_aZ")
                                if len(category_links) >= 2:
                                    story_category = category_links[1].text.strip()
                                    if story_category.lower().startswith("inc"):
                                        story_category = "I/T"

                            # Tags
                            tag_elements = soup.find_all("a", class_="av_as av_r")
                            story_tags = [tag.text.strip() for tag in tag_elements
                                          if not tag.text.strip().lower().startswith("inc")]
                            if story_category and story_category not in story_tags:
                                story_tags = [story_category] + story_tags
                            log_action(f"Extracted category: {story_category} and {len(story_tags)} tags")

                        # ----------------- Description extraction --------------------
                        # Use the provided XPath
                        tree = html.fromstring(response.text)
                        desc_nodes = tree.xpath(
                            '/html/body/div/div/div/div[3]/div[5]/div[1]/div[1]/div[2]/div[1]/div[2]/div/div[1]/div[3]/span'
                        )
                        chapter_description = desc_nodes[0].text_content().strip() if desc_nodes else ""
                        chapter_descriptions.append(chapter_description)

                    # ------------------------------------------------------------------
                    #  Story content
                    # ------------------------------------------------------------------
                    content_div = soup.find("div", class_="aa_ht")
                    if content_div:
                        if current_page == 1:
                            chapter_titles.append(current_title)
                            log_action(f"Added chapter title: {current_title}")
                        for paragraph in content_div.find_all("p"):
                            current_chapter_content += paragraph.get_text(strip=True) + "\n\n"
                        log_action(f"Extracted content from page {current_page}")

                    # ------------------------------------------------------------------
                    #  Next page / next part
                    # ------------------------------------------------------------------
                    next_page_link = soup.find("a", class_="l_bJ", title="Next Page")
                    if next_page_link:
                        next_url = next_page_link["href"]
                        if not next_url.startswith("http"):
                            next_url = "https://www.literotica.com" + next_url
                        current_url = next_url
                        current_page += 1
                        log_action(f"Found next page link: {next_url}")
                    else:
                        chapter_contents.append(current_chapter_content)
                        log_action(f"Completed chapter {current_chapter}")

                        # Look for “Next Part” links inside the series panel
                        series_panel = soup.find("div", class_="panel z_r z_R")
                        if series_panel:
                            if not series_title:
                                story_links = series_panel.find_all("div", class_="z_S")
                                for story_div in story_links:
                                    series_info_span = story_div.find("span", class_="z_pm", string="Series Info")
                                    if series_info_span:
                                        link = story_div.find("a", class_="z_t")
                                        if link:
                                            series_title = link.get_text().strip()
                                            story_title = series_title
                                            log_action(f"Found series title: {series_title}")
                                            break
                            story_links = series_panel.find_all("div", class_="z_S")
                            for story_div in story_links:
                                link = story_div.find("a", class_="z_t")
                                if not link:
                                    continue
                                next_part_span = story_div.find("span", class_="z_pm")
                                if next_part_span and next_part_span.get_text().strip() == "Next Part":
                                    next_url = link["href"]
                                    if not next_url.startswith("http"):
                                        next_url = "https://www.literotica.com" + next_url
                                    if next_url not in processed_urls:
                                        chapter_urls.append(next_url)
                                        log_action(f"Found next chapter link: {next_url}")
                                    break

                        current_url = None
                        current_page = 1

                    time.sleep(3)  # politeness
                    log_action("Waiting 3 seconds before next request")

                except requests.RequestException as e:
                    error_msg = f"Network error while downloading chapter {current_chapter}: {str(e)}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None, None, None
                except Exception as e:
                    error_msg = f"Error processing chapter {current_chapter}: {str(e)}\n{traceback.format_exc()}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None, None, None

        # ------------------------------------------------------------------
        #  Combine all chapters into a single story string
        # ------------------------------------------------------------------
        story_content = ""
        for i, (title, content) in enumerate(zip(chapter_titles, chapter_contents), 1):
            story_content += f"\n\nChapter {i}: {title}\n\n{content}"
        log_action(f"Combined {len(chapter_contents)} chapters into final story content")

        return (
            story_content,
            story_title,
            story_author,
            story_category,
            story_tags,
            chapter_titles,
            chapter_descriptions,
        )

    except Exception as e:
        error_msg = f"Unexpected error in download_story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        return None, None, None, None, None, None, None

# --------------------------------------------------------------------------
# HTML helpers – formatting for EPUB
# --------------------------------------------------------------------------
def format_story_content(content):
    """Format story content into properly formatted paragraphs for EPUB."""
    css = """
        <style>
            body { margin: 1em; padding: 0 1em; }
            p   { margin: 1.5em 0; line-height: 1.7; font-size: 1.1em; }
            h1  { margin: 2em 0 1em 0; text-align: center; }
        </style>
    """
    paragraphs = content.split("\n\n")
    formatted_paragraphs = [f"<p>{p.strip()}</p>" for p in paragraphs if p.strip()]
    return css + "\n".join(formatted_paragraphs)

def format_metadata_content(category=None, tags=None):
    """Format metadata content with proper styling."""
    css = """
        <style>
            body { margin: 1em; padding: 0 1em; }
            h1  { margin: 2em 0 1em 0; text-align: center; }
            .metadata { margin: 1.5em 0; line-height: 1.7; font-size: 1.1em; }
            .metadata-item { margin: 1em 0; }
            .metadata-label { font-weight: bold; margin-right: 0.5em; }
        </style>
    """
    content = f"{css}<h1>Story Information</h1><div class='metadata'>"
    if category:
        content += f"<div class='metadata-item'><span class='metadata-label'>Category: </span>{category}</div>"
    if tags:
        content += f"<div class='metadata-item'><span class='metadata-label'>Tags: </span>{', '.join(tags)}</div>"
    content += "</div>"
    return content

# --------------------------------------------------------------------------
# Cover image generation
# --------------------------------------------------------------------------
def generate_cover_image(title, author, cover_path):
    """Generate a cover image with a gradient background, spine and styled text."""
    try:
        log_action(f"Generating cover image for '{title}' by {author}")
        width, height = 1200, 1600
        background_colors = [
            (47, 53, 66), (44, 62, 80), (52, 73, 94), (69, 39, 60),
            (81, 46, 95), (45, 52, 54), (33, 33, 33), (25, 42, 86),
            (56, 29, 42), (28, 40, 51),
        ]
        color_index = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(background_colors)
        background_color = background_colors[color_index]
        text_color = (255, 255, 255)
        spine_color = tuple(max(0, c - 20) for c in background_color)

        image = Image.new("RGB", (width, height), background_color)
        draw  = ImageDraw.Draw(image, "RGBA")
        spine_w = 40
        draw.rectangle([(0, 0), (spine_w, height)], fill=spine_color)

        # Load font – fall back to default if missing
        try:
            font_path = os.path.join(os.path.dirname(__file__), "static", "fonts",
                                    "Open_Sans", "OpenSans-VariableFont_wdth,wght.ttf")
            title_font  = ImageFont.truetype(font_path, 128)
            author_font = ImageFont.truetype(font_path, 72)
        except Exception:
            title_font  = ImageFont.load_default()
            author_font = ImageFont.load_default()
            log_action("Using default font as Open Sans not found")

        # Text layout – wrap title
        max_w = width - (spine_w + 100)
        words, lines, cur = title.split(), [], []
        for w in words:
            test_line = " ".join(cur + [w])
            wbox = draw.textbbox((0, 0), test_line, font=title_font)
            if wbox[2] - wbox[0] <= max_w:
                cur.append(w)
            else:
                lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))

        # Draw title
        total_h = sum(draw.textbbox((0, 0), l, font=title_font)[3] - draw.textbbox((0, 0), l, font=title_font)[1]
                     for l in lines)
        total_h += 40 * (len(lines) - 1)
        y = (height // 3) - (total_h // 2)
        for l in lines:
            wbox = draw.textbbox((0, 0), l, font=title_font)
            x = (width - (wbox[2] - wbox[0])) // 2
            draw.text((x, y), l, fill=text_color, font=title_font)
            y += (wbox[3] - wbox[1]) + 40

        # Author
        abox = draw.textbbox((0, 0), author, font=author_font)
        ax = (width - (abox[2] - abox[0])) // 2
        ay = height - 200
        draw.text((ax, ay), author, fill=text_color, font=author_font)

        # Resize to final size and save
        image = image.resize((600, 800), Image.Resampling.LANCZOS)
        image.save(cover_path, "JPEG", quality=95, optimize=True)
        log_action("Successfully saved cover image")

    except Exception as e:
        error_msg = f"Error generating cover image: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        log_action("Failed to generate cover image")

# --------------------------------------------------------------------------
# EPUB creation – now accepts chapter titles / descriptions
# --------------------------------------------------------------------------
def create_epub_file(
    story_title,
    story_author,
    story_content,
    output_directory,
    chapter_titles=None,
    chapter_descriptions=None,
    cover_image_path=None,
    story_category=None,
    story_tags=None,
):
    """
    Create an EPUB file from the story content.
    The EPUB will be written to <output_directory>/<sanitized_author>/.
    If chapter_descriptions are provided, they are concatenated and stored in
    the `dc:description` metadata field.
    """
    try:
        log_action(f"Starting EPUB creation for '{story_title}' by {story_author}")
        sanitized_author = sanitize_filename(story_author) or "Unknown_Author"
        author_dir = os.path.join(output_directory, sanitized_author)
        os.makedirs(author_dir, exist_ok=True)
        log_action(f"Created/verified output directory: {author_dir}")

        # Cover image
        if cover_image_path is None:
            cover_image_path = os.path.join(author_dir, f"{sanitize_filename(story_title)}.jpg")
            generate_cover_image(story_title, story_author, cover_image_path)

        book = epub.EpubBook()
        log_action("Created new EPUB book object")
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(story_title)
        book.set_language("en")
        book.add_author(story_author)
        book.add_metadata("DC", "publisher", "Literotica")

        # Optional metadata
        if story_category:
            book.add_metadata("DC", "subject", story_category)
        if story_tags:
            for tag in story_tags:
                book.add_metadata("DC", "subject", tag)

        # Cover image
        try:
            if os.path.exists(cover_image_path):
                with open(cover_image_path, "rb") as f:
                    book.set_cover("cover.jpg", f.read())
                log_action("Added cover image to EPUB")
        except Exception as e:
            log_error(f"Error adding cover image: {str(e)}")

        # ------------------------------------------------------------------
        #  Description metadata (new)
        # ------------------------------------------------------------------
        if chapter_titles and chapter_descriptions:
            parts = []
            for t, d in zip(chapter_titles, chapter_descriptions):
                if d:
                    parts.append(f"{t}: {d}")
            if parts:
                description_text = "\n".join(parts)
                book.add_metadata("DC", "description", description_text)
                log_action("Added chapter descriptions to EPUB metadata")

        # ------------------------------------------------------------------
        #  Chapters
        # ------------------------------------------------------------------
        chapters = []
        toc = []

        # Optional metadata chapter
        if story_category or story_tags:
            try:
                meta_content = format_metadata_content(story_category, story_tags)
                meta_chapter = epub.EpubHtml(
                    title="Story Information",
                    file_name="metadata.xhtml",
                    content=meta_content,
                )
                book.add_item(meta_chapter)
                chapters.append(meta_chapter)
                toc.append(meta_chapter)
                log_action("Added metadata chapter to EPUB")
            except Exception as e:
                log_error(f"Error adding metadata chapter: {str(e)}")

        # Intro (content before first chapter)
        chapter_texts = story_content.split("\n\nChapter ")
        if chapter_texts[0].strip():
            try:
                intro = format_story_content(chapter_texts[0])
                intro_chapter = epub.EpubHtml(
                    title="Introduction",
                    file_name="intro.xhtml",
                    content=f"<h1>Introduction</h1>{intro}",
                )
                book.add_item(intro_chapter)
                chapters.append(intro_chapter)
                toc.append(intro_chapter)
                log_action("Added introduction chapter to EPUB")
            except Exception as e:
                log_error(f"Error adding introduction chapter: {str(e)}")

        # Main chapters
        for i, chapter_text in enumerate(chapter_texts[1:], 1):
            try:
                title_end = chapter_text.find("\n\n")
                if title_end == -1:
                    chapter_title = f"Chapter {i}"
                    chapter_content = chapter_text
                else:
                    chapter_title = f"Chapter {chapter_text[:title_end]}"
                    chapter_content = chapter_text[title_end:].strip()

                formatted = format_story_content(chapter_content)
                chapter = epub.EpubHtml(
                    title=chapter_title,
                    file_name=f"chapter_{i}.xhtml",
                    content=f"<h1>{chapter_title}</h1>{formatted}",
                )
                book.add_item(chapter)
                chapters.append(chapter)
                toc.append(chapter)
                log_action(f"Added chapter {i} to EPUB")
            except Exception as e:
                log_error(f"Error processing chapter {i}: {str(e)}")
                continue

        if not chapters:
            log_error("No valid chapters found to create EPUB")
            raise ValueError("No valid chapters found")

        # Navigation
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        log_action("Added navigation files to EPUB")

        book.toc = toc
        book.spine = ["nav"] + chapters
        log_action("Set table of contents and spine")

        # Write file
        epub_path = os.path.join(author_dir, f"{sanitize_filename(story_title)}.epub")
        epub.write_epub(epub_path, book, {})
        log_action(f"Successfully wrote EPUB file to: {epub_path}")

        return epub_path

    except Exception as e:
        error_msg = f"Error creating EPUB file for '{story_title}' by {story_author}: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        send_telegram_message(f"EPUB creation failed: {story_title} by {story_author}", is_error=True)
        raise

# --------------------------------------------------------------------------
# Example usage (uncomment for manual run)
# --------------------------------------------------------------------------
# if __name__ == "__main__":
#     TEST_URL = "https://www.literotica.com/s/seven-nights-adippin"
#     OUTPUT_DIR = "epub_files"
#     os.makedirs(OUTPUT_DIR, exist_ok=True)
#     (
#         full_content,
#         title,
#         author,
#         category,
#         tags,
#         chapter_titles,
#         chapter_descriptions,
#     ) = download_story(TEST_URL)
#     if full_content:
#         epub_path = create_epub_file(
#             title,
#             author,
#             full_content,
#             OUTPUT_DIR,
#             chapter_titles=chapter_titles,
#             chapter_descriptions=chapter_descriptions,
#             story_category=category,
#             story_tags=tags,
#         )
#         print(f"EPUB created at {epub_path}")
#     else:
#         print("Failed to download story.")
