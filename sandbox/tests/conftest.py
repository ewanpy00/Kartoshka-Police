import pytest_asyncio
from playwright.async_api import async_playwright


@pytest_asyncio.fixture(scope="session")
async def browser():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        yield browser
        await browser.close()
