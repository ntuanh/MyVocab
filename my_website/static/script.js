// my_website/static/script.js

document.addEventListener('DOMContentLoaded', () => {
    // Lấy các element cần thiết từ DOM
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');

    const imageEl = document.getElementById('word-image');
    const imagePanel = document.getElementById('image-panel');

    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');

    const ipaEl = document.getElementById('pronunciation-ipa');
    const synonymListEl = document.getElementById('synonym-list');
    const familyListEl = document.getElementById('family-list');

    const saveButton = document.getElementById('save-button');
    let currentWordData = null;

    function updateUI(data) {
        currentWordData = data;
        definitionEl.innerHTML = data.english_definition || 'N/A';
        exampleEl.textContent = data.example || 'N/A';
        vietnameseMeaningEl.textContent = data.vietnamese_meaning || 'N/A';
        vietnamesePanel.classList.add('hidden');
        vietnamesePanel.classList.remove('revealed');
        ipaEl.textContent = data.pronunciation_ipa || 'N/A';
        synonymListEl.innerHTML = '';
        if (data.synonyms && data.synonyms.length > 0) {
            data.synonyms.forEach(word => {
                const tag = document.createElement('span');
                tag.className = 'tag';
                tag.textContent = word;
                synonymListEl.appendChild(tag);
            });
        } else {
            synonymListEl.innerHTML = 'N/A';
        }
        familyListEl.innerHTML = '';
        if (data.family_words && data.family_words.length > 0) {
             data.family_words.forEach(word => {
                const tag = document.createElement('span');
                tag.className = 'tag';
                tag.textContent = word;
                familyListEl.appendChild(tag);
            });
        } else {
            familyListEl.innerHTML = 'N/A';
        }
        if (data.image_url) {
            imageEl.src = data.image_url;
            imageEl.alt = `Image for '${data.word}'`;
            imageEl.style.display = 'block';
            imagePanel.style.backgroundColor = 'transparent';
        } else {
            imageEl.style.display = 'none';
            imagePanel.style.backgroundColor = 'var(--panel-blue)';
            imageEl.alt = 'No image found';
        }
        if (data.is_saved) {
            saveButton.disabled = true;
            saveButton.classList.add('saved');
            saveButton.innerHTML = '<i class="fas fa-check"></i> Saved!';
        } else {
            saveButton.disabled = false;
            saveButton.classList.remove('saved');
            saveButton.innerHTML = '<i class="fas fa-rocket"></i> Save';
        }
    }

    function resetUI(message) {
        definitionEl.innerHTML = message;
        exampleEl.textContent = '...';
        vietnameseMeaningEl.textContent = '...';
        ipaEl.textContent = '...';
        synonymListEl.innerHTML = '';
        familyListEl.innerHTML = '';
        imageEl.style.display = 'none';
        imageEl.alt = 'Image for the searched word';
        imagePanel.style.backgroundColor = 'var(--panel-blue)';
        currentWordData = null;
        saveButton.disabled = true;
        saveButton.classList.remove('saved');
        saveButton.innerHTML = '<i class="fas fa-rocket"></i> Save';
    }

    // Hàm thực hiện tìm kiếm, được tách ra để tái sử dụng
    async function performSearch(word) {
        if (!word) return;
        resetUI('Searching...');
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: word })
            });
            const data = await response.json();
            if (response.ok) {
                updateUI(data);
            } else {
                let errorMessage = data.error || 'An unknown error occurred.';
                if (data.suggestion) {
                    errorMessage += ` <br>Bạn có muốn tra từ: <a href="#" class="suggestion-link" data-word="${data.suggestion}">${data.suggestion}</a>?`;
                }
                resetUI(errorMessage);
            }
        } catch (error) {
            console.error('Fetch Error:', error);
            resetUI('Failed to connect to the server.');
        }
    }

    searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        performSearch(wordInput.value.trim());
    });

    document.body.addEventListener('click', (e) => {
        if (e.target.classList.contains('suggestion-link')) {
            e.preventDefault();
            const suggestedWord = e.target.dataset.word;
            wordInput.value = suggestedWord;
            performSearch(suggestedWord);
        }
    });

    vietnamesePanel.addEventListener('click', () => {
        if (vietnamesePanel.classList.contains('hidden')) {
            vietnamesePanel.classList.remove('hidden');
            vietnamesePanel.classList.add('revealed');
        }
    });

    saveButton.addEventListener('click', async () => {
        if (!currentWordData) return;
        saveButton.disabled = true;
        saveButton.textContent = 'Saving...';
        try {
            const response = await fetch('/save_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentWordData)
            });
            const result = await response.json();
            if (response.ok) {
                saveButton.classList.add('saved');
                saveButton.innerHTML = '<i class="fas fa-check"></i> Saved!';
                currentWordData.is_saved = true;
            } else {
                alert(`Error: ${result.error}`);
                saveButton.disabled = false;
                saveButton.textContent = 'Save';
            }
        } catch (error) {
            console.error('Save Error:', error);
            alert('Failed to save word. Please check the server.');
            saveButton.disabled = false;
            saveButton.textContent = 'Save';
        }
    });

    /**
     * Kiểm tra xem có parameter 'research' trên URL không.
     * Nếu có, tự động thực hiện tìm kiếm.
     */
    function checkAndResearch() {
        const urlParams = new URLSearchParams(window.location.search);
        const wordToResearch = urlParams.get('research');

        if (wordToResearch) {
            wordInput.value = wordToResearch;
            performSearch(wordToResearch);
            // Xóa parameter khỏi URL để không bị tra lại khi người dùng F5
            window.history.replaceState({}, document.title, "/");
        }
    }

    // Thiết lập trạng thái ban đầu và kiểm tra tra cứu lại
    resetUI('Nhập một từ vào ô tìm kiếm để bắt đầu.');
    checkAndResearch();
});