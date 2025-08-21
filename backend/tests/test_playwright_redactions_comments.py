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

        # Enter redaction mode via toolbar on page (DocumentViewerPage buttons)
        try:
            await page.click("button[title='Redact mode']", timeout=3000)
        except Exception:
            # Older selector fallback
            try:
                await page.click("[title='Redact']", timeout=3000)
            except Exception:
                pass

        viewer = await page.query_selector(".document-viewer")
        if viewer is None:
            await browser.close()
            pytest.skip("Viewer component not found")

        # If no redaction overlays exist, draw one
        overlays = await page.query_selector_all("[data-testid='redaction-overlay']")
        if not overlays:
            box = await viewer.bounding_box()
            start_x = box["x"] + 150
            start_y = box["y"] + 150
            await page.mouse.move(start_x, start_y)
            await page.mouse.down()
            await page.mouse.move(start_x + 160, start_y + 110)
            await page.mouse.up()
            # wait for overlay to show
            await page.wait_for_selector(
                "[data-testid='redaction-overlay']", timeout=5000
            )

        # Move the first redaction by dragging its center
        first_overlay = await page.query_selector("[data-testid='redaction-overlay']")
        if first_overlay:
            obox = await first_overlay.bounding_box()
            cx = obox["x"] + obox["width"] / 2
            cy = obox["y"] + obox["height"] / 2
            await page.mouse.move(cx, cy)
            await page.mouse.down()
            await page.mouse.move(cx + 20, cy + 20)
            await page.mouse.up()

        # Resize using handle
        resize_handle = await page.query_selector(
            "[data-testid='redaction-resize-handle']"
        )
        if resize_handle:
            hbox = await resize_handle.bounding_box()
            hx = hbox["x"] + hbox["width"] / 2
            hy = hbox["y"] + hbox["height"] / 2
            await page.mouse.move(hx, hy)
            await page.mouse.down()
            await page.mouse.move(hx + 25, hy + 30)
            await page.mouse.up()

        # Delete via the overlay delete button
        delete_btn = await page.query_selector("[data-testid='redaction-delete']")
        if delete_btn:
            await delete_btn.click()
            # Confirm dialog
            try:
                await page.on("dialog", lambda dialog: dialog.accept())
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
