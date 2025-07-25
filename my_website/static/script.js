// This event listener ensures that all the HTML is loaded before this script runs.
document.addEventListener('DOMContentLoaded', () => {

    // --- 1. ELEMENT SELECTION ---
    // Get all necessary elements from the HTML document once and store them in variables.
    
    // Main search components
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');

    // Display panels
    const imagePanel = document.getElementById('image-panel');
    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');
    const ipaEl = document.getElementById('pronunciation-ipa');
    const synonymListEl = document.getElementById('synonym-list');
    const familyListEl = document.getElementById('family-list');

    // Action buttons
    const saveBtn = document.getElementById('save-btn');
    const viewDataBtn = document.getElementById('view-data-btn');

    // Save Word Modal elements
    const saveModal = document.getElementById('save-modal');
    const modalWordEl = document.getElementById('modal-word-to-save');
    const modalTopicList = document.getElementById('modal-topic-list');
    const newTopicInput = document.getElementById('new-topic-input');
    const addTopicBtn = document.getElementById('add-topic-btn');
    const cancelSaveBtn = document.getElementById('modal-btn-cancel-save');
    const confirmSaveBtn = document.getElementById('modal-btn-confirm-save');

    // Password Modal elements
    const passwordModalOverlay = document.getElementById('password-modal-overlay');
    const passwordInput = document.getElementById('password-input');
    const submitPasswordBtn = document.getElementById('submit-password-btn');
    const cancelPasswordBtn = document.getElementById('cancel-password-btn');
    const passwordErrorEl = document.getElementById('password-error');

    // Toast Notification elements
    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');
    let toastTimeout; // Variable to hold the timer for the toast

    // A global variable to store the data of the currently looked-up word.
    let currentWordData = null;


    // --- 2. HELPER FUNCTIONS ---
    // Reusable functions for common tasks like showing notifications, updating the UI, etc.

    /**
     * Shows a toast notification with a message.
     * @param {string} message The message to display.
     * @param {string} type The type of toast ('success' or 'error').
     */
    function showToast(message, type = 'success') {
        clearTimeout(toastTimeout); // Clear any existing toast timer
        toastMessage.textContent = message;
        toast.className = 'toast'; // Reset classes
        toast.classList.add(type, 'show');
        toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 3000); // Hide after 3 seconds
    }

    /**
     * Populates the UI with data received from the API.
     * @param {object} data The word data object.
     */
    function updateUI(data) {
        currentWordData = data; // Store the current word's data globally

        // Update text content
        definitionEl.textContent = data.english_definition || 'N/A';
        exampleEl.textContent = data.example || 'N/A';
        vietnameseMeaningEl.textContent = data.vietnamese_meaning || 'N/A';
        ipaEl.textContent = data.pronunciation_ipa || 'N/A';

        // Hide the Vietnamese meaning initially
        vietnamesePanel.classList.add('hidden');
        vietnamesePanel.classList.remove('revealed');

        // Helper function to create lists of tags (for synonyms and family words)
        const createTagList = (element, list) => {
            element.innerHTML = ''; // Clear previous content
            if (list && list.length > 0) {
                list.forEach(item => {
                    const tag = document.createElement('span');
                    tag.className = 'tag';
                    tag.textContent = item;
                    element.appendChild(tag);
                });
            } else {
                element.innerHTML = 'N/A'; // Show N/A if the list is empty
            }
        };

        createTagList(synonymListEl, data.synonyms);
        createTagList(familyListEl, data.family_words);

        // Update the image panel
        imagePanel.innerHTML = ''; // Clear previous content
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
        }
        
        // Update the "Save Word" button's state
        if (data.is_saved) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
        } else {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
        }
    }

    /**
     * Resets the UI to its initial state, showing a specific message.
     * @param {string} message The message to show in the definition panel.
     */
    function resetUI(message) {
        currentWordData = null; // Clear current word data
        definitionEl.textContent = message;
        // Reset other panels
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


    // --- 3. EVENT LISTENERS ---
    // This section connects user actions (like clicks and form submissions) to functions.

    // Handle the main word search
    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault(); // Prevent the form from reloading the page
        const word = wordInput.value.trim();
        if (!word) return;

        resetUI('Searching...'); // Show a loading message
        try {
            const response = await fetch('/lookup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: word })
            });
            const data = await response.json();
            if (response.ok) {
                updateUI(data); // If successful, update the UI with new data
            } else {
                resetUI(data.error || 'An unknown error occurred.'); // Show error message
            }
        } catch (error) {
            resetUI('Failed to connect to the server.'); // Handle network errors
        }
    });

    // Reveal Vietnamese meaning on click
    vietnamesePanel.addEventListener('click', () => {
        vietnamesePanel.classList.toggle('hidden');
        vietnamesePanel.classList.toggle('revealed');
    });

    // --- Save Word Modal Logic ---

    // Show the "Save Word" modal
    saveBtn.addEventListener('click', async () => {
        if (!currentWordData || !currentWordData.word) {
            showToast('Please search for a word first!', 'error');
            return;
        }
        
        modalWordEl.textContent = currentWordData.word;
        try {
            // Fetch the list of topics from the backend
            const response = await fetch('/get_topics');
            const topics = await response.json();

            modalTopicList.innerHTML = ''; // Clear old topic list
            topics.forEach(topic => {
                const topicDiv = document.createElement('div');
                topicDiv.className = 'topic-checkbox';
                topicDiv.innerHTML = `
                    <input type="checkbox" id="modal-topic-${topic.id}" name="modal-topics" value="${topic.id}">
                    <label for="modal-topic-${topic.id}">${topic.name}</label>
                `;
                modalTopicList.appendChild(topicDiv);
            });
            saveModal.classList.remove('hidden'); // Show the modal
        } catch (error) {
            showToast("Could not load topics.", "error");
        }
    });

    // Add a new topic from the modal
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
                // Add the new topic to the list and check it by default
                const topicDiv = document.createElement('div');
                topicDiv.className = 'topic-checkbox';
                topicDiv.innerHTML = `
                    <input type="checkbox" id="modal-topic-${newTopic.id}" name="modal-topics" value="${newTopic.id}" checked>
                    <label for="modal-topic-${newTopic.id}">${newTopic.name}</label>
                `;
                modalTopicList.appendChild(topicDiv);
                newTopicInput.value = ''; // Clear the input field
            }
        } catch (error) {
            showToast("Failed to add topic.", "error");
        }
    });
    
    // Confirm saving the word with selected topics
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
            saveModal.classList.remove('visible'); // Hide the modal
            if (result.status !== 'error') {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
            }
        } catch (error) {
            showToast("Failed to save word.", "error");
        }
    });
    
    // Cancel saving and hide the modal
    cancelSaveBtn.addEventListener('click', () => {
        saveModal.classList.remove('visible');
    });

    // --- Password Modal Logic ---
    
    function showPasswordModal() {
        passwordInput.value = ''; // Clear previous password
        passwordErrorEl.textContent = ''; // Clear previous error
        passwordModalOverlay.classList.add('visible'); // Show the modal
        passwordInput.focus(); // Focus on the input field
    }

    function hidePasswordModal() {
        passwordModalOverlay.classList.remove('visible'); // Hide the modal
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
                // If password is correct, redirect to the data page
                window.location.href = viewDataBtn.href;
            } else {
                // If password is incorrect
                passwordErrorEl.textContent = 'Incorrect password. Please try again.';
            }
        } catch (error) {
            console.error("Error verifying password:", error);
            passwordErrorEl.textContent = 'An error occurred. Please try again.';
        }
    }

    // Show the password modal when "View Data" is clicked
    if (viewDataBtn) {
        viewDataBtn.addEventListener('click', (event) => {
            event.preventDefault(); // Prevent default link behavior
            showPasswordModal();
        });
    }

    // Add event listeners for the password modal buttons and overlay
    if (cancelPasswordBtn) cancelPasswordBtn.addEventListener('click', hidePasswordModal);
    if (submitPasswordBtn) submitPasswordBtn.addEventListener('click', handlePasswordSubmit);
    if (passwordModalOverlay) {
        passwordModalOverlay.addEventListener('click', (event) => {
            // Close modal only if the click is on the dark background
            if (event.target === passwordModalOverlay) {
                hidePasswordModal();
            }
        });
    }
    // Allow submitting with the "Enter" key
    if (passwordInput) {
        passwordInput.addEventListener('keyup', (event) => {
            if (event.key === 'Enter') {
                handlePasswordSubmit();
            }
        });
    }

}); // End of DOMContentLoaded