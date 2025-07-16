document.addEventListener('DOMContentLoaded', () => {
    // --- LẤY TẤT CẢ CÁC ELEMENTS CẦN THIẾT TỪ DOM ---
    // Thanh tìm kiếm
    const searchForm = document.getElementById('search-form');
    const wordInput = document.getElementById('word-input');

    // Panel bên trái
    const imageEl = document.getElementById('word-image');
    const imagePanel = document.getElementById('image-panel');
    const saveBtn = document.getElementById('save-btn');

    // Panel chính
    const vietnamesePanel = document.getElementById('vietnamese-panel');
    const vietnameseMeaningEl = document.getElementById('vietnamese-meaning');
    const definitionEl = document.getElementById('english-definition');
    const exampleEl = document.getElementById('example-sentence');

    // Panel bên phải
    const ipaEl = document.getElementById('pronunciation-ipa');
    const synonymListEl = document.getElementById('synonym-list');
    const familyListEl = document.getElementById('family-list');

    // Modal lưu từ
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

    // Biến toàn cục để lưu trữ dữ liệu của từ đang được hiển thị
    let currentWordData = null;

    // --- ĐỊNH NGHĨA CÁC HÀM XỬ LÝ ---

    /**
     * Hiển thị một thông báo nhỏ (toast) ở cuối màn hình.
     * @param {string} message - Nội dung thông báo.
     * @param {string} type - Loại thông báo ('success' hoặc 'error').
     */
    function showToast(message, type = 'success') {
        clearTimeout(toastTimeout);
        toastMessage.textContent = message;
        toast.className = 'toast';
        toast.classList.add(type, 'show');
        toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    /**
     * Cập nhật toàn bộ giao diện với dữ liệu mới từ API hoặc cache.
     * @param {object} data - Đối tượng JSON chứa thông tin từ vựng.
     */
    function updateUI(data) {
        // LUÔN LUÔN cập nhật currentWordData với dữ liệu mới nhất.
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

        if (data.image_url) {
            imageEl.src = data.image_url;
            imageEl.alt = `Image for '${data.word}'`;
            imageEl.style.display = 'block';
            imagePanel.style.backgroundColor = 'transparent';
        } else {
            imageEl.style.display = 'none';
            imagePanel.style.backgroundColor = 'var(--panel-blue)';
        }

        // Cập nhật trạng thái nút Save dựa trên cờ 'is_saved'
        if (data.is_saved) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
        } else {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
        }
    }

    /**
     * Reset giao diện về trạng thái ban đầu hoặc đang loading.
     */
    function resetUI(message) {
        currentWordData = null; // Xóa dữ liệu từ cũ
        definitionEl.textContent = message;
        ['example-sentence', 'vietnamese-meaning', 'pronunciation-ipa'].forEach(id => {
            document.getElementById(id).textContent = '...';
        });
        ['synonym-list', 'family-list'].forEach(id => {
            document.getElementById(id).innerHTML = '';
        });
        imageEl.style.display = 'none';
        imagePanel.style.backgroundColor = 'var(--panel-blue)';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Word';
    }

    /**
     * Hiển thị modal để chọn chủ đề khi lưu từ.
     */
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

    // --- GÁN CÁC SỰ KIỆN ---

    // Sự kiện tìm kiếm
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

    // Sự kiện nhấn để xem nghĩa
    vietnamesePanel.addEventListener('click', () => {
        if (vietnamesePanel.classList.contains('hidden')) {
            vietnamesePanel.classList.remove('hidden');
            vietnamesePanel.classList.add('revealed');
        }
    });

    // Sự kiện cho nút Save chính: chỉ mở modal
    saveBtn.addEventListener('click', () => {
        if (!currentWordData || !currentWordData.word) {
            showToast('Please search for a word first!', 'error');
            return;
        }
        showSaveModal();
    });

    // Sự kiện cho nút "Add Topic" trong modal
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

    // Sự kiện cho nút "Confirm Save" trong modal
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
            showToast(result.message, result.status);
            saveModal.classList.add('hidden');
            if (result.status !== 'error') {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<i class="fas fa-check"></i> Already Saved';
            }
        } catch (error) {
            showToast("Failed to save.", "error");
        }
    });

    // Sự kiện cho nút "Cancel" trong modal
    cancelSaveBtn.addEventListener('click', () => {
        saveModal.classList.add('hidden');
    });
});