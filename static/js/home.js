// File: static/js/home.js
// The home page's Today section: a word of the day from the saved words (the
// same all day, a new one tomorrow) and every band's week as a ring.

document.addEventListener('DOMContentLoaded', () => {
    const section = document.getElementById('today-home');
    if (!section) return;
    const card = document.getElementById('wotd');
    const image = document.getElementById('wotd-image');
    const wordEl = document.getElementById('wotd-word');
    const ipaEl = document.getElementById('wotd-ipa');
    const definitionEl = document.getElementById('wotd-definition');
    const exampleEl = document.getElementById('wotd-example');
    const reveal = document.getElementById('wotd-reveal');
    const meaningEl = document.getElementById('wotd-meaning');
    const openBtn = document.getElementById('wotd-open');
    const bandList = document.getElementById('glance-bands');

    const RING = 2 * Math.PI * 26;  // the ring's circumference at r = 26
    const SVG = 'http://www.w3.org/2000/svg';

    function svg(tag, attrs) {
        const node = document.createElementNS(SVG, tag);
        Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
        return node;
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    // One band as a ring that fills towards its weekly target.
    function bandRing(band) {
        const share = band.due > 0 ? Math.max(0, Math.min(1, band.points / band.due)) : 0;
        const item = el('li');
        const link = el('a', `glance-band${band.reached ? ' reached' : ''}${band.started ? '' : ' not-started'}`);
        link.href = `/tracking#${band.skill}`;
        const status = !band.started ? 'not started yet' : band.reached ? 'target reached' : `${band.points} of ${band.due} points`;
        link.setAttribute('aria-label', `${band.name}: ${status}`);

        const ring = svg('svg', { viewBox: '0 0 64 64', class: 'glance-ring', 'aria-hidden': 'true' });
        ring.append(svg('circle', { cx: 32, cy: 32, r: 26, class: 'ring-track' }));
        const fill = svg('circle', { cx: 32, cy: 32, r: 26, class: 'ring-fill',
            'stroke-dasharray': RING, 'stroke-dashoffset': RING });
        ring.append(fill);
        const icon = el('i', `fas ${band.icon}`);
        icon.setAttribute('aria-hidden', 'true');
        const middle = el('span', 'glance-icon');
        middle.append(icon);
        const ringBox = el('span', 'glance-ring-box');
        ringBox.append(ring, middle);

        link.append(ringBox, el('span', 'glance-name', band.name),
            el('span', 'glance-score', band.started ? `${band.points} / ${band.due}` : 'Not started'));
        item.append(link);
        // Filled after it is on the page, so the ring sweeps round to its value.
        requestAnimationFrame(() => requestAnimationFrame(() => {
            fill.setAttribute('stroke-dashoffset', RING * (1 - share));
        }));
        return item;
    }

    function showWord(word) {
        if (!word) return;
        wordEl.textContent = word.word;
        ipaEl.textContent = word.pronunciation_ipa && word.pronunciation_ipa !== 'N/A' ? word.pronunciation_ipa : '';
        definitionEl.textContent = word.english_definition || '';
        if (word.example) {
            exampleEl.textContent = word.example;
            exampleEl.classList.remove('hidden');
        }
        meaningEl.textContent = word.vietnamese_meaning || '';
        if (word.image_url) {
            image.src = word.image_url;
            image.classList.remove('hidden');
        }
        card.classList.remove('hidden');
    }

    reveal.addEventListener('click', () => {
        const open = meaningEl.classList.toggle('hidden') === false;
        reveal.setAttribute('aria-expanded', String(open));
        reveal.lastChild.textContent = open ? ' Hide the Vietnamese' : ' Show the Vietnamese';
    });

    // Opens the full word card by searching for the word, as typing it would.
    openBtn.addEventListener('click', () => {
        const input = document.getElementById('word-input');
        const form = document.getElementById('search-form');
        input.value = wordEl.textContent;
        form.requestSubmit();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    (async () => {
        try {
            const response = await fetch(`/api/today?utc_offset=${-new Date().getTimezoneOffset()}`);
            if (!response.ok) return;
            const data = await response.json();
            showWord(data.word);
            bandList.replaceChildren(...data.bands.map(bandRing));
            section.classList.remove('hidden');
        } catch (error) { /* the page works without its Today section */ }
    })();
});
