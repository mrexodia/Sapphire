"""Check the offline explainer, its links, and browser-based simulator behavior.

python research/ps3-monitor/validate_eobj_explainer.py
python research/ps3-monitor/validate_eobj_explainer.py --static-only
Browser checks require Python Playwright and Edge or a Playwright Chromium install.
Screenshots are written to build/ (not source control).
"""
import argparse
from html.parser import HTMLParser
from pathlib import Path


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise AssertionError(f"Duplicate ID: {attrs['id']}")
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "script":
            assert "src" not in attrs, "External script dependency"
            self.scripts += 1
        if tag in ("link", "img", "iframe"):
            raise AssertionError(f"Unexpected external resource element: {tag}")


def static_checks(page):
    doc = Document()
    text = page.read_text(encoding="utf-8")
    doc.feed(text)
    assert doc.scripts == 1
    for href in doc.links:
        if href.startswith("#"):
            assert href[1:] in doc.ids, f"Broken chapter link: {href}"
        else:
            assert "://" not in href, f"Unexpected network link: {href}"
            assert (page.parent / href).is_file(), f"Broken research link: {href}"
    assert "0x1409EC750" in text and "+0x1A2" in text
    assert "0x0097A850" in text and "+0x17A" in text
    print(f"Static checks passed: {len(doc.ids)} IDs, {len(doc.links)} valid local/anchor links")


def browser_checks(path, executable):
    from playwright.sync_api import sync_playwright
    build = Path("build")
    build.mkdir(exist_ok=True)
    with sync_playwright() as p:
        kwargs = {"headless": True}
        if executable:
            kwargs["executable_path"] = str(executable)
        browser = p.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": 1360, "height": 950})
        errors, network = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: network.append(request.url) if request.url.startswith(("http:", "https:")) else None)
        page.goto(path.resolve().as_uri())
        assert page.title().startswith("FFXIV event objects")
        assert page.locator("#slot-rows tr").count() == 4

        def value(id_):
            return page.locator("#" + id_).inner_text()

        def preset(name):
            page.locator(f'[data-preset="{name}"]').click()

        assert value("stored-result") == "0x000A"
        assert value("rising-result") == "0x000A"
        assert value("falling-result") == "0x0004"
        assert value("playing-result") == "0x000A"
        assert value("q-any") == "false"
        assert "close, vfx_off" in value("actions")
        page.locator("#query").fill("0x000C")
        assert value("q-any") == "true" and value("q-all") == "false"
        page.locator("#query").fill("0")
        assert value("q-all") == "true" and value("q-none") == "true"
        assert value("q-any") == "false" and value("q-exact") == "false"

        preset("same")
        assert value("playing-result") == "0x0000"
        assert value("q-any") == "true", "Stored selection must differ from current playback"
        page.locator("#mode").select_option("fallback")
        assert value("playing-result") == "0x0004", "Fallback should request replay"
        preset("split")
        assert value("stored-result") == "0x000A" and value("playing-result") == "0x0004"
        assert value("q-any") == "false" and page.locator("#sim-warning").is_visible()
        preset("or")
        assert value("stored-result") == "0x000C" and value("playing-result") == "0x000C"
        assert "OR-ing in off did not clear on" in value("sim-warning")
        preset("seal")
        page.locator("#ready").uncheck()
        assert value("stored-result") == "0x000A" and value("playing-result") == "0x0004"
        assert "availability is disabled" in value("actions")
        page.locator("#next").fill("0x10000")
        assert page.locator("#next").get_attribute("aria-invalid") == "true"
        assert value("stored-result") == "—" and value("sim-error")
        preset("seal")
        assert value("sim-error") == ""

        # Cross-check the simulator against an independent per-slot specification.
        tested = page.evaluate("""() => {
          let tested = 0;
          for (const mode of ['base', 'fallback', 'direct']) {
            for (let old = 0; old < 16; old++) for (let next = 0; next < 16; next++) {
              for (let playing = 0; playing < 16; playing++) {
                const playback = (old + next + playing) & 15;
                for (const ready of [false, true]) {
                  const actual = transition(mode, old, next, playing, playback, ready);
                  let expected = playing;
                  for (let i = 0; i < 4; i++) {
                    const bit = 1 << i;
                    const before = !!(playing & bit);
                    let start = false, stop = false;
                    if (ready) {
                      if (mode === 'base') {
                        start = !(old & bit) && !!(next & bit) && !before;
                        stop = !!(old & bit) && !(next & bit) && before;
                      } else {
                        const requested = mode === 'direct' ? playback : next;
                        start = !!(requested & bit) && !before;
                        stop = !(requested & bit) && before;
                      }
                    }
                    if (start) expected |= bit;
                    if (stop) expected &= ~bit;
                  }
                  if (actual.stored !== next || actual.after !== expected)
                    throw new Error('Transition mismatch');
                  tested++;
                }
              }
            }
          }
          return tested;
        }""")
        assert tested == 24576
        assert not errors, errors
        assert not network, network
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(build / "eobj-explainer-desktop.png"))
        page.locator("#simulator").scroll_into_view_if_needed()
        page.screenshot(path=str(build / "eobj-explainer-simulator.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("window.scrollTo(0, 0)")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile page overflows viewport"
        page.screenshot(path=str(build / "eobj-explainer-mobile.png"))
        browser.close()
        print(f"Browser checks passed: presets, input validation, mobile layout, {tested} mask transitions, zero network requests")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--browser", type=Path)
    args = parser.parse_args()
    path = Path(__file__).with_name("eobj-flow-explainer.html")
    static_checks(path)
    if not args.static_only:
        edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
        browser_checks(path, args.browser or (edge if edge.is_file() else None))


if __name__ == "__main__":
    main()
