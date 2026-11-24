import pytest_asyncio
from playwright.async_api import async_playwright

from app.capture import BROWSER_ARGS


@pytest_asyncio.fixture(scope="session")
async def browser():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=BROWSER_ARGS)
        yield browser
        await browser.close()
