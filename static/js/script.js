document.addEventListener('DOMContentLoaded', () => {

    // --- 1. ELEMENT SELECTION ---
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');
    const recentWordsEl = document.getElementById('recent-words');
    const statusEl = document.getElementById('lookup-status');

    const wordCard = document.getElementById('word-card');
    const wordTitleEl = document.getElementById('word-title');
    const imagePanel = document.getElementById('image-panel');
    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');
    const ipaEl = document.getElementById('pronunciation-ipa');
    const synonymListEl = document.getElementById('synonym-list');
    const familyListEl = document.getElementById('family-list');
    const saveBtn = document.getElementById('save-btn');

    // Save Word Modal
    const saveModal = document.getElementById('save-modal');
    const modalWordEl = document.getElementById('modal-word-to-save');
    const modalTopicList = document.getElementById('modal-topic-list');
    const newTopicInput = document.getElementById('new-topic-input');
    const addTopicBtn = document.getElementById('add-topic-btn');
    const cancelSaveBtn = document.getElementById('modal-btn-cancel-save');
    const confirmSaveBtn = document.getElementById('modal-btn-confirm-save');
    const aiSaveBtn = document.getElementById('ai-save-btn');
    const aiTasksEl = document.getElementById('ai-tasks');

    // Password Modal
    const passwordModalOverlay = document.getElementById('password-modal-overlay');
    const passwordInput = document.getElementById('password-input');
    const submitPasswordBtn = document.getElementById('submit-password-btn');
    const cancelPasswordBtn = document.getElementById('cancel-password-btn');
    const passwordErrorEl = document.getElementById('password-error');

    // Toast Notification
    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');

    // Recent searches live in this browser only, newest first.
    const RECENT_KEY = 'myvocab-recent';
    const RECENT_MAX = 10;

    let toastTimeout;
    let currentWordData = null;

    // --- 2. HELPER FUNCTIONS ---

    function showToast(message, type = 'success') {
        clearTimeout(toastTimeout);
        toastMessage.textContent = message;
        toast.className = 'toast';
        toast.classList.add(type, 'show');
        toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    // A field the lookup could not fill comes back as 'N/A'; treat it as missing
    // so its row is hidden instead of printed.
    function present(value) {
        return Boolean(value) && value !== 'N/A';
    }

    function showRow(id, visible) {
        document.getElementById(id).classList.toggle('hidden', !visible);
    }

    // Returns whether there was anything to show.
    // Each chip shows its English meaning when pointed at or focused (glosses.js).
    function fillTags(element, list) {
        element.replaceChildren(...(list || []).map(item => {
            const tag = document.createElement('span');
            tag.className = 'tag has-gloss';
            tag.textContent = item;
            tag.dataset.gloss = item;
            tag.tabIndex = 0;
            return tag;
        }));
        return Boolean(list && list.length);
    }

    function setStatus(message, isError = false) {
        statusEl.textContent = message || '';
        statusEl.classList.toggle('error', isError);
        statusEl.classList.toggle('hidden', !message);
    }

    function setSaved(isSaved) {
        saveBtn.disabled = isSaved;
        saveBtn.innerHTML = isSaved
            ? '<i class="fas fa-check"></i> Already Saved'
            : '<i class="fas fa-save"></i> Save Word';
    }

    function setRevealed(revealed) {
        vietnamesePanel.classList.toggle('is-hidden', !revealed);
        vietnamesePanel.classList.toggle('is-revealed', revealed);
        vietnamesePanel.setAttribute('aria-pressed', String(revealed));
    }

    function toggleReveal() {
        setRevealed(vietnamesePanel.classList.contains('is-hidden'));
    }

    function updateUI(data) {
        currentWordData = data;
        setStatus('');

        wordTitleEl.textContent = data.word;
        ipaEl.textContent = present(data.pronunciation_ipa) ? data.pronunciation_ipa : '';
        vietnameseMeaningEl.textContent = data.vietnamese_meaning || 'N/A';
        definitionEl.textContent = data.english_definition || 'N/A';
        exampleEl.textContent = present(data.example) ? data.example : '';
        showRow('example-panel', present(data.example));
        showRow('synonym-panel', fillTags(synonymListEl, data.synonyms));
        showRow('family-panel', fillTags(familyListEl, data.family_words));
        if (window.MyVocabGlosses) {
            window.MyVocabGlosses.hide();
            window.MyVocabGlosses.prepare([...(data.synonyms || []), ...(data.family_words || [])]);
        }

        // Every new word starts with its meaning hidden, so you can test yourself first.
        setRevealed(false);

        imagePanel.replaceChildren();
        if (data.image_url) {
            const img = document.createElement('img');
            img.id = 'word-image';
            img.src = data.image_url;
            img.alt = `Image for '${data.word}'`;
            imagePanel.appendChild(img);
        }
        imagePanel.classList.toggle('hidden', !data.image_url);

        setSaved(Boolean(data.is_saved));
        wordCard.classList.remove('hidden');
        addRecent(data.word);
    }

    function resetUI(message, isError = false) {
        currentWordData = null;
        wordCard.classList.add('hidden');
        setStatus(message, isError);
    }

    // --- 3. RECENT SEARCHES ---

    // Storage can be blocked (private window, site data off); the page then
    // simply has no history.
    function loadRecent() {
        try {
            const list = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
            return Array.isArray(list) ? list.filter(word => typeof word === 'string') : [];
        } catch (error) {
            return [];
        }
    }

    function renderRecent(list) {
        recentWordsEl.replaceChildren();
        recentWordsEl.classList.toggle('hidden', list.length === 0);
        if (!list.length) return;

        const label = document.createElement('span');
        label.className = 'recent-label';
        label.textContent = 'Recent';
        recentWordsEl.append(label);
        list.forEach(word => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'recent-chip';
            chip.textContent = word;
            chip.addEventListener('click', () => lookup(word));
            recentWordsEl.append(chip);
        });
    }

    function addRecent(word) {
        const list = [word, ...loadRecent().filter(w => w !== word)].slice(0, RECENT_MAX);
        try {
            localStorage.setItem(RECENT_KEY, JSON.stringify(list));
        } catch (error) { /* not remembered, still shown below */ }
        renderRecent(list);
    }

    // --- 4. LOOKUP ---

    async function lookup(word) {
        wordInput.value = word;
        resetUI('Searching...');
        try {
            const response = await fetch('/api/lookup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word: word })
            });
            const data = await response.json();
            if (response.ok) {
                updateUI(data);
            } else {
                resetUI(data.error || 'An unknown error occurred.', true);
                // A retryable failure means the upstream dictionary stalled, not
                // that the word is missing -- searching again usually works.
                if (data.retryable) {
                    showToast('Dictionary service is busy. Please search again.', 'error');
                }
            }
        } catch (error) {
            resetUI('Failed to connect to the server.', true);
        }
    }

    searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const word = wordInput.value.trim();
        if (word) lookup(word);
    });

    vietnamesePanel.addEventListener('click', toggleReveal);
    vietnamesePanel.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleReveal();
        }
    });

    // --- 5. SAVE WORD MODAL ---

    function topicCheckbox(topic, checked) {
        const row = document.createElement('div');
        row.className = 'topic-checkbox';
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.id = `modal-topic-${topic.id}`;
        box.name = 'modal-topics';
        box.value = topic.id;
        box.checked = checked;
        const label = document.createElement('label');
        label.htmlFor = box.id;
        label.textContent = topic.name;
        row.append(box, label);
        return row;
    }

    // Creates a topic and adds it to the list, ticked. Returns its row, or null.
    async function createTopic(name) {
        try {
            const response = await fetch('/api/add_topic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic_name: name })
            });
            const newTopic = await response.json();
            if (newTopic && newTopic.id) {
                const row = topicCheckbox(newTopic, true);
                modalTopicList.appendChild(row);
                return row;
            }
        } catch (error) { /* reported below */ }
        showToast("Failed to add topic.", "error");
        return null;
    }

    function selectedTopicIds() {
        return Array.from(document.querySelectorAll('input[name="modal-topics"]:checked'), box => box.value);
    }

    async function showSaveModal() {
        if (!currentWordData) return;
        modalWordEl.textContent = currentWordData.word;
        try {
            const response = await fetch('/api/get_topics');
            const topics = await response.json();
            modalTopicList.replaceChildren(...topics.map(topic => topicCheckbox(topic, false)));
            saveModal.classList.add('visible');
        } catch (error) {
            showToast("Could not load topics.", "error");
        }
    }

    function hideSaveModal() {
        saveModal.classList.remove('visible');
    }

    // --- 5a. SAVE, AND LET AI PICK THE TOPIC ---
    // The dialog closes at once and a small card in the corner follows the
    // word while the server saves it and AI files it under one topic. The page
    // stays free meanwhile, so the next word can be looked up straight away.

    function strong(text) {
        const element = document.createElement('strong');
        element.textContent = text;
        return element;
    }

    function aiTaskCard() {
        const card = document.createElement('div');
        card.className = 'ai-task';
        const icon = document.createElement('i');
        icon.setAttribute('aria-hidden', 'true');
        const text = document.createElement('p');
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'ai-task-close';
        close.setAttribute('aria-label', 'Dismiss');
        close.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';
        close.addEventListener('click', () => card.remove());
        card.append(icon, text, close);
        aiTasksEl.appendChild(card);

        const ICONS = { working: 'fas fa-spinner fa-spin', done: 'fas fa-check-circle', failed: 'fas fa-exclamation-circle' };
        return function show(state, parts, note) {
            card.classList.toggle('failed', state === 'failed');
            icon.className = ICONS[state];
            text.replaceChildren(...parts);
            if (note) {
                const line = document.createElement('span');
                line.className = 'ai-task-note';
                line.textContent = note;
                text.append(line);
            }
            // A finished card leaves by itself; a problem stays a little longer.
            if (state !== 'working') setTimeout(() => card.remove(), state === 'done' ? 6000 : 12000);
        };
    }

    async function saveWithAI(wordData, topicIds) {
        const show = aiTaskCard();
        const stillShowing = () => currentWordData === wordData;
        show('working', ['Saving ', strong(wordData.word), ' and picking its topic...']);
        saveBtn.disabled = true;  // no second save of this word while it is on its way
        try {
            const response = await fetch('/api/save_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word_data: wordData, topic_ids: topicIds, ai_topic: true })
            });
            const result = await response.json();
            if (!response.ok || result.status === 'error') throw new Error(result.message || result.error);
            if (stillShowing()) setSaved(true);

            const ai = result.ai || {};
            if (ai.topic) {
                show('done', [strong(wordData.word), ' saved to ', strong(ai.topic)],
                     ai.is_new ? 'A new topic, made for this word.' : '');
            } else {
                show('failed', [strong(wordData.word), topicIds.length ? ' saved to your topics.' : ' saved without a topic.'],
                     ai.error || 'AI could not choose a topic.');
            }
        } catch (error) {
            if (stillShowing()) setSaved(false);
            show('failed', ['Could not save ', strong(wordData.word), '.'], 'Try the Save button again.');
        }
    }

    aiSaveBtn.addEventListener('click', () => {
        const wordData = currentWordData;
        const topicIds = selectedTopicIds();
        hideSaveModal();
        saveWithAI(wordData, topicIds);
        // Ready for the next word at once.
        wordInput.focus();
        wordInput.select();
    });

    saveBtn.addEventListener('click', () => {
        if (!currentWordData || !currentWordData.word) {
            showToast('Please search for a word first!', 'error');
            return;
        }
        showSaveModal();
    });

    addTopicBtn.addEventListener('click', async () => {
        const newTopicName = newTopicInput.value.trim();
        if (!newTopicName) return;
        if (await createTopic(newTopicName)) newTopicInput.value = '';
    });

    confirmSaveBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/save_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word_data: currentWordData, topic_ids: selectedTopicIds() })
            });
            const result = await response.json();
            showToast(result.message, result.status === 'error' ? 'error' : 'success');
            hideSaveModal();
            if (result.status !== 'error') setSaved(true);
        } catch (error) {
            showToast("Failed to save word.", "error");
        }
    });

    cancelSaveBtn.addEventListener('click', () => {
        hideSaveModal();
    });

    // --- 6. PASSWORD MODAL (My Words) ---

    // The server sends you here with ?unlock=1 when you open My Words before
    // entering the password.
    const wantsUnlock = new URLSearchParams(window.location.search).has('unlock');

    function showPasswordModal() {
        passwordInput.value = '';
        passwordErrorEl.textContent = '';
        passwordModalOverlay.classList.add('visible');
        passwordInput.focus();
    }

    function hidePasswordModal() {
        passwordModalOverlay.classList.remove('visible');
        // Drop ?unlock from the address so a reload does not ask again.
        if (wantsUnlock) history.replaceState(null, '', window.location.pathname);
    }

    async function handlePasswordSubmit() {
        const password = passwordInput.value;
        if (!password) {
            passwordErrorEl.textContent = 'Password cannot be empty.';
            return;
        }
        try {
            const response = await fetch('/api/verify_password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: password }),
            });
            if (response.ok) {
                window.location.href = '/data';
            } else {
                passwordErrorEl.textContent = 'Incorrect password. Please try again.';
            }
        } catch (error) {
            console.error("Error verifying password:", error);
            passwordErrorEl.textContent = 'An error occurred. Please try again.';
        }
    }

    cancelPasswordBtn.addEventListener('click', hidePasswordModal);
    submitPasswordBtn.addEventListener('click', handlePasswordSubmit);
    passwordModalOverlay.addEventListener('click', (event) => {
        if (event.target === passwordModalOverlay) hidePasswordModal();
    });
    passwordInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') handlePasswordSubmit();
    });

    // --- 7. KEYBOARD SHORTCUTS: / search, S save, R reveal, Esc close ---

    function isTyping(event) {
        return event.target.closest('input, textarea, select')
            || event.ctrlKey || event.metaKey || event.altKey;
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            if (saveModal.classList.contains('visible')) hideSaveModal();
            if (passwordModalOverlay.classList.contains('visible')) hidePasswordModal();
            return;
        }
        if (isTyping(event) || document.querySelector('.modal-overlay.visible')) return;

        const key = event.key.toLowerCase();
        if (key === '/') {
            event.preventDefault();
            wordInput.focus();
            wordInput.select();
        } else if (key === 's' && currentWordData && !saveBtn.disabled) {
            event.preventDefault();
            showSaveModal();
        } else if (key === 'r' && currentWordData) {
            toggleReveal();
        }
    });

    // --- 8. INITIALIZATION ---
    renderRecent(loadRecent());
    if (wantsUnlock) showPasswordModal();
    else wordInput.focus();
});
