import json
import os
import re
from typing import Dict, List
import sys

sys.path.append(os.getcwd())

from playwright.sync_api import Browser, Page, sync_playwright
import requests

from src.settings import custom_logger

def is_valid_image_url(url: str) -> bool:
    return any(ext in url for ext in VALID_IMAGE_EXTENSIONS)

def get_image_extension_from_url(url: str) -> str:
    if "f=webp" in url:
        return ".webp"
    for ext in VALID_IMAGE_EXTENSIONS:
        if ext in url:
            return ext
    return ".jpg"


VALID_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]


class ToolScraper:
    def __init__(
        self, output_dir: str = "data/scraped_data", max_tool: int = 60, max_pages: int = 10
    ) -> None:
        """
        Initialize the ToolScraper

        Args:
            output_dir (str): The directory to store scraped data
            max_tool (int): The maximum number of tools items to scrape
        """

        self.logger = custom_logger(self.__class__.__name__)

        # Set up directories for storing scraped data
        self.output_dir = output_dir
        self.images_dir = os.path.join(self.output_dir, "images")
        self.tool_dir = os.path.join(self.output_dir, "tool")

        # Create necessary directories if they don't exist
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.tool_dir, exist_ok=True)

        # Keep track of processed tool to avoid duplicates
        self.processed_tool = set()
        self._load_processed_tool()

        # Initialize counters for processed tool
        self.tool_processed = len(self.processed_tool)
        self.max_pages = max_pages
        self.max_tool = max_tool
        self.logger.info(
            "toolScraper initialized. Output directory: %s", self.output_dir
        )

    def _load_processed_tool(self) -> None:
        """Load already processed tool from existing JSONL files"""

        for filename in os.listdir(self.tool_dir):
            if filename.endswith(".jsonl"):
                tool_id = filename.replace(".jsonl", "")
                self.processed_tool.add(tool_id)
        self.logger.info(
            f"Found {len(self.processed_tool)} previously processed tool"
        )

    def run(self, base_url: str, validation_url: str, pagination_param: str = "currentpage") -> None:
        """
        Run the tool scraper.

        Args:
            base_url (str): The base URL for tool listings.
            validation_url (str): The URL to validate tool links.
        """

        self.logger.info("Starting scraper run")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            current_page = 1

            while current_page <= self.max_pages:
                if self.tool_processed >= self.max_tool:
                    self.logger.info(
                        f"Reached maximum number of new tool items ({self.max_tool})"
                    )
                    break

                connector = "&" if "?" in base_url else "?"
                page_url = f"{base_url}{connector}{pagination_param}={current_page}"
                self.logger.info(f"Processing page {current_page}, URL: {page_url}")

                try:
                    page.goto(page_url, timeout=60000)
                except Exception as e:
                    self.logger.warning(f"Error loading page {current_page}: {e}")
                    break

                tool_links = self._get_tool_links(page, validation_url)
                self.logger.info(
                    f"Found {len(tool_links)} unique tool links on page {current_page}"
                )

                if not tool_links:
                    self.logger.info("No more tools found, ending scraping.")
                    break

                self._process_tool(page, tool_links, browser, current_page)

                current_page += 1

            self.logger.info("Finished processing all tools across all pages")
            browser.close()


    def _get_tool_links(self, page: Page, validation_url: str) -> List[str]:
        """
        Get tool links from the current page

        Args:
            page (Page): The page object to get tool links from
            validation_url (str): The URL to validate tool links

        Returns:
            List[str]: A list of tool links
        """

        tool_links = []

        page.wait_for_selector("a[href*='/product/']", timeout=10000)

        html_content = page.content()
        with open("debug_tool_list_page.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        product_anchors = page.locator("a[href*='/product/']").all()
        for anchor in product_anchors:
            href = anchor.get_attribute("href")
            if href and "/sodimac-uy/product/" in href:
                tool_links.append(href)

        tool_links = list(dict.fromkeys(tool_links))

        return tool_links



    def _process_tool(
        self,
        page: Page,
        tool_links: List[str],
        browser: Browser,
        current_page: int
    ) -> None:
        """
        Process each tool link found on the page

        Args:
            page (Page): The page object to process tool links from
            tool_links (List[str]): A list of tool links to process
            browser (Browser): The browser object to use for processing
        """

        for i, link in enumerate(tool_links, 1):
            try:
                #  Check if the tool has already been processed
                tool = {
                    "id": link.rstrip("/").split("/")[-1],
                    "link": link,
                    "images": [],
                    "details": None,
                }
                if tool["id"] in self.processed_tool:
                    self.logger.info(
                        f"Skipping already processed tool {tool['id']} ({i}/{len(tool_links)})"
                    )
                    continue

                # Process the tool
                self.logger.info(
                    f"Processing tool {i}/{len(tool_links)}: {link}"
                )
                self._process_tool_details(page, tool, current_page)

                # Mark the tool as processed
                self.processed_tool.add(tool["id"])
                self.tool_processed += 1
                self.logger.info(
                    f"Processed {self.tool_processed}/{self.max_tool} tool items"
                )

                # Check if the maximum number of tool has been reached
                if self.tool_processed >= self.max_tool:
                    break

            except Exception as e:
                self.logger.error(f"Error processing tool {link}: {str(e)}")
                continue

    def _process_tool_details(self, page: Page, tool: Dict, current_page: int) -> None:
        import re

        def sanitize_filename(name):
            return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")

        def get_image_extension_from_url(url):
            parsed = url.split("?")[0]
            ext = os.path.splitext(parsed)[-1]
            if ext.lower() in VALID_IMAGE_EXTENSIONS:
                return ext
            return ".jpg"  # Por defecto

        base_domain = "https://www.sodimac.com.uy"
        full_url = tool["link"]
        if full_url.startswith("/"):
            full_url = base_domain + full_url

        self.logger.debug("Navigating to tool URL: %s", full_url)

        page.goto(full_url)
        html_content = page.content()
        with open(f"debug_page_{current_page}.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        self.logger.debug("Processing tool ID: %s", tool["id"])

        try:
            page.wait_for_selector("img[id^='pdpMainImage']", timeout=10000, state="attached")
            img_elements = page.locator("img[id^='pdpMainImage']").all()
            img_urls = [
                img.get_attribute("src")
                for img in img_elements
                if img.get_attribute("src") and "sodimacUY" in img.get_attribute("src")
            ]
            self.logger.debug("Successfully extracted %d image URLs from tool page", len(img_urls))
        except Exception as e:
            self.logger.error("Error retrieving image URLs: %s", str(e))
            img_urls = []

        try:
            name = page.locator("h1.product-title").text_content().strip()
        except Exception as e:
            self.logger.warning(f"No se pudo obtener el nombre: {e}")
            name = None

        try:
            description = page.locator("div.product-model").text_content().strip()
        except Exception as e:
            self.logger.warning(f"No se pudo obtener la descripción: {e}")
            description = None

        try:
            price_spans = page.locator("span.jsx-2816876583").all()
            price = None

            for span in price_spans:
                text = span.text_content().strip()
                # Buscar span que contenga solo números y puntos, como "5.509"
                if re.fullmatch(r"\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?", text):
                    # Convertir formato latino a float: 5.509 → 5509.0
                    price = float(text.replace(".", "").replace(",", "."))
                    break

        except Exception as e:
            self.logger.warning(f"No se pudo obtener el precio: {e}")
            price = None

        tool["details"] = {
            "name": name,
            "price": price,
            "description": description,
        }
        self.logger.debug(f"Detalles parseados → Nombre: {name}, Precio: {price}, Descripción: {description}")


        tool_name = tool["details"]["name"] or tool["id"]
        safe_name = sanitize_filename(tool_name)
        tool_img_dir = os.path.join(self.images_dir, safe_name)
        os.makedirs(tool_img_dir, exist_ok=True)

        jsonlines_data = []

        for i, img_url in enumerate(img_urls, 1):
            if not img_url:
                continue

            ext = get_image_extension_from_url(img_url)
            img_filename = f"image_{i}{ext}"
            img_path = os.path.join(tool_img_dir, img_filename)

            self.logger.debug(
                f"Downloading image {i}/{len(img_urls)} for tool {tool['id']}: {img_filename}"
            )

            try:
                response = requests.get(img_url, timeout=10)
                if response.status_code == 200:
                    with open(img_path, "wb") as f:
                        f.write(response.content)
                    self.logger.info(f"✅ Imagen guardada: {img_path}")
                else:
                    self.logger.warning(f"⚠️ Falló la descarga: {img_url} (status {response.status_code})")
                    continue
            except Exception as e:
                self.logger.error(f"❌ Error al descargar {img_url}: {str(e)}")
                continue

            image_info = {
                "source": "sodimac",
                "id": tool["id"],
                "name": tool["details"]["name"],
                "link": tool["link"],
                "local_image_path": img_path,
                "image_url": img_url,
                "details": tool["details"],
            }
            jsonlines_data.append(image_info)

        self.logger.debug("Saving tool data to JSONL")
        self.save_to_jsonl(tool, jsonlines_data, safe_name)

    def save_to_jsonl(self, tool: Dict, jsonlines_data: List[Dict], safe_name: str):
        jsonl_path = os.path.join(self.tool_dir, f"{safe_name}.jsonl")
        self.logger.debug("Saving data for tool %s to %s", tool["id"], jsonl_path)

        try:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                for item in jsonlines_data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            self.logger.debug("Successfully saved data for tool %s", tool["id"])
        except Exception as e:
            self.logger.error("Failed to save data for tool %s: %s", tool["id"], str(e))
