// This event listener ensures that all the HTML is loaded before this script runs.
document.addEventListener('DOMContentLoaded', () => {

    // --- 1. ELEMENT SELECTION ---
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');
    const imagePanel = document.getElementById('image-panel');
    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');
    const ipaEl = document.getElementById('pronunciation-ipa');
    const synonymListEl = document.getElementById('synonym-list');
    const familyListEl = document.getElementById('family-list');
    const saveBtn = document.getElementById('save-btn');
    const viewDataBtn = document.getElementById('view-data-btn');

    // Save Word Modal
    const saveModal = document.getElementById('save-modal');
    const modalWordEl = document.getElementById('modal-word-to-save');
    const modalTopicList = document.getElementById('modal-topic-list');
    const newTopicInput = document.getElementById('new-topic-input');
    const addTopicBtn = document.getElementById('add-topic-btn');
    const cancelSaveBtn = document.getElementById('modal-btn-cancel-save');
    const confirmSaveBtn = document.getElementById('modal-btn-confirm-save');

    // Password Modal
    const passwordModalOverlay = document.getElementById('password-modal-overlay');
    const passwordInput = document.getElementById('password-input');
    const submitPasswordBtn = document.getElementById('submit-password-btn');
    const cancelPasswordBtn = document.getElementById('cancel-password-btn');
    const passwordErrorEl = document.getElementById('password-error');

    // Toast Notification
    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');
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

    function updateUI(data) {
        currentWordData = data;
        definitionEl.textContent = data.english_definition || 'N/A';
        exampleEl.textContent = data.example || 'N/A';
        vietnameseMeaningEl.textContent = data.vietnamese_meaning || 'N/A';
        ipaEl.textContent = data.pronunciation_ipa || 'N/A';

        // Restore the "Click to reveal" functionality
//        vietnamesePanel.classList.add('hidden');
//        vietnamesePanel.classList.remove('revealed');

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

        imagePanel.innerHTML = '';
        if (data.image_url) {
            const img = document.createElement('img');
            img.id = 'word-image';
            img.src = data.image_url;
            img.alt = `Image for '${data.word}'`;
            imagePanel.appendChild(img);
        } else {
            const placeholder = document.createElement('p');
            placeholder.textContent = 'No Image Found';
            imagePanel.appendChild(placeholder);
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
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
    }

    // [FIX] Define the showSaveModal function properly
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
            // [FIX] Use the standardized class to show the modal
            saveModal.classList.add('visible');
        } catch (error) {
            showToast("Could not load topics.", "error");
        }
    }

    // --- 3. EVENT LISTENERS ---

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
        vietnamesePanel.classList.toggle('hidden');
        vietnamesePanel.classList.toggle('revealed');
    });

    // --- [FIX] Correctly attach event listener for Save Button ---
    if (saveBtn) {
        console.log("SUCCESS: Attaching event listener to Save Word button."); // Debug log
        saveBtn.addEventListener('click', () => {
            console.log("EVENT: Save Word button clicked!"); // Debug log
            if (!currentWordData || !currentWordData.word) {
                console.log("DEBUG: Save condition failed. currentWordData is missing."); // Debug log
                showToast('Please search for a word first!', 'error');
                return;
            }
            console.log("DEBUG: Save condition passed. Showing save modal."); // Debug log
            showSaveModal();
        });
    } else {
        console.error("ERROR: Could not find element with id='save-btn'"); // Debug log
    }

    // --- Save Word Modal Events ---
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
                body: JSON.stringify({ word_data: currentWordData, topic_ids: selectedTopicIds })
            });
            const result = await response.json();
            showToast(result.message, result.status === 'error' ? 'error' : 'success');
            // [FIX] Use the standardized class to hide the modal
            saveModal.classList.remove('visible');
            if (result.status !== 'error') {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
            }
        } catch (error) {
            showToast("Failed to save word.", "error");
        }
    });

    cancelSaveBtn.addEventListener('click', () => {
        // [FIX] Use the standardized class to hide the modal
        saveModal.classList.remove('visible');
    });

    // --- Password Modal Logic ---
    function showPasswordModal() {
        passwordInput.value = '';
        passwordErrorEl.textContent = '';
        passwordModalOverlay.classList.add('visible');
        passwordInput.focus();
    }

    function hidePasswordModal() {
        passwordModalOverlay.classList.remove('visible');
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
                window.location.href = viewDataBtn.href;
            } else {
                passwordErrorEl.textContent = 'Incorrect password. Please try again.';
            }
        } catch (error) {
            console.error("Error verifying password:", error);
            passwordErrorEl.textContent = 'An error occurred. Please try again.';
        }
    }

    if (viewDataBtn) {
        viewDataBtn.addEventListener('click', (event) => {
            event.preventDefault();
            showPasswordModal();
        });
    }

    if (cancelPasswordBtn) cancelPasswordBtn.addEventListener('click', hidePasswordModal);
    if (submitPasswordBtn) submitPasswordBtn.addEventListener('click', handlePasswordSubmit);
    if (passwordModalOverlay) {
        passwordModalOverlay.addEventListener('click', (event) => {
            if (event.target === passwordModalOverlay) {
                hidePasswordModal();
            }
        });
    }
    if (passwordInput) {
        passwordInput.addEventListener('keyup', (event) => {
            if (event.key === 'Enter') {
                handlePasswordSubmit();
            }
        });
    }

}); // End of DOMContentLoaded