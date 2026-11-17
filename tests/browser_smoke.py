"""Browser workflow using test-only fixed text and tones; never a neural demo.

Run: python tests/browser_smoke.py
Uses installed Chrome (or Playwright Chromium). Saves clearly named synthetic-test screenshots.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_integration import FAKE

from multilingua import media

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video = root / "synthetic-test.mp4"
        media.ffmpeg(
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x120:r=25:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=500:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            video,
        )
        adapter = root / "test_adapter.py"
        adapter.write_text(FAKE.replace("duration=0.8", "duration=1.4"))
        config = root / "config.json"
        config.write_text(
            json.dumps(
                {
                    "commands": {
                        stage: [sys.executable, str(adapter), stage]
                        for stage in ("asr", "translate", "tts", "lipsync")
                    }
                }
            )
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        with (root / "server.log").open("w") as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "multilingua.cli",
                    "--config",
                    str(config),
                    "ui",
                    "--port",
                    str(port),
                    "--runs",
                    str(root / "runs"),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                env={**os.environ, "GRADIO_ANALYTICS_ENABLED": "False"},
            )
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError((root / "server.log").read_text())
                    try:
                        with urlopen(url, timeout=1):
                            break
                    except OSError:
                        time.sleep(0.1)
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        executable_path=shutil.which("google-chrome"),
                        args=[
                            "--no-sandbox",
                            "--use-fake-device-for-media-stream",
                            "--use-fake-ui-for-media-stream",
                        ],
                    )
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    errors = []
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.goto(url, wait_until="domcontentloaded")
                    page.get_by_role("heading", name="Your ideas. A new language.").wait_for()
                    expect(
                        page.get_by_role("button", name="Generate dubbed video")
                    ).to_be_disabled()
                    page.get_by_role("button", name="Transcribe & translate").click()
                    expect(page.locator("#status")).to_contain_text(
                        "Upload an English video first", timeout=15000
                    )
                    page.locator("input[type=file]").first.set_input_files(str(video))
                    expect(page.locator("#status")).to_contain_text("New source", timeout=15000)
                    page.get_by_role("button", name="Transcribe & translate").click()
                    expect(page.locator("#status")).to_contain_text(
                        "Confirm permission", timeout=15000
                    )
                    page.get_by_role("checkbox", name="I have permission").check()
                    page.get_by_role("button", name="Transcribe & translate").click()
                    expect(page.locator("#status")).to_contain_text(
                        "Ready for review", timeout=30000
                    )
                    expect(page.get_by_test_id("cell-0-4")).to_contain_text("नमस्ते")
                    page.get_by_role("checkbox", name="I checked the Hindi").check()
                    page.get_by_test_id("cell-0-4").dblclick()
                    editor = page.get_by_test_id("cell-0-4").locator("textarea")
                    editor.fill("नमस्कार")
                    editor.press("Tab")
                    expect(page.get_by_test_id("cell-0-4")).to_contain_text("नमस्कार")
                    expect(
                        page.get_by_role("checkbox", name="I checked the Hindi")
                    ).not_to_be_checked()
                    page.get_by_role("radio", name="Audio-only comparison", exact=True).check()
                    page.get_by_role("button", name="Generate dubbed video").click()
                    expect(page.locator("#status")).to_contain_text(
                        "Confirm that you checked", timeout=15000
                    )
                    page.get_by_role("checkbox", name="I checked the Hindi").check()
                    flexible = page.get_by_role("checkbox", name="Allow a longer video")
                    expect(flexible).to_be_checked()
                    flexible.uncheck()
                    page.get_by_role("button", name="Generate dubbed video").click()
                    expect(page.locator("#status")).to_contain_text("Review row 1", timeout=45000)
                    flexible.check()
                    page.get_by_role("button", name="Generate dubbed video").click()
                    expect(page.locator("#status")).to_contain_text("Complete", timeout=45000)
                    expect(page.locator("#status")).to_contain_text("Added 0.12 s")
                    expect(page.locator('a[href$="/delivery.zip"]')).to_be_visible()
                    with page.expect_download() as download:
                        page.locator('a[href$="/delivery.zip"]').click()
                    assert download.value.failure() is None
                    artifact = ROOT / "artifacts"
                    artifact.mkdir(exist_ok=True)
                    page.screenshot(
                        path=str(artifact / "synthetic-workflow-desktop.png"), full_page=True
                    )
                    # Explicit lip failure must replace success UI, never silently pass through.
                    page.get_by_role("radio", name="Lip-synced Hindi", exact=True).check()
                    page.get_by_role("button", name="Generate dubbed video").click()
                    expect(page.locator("#status")).to_contain_text("lipsync failed", timeout=45000)
                    expect(page.locator('a[href$="/delivery.zip"]')).not_to_be_visible()
                    page.get_by_role("tab", name="Quick Webcam").click()
                    page.get_by_role("checkbox", name="I have permission to record").check()
                    page.get_by_role("button", name="Click to Access Webcam").click()
                    record = page.get_by_role("button", name="start recording")
                    record.click()
                    expect(record).to_have_text("Stop")
                    page.wait_for_timeout(1300)  # Let the simulated webcam record a real container.
                    record.click()
                    quick_status = page.get_by_role("textbox", name="Preview status")
                    expect(quick_status).to_have_value(re.compile(r"^Preview ready"), timeout=20000)
                    expect(page.get_by_role("textbox", name="Hindi translation")).to_have_value(
                        "नमस्ते"
                    )
                    expect(page.locator('a[href$="/hindi.srt"]')).to_be_visible()
                    mobile = browser.new_page(viewport={"width": 390, "height": 844})
                    mobile.goto(url, wait_until="domcontentloaded")
                    mobile.get_by_role("heading", name="Your ideas. A new language.").wait_for()
                    mobile.screenshot(path=str(artifact / "studio-mobile.png"), full_page=True)
                    assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert not errors, errors
                    browser.close()
                    print(
                        "PASS: studio review, audio render, ZIP download, lip failure, webcam Stop → Hindi preview, mobile layout."
                    )
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
