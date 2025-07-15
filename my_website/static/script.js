document.addEventListener('DOMContentLoaded', () => {
    // Lấy các element cần thiết từ DOM
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');

    // Panel bên trái
    const imageEl = document.getElementById('word-image');
    const imagePanel = document.getElementById('image-panel');

    // Panel chính
    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');

    // Panel bên phải
    const ipaEl = document.getElementById('pronunciation-ipa');
    const synonymListEl = document.getElementById('synonym-list');
    const familyListEl = document.getElementById('family-list');

    /**
     * Cập nhật toàn bộ giao diện với dữ liệu mới từ API
     * @param {object} data - Đối tượng JSON chứa thông tin từ vựng
     */
    function updateUI(data) {
        definitionEl.textContent = data.english_definition || 'N/A';
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

        // Cập nhật hình ảnh
        if (data.image_url) {
            imageEl.src = data.image_url;
            imageEl.alt = `Image for '${data.word}'`;
            imageEl.style.display = 'block';
            imagePanel.style.backgroundColor = 'transparent'; // Nền trong suốt để ảnh nổi bật
        } else {
            imageEl.style.display = 'none';
            imagePanel.style.backgroundColor = 'var(--panel-blue)'; // Hiện lại màu nền
            imageEl.alt = 'No image found';
        }
    }

    /**
     * Reset giao diện về trạng thái ban đầu hoặc đang loading
     * @param {string} message - Tin nhắn để hiển thị trong ô định nghĩa
     */
    function resetUI(message) {
        definitionEl.textContent = message;
        exampleEl.textContent = '...';
        vietnameseMeaningEl.textContent = '...';
        ipaEl.textContent = '...';
        synonymListEl.innerHTML = '';
        familyListEl.innerHTML = '';
        imageEl.style.display = 'none';
        imageEl.alt = 'Image for the searched word';
        imagePanel.style.backgroundColor = 'var(--panel-blue)';
    }

    // Xử lý sự kiện tìm kiếm
    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const word = wordInput.value.trim();
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
                resetUI(data.error || 'An unknown error occurred.');
            }
        } catch (error) {
            console.error('Fetch Error:', error);
            resetUI('Failed to connect to the server.');
        }
    });

    // Xử lý sự kiện nhấn để xem nghĩa
    vietnamesePanel.addEventListener('click', () => {
        if (vietnamesePanel.classList.contains('hidden')) {
            vietnamesePanel.classList.remove('hidden');
            vietnamesePanel.classList.add('revealed');
        }
    });
});