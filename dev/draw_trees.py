"""Draw the two big background trees into templates/partials/trees.html.

A banyan stands on the left and an Indian almond on the right. Shapes are
coloured with var(--tree-...) tokens, so style.css repaints the trees for
morning, evening and night. Each tree is two SVGs in the same box: the swaying
part (trunk, limbs, leaves) and the still base (roots, ground, fireflies), so
only the first needs to move. Leaf clumps are drawn once and reused with <use>;
their colours sit in inline styles so they reach the copies.

Usage (from the project root), after changing a shape here:

    python3 dev/draw_trees.py

The drawing is seeded, so the same script always draws the same trees.
"""
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "templates" / "partials" / "trees.html"


def f(v):
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def bez(p, t):
    u = 1 - t
    return tuple(u**3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t**3 * d for a, b, c, d in zip(*p))


def normal(p, t):
    u = 1 - t
    dx, dy = (3 * u * u * (b - a) + 6 * u * t * (c - b) + 3 * t * t * (d - c) for a, b, c, d in zip(*p))
    ln = math.hypot(dx, dy) or 1
    return -dy / ln, dx / ln


def limb(p, w0, w1, side=None):
    """A tapering branch along the cubic Bezier p: its two edges are the curve
    pushed out along its normals. side='left'/'right' keeps that flank only."""
    edges = ([], [])
    for i, t in enumerate((0, 1 / 3, 2 / 3, 1)):
        x, y = p[i]
        nx, ny = normal(p, t)
        w = (w0 + (w1 - w0) * t) / 2
        a, b = -w, w
        if side == "left":
            b = -0.1 * w
        elif side == "right":
            a = 0.1 * w
        edges[0].append((x + nx * a, y + ny * a))
        edges[1].append((x + nx * b, y + ny * b))
    l, r = edges
    pt = lambda q: f"{f(q[0])},{f(q[1])}"
    return (f"M{pt(l[0])}C{pt(l[1])} {pt(l[2])} {pt(l[3])}L{pt(r[3])}"
            f"C{pt(r[2])} {pt(r[1])} {pt(r[0])}Z")


def circle(cx, cy, r):
    return f"M{f(cx - r)},{f(cy)}a{f(r)},{f(r)} 0 1,0 {f(2 * r)},0a{f(r)},{f(r)} 0 1,0 {f(-2 * r)},0"


def blob(rng, cx, cy, r, bumps, size=0.3, arc=(0, 360)):
    """A disc with smaller discs scalloping its edge: a leafy outline."""
    parts = [circle(cx, cy, r)]
    for i in range(bumps):
        a = math.radians(arc[0] + (arc[1] - arc[0]) * (i + rng.uniform(0.25, 0.75)) / bumps)
        rr = r * rng.uniform(0.78, 0.9)
        parts.append(circle(cx + math.cos(a) * rr, cy + math.sin(a) * rr, r * size * rng.uniform(0.8, 1.2)))
    return "".join(parts)


def shape(token, d, extra=""):
    return f'<path style="fill:var(--tree-{token}){extra}" d="{d}"/>'


def clump_def(cid, seed):
    """A clump of leaves at radius 100, lit from the right: a shadow underneath,
    the leaves, and a rim of light along their upper right edge (the leaf shape
    drawn in the light colour, then again in the leaf colour a little lower)."""
    rng = random.Random(seed)
    back = blob(rng, -6, 8, 100, 9)
    leaf_seed = rng.random()
    leaf = lambda dx, dy: blob(random.Random(leaf_seed), dx, dy, 86, 8, 0.32, arc=(150, 390))
    # Copies made by <use> may not match the stylesheet's selectors, so the
    # transitions are inline too.
    fade = ";transition:fill 1.2s ease,opacity 1.2s ease"
    parts = [shape("leaf-back", back, fade), shape("leaf-lit", leaf(8, -8), fade), shape("leaf", leaf(-2, 3), fade),
             # Snow resting on top, shown only when it snows (--tree-snow-opacity).
             shape("snow", "M-64,-56Q-2,-130 62,-56Q-2,-86 -64,-56Z", ";opacity:var(--tree-snow-opacity)" + fade)]
    return f'<g id="{cid}">{"".join(parts)}</g>'


