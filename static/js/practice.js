// File: static/js/practice.js
// Grammar and vocabulary practice: AI writes the exercises and marks the answers.

document.addEventListener('DOMContentLoaded', () => {
    // --- 1. ELEMENT SELECTION ---
    const topicList = document.getElementById('practice-topic-list');
    const topicsSection = document.getElementById('practice-topics');
    const startBtn = document.getElementById('start-practice-btn');

    const intro = document.getElementById('practice-intro');
    const notice = document.getElementById('practice-notice');
    const card = document.getElementById('exercise-card');
    const modeLabel = document.getElementById('exercise-mode-label');
    const progress = document.getElementById('exercise-progress');
    const instruction = document.getElementById('exercise-instruction');
    const promptEl = document.getElementById('exercise-prompt');

    const hints = document.getElementById('exercise-hints');
    const hintBtn = document.getElementById('hint-btn');
    const hintText = document.getElementById('hint-text');

    const form = document.getElementById('practice-form');
    const answerLabel = document.getElementById('practice-answer-label');
    const answerInput = document.getElementById('practice-answer');
    const checkBtn = document.getElementById('check-btn');
    const giveUpBtn = document.getElementById('give-up-btn');

    const feedback = document.getElementById('practice-feedback');
    const verdictEl = document.getElementById('feedback-verdict');
    const correctedBlock = document.getElementById('feedback-corrected-block');
    const correctedEl = document.getElementById('feedback-corrected');
    const mistakesBlock = document.getElementById('feedback-mistakes-block');
    const mistakesEl = document.getElementById('feedback-mistakes');
    const vocabEl = document.getElementById('feedback-vocab');
    const explanationEl = document.getElementById('feedback-explanation');
    const tipEl = document.getElementById('feedback-tip');
    const referenceBlock = document.getElementById('feedback-reference-block');
    const referenceLabel = document.getElementById('feedback-reference-label');
    const referenceEl = document.getElementById('feedback-reference');
    const sourceEl = document.getElementById('feedback-source');
    const nextBtn = document.getElementById('next-exercise-btn');

    const sessionScore = document.getElementById('session-score');
    const scoreEls = {
        correct: document.getElementById('score-correct'),
        almost: document.getElementById('score-almost'),
        incorrect: document.getElementById('score-incorrect'),
    };
    const scorePointsEl = document.getElementById('score-points');
    const pointsBadge = document.getElementById('feedback-points');
    const pointsWhy = document.getElementById('feedback-points-why');


    const BLANK = '___';

    const MODES = {
        fill_blank: {
            label: 'Fill the blank',
            instruction: 'Fill the blank with the right word, in the right form.',
            answerLabel: 'Missing word(s)',
            rows: 1,
            referenceLabel: 'Answer',
        },
        fix_mistake: {
            label: 'Fix the mistake',
            instruction: 'This sentence has one mistake. Rewrite the whole sentence correctly.',
            answerLabel: 'Corrected sentence',
            rows: 2,
            referenceLabel: 'One correct version',
        },
        translate: {
            label: 'Translate',
            instruction: 'Translate into English, using the word',
            answerLabel: 'Your English sentence',
            rows: 2,
            referenceLabel: 'One good translation',
        },
        use_it: {
            label: 'Use it in a sentence',
            instruction: 'Write your own English sentence using this word.',
            answerLabel: 'Your sentence',
            rows: 3,
            referenceLabel: 'Answer',
        },
        grammar: {
            label: 'Check my writing',
            instruction: 'Write or paste some English. AI corrects the grammar, vocabulary and spelling.',
            answerLabel: 'Your text',
            rows: 7,
            referenceLabel: 'Answer',
        },
    };

    const SOURCES = {
        match: 'Marked instantly: it matches the expected answer.',
        ai: 'Marked by AI.',
        languagetool: 'AI is unavailable right now, so only grammar and spelling were checked (by LanguageTool, in English).',
        none: 'AI and the grammar checker are both unavailable right now.',
    };

    // The last practice type and topics, so the next session can start with one
    // click. The topics key is shared with the Exam page. Browser-only.
    const TOPICS_KEY = 'myvocab-topics';
    const MODE_KEY = 'myvocab-practice-mode';

    let mode = 'fill_blank';
    let topicIds = [];
    let queue = [];
    let index = 0;
    let answered = false;
    let busy = false;
    const score = { correct: 0, almost: 0, incorrect: 0 };
    let sessionPoints = 0;

    // --- 2. HELPERS ---

    function show(el, visible) {
        el.classList.toggle('hidden', !visible);
    }

    function setText(el, text) {
        el.textContent = text || '';
        show(el, Boolean(text));
    }

    function normalize(text) {
        return (text || '').toLowerCase().replace(/[‘’]/g, "'")
            .replace(/\s+/g, ' ').trim().replace(/[ .!?]+$/, '');
    }

    function showNotice(message, isError) {
        notice.textContent = message || '';
        notice.classList.toggle('error', Boolean(isError));
        show(notice, Boolean(message));
    }

    async function postJSON(url, body) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || `The server answered ${response.status}.`);
        }
        return data;
    }

    function setBusy(isBusy, label) {
        busy = isBusy;
        checkBtn.disabled = isBusy;
        giveUpBtn.disabled = isBusy;
        startBtn.disabled = isBusy;
        if (label) checkBtn.textContent = label;
    }

    function currentItem() {
        return queue[index];
    }

    function remembered(key, fallback) {
        try {
            const value = JSON.parse(localStorage.getItem(key));
            return value === null ? fallback : value;
        } catch (error) {
            return fallback;
        }
    }

    function remember(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) { /* not remembered */ }
    }

    // --- 3. TOPICS ---

    async function loadTopics() {
        try {
            const response = await fetch('/api/get_topics');
            const topics = await response.json();
            const savedIds = [].concat(remembered(TOPICS_KEY, [])).map(String);
            topicList.replaceChildren();
            topics.filter(topic => topic.word_count > 0).forEach(topic => {
                const row = document.createElement('label');
                row.className = 'topic-checkbox';
                const box = document.createElement('input');
                box.type = 'checkbox';
                box.name = 'practice-topics';
                box.value = topic.id;
                box.checked = savedIds.includes(String(topic.id));
                row.append(box, ` ${topic.name} (${topic.word_count})`);
                topicList.appendChild(row);
            });
            if (!topicList.children.length) {
                topicList.textContent = 'No saved words yet. Save some words in the dictionary first.';
            }
        } catch (error) {
            topicList.textContent = 'Error loading topics.';
        }
    }

    function selectedMode() {
        return document.querySelector('input[name="mode"]:checked').value;
    }

    function selectedTopicIds() {
        return Array.from(document.querySelectorAll('input[name="practice-topics"]:checked'))
            .map(box => Number(box.value));
    }

    // --- 3a. WEEKLY GOAL (vocab score, drawn by goals.js) ---

    const goals = window.MyVocabGoals;
    const vocabGoal = goals.panel(document.querySelector('.goal-panel[data-skill="vocab"]'));

    // What one answer won or lost, next to its verdict.
    function showPoints(points, verdict) {
        if (!points) {
            pointsBadge.textContent = '';
            pointsBadge.className = 'points-badge hidden';
            setText(pointsWhy, verdict === 'unchecked' ? 'Not marked, so no points were won or lost.' : '');
            return;
        }
        const { worth, change } = points;
        pointsBadge.textContent = `${change > 0 ? '+' : change < 0 ? '−' : ''}${Math.abs(change)} point${Math.abs(change) === 1 ? '' : 's'}`;
        pointsBadge.className = `points-badge ${change > 0 ? 'gain' : change < 0 ? 'loss' : ''}`;
        setText(pointsWhy, {
            correct: `This sentence was worth ${worth} points.`,
            almost: `Almost right loses a third of this sentence's ${worth} points.`,
            incorrect: `A wrong answer loses half of this sentence's ${worth} points.`,
        }[verdict] || '');

        const fx = window.MyVocabFx;
        if (fx && change) {
            fx.replay(pointsBadge, change > 0 ? 'fx-pop' : 'fx-shake');
            fx.floatText(pointsBadge, `${change > 0 ? '+' : '−'}${Math.abs(change)}`, change > 0 ? 'gain' : 'loss');
            if (verdict === 'correct') fx.burstFrom(pointsBadge, 22);
        }

        sessionPoints += change;
        scorePointsEl.textContent = sessionPoints;
        show(sessionScore, true);
    }

    // --- 4. SHOWING AN EXERCISE ---

    function renderPrompt(item) {
        promptEl.replaceChildren();
        promptEl.className = '';

        if (mode === 'fill_blank') {
            const [before, after] = item.sentence.split(BLANK);
            const blank = document.createElement('span');
            blank.className = 'blank';
            blank.id = 'blank-slot';
            blank.textContent = ' '.repeat(10);
            promptEl.append(before, blank, after);
        } else if (mode === 'fix_mistake') {
            promptEl.className = 'prompt-wrong';
            promptEl.textContent = item.wrong_sentence;
        } else if (mode === 'translate') {
            promptEl.textContent = item.vietnamese_sentence;
        } else if (mode === 'use_it') {
            promptEl.className = 'prompt-word';
            const word = document.createElement('span');
            word.textContent = item.word;
            const meaning = document.createElement('small');
            meaning.textContent = item.meaning_vi;
            promptEl.append(word, meaning);
        }
    }

    function renderInstruction(item) {
        instruction.replaceChildren(MODES[mode].instruction);
        if (mode === 'translate') {
            const word = document.createElement('strong');
            word.textContent = ` “${item.word}”`;
            instruction.append(word, '.');
        }
    }

    function hintFor(item) {
        if (mode === 'fill_blank') {
            const lines = [`Meaning: ${item.meaning_vi}`];
            if (item.sentence_vi) lines.push(`Sentence: ${item.sentence_vi}`);
            return lines.join('\n');
        }
        if (mode === 'fix_mistake') {
            return 'Check the verb tense, subject–verb agreement, articles (a/an/the), '
                + 'prepositions, plurals, word form and word order.';
        }
        if (mode === 'translate') return `“${item.word}” means: ${item.meaning_vi}`;
        if (mode === 'use_it') return item.definition ? `Definition: ${item.definition}` : '';
        return '';
    }

    function resetAnswerArea() {
        answered = false;
        answerInput.value = '';
        answerInput.rows = MODES[mode].rows;
        answerInput.disabled = false;
        answerLabel.textContent = MODES[mode].answerLabel;
        show(form, true);
        feedback.className = '';
        show(feedback, false);
        hintText.textContent = '';
        show(hintText, false);
        setBusy(false, 'Check');
    }

    // On a phone the setup panel sits above the exercise, so bring the
    // exercise up when it starts below the middle of the screen.
    function bringIntoView() {
        if (card.getBoundingClientRect().top > window.innerHeight / 2) {
            card.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    function showExercise() {
        const item = currentItem();
        modeLabel.textContent = MODES[mode].label;
        progress.textContent = `${index + 1} of ${queue.length}`;
        renderInstruction(item);
        renderPrompt(item);
        const hint = hintFor(item);
        show(hints, Boolean(hint));
        hintBtn.dataset.hint = hint;
        show(giveUpBtn, mode !== 'use_it');
        resetAnswerArea();
        nextBtn.textContent = index + 1 < queue.length ? 'Next' : 'New exercises';
        show(card, true);
        bringIntoView();
        answerInput.focus({ preventScroll: true });
    }

    function showGrammarChecker() {
        modeLabel.textContent = MODES.grammar.label;
        progress.textContent = '';
        renderInstruction(null);
        promptEl.replaceChildren();
        show(hints, false);
        show(giveUpBtn, false);
        resetAnswerArea();
        nextBtn.textContent = 'Check another text';
        show(card, true);
        bringIntoView();
        answerInput.focus({ preventScroll: true });
    }

    async function loadExercises() {
        setBusy(true);
        show(card, false);
        showNotice('Writing new exercises...');
        try {
            const data = await postJSON('/api/practice/exercises', { mode, topic_ids: topicIds });
            queue = data.items;
            index = 0;
            showNotice(data.notice || '');
            showExercise();
        } catch (error) {
            showNotice(error.message, true);
        } finally {
            setBusy(false, 'Check');
        }
    }

    // --- 5. MARKING ---

    function learnerSentence(item, answer) {
        return mode === 'fill_blank' ? item.sentence.replace(BLANK, answer) : answer;
    }

    function verdictTitle(result) {
        if (mode === 'grammar') {
            return result.verdict === 'correct' ? 'No mistakes found.' : 'Here are the corrections.';
        }
        return {
            correct: 'Correct!',
            almost: 'Almost there.',
            incorrect: 'Not quite.',
            unchecked: 'Could not mark this one.',
        }[result.verdict] || 'Checked.';
    }

    function renderMistakes(mistakes) {
        mistakesEl.replaceChildren();
        mistakes.forEach(m => {
            const li = document.createElement('li');
            const change = document.createElement('div');
            change.className = 'mistake-change';
            if (m.wrong) {
                const wrong = document.createElement('del');
                wrong.textContent = m.wrong;
                change.append(wrong);
            }
            if (m.right) {
                const right = document.createElement('ins');
                right.textContent = m.right;
                change.append(m.wrong ? ' → ' : '', right);
            }
            const type = document.createElement('span');
            type.className = `mistake-type ${m.type}`;
            type.textContent = m.type;
            change.append(' ', type);
            li.append(change);
            if (m.why) {
                const why = document.createElement('p');
                why.textContent = m.why;
                li.append(why);
            }
            mistakesEl.append(li);
        });
        show(mistakesBlock, mistakes.length > 0);
    }

    function showFeedback(result, answer) {
        const item = currentItem();
        const sentence = mode === 'grammar' ? answer : learnerSentence(item, answer);
        answered = true;

        feedback.className = `verdict-${result.verdict}`;
        verdictEl.textContent = verdictTitle(result);

        const corrected = result.corrected || '';
        const showCorrected = corrected && (normalize(corrected) !== normalize(sentence) || mode === 'fill_blank');
        correctedEl.textContent = corrected;
        show(correctedBlock, Boolean(showCorrected));

        renderMistakes(result.mistakes || []);
        setText(vocabEl, result.vocab_note);
        setText(explanationEl, result.explanation && `Explanation: ${result.explanation}`);
        setText(tipEl, result.tip && `Tip: ${result.tip}`);

        const reference = result.reference || '';
        const showReference = reference && result.verdict !== 'correct'
            && normalize(reference) !== normalize(corrected);
        referenceLabel.textContent = MODES[mode].referenceLabel;
        referenceEl.textContent = reference;
        show(referenceBlock, Boolean(showReference));

        sourceEl.textContent = SOURCES[result.source] || '';

        const blank = document.getElementById('blank-slot');
        if (blank) {
            blank.textContent = answer;
            blank.classList.add('filled');
        }

        // Free writing checks are not exercises, so they stay out of the score.
        if (mode !== 'grammar' && result.verdict in score) {
            score[result.verdict] += 1;
            Object.entries(score).forEach(([key, value]) => { scoreEls[key].textContent = value; });
            show(sessionScore, true);
        }
        showPoints(mode === 'grammar' ? null : result.points, result.verdict);
        vocabGoal.render(result.progress);

        answerInput.disabled = true;
        show(form, false);
        show(feedback, true);
        nextBtn.focus();
    }

    async function checkAnswer() {
        const answer = answerInput.value.trim();
        if (!answer || busy || answered) return;
        setBusy(true, 'Checking...');
        showNotice('');
        try {
            const result = mode === 'grammar'
                ? await postJSON('/api/grammar_check', { text: answer })
                : await postJSON('/api/practice/check', { mode, item: currentItem(), answer, utc_offset: goals.utcOffset() });
            showFeedback(result, answer);
        } catch (error) {
            showNotice(error.message, true);
        } finally {
            setBusy(false, 'Check');
        }
    }

    async function giveUp() {
        const item = currentItem();
        if (!item || busy || answered) return;
        answered = true;
        const reference = mode === 'fill_blank' ? item.answer
            : mode === 'fix_mistake' ? item.correct_sentence : item.english_reference;
        showFeedback({
            verdict: 'incorrect',
            source: '',
            reference: mode === 'fill_blank' ? item.sentence.replace(BLANK, item.answer) : reference,
            explanation: item.explanation_vi,
            mistakes: [],
        }, mode === 'fill_blank' ? item.answer : '');
        verdictEl.textContent = 'Here is the answer.';
        // Showing the answer counts as a wrong answer, for the word and the points.
        try {
            const result = await postJSON('/api/practice/give_up', { mode, item, utc_offset: goals.utcOffset() });
            showPoints(result.points, 'incorrect');
            vocabGoal.render(result.progress);
        } catch (error) {
            console.error('Failed to record the answer:', error);
        }
    }

    function next() {
        if (mode === 'grammar') {
            showGrammarChecker();
        } else if (index + 1 < queue.length) {
            index += 1;
            showExercise();
        } else {
            loadExercises();
        }
    }

    // --- 6. EVENT LISTENERS ---

    document.querySelectorAll('input[name="mode"]').forEach(radio => {
        radio.addEventListener('change', () => show(topicsSection, selectedMode() !== 'grammar'));
    });

    startBtn.addEventListener('click', () => {
        mode = selectedMode();
        topicIds = selectedTopicIds();
        remember(MODE_KEY, mode);
        if (mode !== 'grammar') remember(TOPICS_KEY, topicIds);
        show(intro, false);
        showNotice('');
        if (mode === 'grammar') {
            showGrammarChecker();
        } else {
            loadExercises();
        }
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        checkAnswer();
    });

    // Enter checks a one-line answer; longer answers use Ctrl+Enter so Enter can
    // still start a new line.
    answerInput.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' || e.shiftKey) return;
        if (MODES[mode].rows === 1 || e.ctrlKey || e.metaKey) {
            e.preventDefault();
            checkAnswer();
        }
    });

    hintBtn.addEventListener('click', () => {
        hintText.textContent = hintBtn.dataset.hint;
        show(hintText, hintText.classList.contains('hidden'));
    });

    giveUpBtn.addEventListener('click', giveUp);
    nextBtn.addEventListener('click', next);

    // N moves on once an answer has been marked. The answer box is locked by
    // then, so the key cannot be a letter meant for it.
    document.addEventListener('keydown', (e) => {
        if (e.key.toLowerCase() !== 'n' || e.ctrlKey || e.metaKey || e.altKey) return;
        if (e.target.closest('input:not([type="radio"]):not([type="checkbox"]), textarea:not(:disabled)')) return;
        if (answered && !busy) {
            e.preventDefault();
            next();
        }
    });

    // --- 7. INITIALIZATION ---
    const savedMode = remembered(MODE_KEY, null);
    if (typeof savedMode === 'string' && Object.hasOwn(MODES, savedMode)) {
        document.querySelector(`input[name="mode"][value="${savedMode}"]`).checked = true;
        show(topicsSection, savedMode !== 'grammar');
    }
    loadTopics();
    vocabGoal.load();
});
