// File: static/fx.js
// Small celebrations and motion shared by every page: confetti, a floating
// "+18" beside what earned it, an achievement card, and numbers that count up
// to their new value. Pages call window.MyVocabFx; everything here is skipped
// (the card simply appears) for people whose system asks for reduced motion.

(function () {
    const motionOff = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // --- CONFETTI: one canvas over the page, drawn only while pieces are falling ---
    let canvas = null;
    let ctx = null;
    let pieces = [];
    let frame = 0;

    function palette() {
        const css = getComputedStyle(document.documentElement);
        const token = name => css.getPropertyValue(name).trim();
        return [token('--accent'), token('--tree-leaf-lit'), '#f6c177', '#ef7d57', '#5aa9e6', '#f2d16b', '#b388eb']
            .filter(Boolean);
    }

    function ensureCanvas() {
        if (canvas) return;
        canvas = document.createElement('canvas');
        canvas.className = 'fx-confetti';
        canvas.setAttribute('aria-hidden', 'true');
        document.body.append(canvas);
        ctx = canvas.getContext('2d');
        const size = () => {
            const ratio = Math.min(window.devicePixelRatio || 1, 2);
            canvas.width = innerWidth * ratio;
            canvas.height = innerHeight * ratio;
            ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        };
        size();
        window.addEventListener('resize', size);
    }

    function step() {
        ctx.clearRect(0, 0, innerWidth, innerHeight);
        pieces = pieces.filter(p => p.life > 0 && p.y < innerHeight + 40);
        for (const p of pieces) {
            p.vx *= 0.985;
            p.vy = p.vy * 0.985 + 0.32;    // drag, then gravity
            p.x += p.vx + Math.sin(p.wobble += 0.12) * 0.6;
            p.y += p.vy;
            p.spin += p.turn;
            p.life -= 1;
            ctx.save();
            ctx.globalAlpha = Math.min(1, p.life / 40);
            ctx.translate(p.x, p.y);
            ctx.rotate(p.spin);
            ctx.scale(1, Math.cos(p.spin * 1.7));  // a flat piece flipping over
            ctx.fillStyle = p.colour;
            if (p.round) {
                ctx.beginPath();
                ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
                ctx.fill();
            } else {
                ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
            }
            ctx.restore();
        }
        if (pieces.length) {
            frame = requestAnimationFrame(step);
        } else {
            frame = 0;
            ctx.clearRect(0, 0, innerWidth, innerHeight);
        }
    }

    // x, y: where the burst starts; spread: degrees either side of straight up.
    function confetti({ x = innerWidth / 2, y = innerHeight * 0.35, count = 140, spread = 75, power = 13 } = {}) {
        if (motionOff()) return;
        ensureCanvas();
        const colours = palette();
        for (let i = 0; i < count; i++) {
            const angle = (-90 + (Math.random() * 2 - 1) * spread) * Math.PI / 180;
            const speed = power * (0.45 + Math.random() * 0.75);
            pieces.push({
                x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
                size: 6 + Math.random() * 7, colour: colours[i % colours.length], round: Math.random() < 0.3,
                spin: Math.random() * Math.PI, turn: (Math.random() - 0.5) * 0.3,
                wobble: Math.random() * 6, life: 150 + Math.random() * 60,
            });
        }
        if (!frame) frame = requestAnimationFrame(step);
    }

    // A small burst from an element, for a right answer or points won.
    function burstFrom(el, count = 26) {
        if (!el) return;
        const r = el.getBoundingClientRect();
        confetti({ x: r.left + r.width / 2, y: r.top + r.height / 2, count, spread: 55, power: 8 });
    }

    // Both sides of the screen at once, for the biggest moments.
    function cannons() {
        confetti({ x: 0, y: innerHeight * 0.75, count: 90, spread: 35, power: 17 });
        confetti({ x: innerWidth, y: innerHeight * 0.75, count: 90, spread: 35, power: 17 });
        setTimeout(() => confetti({ count: 80, power: 11 }), 250);
    }

    // --- FLOATING TEXT: "+18" rising from what earned it ---
    function floatText(el, text, kind = 'gain') {
        if (!el || motionOff()) return;
        const r = el.getBoundingClientRect();
        const tag = document.createElement('span');
        tag.className = `fx-float ${kind}`;
        tag.textContent = text;
        tag.setAttribute('aria-hidden', 'true');
        tag.style.left = `${r.left + r.width / 2}px`;
        tag.style.top = `${r.top}px`;
        document.body.append(tag);
        tag.addEventListener('animationend', () => tag.remove());
    }

    // --- ACHIEVEMENT CARD: a short, friendly note that slides in and out ---
    let stack = null;
    function celebrate(title, detail = '', icon = 'fa-trophy') {
        if (!stack) {
            stack = document.createElement('div');
            stack.className = 'fx-achievements';
            stack.setAttribute('role', 'status');
            stack.setAttribute('aria-live', 'polite');
            document.body.append(stack);
        }
        const card = document.createElement('div');
        card.className = 'fx-achievement';
        const badge = document.createElement('span');
        badge.className = 'fx-achievement-icon';
        const i = document.createElement('i');
        i.className = `fas ${icon}`;
        i.setAttribute('aria-hidden', 'true');
        badge.append(i);
        const words = document.createElement('div');
        const strong = document.createElement('strong');
        strong.textContent = title;
        words.append(strong);
        if (detail) {
            const small = document.createElement('span');
            small.textContent = detail;
            words.append(small);
        }
        card.append(badge, words);
        stack.append(card);
        setTimeout(() => {
            card.classList.add('leaving');
            setTimeout(() => card.remove(), motionOff() ? 0 : 400);
        }, 4800);
    }

    // --- COUNTING UP: a number rolls from its old value to the new one ---
    function countTo(el, to, duration = 650) {
        if (!el) return;
        const from = Number.parseInt(el.textContent, 10);
        cancelAnimationFrame(el.fxCount || 0);
        if (motionOff() || !Number.isFinite(from) || from === to) {
            el.textContent = to;
            return;
        }
        const start = performance.now();
        const tick = (now) => {
            const t = Math.min(1, (now - start) / duration);
            const eased = 1 - (1 - t) ** 3;
            el.textContent = Math.round(from + (to - from) * eased);
            if (t < 1) el.fxCount = requestAnimationFrame(tick);
        };
        el.fxCount = requestAnimationFrame(tick);
    }

    // Restarts a CSS animation class on an element (a pop or a shake).
    function replay(el, className) {
        if (!el) return;
        el.classList.remove(className);
        void el.offsetWidth;
        el.classList.add(className);
        el.addEventListener('animationend', () => el.classList.remove(className), { once: true });
    }

    window.MyVocabFx = { confetti, burstFrom, cannons, floatText, celebrate, countTo, replay, motionOff };
})();
