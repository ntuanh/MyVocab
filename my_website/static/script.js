document.addEventListener('DOMContentLoaded', () => {
    // Lấy các element cần thiết từ DOM
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');

    // Panel bên trái
    const imageEl = document.getElementById('word-image');
    const imagePanel = document.getElementById('image-panel');
    const saveBtn = document.getElementById('save-btn'); // Nút Save mới

    // Panel chính
    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');

    // Panel bên phải
    const ipaEl = document.getElementById('pronunciation-ipa');
    const synonymListEl = document.getElementById('synonym-list');
    const familyListEl = document.getElementById('family-list');

    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');
    let toastTimeout; // Biến để quản lý thời gian hiển thị

    // Biến để lưu trữ dữ liệu của từ vừa tra thành công
    let currentWordData = null;

    /**
     * Cập nhật toàn bộ giao diện với dữ liệu mới từ API
     * @param {object} data - Đối tượng JSON chứa thông tin từ vựng
     */

     function showToast(message, type = 'success') {
        // Xóa timeout cũ nếu có
        clearTimeout(toastTimeout);

        // Cập nhật nội dung và class
        toastMessage.textContent = message;
        toast.className = 'toast'; // Reset class
        toast.classList.add(type); // Thêm class 'success' hoặc 'error'
        toast.classList.add('show');

        // Tự động ẩn sau 3 giây
        toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    function updateUI(data) {
        // Lưu dữ liệu của từ hiện tại vào biến toàn cục
        currentWordData = data;

        // Cập nhật các panel
        definitionEl.textContent = data.english_definition || 'N/A';
        exampleEl.textContent = data.example || 'N/A';
        vietnameseMeaningEl.textContent = data.vietnamese_meaning || 'N/A';
        ipaEl.textContent = data.pronunciation_ipa || 'N/A';

        // Reset lại trạng thái của panel tiếng Việt
        vietnamesePanel.classList.add('hidden');
        vietnamesePanel.classList.remove('revealed');

        // Xóa nội dung cũ và tạo tag mới cho từ đồng nghĩa
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
         if (data.is_saved) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
        } else {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
        }
    }

    /**
     * Reset giao diện về trạng thái ban đầu hoặc đang loading
     * @param {string} message - Tin nhắn để hiển thị trong ô định nghĩa
     */
    function resetUI(message) {
        currentWordData = null; // Xóa dữ liệu từ cũ
        definitionEl.textContent = message;
        exampleEl.textContent = '...';
        vietnameseMeaningEl.textContent = '...';
        ipaEl.textContent = '...';
        synonymListEl.innerHTML = '';
        familyListEl.innerHTML = '';
        imageEl.style.display = 'none';
        imageEl.alt = 'Image for the searched word';
        imagePanel.style.backgroundColor = 'var(--panel-blue)';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
    }

    // Xử lý sự kiện tìm kiếm
    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const word = wordInput.value.trim();
        if (!word) return;

        resetUI('Searching...');

        try {
            // Gọi đến endpoint /lookup mới
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

    // Xử lý sự kiện nhấn nút Save
    saveBtn.addEventListener('click', async () => {
        if (!currentWordData || !currentWordData.word) {
            showToast('Please search for a word first!', 'error');
            return;
        }

        // Vô hiệu hóa nút để tránh nhấn nhiều lần
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        try {
            const response = await fetch('/save_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentWordData)
            });
            const result = await response.json();

            // Thay thế alert bằng toast
            if (response.ok && result.status !== 'error') {
                showToast(result.message, 'success');
                // Cập nhật trạng thái nút ngay lập tức
                saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
            } else {
                showToast(result.message || 'An error occurred.', 'error');
                // Nếu lỗi, kích hoạt lại nút
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
            }

        } catch (error) {
            console.error('Save Error:', error);
            // Thay thế alert bằng toast
            showToast('Failed to connect to server.', 'error');
            // Kích hoạt lại nút
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
        }
    });
});