def clump(cid, cx, cy, r, light=1, turn=0):
    """One use of a clump; light=-1 mirrors it to be lit from the left."""
    s = r / 100
    return (f'<use href="#{cid}" transform="translate({f(cx)} {f(cy)}) rotate({f(turn)}) '
            f'scale({f(s * light)} {f(s)})"/>')


def grass(rng, x0, x1, ground_y):
    """Little blades of grass standing along the mound's edge."""
    parts, x = [], x0
    while x < x1:
        y, h, lean = ground_y(x), rng.uniform(9, 18), rng.uniform(-4, 4)
        parts.append(f"M{f(x - 3)},{f(y + 2)}L{f(x + lean)},{f(y - h)}L{f(x + 3)},{f(y + 2)}Z")
        x += rng.uniform(8, 16)
    return "".join(parts)


def fireflies(rng, count, box):
    x0, y0, x1, y1 = box
    out = []
    for _ in range(count):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        out.append(f'<g class="firefly" style="animation-delay:{-rng.uniform(0, 6):.1f}s">'
                   f'<circle cx="{f(x)}" cy="{f(y)}" r="10" fill="url(#firefly-glow)"/>'
                   f'<circle cx="{f(x)}" cy="{f(y)}" r="2.2" fill="#fff4c4"/></g>')
    return "".join(out)


# ---------- Banyan (left): broad dome, thick trunk, aerial roots ----------
def banyan():
    rng = random.Random(7)
    sway = []
    long_limb = ((176, 560), (232, 468), (340, 416), (510, 398))
    limbs = [
        (((150, 1010), (148, 860), (158, 700), (166, 540)), 220, 120),   # trunk
        (((160, 580), (130, 460), (90, 340), (40, 200)), 96, 30),        # up-left
        (((172, 560), (196, 430), (236, 310), (270, 160)), 100, 34),     # up the middle
        (long_limb, 76, 24),                                             # arching out over the valley
        (((240, 320), (300, 260), (360, 230), (430, 230)), 44, 14),      # off the middle
        (((bez(long_limb, 0.8)), (480, 380), (530, 345), (575, 310)), 26, 10),  # tip of the long limb
    ]
    # Aerial roots: thin ones hang from the long limb and the canopy's underside;
    # a few have reached the ground and thickened into pillars.
    hang = [(bez(long_limb, t), drop) for t, drop in ((0.3, 170), (0.42, 300), (0.55, 120), (0.66, 230),
                                                       (0.78, 140), (0.9, 260))]
    hang += [((x, y), drop) for x, y, drop in ((70, 380, 150), (110, 420, 210), (40, 330, 120), (226, 400, 90))]
    roots = "".join(limb(((x, y), (x + 4, y + d / 3), (x - 4, y + 2 * d / 3), (x + 2, y + d)), 6, 2.5)
                    for (x, y), d in hang)
    pillars = [bez(long_limb, 0.48), bez(long_limb, 0.84)]
    roots += "".join(limb(((x, y), (x + 6, y + (1000 - y) / 3), (x - 6, y + 2 * (1000 - y) / 3), (x + 4, 1000)), 8, 18)
                     for x, y in pillars)
    sway.append(shape("root", roots))
    sway.append(shape("bark", "".join(limb(*l) for l in limbs)))
    sway.append(shape("bark-shade", "".join(limb(*l, side="left") for l in limbs[:3])))
    clumps = [   # top clumps first, so the lower ones overlap them
        (-20, 40, 150), (130, -10, 170), (300, 40, 150), (440, 120, 120),
        (-30, 210, 130), (110, 170, 150), (260, 190, 140), (400, 260, 110),
        (530, 300, 85), (40, 330, 105), (180, 330, 115), (310, 340, 95), (600, 360, 55),
    ]
    for i, (cx, cy, r) in enumerate(clumps):
        sway.append(clump("clump-a" if i % 2 else "clump-b", cx, cy, r))

    base = []
    flares = [
        (((150, 905), (110, 930), (60, 950), (0, 985)), 70, 16),
        (((160, 905), (210, 930), (260, 950), (320, 975)), 64, 14),
        (((150, 915), (140, 950), (110, 975), (80, 1000)), 50, 20),
    ]
    base.append(shape("bark", "".join(limb(*l) for l in flares)))
    base.append(shape("ground", "M-80,1000L-80,955C40,915 140,935 240,950C340,962 460,975 660,1000Z"))
    base.append(shape("ground", grass(rng, -60, 610, lambda x: 955 - 30 * math.exp(-((x - 120) / 150) ** 2) + 0.07 * max(0, x - 200))))
    base.append(fireflies(random.Random(3), 7, (200, 560, 560, 890)))
    return 640, sway, base


