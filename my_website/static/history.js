document.addEventListener('DOMContentLoaded', () => {
    const wordListContainer = document.getElementById('word-list');

    // Hàm để tạo một thẻ từ vựng
    function createWordCard(wordData) {
        const card = document.createElement('div');
        card.className = 'word-card';
        card.dataset.word = wordData.word; // Thêm data-word để dễ dàng lấy lại tên từ

        const savedDate = new Date(wordData.saved_at).toLocaleDateString('vi-VN', {
            day: '2-digit', month: '2-digit', year: 'numeric'
        });

        // Thêm nút xóa vào footer của thẻ
        card.innerHTML = `
            <div class="word-card-header">
                <h2 class="word-title">${wordData.word}</h2>
                <span class="word-ipa">${wordData.pronunciation_ipa || 'N/A'}</span>
            </div>
            <div class="word-card-body">
                <p><strong>Nghĩa:</strong> ${wordData.vietnamese_meaning || 'N/A'}</p>
                <p><strong>Definition:</strong> ${wordData.english_definition || 'N/A'}</p>
                <p><strong>Example:</strong> ${wordData.example || 'N/A'}</p>
            </div>
            <div class="word-card-footer">
                <small>Đã lưu vào: ${savedDate}</small>
                <button class="delete-btn">
                    <i class="fas fa-sync-alt"></i> Xóa & Tra lại
                </button>
            </div>
        `;
        return card;
    }

    // Hàm để xử lý yêu cầu xóa
    async function handleDeleteAndReSearch(e) {
        // Chỉ xử lý nếu người dùng click vào nút delete
        if (!e.target.classList.contains('delete-btn')) {
            return;
        }

        const card = e.target.closest('.word-card');
        const wordToDelete = card.dataset.word;

        if (!wordToDelete || !confirm(`Bạn có chắc muốn xóa và tra lại từ "${wordToDelete}" không?`)) {
            return;
        }

        e.target.textContent = 'Đang xóa...';
        e.target.disabled = true;

        try {
            const response = await fetch('/delete_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word: wordToDelete })
            });

            if (response.ok) {
                // Nếu xóa thành công, chuyển hướng về trang chủ
                // và truyền từ cần tra lại qua URL parameter
                window.location.href = `/?research=${encodeURIComponent(wordToDelete)}`;
            } else {
                const result = await response.json();
                alert(`Lỗi khi xóa: ${result.error}`);
                e.target.textContent = 'Xóa & Tra lại';
                e.target.disabled = false;
            }
        } catch (error) {
            console.error('Failed to delete word:', error);
            alert('Lỗi kết nối khi xóa từ.');
            e.target.textContent = 'Xóa & Tra lại';
            e.target.disabled = false;
        }
    }

    // Thêm trình xử lý sự kiện vào container cha
    wordListContainer.addEventListener('click', handleDeleteAndReSearch);

    // Hàm để lấy và hiển thị dữ liệu (giữ nguyên)
    async function loadSavedWords() {
        // ... code của hàm này giữ nguyên như cũ ...
        try {
            const response = await fetch('/get_saved_words');
            const words = await response.json();
            wordListContainer.innerHTML = '';
            if (response.ok && words.length > 0) {
                words.forEach(wordData => {
                    const card = createWordCard(wordData);
                    wordListContainer.appendChild(card);
                });
            } else if (words.length === 0) {
                wordListContainer.innerHTML = '<p class="loading-text">Bạn chưa lưu từ vựng nào.</p>';
            } else {
                 wordListContainer.innerHTML = `<p class="loading-text">Lỗi: ${words.error}</p>`;
            }
        } catch (error) {
            console.error('Failed to load saved words:', error);
            wordListContainer.innerHTML = '<p class="loading-text">Không thể tải dữ liệu. Vui lòng thử lại.</p>';
        }
    }

    loadSavedWords();
});