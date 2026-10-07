"""Live checks for the background trees (motion on unless stated)."""
from playwright.sync_api import sync_playwright

from common import BASE
INIT = """
(([look, weather, effects]) => {
  const place = { name: 'Hà Nội', country: 'Vietnam', lat: 21.0285, lon: 105.8542 };
  localStorage.setItem('myvocab-sky', JSON.stringify({ look, effects, place }));
  localStorage.setItem('myvocab-sky-reading', JSON.stringify({
    place: `${place.lat.toFixed(3)},${place.lon.toFixed(3)}`, fetchedAt: Date.now(),
    utcOffset: 25200, sunrise: 350, sunset: 1060, isDay: true, temperature: 27,
    label: 'Test', weather }));
})(%s)
"""
results = []

def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

def open_page(browser, path="/", look="morning", weather="clear", effects=True, size=(1440, 900), motion="no-preference"):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, reduced_motion=motion)
    ctx.add_init_script(INIT % f'["{look}", "{weather}", {str(effects).lower()}]')
    ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "open-meteo" not in m.text
            and "ERR_FAILED" not in m.text else None)
    page.goto(BASE + path, wait_until="networkidle")
    return ctx, page, errors

def anim(page, sel=".tree-banyan .tree-sway"):
    return page.eval_on_selector(sel, "e => getComputedStyle(e).animationName")

with sync_playwright() as p:
    b = p.chromium.launch()

    # Every page carries the trees, with no errors.
    for path in ("/", "/practice", "/exam", "/data", "/manage_topics"):
        ctx, page, errors = open_page(b, path)
        n = page.locator(".scene-trees .tree").count()
        check(f"{path}: two trees", n == 2, str(n))
        check(f"{path}: no console errors", not errors, "; ".join(errors)[:200])
        ctx.close()

    # Wind follows the weather; the rain & snow switch calms it.
    for weather, effects, want in (("clear", True, "tree-sway"), ("drizzle", True, "tree-sway-breeze"),
                                   ("rain", True, "tree-sway-wind"), ("storm", True, "tree-sway-gale"),
                                   ("storm", False, "tree-sway")):
        ctx, page, _ = open_page(b, weather=weather, effects=effects)
        got = anim(page)
        check(f"{weather}, effects {'on' if effects else 'off'}: {want}", got == want, got)
        ctx.close()

    # The tree really moves, turning on its trunk.
    ctx, page, _ = open_page(b, weather="storm")
    t1 = page.eval_on_selector(".tree-banyan .tree-sway", "e => getComputedStyle(e).transform")
    page.wait_for_timeout(700)
    t2 = page.eval_on_selector(".tree-banyan .tree-sway", "e => getComputedStyle(e).transform")
    check("storm: the banyan sways", t1 != t2 and t1 != "none", f"{t1} -> {t2}")
    origin = page.eval_on_selector(".tree-banyan .tree-sway", "e => getComputedStyle(e).transformOrigin")
    check("banyan turns near its trunk's foot", origin.split()[1].startswith(("8", "7")), origin)
    ctx.close()

    # Reduced motion: still trees, steady fireflies.
    ctx, page, _ = open_page(b, look="night", motion="reduce")
    check("reduced motion: trees still", anim(page) == "none", anim(page))
    ff = page.eval_on_selector(".firefly", "e => [getComputedStyle(e).animationName, getComputedStyle(e).opacity]")
    check("reduced motion: fireflies shown, not blinking", ff[0] == "none" and float(ff[1]) > 0.5, str(ff))
    ctx.close()

    # Fireflies: night only, and not in the rain.
    for look, weather, want in (("night", "clear", True), ("night", "rain", False), ("morning", "clear", False),
                                ("evening", "clear", False)):
        ctx, page, _ = open_page(b, look=look, weather=weather)
        page.wait_for_timeout(1400)
        name = page.eval_on_selector(".firefly", "e => getComputedStyle(e).animationName")
        ops = page.eval_on_selector_all(".firefly", "es => es.map(e => +getComputedStyle(e).opacity)")
        shown = name == "firefly" and max(ops) > 0.3
        check(f"{look}/{weather}: fireflies {'on' if want else 'off'}", shown == want, f"{name} max {max(ops):.2f}")
        ctx.close()

    # Snow: the caps are drawn in shared clumps, so read the variable they use.
    for weather, want in (("snow", "0.95"), ("clear", "0")):
        ctx, page, _ = open_page(b, weather=weather)
        v = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--tree-snow-opacity').trim()")
        check(f"{weather}: snow on the leaves {want}", v == want, v)
        ctx.close()

    # Changing the look fades the leaves (the <use> copies too), not a jump.
    ctx, page, _ = open_page(b, look="morning")
    page.wait_for_timeout(300)
    def pixel(x, y):
        shot = page.screenshot(clip={"x": x, "y": y, "width": 1, "height": 1})
        from PIL import Image
        import io
        return Image.open(io.BytesIO(shot)).convert("RGB").getpixel((0, 0))
    # A point inside a leaf clump of the banyan, clear of the page's cards.
    x, y = 120, 330
    before = pixel(x, y)
    page.evaluate("MyVocabSky.prefs.look = 'night'; MyVocabSky.apply()")
    page.wait_for_timeout(450)
    mid = pixel(x, y)
    page.wait_for_timeout(1500)
    after = pixel(x, y)
    between = all(min(a, c) - 3 <= m_ <= max(a, c) + 3 for a, m_, c in zip(before, mid, after)) and mid not in (before, after)
    check("leaves fade from morning to night", between and before != after, f"{before} -> {mid} -> {after}")
    ctx.close()

    # Trees never block clicks or widen the page.
    for size in ((390, 844), (768, 1024), (1440, 900)):
        ctx, page, _ = open_page(b, size=size)
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(f"{size[0]}x{size[1]}: no sideways scroll", over == 0, str(over))
        pe = page.eval_on_selector(".scene-trees", "e => getComputedStyle(e).pointerEvents")
        check(f"{size[0]}x{size[1]}: trees ignore the pointer", pe == "none", pe)
        # The thing on top at a point over the banyan is page content or the body, never a tree.
        top = page.evaluate("(() => { const e = document.elementFromPoint(40, innerHeight - 60); return e.closest('.scene-trees') ? 'tree' : e.tagName; })()")
        check(f"{size[0]}x{size[1]}: nothing of the tree is clickable", top != "tree", top)
        ctx.close()

    b.close()

print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
