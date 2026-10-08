// File: static/js/glosses.js
// Point at a word chip (Similar, Family) and a small box shows its English
// definition. The definitions come from /api/glosses (myvocab/glosses.py):
// the learner's own words first, then Wiktionary. They are asked for once per
// word card, so the box usually opens at once. It also opens on keyboard focus,
// and with a long press on a touch screen, because a tap stays free for other uses.
// Use: MyVocabGlosses.prepare(['word', ...]) when the chips are drawn, and give
// each chip data-gloss="word".

(() => {
    const SHOW_AFTER = 120;   // ms of pointing before the box opens
    const LONG_PRESS = 450;   // ms of holding on a touch screen
    const known = new Map();  // word -> definition, or null when none was found
    const waiting = new Map(); // word -> the request that will answer it

    const tip = document.createElement('div');
    tip.id = 'gloss-tip';
    tip.className = 'gloss-tip';
    tip.setAttribute('role', 'tooltip');
    tip.hidden = true;
    const head = document.createElement('p');
    head.className = 'gloss-head';
    const wordEl = document.createElement('span');
    wordEl.className = 'gloss-word';
    const posEl = document.createElement('span');
    posEl.className = 'gloss-pos';
    head.append(wordEl, posEl);
    const defEl = document.createElement('p');
    defEl.className = 'gloss-def';
    const srcEl = document.createElement('p');
    srcEl.className = 'gloss-src';
    tip.append(head, defEl, srcEl);

    let anchor = null;
    let showTimer = 0;
    let pressTimer = 0;

    function prepare(words) {
        const wanted = [...new Set((words || []).map(w => String(w).trim().toLowerCase()))]
            .filter(w => w && !known.has(w) && !waiting.has(w));
        if (!wanted.length) return;
        const request = fetch('/api/glosses', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ words: wanted }),
        })
            .then(r => (r.ok ? r.json() : { glosses: {} }))
            .catch(() => ({ glosses: {} }))
            .then(data => {
                // A word the server left out (it only looks up plain words) has no meaning to
                // show; remember that, so pointing at it does not ask again and again.
                const answered = data.glosses || {};
                wanted.forEach(w => {
                    known.set(w, w in answered ? answered[w] : null);
                    waiting.delete(w);
                });
                if (anchor) fill(anchor);
            });
        wanted.forEach(w => waiting.set(w, request));
    }

    function fill(chip) {
        const word = chip.dataset.gloss;
        const key = word.toLowerCase();
        wordEl.textContent = word;
        const gloss = known.get(key);
        posEl.textContent = gloss && gloss.part_of_speech ? gloss.part_of_speech : '';
        srcEl.textContent = gloss ? (gloss.source === 'your words' ? 'From your saved words' : `From ${gloss.source}`) : '';
        if (gloss) {
            defEl.textContent = gloss.definition;
            tip.classList.remove('gloss-empty');
        } else {
            defEl.textContent = waiting.has(key) || !known.has(key) ? 'Looking it up …' : 'No short definition found for this word.';
            tip.classList.add('gloss-empty');
            if (!known.has(key) && !waiting.has(key)) prepare([word]);
        }
        place(chip);
    }

    // Above the chip, centred on it and kept on screen; below it when there is no room above.
    function place(chip) {
        const r = chip.getBoundingClientRect();
        const box = tip.getBoundingClientRect();
        const margin = 8;
        let left = r.left + r.width / 2 - box.width / 2;
        left = Math.max(margin, Math.min(left, window.innerWidth - box.width - margin));
        const above = r.top - box.height - 10;
        const below = above < margin;
        tip.style.left = `${Math.round(left)}px`;
        tip.style.top = `${Math.round(below ? r.bottom + 10 : above)}px`;
        tip.classList.toggle('below', below);
        tip.style.setProperty('--arrow', `${Math.round(r.left + r.width / 2 - left)}px`);
    }

    function show(chip) {
        clearTimeout(showTimer);
        if (!tip.isConnected) document.body.append(tip);
        anchor = chip;
        chip.setAttribute('aria-describedby', 'gloss-tip');
        tip.hidden = false;
        fill(chip);
        tip.classList.remove('shown');
        requestAnimationFrame(() => tip.classList.add('shown'));
    }

    function hide() {
        clearTimeout(showTimer);
        clearTimeout(pressTimer);
        if (anchor) anchor.removeAttribute('aria-describedby');
        anchor = null;
        tip.hidden = true;
        tip.classList.remove('shown');
    }

    const chipOf = target => (target instanceof Element ? target.closest('[data-gloss]') : null);

    document.addEventListener('pointerover', (e) => {
        const chip = chipOf(e.target);
        if (!chip || e.pointerType === 'touch' || chip === anchor) return;
        clearTimeout(showTimer);
        showTimer = setTimeout(() => show(chip), SHOW_AFTER);
    });
    document.addEventListener('pointerout', (e) => {
        const chip = chipOf(e.target);
        if (!chip || e.pointerType === 'touch' || chip.contains(e.relatedTarget)) return;
        hide();
    });
    document.addEventListener('focusin', (e) => {
        const chip = chipOf(e.target);
        if (chip) show(chip);
    });
    document.addEventListener('focusout', (e) => {
        if (chipOf(e.target)) hide();
    });
    // Touch: hold a chip to see its meaning; touching anywhere else closes it.
    document.addEventListener('pointerdown', (e) => {
        if (e.pointerType !== 'touch') return;
        const chip = chipOf(e.target);
        clearTimeout(pressTimer);
        if (!chip) {
            if (anchor) hide();
            return;
        }
        pressTimer = setTimeout(() => show(chip), LONG_PRESS);
    });
    ['pointerup', 'pointercancel'].forEach(type => document.addEventListener(type, () => clearTimeout(pressTimer)));
    document.addEventListener('contextmenu', (e) => {
        if (chipOf(e.target) && anchor) e.preventDefault();  // the long press shows the meaning, not a menu
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && anchor) hide();
    });
    window.addEventListener('scroll', () => anchor && place(anchor), { passive: true });
    window.addEventListener('resize', () => anchor && place(anchor));

    window.MyVocabGlosses = { prepare, hide };
})();
