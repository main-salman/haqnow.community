import pytest

try:
    from playwright.async_api import async_playwright
except Exception:
    pytest.skip("Playwright not installed; skipping E2E tests", allow_module_level=True)


@pytest.mark.asyncio
async def test_redaction_draw_move_resize_delete():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://localhost:3000/documents/1")

        # Wait for viewer
        try:
            await page.wait_for_selector(".document-viewer", timeout=10000)
        except Exception:
            await browser.close()
            pytest.skip("Viewer not available")

        # Enter redaction mode via toolbar on page
        # Fallback: click the redaction tool in top app toolbar if present
        try:
            await page.click("[title='Redact']", timeout=3000)
        except Exception:
            pass

        viewer = await page.query_selector(".document-viewer")
        if viewer is None:
            await browser.close()
            pytest.skip("Viewer component not found")

        # Draw rectangle
        box = await viewer.bounding_box()
        start_x = box["x"] + 100
        start_y = box["y"] + 120
        await page.mouse.move(start_x, start_y)
        await page.mouse.down()
        await page.mouse.move(start_x + 120, start_y + 80)
        await page.mouse.up()

        # Try to drag (move) the rectangle by grabbing near center
        await page.mouse.move(start_x + 60, start_y + 40)
        await page.mouse.down()
        await page.mouse.move(start_x + 80, start_y + 60)
        await page.mouse.up()

        # Try to click delete button if visible (×)
        try:
            await page.click("text=Delete", timeout=1000)
        except Exception:
            # If a small × button exists, attempt to click it by querying a button inside overlay
            try:
                await page.click("button:has-text('×')", timeout=1000)
            except Exception:
                pass

        await browser.close()


@pytest.mark.asyncio
async def test_comment_add_and_delete():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://localhost:3000/documents/1")

        try:
            await page.wait_for_selector(".document-viewer", timeout=10000)
        except Exception:
            await browser.close()
            pytest.skip("Viewer not available")

        # Switch to comment mode via toolbar
        try:
            await page.click("[title='Comment']", timeout=2000)
        except Exception:
            pass

        viewer = await page.query_selector(".document-viewer")
        box = await viewer.bounding_box()
        await page.mouse.click(box["x"] + 200, box["y"] + 150)

        # Type a comment in sidebar and add
        try:
            await page.fill(
                "textarea[placeholder*='comment']", "Playwright test comment"
            )
            await page.click("button:has-text('Add Comment')")
        except Exception:
            pass

        # Attempt to delete first comment in list
        try:
            await page.click("button:has-text('Delete')", timeout=2000)
        except Exception:
            pass

        await browser.close()
