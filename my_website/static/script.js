document.addEventListener('DOMContentLoaded', () => {
    // Lấy các element cần thiết
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');

    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');

    // Hàm cập nhật giao diện
    function updateUI(data) {
        definitionEl.textContent = data.english_definition || 'N/A';
        exampleEl.textContent = data.example || 'N/A';
        vietnameseMeaningEl.textContent = data.vietnamese_meaning || 'N/A';

        // Reset lại trạng thái của panel tiếng Việt
        vietnamesePanel.classList.add('hidden');
        vietnamesePanel.classList.remove('revealed');
    }

    // Xử lý sự kiện tìm kiếm
    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const word = wordInput.value.trim();
        if (!word) return;

        // Hiển thị trạng thái loading
        definitionEl.textContent = 'Searching...';
        exampleEl.textContent = '...';
        vietnameseMeaningEl.textContent = '...';

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
                // Hiển thị lỗi từ server
                definitionEl.textContent = data.error || 'An unknown error occurred.';
                exampleEl.textContent = 'N/A';
                vietnameseMeaningEl.textContent = 'N/A';
            }
        } catch (error) {
            console.error('Fetch Error:', error);
            definitionEl.textContent = 'Failed to connect to the server.';
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