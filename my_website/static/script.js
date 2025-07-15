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

    // Nút Save
    const saveButton = document.getElementById('save-button');

    // Biến tạm để lưu dữ liệu của từ đang hiển thị
    let currentWordData = null;

    /**
     * Cập nhật toàn bộ giao diện với dữ liệu mới từ API hoặc từ cache
     * @param {object} data - Đối tượng JSON chứa thông tin từ vựng
     */
    function updateUI(data) {
        currentWordData = data;

        definitionEl.innerHTML = data.english_definition || 'N/A'; // Dùng innerHTML để render link nếu có
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

    /**
     * Reset giao diện về trạng thái ban đầu hoặc đang loading
     * @param {string} message - Tin nhắn để hiển thị trong ô định nghĩa (có thể chứa HTML)
     */
    function resetUI(message) {
        definitionEl.innerHTML = message; // Dùng innerHTML để hiển thị link gợi ý
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

    // Xử lý sự kiện tìm kiếm từ
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
                let errorMessage = data.error || 'An unknown error occurred.';

                // Kiểm tra xem có trường 'suggestion' trong phản hồi lỗi không
                if (data.suggestion) {
                    // Tạo một liên kết HTML có thể click để tra từ gợi ý
                    errorMessage += ` <br>Bạn có muốn tra từ: <a href="#" class="suggestion-link" data-word="${data.suggestion}">${data.suggestion}</a>?`;
                }

                resetUI(errorMessage);
            }
        } catch (error) {
            console.error('Fetch Error:', error);
            resetUI('Failed to connect to the server.');
        }
    });

    // Thêm một trình xử lý sự kiện tập trung vào document.body
    // để bắt các click trên các link gợi ý được tạo động
    document.body.addEventListener('click', (e) => {
        // Kiểm tra xem phần tử được click có phải là link gợi ý không
        if (e.target.classList.contains('suggestion-link')) {
            e.preventDefault(); // Ngăn hành vi mặc định của thẻ <a> (tải lại trang)
            const suggestedWord = e.target.dataset.word;

            // Tự động điền từ gợi ý vào ô search
            wordInput.value = suggestedWord;
            // Kích hoạt lại sự kiện 'submit' của form để bắt đầu một cuộc tra cứu mới
            searchForm.dispatchEvent(new Event('submit', { cancelable: true }));
        }
    });

    // Xử lý sự kiện nhấn để xem nghĩa
    vietnamesePanel.addEventListener('click', () => {
        if (vietnamesePanel.classList.contains('hidden')) {
            vietnamesePanel.classList.remove('hidden');
            vietnamesePanel.classList.add('revealed');
        }
    });

    // Xử lý sự kiện click nút Save
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

    // Gọi resetUI lúc ban đầu để thiết lập trạng thái ban đầu
    resetUI('Nhập một từ vào ô tìm kiếm để bắt đầu.');
});