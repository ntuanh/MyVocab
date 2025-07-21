document.addEventListener('DOMContentLoaded', () => {
    // --- 1. get all of ELEMENTS from DOM ---
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');

    // Panel left
    const imagePanel = document.getElementById('image-panel');
    const saveBtn = document.getElementById('save-btn');

    // Panel center
    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');

    // Panel right
    const ipaEl = document.getElementById('pronunciation-ipa');
    const synonymListEl = document.getElementById('synonym-list');
    const familyListEl = document.getElementById('family-list');

    // Modal save words
    const saveModal = document.getElementById('save-modal');
    const modalWordEl = document.getElementById('modal-word-to-save');
    const modalTopicList = document.getElementById('modal-topic-list');
    const newTopicInput = document.getElementById('new-topic-input');
    const addTopicBtn = document.getElementById('add-topic-btn');
    const cancelSaveBtn = document.getElementById('modal-btn-cancel-save');
    const confirmSaveBtn = document.getElementById('modal-btn-confirm-save');

    // Toast Notification
    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');
    let toastTimeout;

    let currentWordData = null;

    // --- 2. Define handle functions ---

    function showToast(message, type = 'success') {
        clearTimeout(toastTimeout);
        toastMessage.textContent = message;
        toast.className = 'toast';
        toast.classList.add(type, 'show');
        toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    function updateUI(data) {
        currentWordData = data;

        definitionEl.textContent = data.english_definition || 'N/A';
        exampleEl.textContent = data.example || 'N/A';
        vietnameseMeaningEl.textContent = data.vietnamese_meaning || 'N/A';
        ipaEl.textContent = data.pronunciation_ipa || 'N/A';

        vietnamesePanel.classList.add('hidden');
        vietnamesePanel.classList.remove('revealed');

        const createTagList = (element, list) => {
            element.innerHTML = '';
            if (list && list.length > 0) {
                list.forEach(item => {
                    const tag = document.createElement('span');
                    tag.className = 'tag';
                    tag.textContent = item;
                    element.appendChild(tag);
                });
            } else {
                element.innerHTML = 'N/A';
            }
        };

        createTagList(synonymListEl, data.synonyms);
        createTagList(familyListEl, data.family_words);

        imagePanel.innerHTML = ''; // clean
        if (data.image_url) {
            const img = document.createElement('img');
            img.id = 'word-image';
            img.src = data.image_url;
            img.alt = `Image for '${data.word}'`;
            imagePanel.appendChild(img);
            imagePanel.style.backgroundColor = 'transparent';
        } else {
            const placeholder = document.createElement('p');
            placeholder.textContent = 'No Image Found';
            imagePanel.appendChild(placeholder);
            imagePanel.style.backgroundColor = 'var(--panel-blue)';
        }

        if (data.is_saved) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
        } else {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
        }
    }

    function resetUI(message) {
        currentWordData = null;
        definitionEl.textContent = message;
        ['example-sentence', 'vietnamese-meaning', 'pronunciation-ipa'].forEach(id => {
            document.getElementById(id).textContent = '...';
        });
        ['synonym-list', 'family-list'].forEach(id => {
            document.getElementById(id).innerHTML = '';
        });
        imagePanel.innerHTML = '<p>Image Placeholder</p>';
        imagePanel.style.backgroundColor = 'var(--panel-blue)';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
    }

    async function showSaveModal() {
        if (!currentWordData) return;
        modalWordEl.textContent = currentWordData.word;

        try {
            const response = await fetch('/get_topics');
            const topics = await response.json();

            modalTopicList.innerHTML = '';
            topics.forEach(topic => {
                const topicDiv = document.createElement('div');
                topicDiv.className = 'topic-checkbox';
                topicDiv.innerHTML = `
                    <input type="checkbox" id="modal-topic-${topic.id}" name="modal-topics" value="${topic.id}">
                    <label for="modal-topic-${topic.id}">${topic.name}</label>
                `;
                modalTopicList.appendChild(topicDiv);
            });
            saveModal.classList.remove('hidden');
        } catch (error) {
            showToast("Could not load topics.", "error");
        }
    }

    // --- 3. assign events ---

    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const word = wordInput.value.trim();
        if (!word) return;
        resetUI('Searching...');
        try {
            const response = await fetch('/lookup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: word })
            });
            const data = await response.json();
            if (response.ok) {
                updateUI(data);
            } else {
                resetUI(data.error || 'An unknown error occurred.');
            }
        } catch (error) {
            resetUI('Failed to connect to the server.');
        }
    });

    vietnamesePanel.addEventListener('click', () => {
        if (vietnamesePanel.classList.contains('hidden')) {
            vietnamesePanel.classList.remove('hidden');
            vietnamesePanel.classList.add('revealed');
        }
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
        try {
            const response = await fetch('/add_topic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic_name: newTopicName })
            });
            const newTopic = await response.json();
            if (newTopic && newTopic.id) {
                const topicDiv = document.createElement('div');
                topicDiv.className = 'topic-checkbox';
                topicDiv.innerHTML = `
                    <input type="checkbox" id="modal-topic-${newTopic.id}" name="modal-topics" value="${newTopic.id}" checked>
                    <label for="modal-topic-${newTopic.id}">${newTopic.name}</label>
                `;
                modalTopicList.appendChild(topicDiv);
                newTopicInput.value = '';
            }
        } catch (error) {
            showToast("Failed to add topic.", "error");
        }
    });

    confirmSaveBtn.addEventListener('click', async () => {
        const selectedCheckboxes = document.querySelectorAll('input[name="modal-topics"]:checked');
        const selectedTopicIds = Array.from(selectedCheckboxes).map(cb => cb.value);
        try {
            const response = await fetch('/save_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    word_data: currentWordData,
                    topic_ids: selectedTopicIds
                })
            });
            const result = await response.json();
            showToast(result.message, result.status === 'error' ? 'error' : 'success');
            saveModal.classList.add('hidden');
            if (result.status !== 'error') {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
            }
        } catch (error) {
            showToast("Failed to save.", "error");
        }
    });

    cancelSaveBtn.addEventListener('click', () => {
        saveModal.classList.add('hidden');
    });
});