# ---------- Indian almond (right): flat tiers of big leaves ----------
def almond():
    rng = random.Random(11)
    sway = []
    trunk = ((450, 1010), (446, 760), (430, 420), (410, 60))
    tiers = [(640, 150, 56), (480, 70, 62), (330, 120, 58), (190, 220, 52), (70, 300, 48)]
    branches = []
    for y, reach, _ in tiers:
        tx = 450 - (1010 - y) * 0.04
        branches.append(limb(((tx, y), (tx - 120, y - 10), (reach + 120, y - 40), (reach, y - 60)), 30, 8))
        branches.append(limb(((tx, y), (tx + 50, y - 6), (tx + 100, y - 20), (tx + 160, y - 40)), 24, 8))
    sway.append(shape("bark", limb(trunk, 104, 34) + "".join(branches)))
    sway.append(shape("bark-shade", limb(trunk, 104, 34, side="right")))
    for y, reach, r in tiers:
        tx = 450 - (1010 - y) * 0.04
        # A tier is a row of clumps along its branch: wide and flat.
        for i in range(6):
            x = reach + i * (tx + 170 - reach) / 5
            cy = y - 90 + (i / 5) * 40 - rng.uniform(0, 14)
            sway.append(clump(rng.choice(("clump-a", "clump-b", "clump-c")), x, cy, r * rng.uniform(0.85, 1.12),
                              light=-1, turn=rng.uniform(-14, 14)))

    base = []
    flares = [
        (((440, 930), (400, 950), (360, 970), (320, 1000)), 56, 14),
        (((460, 930), (500, 955), (540, 975), (600, 995)), 50, 14),
    ]
    base.append(shape("bark", "".join(limb(*l) for l in flares)))
    base.append(shape("ground", "M-20,1000C160,975 300,945 420,940C520,936 600,945 700,955L700,1000Z"))
    base.append(shape("ground", grass(rng, 0, 690, lambda x: 945 + 55 * max(0, (380 - x) / 380) ** 1.5)))
    base.append(fireflies(random.Random(5), 6, (60, 560, 400, 890)))
    return 600, sway, base


def svg(cls, width, inner, defs=""):
    return (f'<svg class="{cls}" viewBox="0 0 {width} 1000" preserveAspectRatio="xMidYMax meet" '
            f'focusable="false">{defs}{"".join(inner)}</svg>')


DEFS = ('<defs>' + clump_def("clump-a", 1) + clump_def("clump-b", 2) + clump_def("clump-c", 4)
        + '<radialGradient id="firefly-glow"><stop offset="0" stop-color="#ffe7a0" stop-opacity=".9"/>'
          '<stop offset="1" stop-color="#ffe7a0" stop-opacity="0"/></radialGradient></defs>')

bw, bsway, bbase = banyan()
aw, asway, abase = almond()
OUT.write_text("\n".join([
    "{# The two big trees in front of the valley: a banyan on the left, an Indian",
    "   almond on the right. Made by dev/draw_trees.py: change the script and run",
    "   it again rather than editing here. style.css colours them from the --tree-*",
    "   tokens, sways them with the weather and shows the snow, fireflies and",
    "   falling leaves. #}",
    '<div class="scene-trees" aria-hidden="true">',
    '    <div class="tree tree-banyan">',
    "        " + svg("tree-sway", bw, bsway, DEFS),
    "        " + svg("tree-base", bw, bbase),
    "    </div>",
    '    <div class="tree tree-almond">',
    "        " + svg("tree-sway", aw, asway),
    "        " + svg("tree-base", aw, abase),
    "    </div>",
    '    <div class="falling-leaves">' + "<i></i>" * 7 + "</div>",
    "</div>",
]) + "\n")
print(f"Wrote {OUT}")
