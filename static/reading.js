// File: static/reading.js
// Reading practice: a 50-day plan of IELTS-style parts, one a day. Opening a
// part shows the passage beside its questions with a 20-minute timer; answers
// are kept on this device until submitted, then marked by the server
// (reading.py), which sends back the answer key and where each answer is.

document.addEventListener('DOMContentLoaded', () => {
    const goals = window.MyVocabGoals;
    const readingGoal = goals.panel(document.querySelector('.goal-panel[data-skill="reading"]'));

    // --- 1. ELEMENTS ---
    const planView = document.querySelector('.reading-plan-view');
    const practiceTabs = document.querySelector('.practice-tabs');
    const todayKicker = document.getElementById('today-kicker');
    const todayTitle = document.getElementById('today-title');
    const todayMeta = document.getElementById('today-meta');
    const todayNote = document.getElementById('today-note');
    const todayStart = document.getElementById('today-start');
    const dayStreak = document.getElementById('day-streak');
    const planGrid = document.getElementById('plan-grid');
    const planCount = document.getElementById('plan-count');

    const testView = document.getElementById('reading-test');
    const testDay = document.getElementById('test-day');
    const testTitle = document.getElementById('test-title');
    const timerBox = document.getElementById('test-timer');
    const timerText = document.getElementById('timer-text');
    const submitBtn = document.getElementById('test-submit');
    const exitBtn = document.getElementById('test-exit');
    const resultBox = document.getElementById('test-result');
    const panes = document.querySelector('.test-panes');
    const passagePane = document.getElementById('passage-pane');
    const questionsPane = document.getElementById('questions-pane');
    const showPassage = document.getElementById('show-passage');
    const showQuestions = document.getElementById('show-questions');
    const answeredCount = document.getElementById('answered-count');

    const LETTERS = 'ABCDEFGHIJ';
    const ROMAN = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 'xi', 'xii'];
    const TFNG = ['TRUE', 'FALSE', 'NOT GIVEN'];
    const NUMBER_WORDS = ['', 'ONE WORD', 'TWO WORDS', 'THREE WORDS', 'FOUR WORDS'];
    const DRAFT_HOURS = 12;  // an unfinished draft older than this starts afresh

    let plan = null;
    let part = null;
    let timer = null;
    let startedAt = 0;
    let submitted = false;
    let confirmUntil = 0;

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

    function plural(n, word) {
        return `${n} ${word}${n === 1 ? '' : 's'}`;
    }

    function pointsText(n) {
        const sign = n > 0 ? '+' : n < 0 ? '−' : '';
        return `${sign}${Math.abs(n)} point${Math.abs(n) === 1 ? '' : 's'}`;
    }

    // Drafts live in this browser only; storage can fail in a private window.
    function draftKey(id) {
        return `myvocab-reading-draft-${id}`;
    }

    function readDraft(id) {
        try {
            const draft = JSON.parse(localStorage.getItem(draftKey(id)));
            return draft && Date.now() - draft.startedAt < DRAFT_HOURS * 3600 * 1000 ? draft : null;
        } catch (error) {
            return null;
        }
    }

    function writeDraft() {
        if (!part || submitted) return;
        try {
            localStorage.setItem(draftKey(part.id), JSON.stringify({ startedAt, answers: collectAnswers() }));
        } catch (error) { /* not kept */ }
    }

    function dropDraft(id) {
        try {
            localStorage.removeItem(draftKey(id));
        } catch (error) { /* nothing kept */ }
    }

    // --- 3. THE PLAN ---

    function partSummary(p) {
        return `Day ${p.day} · ${p.topic} · ${p.words} words · ${p.questions} questions · about ${plan.minutes} minutes`;
    }

    function renderToday() {
        const doneToday = plan.parts.filter(p => plan.done_today.includes(p.id));
        const next = plan.parts.find(p => p.id === plan.next_id);
        show(todayNote, false);
        if (doneToday.length) {
            const last = doneToday[doneToday.length - 1];
            todayKicker.textContent = "Today's part is done";
            todayTitle.textContent = `✓ ${last.title}`;
            todayMeta.textContent = `${last.scores.first.correct}/${last.scores.first.total} right · ${pointsText(last.scores.first.points)}`;
            todayNote.textContent = next ? 'Want more? The next part is ready whenever you are.' : 'That was the last part of the plan.';
            show(todayNote, true);
        } else if (next) {
            todayKicker.textContent = `Today · Day ${next.day} of ${plan.parts.length}`;
            todayTitle.textContent = next.title;
            todayMeta.textContent = partSummary(next);
        } else {
            todayKicker.textContent = 'Plan complete';
            todayTitle.textContent = `All ${plan.parts.length} parts are done. Brilliant!`;
            todayMeta.textContent = 'You can redo any part for practice.';
        }
        if (next) {
            todayStart.querySelector('span').textContent = doneToday.length ? `Read Day ${next.day}` : "Start today's part";
            todayStart.dataset.id = next.id;
        }
        show(todayStart, Boolean(next));
        const flame = el('i', 'fas fa-fire');
        flame.setAttribute('aria-hidden', 'true');
        dayStreak.replaceChildren(flame, ` ${plural(plan.streak, 'day')} in a row`);
        show(dayStreak, plan.streak > 0);
    }

    function renderGrid() {
        const done = plan.parts.filter(p => p.scores).length;
        planCount.textContent = `${done} of ${plan.parts.length} done`;
        planGrid.replaceChildren(...plan.parts.map(p => {
            const item = el('li');
            const button = el('button', 'plan-day');
            button.type = 'button';
            const first = p.scores && p.scores.first;
            button.classList.toggle('done', Boolean(p.scores));
            button.classList.toggle('next', p.id === plan.next_id);
            button.append(el('span', 'plan-day-num', p.day));
            button.append(el('span', 'plan-day-score', first ? `${first.correct}/${first.total}` : p.id === plan.next_id ? 'next' : ''));
            const status = first ? `done, ${first.correct} of ${first.total} right` : p.id === plan.next_id ? 'up next' : 'not done yet';
            button.setAttribute('aria-label', `Day ${p.day}: ${p.title}, ${status}`);
            button.title = `Day ${p.day}: ${p.title}`;
            button.addEventListener('click', () => openPart(p.id));
            button.style.setProperty('--i', p.day - 1);
            item.append(button);
            return item;
        }));
    }

    async function loadPlan() {
        try {
            plan = await goals.requestJSON(`/api/reading/plan?utc_offset=${goals.utcOffset()}`);
            renderToday();
            renderGrid();
        } catch (error) {
            todayTitle.textContent = 'Could not load your reading plan.';
        }
    }

    todayStart.addEventListener('click', () => openPart(Number(todayStart.dataset.id)));

    // --- 4. THE PASSAGE AND QUESTIONS ---

    function renderPassage() {
        passagePane.replaceChildren(el('h3', 'passage-title', part.title),
            ...part.paragraphs.map((text, i) => {
                const p = el('p', 'para');
                p.id = `para-${LETTERS[i]}`;
                p.append(el('span', 'para-letter', LETTERS[i]), text);
                return p;
            }));
    }

    function instructions(group) {
        const count = part.paragraphs.length;
        const last = LETTERS[count - 1];
        return {
            tfng: 'Do the following statements agree with the information in the passage? Choose TRUE if the statement agrees with the information, FALSE if it contradicts the information, or NOT GIVEN if there is no information on this.',
            gap: `Complete the sentences. Choose NO MORE THAN ${NUMBER_WORDS[group.words]} from the passage for each answer.`,
            mcq: 'Choose the correct letter, A, B, C or D.',
            para: `The passage has ${count} paragraphs, A–${last}. Which paragraph contains the following information? You may use any letter more than once.`,
            heading: `The passage has ${count} paragraphs, A–${last}. Choose the correct heading for each paragraph from the list of headings.`,
        }[group.type];
    }

    function choiceList(n, values, labels) {
        const box = el('div', 'q-choices');
        box.setAttribute('role', 'radiogroup');
        box.setAttribute('aria-labelledby', `q-${n}-text`);
        values.forEach((value, i) => {
            const label = el('label', 'q-choice');
            const input = el('input');
            input.type = 'radio';
            input.name = `q${n}`;
            input.value = value;
            label.append(input, el('span', '', labels ? labels[i] : value));
            box.append(label);
        });
        return box;
    }

    function selectBox(n, options) {
        const select = el('select', 'q-select');
        select.name = `q${n}`;
        select.setAttribute('aria-labelledby', `q-${n}-text`);
        select.append(el('option', '', 'Choose...'));
        select.options[0].value = '';
        options.forEach(([value, label]) => {
            const option = el('option', '', label);
            option.value = value;
            select.append(option);
        });
        return select;
    }

    function questionItem(group, q) {
        const li = el('li', 'q');
        li.id = `q-${q.n}`;
        li.dataset.n = q.n;
        const body = el('div', 'q-body');
        if (group.type === 'gap') {
            // The sentence with a box where the blank was.
            const [before, after] = q.q.split('____');
            const line = el('p', 'q-text');
            line.id = `q-${q.n}-text`;
            const input = el('input', 'q-gap');
            input.type = 'text';
            input.name = `q${q.n}`;
            input.autocomplete = 'off';
            input.spellcheck = false;
            input.maxLength = 60;
            input.dataset.words = group.words;
            input.setAttribute('aria-label', `Answer ${q.n}`);
            line.append(before, input, after || '');
            body.append(line);
        } else {
            const text = el('p', 'q-text', group.type === 'heading' ? `Paragraph ${q.q}` : q.q);
            text.id = `q-${q.n}-text`;
            body.append(text);
            if (group.type === 'tfng') body.append(choiceList(q.n, TFNG));
            if (group.type === 'mcq') body.append(choiceList(q.n, q.options.map((_, i) => LETTERS[i]),
                q.options.map((o, i) => `${LETTERS[i]}  ${o}`)));
            if (group.type === 'para') body.append(selectBox(q.n, part.paragraphs.map((_, i) => [LETTERS[i], LETTERS[i]])));
            if (group.type === 'heading') body.append(selectBox(q.n, group.headings.map((h, i) => [String(i), `${ROMAN[i]}  ${h}`])));
        }
        body.append(el('p', 'q-feedback hidden'));
        li.append(el('span', 'q-num', q.n), body);
        return li;
    }

    function renderQuestions() {
        questionsPane.replaceChildren(...part.groups.map(group => {
            const section = el('section', `q-group group-${group.type}`);
            const first = group.questions[0].n;
            const last = group.questions[group.questions.length - 1].n;
            section.append(el('h3', 'q-range', first === last ? `Question ${first}` : `Questions ${first}–${last}`),
                el('p', 'q-instructions', instructions(group)));
            if (group.type === 'heading') {
                const list = el('div', 'heading-list');
                list.append(el('h4', '', 'List of headings'));
                const ol = el('ol');
                group.headings.forEach((h, i) => {
                    const li = el('li');
                    li.append(el('span', 'heading-roman', ROMAN[i]), h);
                    ol.append(li);
                });
                list.append(ol);
                section.append(list);
            }
            const ol = el('ol', 'q-list');
            ol.append(...group.questions.map(q => questionItem(group, q)));
            section.append(ol);
            return section;
        }));
    }

    function collectAnswers() {
        const answers = {};
        for (const field of questionsPane.elements) {
            const n = field.name.slice(1);
            if (field.type === 'radio') {
                if (field.checked) answers[n] = field.value;
            } else if (field.value.trim()) {
                answers[n] = field.value.trim();
            }
        }
        return answers;
    }

    function restoreAnswers(answers) {
        for (const field of questionsPane.elements) {
            const value = answers[field.name.slice(1)];
            if (value === undefined) continue;
            if (field.type === 'radio') field.checked = field.value === value;
            else field.value = value;
        }
    }

    function updateAnswered() {
        const done = Object.keys(collectAnswers()).length;
        answeredCount.textContent = `${done}/${part.total}`;
        questionsPane.querySelectorAll('.q').forEach(li => {
            li.classList.toggle('answered', collectAnswersFor(li) !== '');
        });
    }

    function collectAnswersFor(li) {
        const field = li.querySelector('input:checked, input.q-gap, select');
        return field ? (field.type === 'radio' ? field.value : field.value.trim()) : '';
    }

    // A gap answer longer than the word limit is flagged, as the real test would mark it wrong.
    questionsPane.addEventListener('input', (e) => {
        if (e.target.classList.contains('q-gap')) {
            const words = e.target.value.trim().split(/\s+/).filter(Boolean).length;
            const tooMany = words > Number(e.target.dataset.words);
            e.target.classList.toggle('too-many', tooMany);
            e.target.title = tooMany ? `No more than ${NUMBER_WORDS[e.target.dataset.words].toLowerCase()}` : '';
        }
        updateAnswered();
        writeDraft();
    });
    questionsPane.addEventListener('change', () => { updateAnswered(); writeDraft(); });
    questionsPane.addEventListener('submit', (e) => e.preventDefault());

    // --- 5. TIMER ---

    function tick() {
        const left = part.minutes * 60 - Math.floor((Date.now() - startedAt) / 1000);
        const shown = Math.abs(left);
        const text = `${left < 0 ? '+' : ''}${Math.floor(shown / 60)}:${String(shown % 60).padStart(2, '0')}`;
        timerText.textContent = left < 0 ? `Time's up ${text}` : text;
        timerBox.classList.toggle('low', left >= 0 && left <= 5 * 60);
        timerBox.classList.toggle('over', left < 0);
    }

    function startTimer() {
        clearInterval(timer);
        tick();
        timer = setInterval(tick, 1000);
    }

    // --- 6. OPENING, SUBMITTING, CLOSING ---

    function setView(testing) {
        show(planView, !testing);
        show(practiceTabs, !testing);
        show(testView, testing);
        document.body.classList.toggle('reading-testing', testing);
        window.scrollTo({ top: 0 });
    }

    function setPane(which) {
        panes.dataset.show = which;
        showPassage.setAttribute('aria-selected', String(which === 'passage'));
        showQuestions.setAttribute('aria-selected', String(which === 'questions'));
    }

    async function openPart(id) {
        let data;
        try {
            data = await goals.requestJSON(`/api/reading/part/${id}`);
        } catch (error) {
            todayNote.textContent = error.message;
            show(todayNote, true);
            return;
        }
        part = { ...data, minutes: plan ? plan.minutes : 20 };
        const info = plan && plan.parts.find(p => p.id === id);
        submitted = false;
        confirmUntil = 0;
        testDay.textContent = info ? `Day ${info.day} · ${info.topic}${info.scores ? ' · practice: already done once' : ''}` : '';
        testTitle.textContent = part.title;
        renderPassage();
        renderQuestions();
        const draft = readDraft(id);
        startedAt = draft ? draft.startedAt : Date.now();
        if (draft) restoreAnswers(draft.answers);
        updateAnswered();
        show(resultBox, false);
        submitBtn.textContent = 'Submit answers';
        submitBtn.disabled = false;
        show(submitBtn, true);
        show(timerBox, true);
        setPane('passage');
        setView(true);
        startTimer();
        try {
            history.replaceState(null, '', `#part-${id}`);
        } catch (error) { /* the address keeps the plan */ }
    }

    function closeTest() {
        clearInterval(timer);
        part = null;
        setView(false);
        try {
            history.replaceState(null, '', location.pathname);
        } catch (error) { /* the address keeps the part */ }
        loadPlan();
    }

    function goToParagraph(letter) {
        const target = document.getElementById(`para-${letter}`);
        if (!target) return;
        setPane('passage');
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.classList.remove('flash');
        void target.offsetWidth;  // restart the highlight
        target.classList.add('flash');
    }

    function headingText(roman) {
        const group = part.groups.find(g => g.type === 'heading');
        const i = ROMAN.indexOf(roman);
        return group && i >= 0 ? `${roman}  ${group.headings[i]}` : roman;
    }

    function showMarks(body) {
        body.results.forEach(r => {
            const li = document.getElementById(`q-${r.n}`);
            li.style.setProperty('--n', r.n);  // marks are revealed one after another
            li.classList.add(r.right ? 'right' : r.blank ? 'blank' : 'wrong');
            const feedback = li.querySelector('.q-feedback');
            const isHeading = li.closest('.group-heading') !== null;
            feedback.replaceChildren(el('span', 'q-verdict', r.right ? '✓ Right' : r.blank ? '– No answer' : '✗ Wrong'));
            if (!r.right) feedback.append(' Answer: ', el('strong', '', isHeading ? headingText(r.answer) : r.answer));
            if (r.paragraph) {
                const link = el('button', 'q-where', `See paragraph ${r.paragraph}`);
                link.type = 'button';
                link.addEventListener('click', () => goToParagraph(r.paragraph));
                feedback.append(link);
            }
            show(feedback, true);
        });
        // Lock the answers, but not the "See paragraph" buttons beside them.
        for (const field of questionsPane.elements) {
            if (field.tagName !== 'BUTTON') field.disabled = true;
        }
    }

    function showResult(body) {
        const pct = body.correct / body.total;
        resultBox.className = `test-result ${pct >= 0.7 ? 'great' : pct >= 0.4 ? 'good' : 'low'}`;
        const score = el('p', 'result-score');
        score.append(el('strong', '', `${body.correct}/${body.total}`), ' right');
        const facts = el('p', 'result-facts');
        facts.textContent = [
            body.band ? `about band ${body.band.toFixed(1)}` : '',
            body.counted ? pointsText(body.points) : 'practice only, no points',
            body.wrong ? `${body.wrong} wrong` : '',
            body.total - body.correct - body.wrong ? `${body.total - body.correct - body.wrong} blank` : '',
        ].filter(Boolean).join(' · ');
        const note = el('p', 'result-note', 'The band is a rough guide: one part is a third of the real test.');
        const actions = el('div', 'result-actions');
        const back = el('button', 'result-back', 'Back to the plan');
        back.type = 'button';
        back.addEventListener('click', closeTest);
        actions.append(back);
        const index = plan ? plan.parts.findIndex(p => p.id === part.id) : -1;
        const next = index >= 0 ? plan.parts.slice(index + 1).find(p => !p.scores && p.id !== part.id) : null;
        if (next) {
            const go = el('button', 'result-next', `Next: Day ${next.day}`);
            go.type = 'button';
            go.addEventListener('click', () => openPart(next.id));
            actions.append(go);
        }
        resultBox.replaceChildren(score, facts, note, actions);
        show(resultBox, true);
        resultBox.scrollIntoView({ behavior: 'smooth', block: 'start' });

        const fx = window.MyVocabFx;
        if (fx) {
            if (body.counted) fx.floatText(score, pointsText(body.points).replace(/ points?$/, ''), body.points >= 0 ? 'gain' : 'loss');
            if (body.correct === body.total) {
                fx.cannons();
                fx.celebrate('Perfect part!', `All ${body.total} answers right`, 'fa-star');
            } else if (pct >= 0.7) {
                fx.burstFrom(score, 40);
            }
            if (body.counted && plan && plan.done_today.length === 0) {
                plan.done_today.push(part.id);
                fx.celebrate("Today's reading is done", 'One part a day: see you tomorrow!', 'fa-calendar-check');
            }
        }
        document.dispatchEvent(new CustomEvent('myvocab:reading-result', { detail: body }));
    }

    async function submit() {
        if (!part || submitted) return;
        const answers = collectAnswers();
        const blanks = part.total - Object.keys(answers).length;
        // A first click with questions unanswered asks for a second, so nothing is sent by accident.
        if (blanks > 0 && Date.now() > confirmUntil) {
            confirmUntil = Date.now() + 4000;
            submitBtn.textContent = `${plural(blanks, 'blank')}. Submit anyway?`;
            setTimeout(() => { if (!submitted && Date.now() > confirmUntil) submitBtn.textContent = 'Submit answers'; }, 4100);
            return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = 'Marking...';
        try {
            const body = await goals.requestJSON('/api/reading/submit',
                { part_id: part.id, answers, utc_offset: goals.utcOffset() });
            submitted = true;
            clearInterval(timer);
            const took = Math.floor((Date.now() - startedAt) / 1000);
            timerText.textContent = `Took ${Math.floor(took / 60)}:${String(took % 60).padStart(2, '0')}`;
            timerBox.classList.remove('low', 'over');
            dropDraft(part.id);
            showMarks(body);
            showResult(body);
            show(submitBtn, false);
            readingGoal.render(body.progress);
            if (plan) {
                const p = plan.parts.find(x => x.id === part.id);
                if (p && !p.scores) p.scores = { first: { correct: body.correct, total: body.total, points: body.points } };
            }
        } catch (error) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit answers';
            resultBox.className = 'test-result low';
            resultBox.textContent = error.message;
            show(resultBox, true);
        }
    }

    submitBtn.addEventListener('click', submit);
    exitBtn.addEventListener('click', () => {
        writeDraft();
        closeTest();
    });
    showPassage.addEventListener('click', () => setPane('passage'));
    showQuestions.addEventListener('click', () => setPane('questions'));

    // --- 7. START ---

    function partInAddress() {
        const m = location.hash.match(/^#part-(\d+)$/);
        return m ? Number(m[1]) : null;
    }

    window.addEventListener('hashchange', () => {
        const id = partInAddress();
        if (id && (!part || part.id !== id)) openPart(id);
    });

    readingGoal.load();
    loadPlan().then(() => {
        const id = partInAddress();
        if (id) openPart(id);
    });
});
