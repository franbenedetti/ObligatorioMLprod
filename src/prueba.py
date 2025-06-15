from playwright.sync_api import sync_playwright

BASE_URL = "https://www.sodimac.com.uy/sodimac-uy/category/cat20864/herramientas-manuales"
PAGINATION_PARAM = "currentpage"
VALIDATION_URL = "https://www.sodimac.com.uy/sodimac-uy/product/"
MAX_PAGES_TO_TEST = 5  # Cambiá este número para probar más páginas

def get_tool_links(page, validation_url):
    # Acá simplificamos: busca todos los <a> con href que empiece con validation_url
    links = page.eval_on_selector_all("a[href^='/sodimac-uy/product/']", "elements => elements.map(e => e.href)")
    return list(set([l for l in links if validation_url in l]))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    for i in range(1, MAX_PAGES_TO_TEST + 1):
        connector = "&" if "?" in BASE_URL else "?"
        page_url = f"{BASE_URL}{connector}{PAGINATION_PARAM}={i}"
        print(f"🔎 Probando página {i} → {page_url}")
        page.goto(page_url, timeout=60000)

        tool_links = get_tool_links(page, VALIDATION_URL)
        print(f"✅ Página {i}: {len(tool_links)} muebles encontrados")

        if not tool_links:
            print("🚫 No se encontraron más muebles, probablemente sea la última página.")
            break

    browser.close()

