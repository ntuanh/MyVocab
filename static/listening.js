// File: static/listening.js
// Listening practice: pick a BBC 6 Minute English episode, watch it in the
// BBC's YouTube player, then enter your score on its BBC quiz or worksheet.
// The first score of each episode becomes listening points (listening.py).

document.addEventListener('DOMContentLoaded', () => {
    const goals = window.MyVocabGoals;
    const listeningGoal = goals.panel(document.querySelector('.goal-panel[data-skill="listening"]'));

    // --- 1. ELEMENTS ---
    const titleEl = document.getElementById('episode-title');
    const metaEl = document.getElementById('episode-meta');
    const frameBox = document.getElementById('video-frame');
    const youtubeLink = document.getElementById('episode-youtube');
    const form = document.getElementById('score-form');
    const correctInput = document.getElementById('score-correct');
    const totalInput = document.getElementById('score-total');
    const saveBtn = document.getElementById('score-save');
    const preview = document.getElementById('score-preview');
    const resultEl = document.getElementById('score-result');
    const historyEl = document.getElementById('score-history');
    const grid = document.getElementById('episode-grid');
    const emptyEl = document.getElementById('library-empty');
    const filterBtns = Array.from(document.querySelectorAll('[data-filter]'));
    const topicSelect = document.getElementById('topic-filter');

    const PER_ANSWER = Number(form.dataset.pointsPerAnswer);
    const WRONG_LOSES = Number(form.dataset.wrongLoses);
    const DEFAULT_TOTAL = 6;  // most 6 Minute English quizzes

    let episodes = [];
    let current = null;
    let filter = 'all';

    // --- 2. HELPERS ---

    function show(el, visible) {
        el.classList.toggle('hidden', !visible);
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function pointsText(n) {
        const sign = n > 0 ? '+' : n < 0 ? '−' : '';
        return `${sign}${Math.abs(n)} point${Math.abs(n) === 1 ? '' : 's'}`;
    }

    function scorePoints(correct, total) {
        return correct * PER_ANSWER - (total - correct) * WRONG_LOSES;
    }

    function isDone(episode) {
        return Boolean(episode.scores);
    }

    // --- 3. THE LIBRARY ---

    function visible() {
        return episodes.filter(ep => (filter === 'all' || (filter === 'done') === isDone(ep))
            && (!topicSelect.value || ep.topic === topicSelect.value));
    }

    function renderCounts() {
        const done = episodes.filter(isDone).length;
        const counts = { all: episodes.length, todo: episodes.length - done, done };
        document.querySelectorAll('[data-count]').forEach(span => { span.textContent = counts[span.dataset.count]; });
    }

    function card(episode, index) {
        const item = el('li');
        const button = el('button', 'episode-card');
        button.type = 'button';
        button.dataset.id = episode.id;
        if (current && current.id === episode.id) button.setAttribute('aria-current', 'true');

        const thumb = el('span', 'episode-thumb');
        const img = el('img');
        img.src = `https://i.ytimg.com/vi/${episode.id}/mqdefault.jpg`;
        img.alt = '';
        img.loading = 'lazy';
        thumb.append(img, el('span', 'episode-duration', episode.duration));

        const status = isDone(episode)
            ? el('span', 'episode-status done', `✓ ${episode.scores.first.correct}/${episode.scores.first.total}`)
            : el('span', 'episode-status', 'To do');
        const meta = el('span', 'episode-card-meta');
        meta.append(el('span', '', episode.topic), status);

        button.append(thumb, el('span', 'episode-card-title', episode.title), meta);
        button.style.setProperty('--i', Math.min(index, 20));  // cards appear one after another
        button.addEventListener('click', () => choose(episode.id, true));
        item.append(button);
        return item;
    }

    function renderGrid() {
        const list = visible();
        grid.replaceChildren(...list.map((episode, i) => card(episode, i)));
        show(emptyEl, list.length === 0);
        renderCounts();
    }

    filterBtns.forEach(btn => btn.addEventListener('click', () => {
        filter = btn.dataset.filter;
        filterBtns.forEach(b => b.setAttribute('aria-pressed', String(b === btn)));
        renderGrid();
    }));
    topicSelect.addEventListener('change', renderGrid);

    // --- 4. THE CHOSEN EPISODE ---

    function renderHistory() {
        const scores = current.scores;
        if (!scores) {
            show(historyEl, false);
            return;
        }
        const tries = scores.tries === 1 ? '1 try' : `${scores.tries} tries`;
        historyEl.textContent = `First score ${scores.first.correct}/${scores.first.total} `
            + `(${pointsText(scores.first.points)}) · best ${scores.best.correct}/${scores.best.total} · ${tries}. `
            + 'New scores for this episode are kept as practice and earn no points.';
        show(historyEl, true);
    }

    function updatePreview() {
        const correct = Number(correctInput.value);
        const total = Number(totalInput.value);
        const filled = correctInput.value !== '' && totalInput.value !== '';
        if (!filled || !Number.isInteger(correct) || !Number.isInteger(total) || total < 1 || correct < 0 || correct > total) {
            preview.textContent = '';
            return;
        }
        preview.textContent = isDone(current)
            ? `${correct}/${total}: practice only, no points.`
            : `${correct}/${total} is worth ${pointsText(scorePoints(correct, total))}.`;
    }

    function choose(id, scroll) {
        const episode = episodes.find(ep => ep.id === id);
        if (!episode) return;
        current = episode;
        titleEl.textContent = episode.title;
        metaEl.textContent = `${episode.duration} · ${episode.topic} · BBC Learning English`;
        youtubeLink.href = `https://www.youtube.com/watch?v=${episode.id}`;

        // The BBC's own player, without cookies until it is played.
        const frame = el('iframe');
        frame.src = `https://www.youtube-nocookie.com/embed/${episode.id}?rel=0&hl=en&cc_lang_pref=en`;
        frame.title = `${episode.title} (video)`;
        frame.allow = 'accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen';
        frame.allowFullscreen = true;
        frame.referrerPolicy = 'strict-origin-when-cross-origin';
        frameBox.replaceChildren(frame);

        correctInput.value = '';
        totalInput.value = DEFAULT_TOTAL;
        show(resultEl, false);
        renderHistory();
        updatePreview();
        grid.querySelectorAll('.episode-card').forEach(b => {
            if (b.dataset.id === id) b.setAttribute('aria-current', 'true');
            else b.removeAttribute('aria-current');
        });
        try {
            history.replaceState(null, '', `#${id}`);
        } catch (error) { /* the address keeps its old episode */ }
        if (scroll) document.getElementById('episode-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    correctInput.addEventListener('input', updatePreview);
    totalInput.addEventListener('input', updatePreview);

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!current) return;
        saveBtn.disabled = true;
        try {
            const body = await goals.requestJSON('/api/listening/score', {
                episode_id: current.id, correct: correctInput.value, total: totalInput.value,
                utc_offset: goals.utcOffset(),
            });
            resultEl.textContent = body.counted
                ? `Saved: ${body.correct}/${body.total}, ${pointsText(body.points)} for your listening score.`
                : `Saved as practice: ${body.correct}/${body.total}. Only your first score for an episode earns points.`;
            resultEl.className = `score-result ${body.counted && body.points > 0 ? 'gain' : body.counted && body.points < 0 ? 'loss' : ''}`;
            const fx = window.MyVocabFx;
            if (fx && body.counted) {
                fx.floatText(saveBtn, pointsText(body.points).replace(/ points?$/, ''), body.points >= 0 ? 'gain' : 'loss');
                if (body.correct === body.total) {
                    fx.cannons();
                    fx.celebrate('Perfect score!', `${body.correct}/${body.total}: ${current.title}`, 'fa-headphones');
                } else if (body.points > 0) {
                    fx.burstFrom(saveBtn, 24);
                }
            }
            listeningGoal.render(body.progress);
            await loadEpisodes();
            current = episodes.find(ep => ep.id === current.id);
            renderHistory();
            updatePreview();
        } catch (error) {
            resultEl.textContent = error.message;
            resultEl.className = 'score-result loss';
        } finally {
            saveBtn.disabled = false;
        }
    });

    // --- 5. LOADING ---

    async function loadEpisodes() {
        const data = await goals.requestJSON('/api/listening/episodes');
        episodes = data.episodes;
        renderGrid();
    }

    async function start() {
        try {
            await loadEpisodes();
        } catch (error) {
            titleEl.textContent = 'Could not load the episodes.';
            return;
        }
        const topics = [...new Set(episodes.map(ep => ep.topic))].sort();
        topicSelect.append(...topics.map(t => { const o = el('option', '', t); o.value = t; return o; }));
        // The address can name an episode (/listening#ID); otherwise the newest one still to do.
        const wanted = decodeURIComponent(location.hash.slice(1));
        const first = episodes.find(ep => ep.id === wanted) || episodes.find(ep => !isDone(ep)) || episodes[0];
        choose(first.id, false);
    }

    // The address names the open episode (/listening#ID), also when it is
    // changed by hand or by the Back button on this page.
    window.addEventListener('hashchange', () => {
        const id = decodeURIComponent(location.hash.slice(1));
        if (!current || id !== current.id) choose(id, false);
    });

    listeningGoal.load();
    start();
});
