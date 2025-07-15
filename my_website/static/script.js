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
        // Lưu dữ liệu từ hiện tại để có thể dùng cho việc lưu trữ
        currentWordData = data;

        // Cập nhật các panel chính
        definitionEl.textContent = data.english_definition || 'N/A';
        exampleEl.textContent = data.example || 'N/A';
        vietnameseMeaningEl.textContent = data.vietnamese_meaning || 'N/A';

        // Reset trạng thái ẩn/hiện của panel nghĩa tiếng Việt
        vietnamesePanel.classList.add('hidden');
        vietnamesePanel.classList.remove('revealed');

        // Cập nhật các panel bên phải
        ipaEl.textContent = data.pronunciation_ipa || 'N/A';

        // Tạo tag cho từ đồng nghĩa
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

        // Tạo tag cho họ từ
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
            imagePanel.style.backgroundColor = 'transparent';
        } else {
            imageEl.style.display = 'none';
            imagePanel.style.backgroundColor = 'var(--panel-blue)';
            imageEl.alt = 'No image found';
        }

        // Cập nhật trạng thái nút "Save" dựa trên dữ liệu từ backend
        if (data.is_saved) {
            // Nếu từ này đã được lưu từ trước, hiển thị trạng thái "Saved"
            saveButton.disabled = true; // Bạn có thể đặt là false nếu muốn cho phép lưu lại
            saveButton.classList.add('saved');
            saveButton.innerHTML = '<i class="fas fa-check"></i> Saved!';
        } else {
            // Nếu đây là từ mới, cho phép lưu
            saveButton.disabled = false;
            saveButton.classList.remove('saved');
            saveButton.innerHTML = '<i class="fas fa-rocket"></i> Save';
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

        // Vô hiệu hóa và reset nút Save
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
                // Cập nhật lại trạng thái đã lưu cho dữ liệu hiện tại
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

    // Gọi resetUI lúc ban đầu để vô hiệu hóa nút save
    resetUI('Nhập một từ vào ô tìm kiếm để bắt đầu.');
});