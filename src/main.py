from scrapers.sodimac import ToolScraper
from settings.settings import load_settings
from settings.logger import custom_logger

logger = custom_logger("Main")

if __name__ == "__main__":
    # Set the settings
    settings = load_settings(key="WebPage")
    BASE_URL = settings["BaseUrl"]
    VALIDATION_URL = settings["ValidationUrl"]
    MAX_PRODUCTS = settings["MaxProducts"]
    PAGINATION_PARAM = settings.get("PaginationParam", "currentpage")
    START_PAGE = settings.get("StartPage", 1)
    MAX_PAGES = settings.get("MaxPages", 10)

    # Initialize the scraper
    scraper = ToolScraper(
        max_tool=MAX_PRODUCTS
    )

    # Run the scraper
    scraper.run(
        base_url=BASE_URL,
        validation_url=VALIDATION_URL,
        pagination_param=PAGINATION_PARAM
    )