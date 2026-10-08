// File: static/js/listening.js
// Listening practice: pick a BBC 6 Minute English episode, watch it in the
// BBC's YouTube player, then enter your score on its BBC quiz or worksheet.
// The first score of each episode becomes listening points (listening.py).
// Each episode can also keep the learner's own files (worksheet, transcript,
// audio), shown next to the video: see section 5.

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
    const docsBox = document.getElementById('episode-docs');
    const docsList = document.getElementById('docs-list');
    const docsInput = document.getElementById('docs-input');
    const docsAdd = document.getElementById('docs-add');
    const docsStatus = document.getElementById('docs-status');
    const docsViewer = document.getElementById('docs-viewer');

    const PER_ANSWER = Number(form.dataset.pointsPerAnswer);
    const WRONG_LOSES = Number(form.dataset.wrongLoses);
    const DEFAULT_TOTAL = 6;  // most 6 Minute English quizzes

    let episodes = [];
    let current = null;
    let filter = 'all';
    let docs = {};          // episode id -> its files
    let docsLocked = false; // online, before the My Words password
    let maxDocBytes = 20 * 1024 * 1024;

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
        const files = (docs[episode.id] || []).length;
        if (files) {
            const clip = el('span', 'episode-docs-count');
            clip.title = `${files} file${files === 1 ? '' : 's'} kept`;
            clip.append(el('i', 'fas fa-paperclip'), ` ${files}`);
            meta.append(clip);
        }

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

        // The episode's picture with a play button. The BBC's own YouTube player (about
        // 5 MB, and busy even when still) is only loaded when it is pressed.
        const cover = el('button', 'video-cover');
        cover.type = 'button';
        cover.setAttribute('aria-label', `Play: ${episode.title}`);
        const poster = el('img');
        poster.src = `https://i.ytimg.com/vi/${episode.id}/hqdefault.jpg`;
        poster.alt = '';
        const play = el('span', 'video-play');
        play.append(el('i', 'fas fa-play'));
        cover.append(poster, play);
        cover.addEventListener('click', () => {
            const frame = el('iframe');
            frame.src = `https://www.youtube-nocookie.com/embed/${episode.id}?rel=0&hl=en&cc_lang_pref=en&autoplay=1`;
            frame.title = `${episode.title} (video)`;
            frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen';
            frame.allowFullscreen = true;
            frame.referrerPolicy = 'strict-origin-when-cross-origin';
            frameBox.replaceChildren(frame);
            frame.focus();
        });
        frameBox.replaceChildren(cover);

        renderDocs();
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

    // --- 5. THE EPISODE'S FILES ---

    const ICONS = {
        'application/pdf': 'fa-file-pdf', 'text/plain': 'fa-file-alt', 'audio/mpeg': 'fa-file-audio',
        'image/png': 'fa-file-image', 'image/jpeg': 'fa-file-image', 'image/webp': 'fa-file-image',
    };
    const kind = doc => doc.content_type.split(';')[0];
    const shownInPage = doc => kind(doc) in ICONS;  // Word files are downloaded instead

    function sizeText(bytes) {
        return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    function docsMessage(text, tone) {
        docsStatus.textContent = text;
        docsStatus.className = `docs-status${tone ? ' ' + tone : ''}`;
    }

    function closeViewer() {
        docsViewer.replaceChildren();
        show(docsViewer, false);
        docsList.querySelectorAll('[data-open]').forEach(b => b.setAttribute('aria-expanded', 'false'));
    }

    function openViewer(doc, button) {
        const wasOpen = button.getAttribute('aria-expanded') === 'true';
        closeViewer();
        if (wasOpen) return;
        const url = `/api/listening/docs/${doc.id}`;
        let view;
        if (kind(doc) === 'audio/mpeg') {
            view = el('audio');
            view.controls = true;
            view.src = url;
        } else if (kind(doc).startsWith('image/')) {
            view = el('img');
            view.src = url;
            view.alt = doc.filename;
        } else {
            view = el('iframe');
            view.src = url;
            view.title = doc.filename;
        }
        docsViewer.replaceChildren(view);
        show(docsViewer, true);
        button.setAttribute('aria-expanded', 'true');
    }

    function renderDocs() {
        if (!current) return;
        closeViewer();
        if (docsLocked) {
            docsList.replaceChildren();
            docsAdd.disabled = true;
            docsStatus.replaceChildren('Your files are private. ');
            const link = el('a', '', 'Unlock My Words');
            link.href = '/?unlock=1';
            docsStatus.append(link, ' to see and add them.');
            return;
        }
        docsAdd.disabled = false;
        const files = docs[current.id] || [];
        docsList.replaceChildren(...files.map(doc => {
            const li = el('li', 'doc-item');
            const icon = el('i', `fas ${ICONS[kind(doc)] || 'fa-file-word'} doc-icon`);
            icon.setAttribute('aria-hidden', 'true');
            const name = el('span', 'doc-name', doc.filename);
            const meta = el('span', 'doc-meta', `${sizeText(doc.size)} · added ${new Date(doc.uploaded_at).toLocaleDateString()}`);
            const actions = el('span', 'doc-actions');
            if (shownInPage(doc)) {
                const open = el('button', 'doc-open', kind(doc) === 'audio/mpeg' ? 'Play' : 'Open');
                open.type = 'button';
                open.dataset.open = doc.id;
                open.setAttribute('aria-expanded', 'false');
                open.addEventListener('click', () => openViewer(doc, open));
                actions.append(open);
            }
            const download = el('a', 'doc-download', 'Download');
            download.href = `/api/listening/docs/${doc.id}?download=1`;
            const remove = el('button', 'doc-delete');
            remove.type = 'button';
            remove.setAttribute('aria-label', `Delete ${doc.filename}`);
            remove.dataset.delete = doc.id;
            remove.append(el('i', 'fas fa-trash-alt'));
            remove.addEventListener('click', () => deleteDoc(doc));
            actions.append(download, remove);
            const text = el('span', 'doc-text');
            text.append(name, meta);
            li.append(icon, text, actions);
            return li;
        }));
        if (!docsStatus.classList.contains('gain') && !docsStatus.classList.contains('loss')) docsMessage('');
    }

    async function loadDocs() {
        try {
            const data = await goals.requestJSON('/api/listening/docs');
            docs = data.docs;
            maxDocBytes = data.max_bytes || maxDocBytes;
            docsLocked = false;
        } catch (error) {
            docs = {};
            docsLocked = Boolean(error.data && error.data.locked);
            if (!docsLocked) docsMessage('Could not load your files.', 'loss');
        }
    }

    async function uploadFiles(fileList) {
        if (!current || docsLocked) return;
        const files = Array.from(fileList);
        if (!files.length) return;
        const episodeId = current.id;
        const problems = [];
        let added = 0;
        docsAdd.disabled = true;
        for (const [i, file] of files.entries()) {
            docsMessage(files.length > 1 ? `Adding ${i + 1} of ${files.length}: ${file.name} …` : `Adding ${file.name} …`);
            if (file.size > maxDocBytes) {
                problems.push(`${file.name}: over ${Math.round(maxDocBytes / 1024 / 1024)} MB.`);
                continue;
            }
            const form = new FormData();
            form.append('episode_id', episodeId);
            form.append('file', file);
            try {
                const response = await fetch('/api/listening/docs', { method: 'POST', body: form });
                const body = await response.json().catch(() => ({}));
                if (response.ok) added += 1;
                else problems.push(`${file.name}: ${body.error || (response.status === 413 ? 'too big to send.' : `the server answered ${response.status}.`)}`);
            } catch (error) {
                problems.push(`${file.name}: MyVocab is not answering.`);
            }
        }
        await loadDocs();
        renderGrid();
        if (current && current.id === episodeId) renderDocs();
        docsAdd.disabled = docsLocked;
        const done = added ? `Added ${added} file${added === 1 ? '' : 's'}.` : '';
        docsMessage([done, ...problems].filter(Boolean).join('\n'), problems.length ? 'loss' : 'gain');  // one line each
        docsInput.value = '';
    }

    async function deleteDoc(doc) {
        if (!confirm(`Delete "${doc.filename}" from this episode?`)) return;
        try {
            const response = await fetch(`/api/listening/docs/${doc.id}`, { method: 'DELETE' });
            if (!response.ok) throw new Error();
            docsMessage(`Deleted ${doc.filename}.`, 'gain');
        } catch (error) {
            docsMessage(`Could not delete ${doc.filename}.`, 'loss');
        }
        await loadDocs();
        renderGrid();
        renderDocs();
    }

    docsAdd.addEventListener('click', () => docsInput.click());
    docsInput.addEventListener('change', () => uploadFiles(docsInput.files));
    // Files can also be dropped anywhere on the box.
    ['dragenter', 'dragover'].forEach(type => docsBox.addEventListener(type, (e) => {
        if (docsLocked || !e.dataTransfer || !Array.from(e.dataTransfer.types).includes('Files')) return;
        e.preventDefault();
        docsBox.classList.add('dropping');
    }));
    ['dragleave', 'drop'].forEach(type => docsBox.addEventListener(type, (e) => {
        if (type === 'dragleave' && docsBox.contains(e.relatedTarget)) return;
        docsBox.classList.remove('dropping');
    }));
    docsBox.addEventListener('drop', (e) => {
        if (docsLocked || !e.dataTransfer || !e.dataTransfer.files.length) return;
        e.preventDefault();
        uploadFiles(e.dataTransfer.files);
    });

    // --- 6. LOADING ---

    async function loadEpisodes() {
        const data = await goals.requestJSON('/api/listening/episodes');
        episodes = data.episodes;
        renderGrid();
    }

    async function start() {
        try {
            await loadDocs();
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
