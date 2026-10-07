// File: static/js/writing.js
// Writing practice: choose a diary, IELTS Task 1 or Task 2; write; then AI
// marks it like a teacher (writing.py): four criteria out of 20, 80 in all,
// with corrections, better words and an improved version. Drafts are kept in
// this browser until the piece is marked.

document.addEventListener('DOMContentLoaded', () => {
    const goals = window.MyVocabGoals;
    const writingGoal = goals.panel(document.querySelector('.goal-panel[data-skill="writing"]'));

    // --- 1. ELEMENTS ---
    const kindInputs = Array.from(document.querySelectorAll('input[name="kind"]'));
    const taskKicker = document.getElementById('task-kicker');
    const taskTitle = document.getElementById('task-title');
    const taskInstructions = document.getElementById('task-instructions');
    const taskChart = document.getElementById('task-chart');
    const wordsBox = document.getElementById('words-to-try');
    const wordsList = document.getElementById('words-to-try-list');
    const taskNote = document.getElementById('task-note');
    const anotherBtn = document.getElementById('task-another');

    const editorPanel = document.getElementById('editor-panel');
    const textArea = document.getElementById('writing-text');
    const timerBox = document.getElementById('writing-timer');
    const revisingNote = document.getElementById('revising-note');
    const meterFill = document.getElementById('word-meter-fill');
    const wordCount = document.getElementById('word-count');
    const checkBtn = document.getElementById('check-writing');
    const errorEl = document.getElementById('writing-error');

    const markingPanel = document.getElementById('marking-panel');
    const markingStep = document.getElementById('marking-step');
    const resultPanel = document.getElementById('result-panel');
    const historyNote = document.getElementById('history-note');
    const historyList = document.getElementById('history-list');

    const KIND_KEY = 'myvocab-writing-kind';
    const ICONS = { diary: 'fa-book', task1: 'fa-chart-bar', task2: 'fa-feather-alt' };
    const NAMES = { diary: 'Diary', task1: 'Task 1', task2: 'Task 2' };
    const STEPS = ['Checking grammar', 'Looking at your vocabulary', 'Following your ideas',
        'Counting linking words', 'Writing your feedback', 'Almost done'];

    let task = null;          // what the API gave for the current kind
    let revisingOf = null;    // the id of the piece being revised, if any
    let startedAt = 0;        // when typing began, for the IELTS timer
    let timer = 0;

    // --- 2. HELPERS ---

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function show(node, visible) {
        node.classList.toggle('hidden', !visible);
    }

    function kind() {
        return (kindInputs.find(i => i.checked) || kindInputs[0]).value;
    }

    function store(key, value) {
        try {
            if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value);
        } catch (error) { /* not kept */ }
    }

    function stored(key) {
        try {
            return localStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function draftKey() {
        return task ? `myvocab-writing-draft-${task.kind}-${task.id}` : null;
    }

    function countWords(text) {
        return (text.match(/[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*/g) || []).length;
    }

    function dateText(iso) {
        return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    // --- 3. THE TASK ---

    function renderTask() {
        const info = task.info;
        show(taskChart, false);
        show(wordsBox, false);
        show(taskNote, false);
        show(taskInstructions, false);
        if (task.kind === 'diary') {
            taskKicker.textContent = "Today's idea (optional)";
            taskTitle.textContent = task.idea;
            anotherBtn.querySelector('span').textContent = 'Another idea';
            if (task.words_to_try.length) {
                wordsList.replaceChildren(...task.words_to_try.map(w => {
                    const li = el('li');
                    li.append(el('strong', '', w.word));
                    if (w.vietnamese_meaning) li.append(el('span', '', w.vietnamese_meaning));
                    li.dataset.word = w.word;
                    return li;
                }));
                show(wordsBox, true);
            }
            if (task.done_today) {
                taskNote.textContent = "Today's diary already earned its points. You can still write more for practice.";
                show(taskNote, true);
            }
        } else {
            taskKicker.textContent = `${info.name}${task.type ? ` · ${task.type}` : ''} · ${task.done_count} of ${task.total} done`;
            taskTitle.textContent = task.prompt;
            taskInstructions.textContent = task.instructions;
            show(taskInstructions, true);
            anotherBtn.querySelector('span').textContent = 'Another question';
            if (task.chart) {
                show(taskChart, true);  // shown first, so the chart knows its width
                window.MyVocabCharts.render(taskChart, task.chart);
            }
            if (task.best !== null && task.best !== undefined) {
                taskNote.textContent = `You have written this one before (best ${task.best}/80). A new answer is for practice.`;
                show(taskNote, true);
            }
        }
        textArea.placeholder = task.kind === 'diary' ? 'Dear diary, today...' : 'Start writing your answer here...';
        restoreDraft();
    }

    async function loadTask(after) {
        taskTitle.textContent = 'Loading...';
        try {
            const params = new URLSearchParams({ kind: kind(), utc_offset: goals.utcOffset() });
            if (after) params.set('after', after);
            task = await goals.requestJSON(`/api/writing/prompt?${params}`);
            renderTask();
        } catch (error) {
            taskTitle.textContent = error.message;
        }
    }

    kindInputs.forEach(input => input.addEventListener('change', () => {
        store(KIND_KEY, kind());
        stopRevising();
        loadTask();
    }));
    anotherBtn.addEventListener('click', () => {
        stopRevising();
        loadTask(task ? (task.kind === 'diary' ? 'diary' : task.id) : null);
    });

    // --- 4. THE PAGE TO WRITE ON ---

    function updateCount() {
        const words = countWords(textArea.value);
        const target = task ? task.info.words : 100;
        const min = task ? task.info.min_words : 40;
        wordCount.textContent = words < min
            ? `${words} words · write at least ${min} to have it marked (about ${target} is ideal)`
            : words < target ? `${words} words · about ${target} is ideal` : `${words} words ✓`;
        meterFill.style.width = `${Math.min(100, (words / target) * 100)}%`;
        meterFill.parentElement.classList.toggle('full', words >= target);
        checkBtn.disabled = words < min;
        // Words to try light up once they appear in the text.
        const lower = textArea.value.toLowerCase();
        wordsList.querySelectorAll('li').forEach(li => {
            li.classList.toggle('used', new RegExp(`\\b${li.dataset.word.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`).test(lower));
        });
    }

    function tick() {
        const minutes = task && task.info.minutes;
        if (!minutes || !startedAt) return;
        const left = minutes * 60 - Math.floor((Date.now() - startedAt) / 1000);
        const shown = Math.abs(left);
        timerBox.querySelector('span').textContent = `${left < 0 ? 'Over by ' : ''}${Math.floor(shown / 60)}:${String(shown % 60).padStart(2, '0')}`;
        timerBox.classList.toggle('low', left >= 0 && left <= 5 * 60);
        timerBox.classList.toggle('over', left < 0);
    }

    function startTimer() {
        clearInterval(timer);
        show(timerBox, Boolean(task && task.info.minutes));
        if (task && task.info.minutes) {
            timerBox.querySelector('span').textContent = `${task.info.minutes}:00`;
            timer = setInterval(tick, 1000);
        }
    }

    function restoreDraft() {
        const key = draftKey();
        let draft = null;
        try {
            draft = key ? JSON.parse(stored(key)) : null;
        } catch (error) { /* a damaged draft is ignored */ }
        textArea.value = draft ? draft.text : '';
        startedAt = draft ? draft.startedAt : 0;
        startTimer();
        tick();
        updateCount();
        show(errorEl, false);
    }

    textArea.addEventListener('input', () => {
        if (!startedAt) startedAt = Date.now();
        updateCount();
        const key = draftKey();
        if (key && !revisingOf) store(key, JSON.stringify({ text: textArea.value, startedAt }));
    });

    function stopRevising() {
        revisingOf = null;
        show(revisingNote, false);
    }

    // --- 5. MARKING ---

    let stepTimer = 0;
    function setMarking(on) {
        show(markingPanel, on);
        checkBtn.disabled = on;
        textArea.readOnly = on;
        clearInterval(stepTimer);
        if (on) {
            let i = 0;
            markingStep.textContent = STEPS[0];
            stepTimer = setInterval(() => { i = Math.min(i + 1, STEPS.length - 1); markingStep.textContent = STEPS[i]; }, 2600);
            markingPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    async function submit() {
        if (!task) return;
        show(errorEl, false);
        setMarking(true);
        show(resultPanel, false);
        try {
            const body = await goals.requestJSON('/api/writing/check', {
                kind: task.kind, prompt_id: task.id, idea: task.idea,
                words_to_try: (task.words_to_try || []).map(w => w.word),
                text: textArea.value, revision_of: revisingOf, utc_offset: goals.utcOffset(),
            });
            setMarking(false);
            if (body.waiting) {
                renderWaiting(body);
            } else {
                const key = draftKey();
                if (key && !revisingOf) store(key, null);
                renderResult(body.piece, { fresh: true });
                writingGoal.render(body.progress);
            }
            loadHistory();
        } catch (error) {
            setMarking(false);
            errorEl.textContent = error.message;
            show(errorEl, true);
        } finally {
            checkBtn.disabled = countWords(textArea.value) < task.info.min_words;
        }
    }

    checkBtn.addEventListener('click', submit);
    textArea.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !checkBtn.disabled) submit();
    });

    // --- 6. THE TEACHER'S MARKS ---

    function ring(score) {
        const box = el('div', 'score-ring');
        const SVG = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(SVG, 'svg');
        svg.setAttribute('viewBox', '0 0 120 120');
        svg.setAttribute('aria-hidden', 'true');
        const circle = (cls, extra = {}) => {
            const c = document.createElementNS(SVG, 'circle');
            Object.entries({ cx: 60, cy: 60, r: 52, class: cls, ...extra }).forEach(([k, v]) => c.setAttribute(k, v));
            return c;
        };
        const length = 2 * Math.PI * 52;
        const fill = circle('score-ring-fill', { 'stroke-dasharray': length, 'stroke-dashoffset': length });
        svg.append(circle('score-ring-track'), fill);
        const number = el('strong', 'score-number', '0');
        const middle = el('div', 'score-middle');
        middle.append(number, el('span', '', '/ 80'));
        box.append(svg, middle);
        requestAnimationFrame(() => requestAnimationFrame(() => {
            fill.setAttribute('stroke-dashoffset', length * (1 - score / 80));
            const fx = window.MyVocabFx;
            if (fx) fx.countTo(number, score, 1100); else number.textContent = score;
        }));
        return box;
    }

    function criterionRow(c) {
        const row = el('li', 'criterion');
        const head = el('div', 'criterion-head');
        head.append(el('span', 'criterion-name', c.name), el('span', 'criterion-score', `${c.score}/20`));
        const bar = el('div', 'criterion-bar');
        const fill = el('span');
        bar.append(fill);
        requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = `${(c.score / 20) * 100}%`; }));
        row.append(head, bar);
        if (c.comment) row.append(el('p', 'criterion-comment', c.comment));
        return row;
    }

    // The writer's text with each mistake marked; the correction is beside it.
    function markedText(text, mistakes) {
        const box = el('div', 'marked-text');
        let at = 0;
        const parts = [];
        mistakes.forEach((m, i) => {
            if (!m.wrong) return;
            const found = text.indexOf(m.wrong, at);
            if (found < 0) return;
            parts.push(text.slice(at, found));
            const mark = el('mark', `mistake type-${m.type}`, m.wrong);
            mark.title = m.right ? `→ ${m.right}` : m.why;
            mark.dataset.n = i + 1;
            parts.push(mark);
            at = found + m.wrong.length;
        });
        parts.push(text.slice(at));
        box.append(...parts);
        return box;
    }

    function section(title, ...children) {
        const s = el('section', 'result-section');
        s.append(el('h4', '', title), ...children);
        return s;
    }

    function renderResult(piece, { fresh = false } = {}) {
        const f = piece.feedback || {};
        const parts = [];

        const head = el('div', 'result-head');
        const facts = el('div', 'result-facts-box');
        facts.append(el('p', 'result-kind', `${NAMES[piece.kind] || piece.kind} · ${dateText(piece.created_at)} · ${piece.words} words`));
        facts.append(el('h3', '', piece.kind === 'diary' ? 'Your teacher says' : 'Your marks'));
        const chips = el('div', 'result-chips');
        if (piece.band !== null && piece.band !== undefined) chips.append(el('span', 'chip band', `Band ≈ ${Number(piece.band).toFixed(1)}`));
        chips.append(el('span', `chip ${piece.counted ? 'gain' : ''}`,
            piece.counted ? `+${piece.points} points` : piece.revision_of ? 'Revision: practice only' : 'Practice only: no points'));
        facts.append(chips);
        if (f.overall) facts.append(el('p', 'result-overall', f.overall));
        head.append(ring(piece.score), facts);
        parts.push(head);

        const criteria = el('ul', 'criteria');
        (f.criteria || []).forEach(c => criteria.append(criterionRow(c)));
        parts.push(criteria);

        if ((f.strengths || []).length) {
            const ul = el('ul', 'strengths');
            f.strengths.forEach(s => ul.append(el('li', '', s)));
            parts.push(section('What you did well', ul));
        }
        if ((f.mistakes || []).length) {
            const ol = el('ol', 'mistake-list');
            f.mistakes.forEach(m => {
                const li = el('li');
                const change = el('p', 'mistake-change');
                change.append(el('del', '', m.wrong), ' → ', el('ins', '', m.right));
                li.append(el('span', `mistake-type type-${m.type}`, m.type), change);
                if (m.why) li.append(el('p', 'mistake-why', m.why));
                ol.append(li);
            });
            parts.push(section(`Corrections (${f.mistakes.length})`, markedText(piece.text, f.mistakes), ol));
        }
        if ((f.vocabulary || []).length) {
            const ul = el('ul', 'vocab-upgrades');
            f.vocabulary.forEach(v => {
                const li = el('li');
                const line = el('p', 'upgrade-line');
                line.append(el('span', 'upgrade-from', v.word), ' → ');
                v.better.forEach((b, i) => line.append(el('span', 'upgrade-to', b), i < v.better.length - 1 ? ' ' : ''));
                li.append(line);
                if (v.note) li.append(el('p', 'upgrade-note', v.note));
                ul.append(li);
            });
            parts.push(section('Better words', ul));
        }
        if ((f.words_used || []).length) {
            const ul = el('ul', 'words-used');
            f.words_used.forEach(w => {
                const li = el('li', w.used_well ? 'well' : 'not-well');
                li.append(el('strong', '', `${w.used_well ? '✓' : '✗'} ${w.word}`));
                if (w.note) li.append(el('span', '', w.note));
                ul.append(li);
            });
            parts.push(section('Your words to try', ul));
        }
        if (f.improved) {
            const details = el('details', 'improved');
            details.append(el('summary', '', 'An improved version'), el('p', 'improved-text', f.improved));
            parts.push(details);
        }
        if (f.next_step) parts.push(section('Next time', el('p', 'next-step', f.next_step)));
        if (f.summary_vi) {
            const vi = el('p', 'summary-vi', f.summary_vi);
            vi.lang = 'vi';
            parts.push(section('Tóm tắt', vi));
        }

        const actions = el('div', 'result-actions');
        const revise = el('button', 'result-revise', 'Revise this piece');
        revise.type = 'button';
        revise.addEventListener('click', () => startRevising(piece));
        const fresh2 = el('button', 'result-new', 'Write something new');
        fresh2.type = 'button';
        fresh2.addEventListener('click', () => {
            show(resultPanel, false);
            stopRevising();
            loadTask(task && task.kind === piece.kind ? (piece.kind === 'diary' ? 'diary' : piece.prompt_id) : null);
            editorPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
        actions.append(revise, fresh2);
        parts.push(actions);

        resultPanel.replaceChildren(...parts);
        show(resultPanel, true);
        resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });

        const fx = window.MyVocabFx;
        if (fresh && fx) {
            const ringEl = resultPanel.querySelector('.score-ring');
            if (piece.counted) fx.floatText(ringEl, `+${piece.points}`, 'gain');
            if (piece.score >= 64) {
                fx.cannons();
                fx.celebrate('Excellent writing!', `${piece.score}/80${piece.band ? ` · band ≈ ${Number(piece.band).toFixed(1)}` : ''}`, 'fa-award');
            } else if (piece.score >= 48) {
                fx.burstFrom(ringEl, 40);
            }
            if (piece.counted && piece.kind === 'diary') fx.celebrate('Diary done for today', 'See you tomorrow for the next one!', 'fa-book');
        }
    }

    // The teacher could not be reached: the piece is kept, with grammar notes if any.
    function renderWaiting(body) {
        const piece = body.piece;
        const parts = [el('h3', '', 'Saved, waiting for your teacher'),
            el('p', 'waiting-note', 'The AI could not mark this just now (it may be busy or out of its daily quota). Your writing is kept; try again in a little while.')];
        const notes = body.grammar;
        if (notes && notes.mistakes.length) {
            const ol = el('ol', 'mistake-list');
            notes.mistakes.forEach(m => {
                const li = el('li');
                const change = el('p', 'mistake-change');
                change.append(el('del', '', m.wrong), ' → ', el('ins', '', m.right || '?'));
                li.append(change);
                if (m.why) li.append(el('p', 'mistake-why', m.why));
                ol.append(li);
            });
            parts.push(section('Grammar checker notes, meanwhile', ol));
        }
        const retry = el('button', 'result-revise', 'Mark it now');
        retry.type = 'button';
        retry.addEventListener('click', () => retryPiece(piece.id));
        const actions = el('div', 'result-actions');
        actions.append(retry);
        parts.push(actions);
        resultPanel.replaceChildren(...parts);
        show(resultPanel, true);
        resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function retryPiece(id) {
        setMarking(true);
        try {
            const body = await goals.requestJSON(`/api/writing/retry/${id}`, { utc_offset: goals.utcOffset() });
            setMarking(false);
            if (body.waiting) renderWaiting(body);
            else {
                renderResult(body.piece, { fresh: true });
                writingGoal.render(body.progress);
            }
            loadHistory();
        } catch (error) {
            setMarking(false);
            errorEl.textContent = error.message;
            show(errorEl, true);
        }
    }

    function startRevising(piece) {
        const input = kindInputs.find(i => i.value === piece.kind);
        if (input && !input.checked) {
            input.checked = true;
            store(KIND_KEY, piece.kind);
        }
        revisingOf = piece.id;
        textArea.value = piece.text;
        revisingNote.textContent = 'Revising: use the feedback to improve it, then mark it again. A revision shows your new score but earns no points.';
        show(revisingNote, true);
        show(resultPanel, false);
        updateCount();
        editorPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        textArea.focus();
    }

    // --- 7. PAST WRITING ---

    async function openPiece(id) {
        try {
            renderResult(await goals.requestJSON(`/api/writing/piece/${id}`));
        } catch (error) {
            historyNote.textContent = error.message;
        }
    }

    async function loadHistory() {
        try {
            const { pieces } = await goals.requestJSON('/api/writing/history');
            historyNote.textContent = pieces.length ? '' : 'Nothing yet. Your marked writing will be listed here.';
            show(historyNote, !pieces.length);
            historyList.replaceChildren(...pieces.map((p, i) => {
                const li = el('li');
                const button = el('button', `history-item ${p.status}`);
                button.type = 'button';
                button.style.setProperty('--i', Math.min(i, 12));
                const icon = el('i', `fas ${ICONS[p.kind] || 'fa-pen'}`);
                icon.setAttribute('aria-hidden', 'true');
                const what = el('span', 'history-what');
                what.append(el('strong', '', `${NAMES[p.kind]}${p.revision_of ? ' · revision' : ''}`), el('span', '', p.prompt));
                const score = el('span', 'history-score', p.status === 'scored' ? `${p.score}/80` : 'Not marked yet');
                button.append(icon, what, el('span', 'history-date', dateText(p.created_at)), score);
                button.addEventListener('click', () => (p.status === 'scored' ? openPiece(p.id) : retryPiece(p.id)));
                li.append(button);
                return li;
            }));
        } catch (error) {
            historyList.replaceChildren();
            show(historyNote, true);
            historyNote.replaceChildren(error.message);
            if (error.data && error.data.locked) {
                const link = el('a', '', 'Unlock');
                link.href = '/?unlock=1';
                historyNote.append(' ', link);
            }
        }
    }

    // --- 8. START ---
    const saved = stored(KIND_KEY);
    const savedInput = kindInputs.find(i => i.value === saved);
    if (savedInput) savedInput.checked = true;
    writingGoal.load();
    loadTask();
    loadHistory();
});
