// my_website/static/data.js
document.addEventListener('DOMContentLoaded', () => {
    // Lấy các element của Modal
    const confirmModal = document.getElementById('confirm-modal');
    const modalText = document.getElementById('modal-text');
    const cancelBtn = document.getElementById('modal-btn-cancel');
    const confirmBtn = document.getElementById('modal-btn-confirm');

    // Biến để lưu trữ hàm sẽ được thực thi khi người dùng nhấn "Confirm"
    let onConfirmAction = null;

    // Hàm để hiển thị modal
    function showConfirmModal(word, onConfirm) {
        modalText.textContent = `Are you sure you want to delete the word "${word}"? This action cannot be undone.`;
        onConfirmAction = onConfirm; // Lưu lại hành động cần thực hiện
        confirmModal.classList.remove('hidden');
    }

    // Hàm để ẩn modal
    function hideConfirmModal() {
        confirmModal.classList.add('hidden');
        onConfirmAction = null; // Reset hành động
    }

    // Gán sự kiện cho các nút trong modal
    cancelBtn.addEventListener('click', hideConfirmModal);
    confirmBtn.addEventListener('click', () => {
        if (onConfirmAction) {
            onConfirmAction(); // Thực thi hành động đã lưu
        }
        hideConfirmModal(); // Sau đó ẩn modal đi
    });
    // Cũng có thể đóng modal khi click ra ngoài
    confirmModal.addEventListener('click', (event) => {
        if(event.target === confirmModal) {
            hideConfirmModal();
        }
    });

    // Lấy tất cả các nút xóa
    const deleteButtons = document.querySelectorAll('.delete-btn');

    // Thêm sự kiện click cho mỗi nút xóa
    deleteButtons.forEach(button => {
        button.addEventListener('click', (event) => {
            const wordId = event.target.dataset.id;
            const row = document.querySelector(`tr[data-id="${wordId}"]`);
            const word = row ? row.querySelector('td:first-child').textContent : 'this word';

            // Hiển thị modal thay vì confirm()
            showConfirmModal(word, () => {
                // Hành động này sẽ được gọi khi người dùng nhấn "Delete" trong modal
                deleteWord(wordId, row);
            });
        });
    });

    /**
     * Hàm để thực hiện việc xóa thực sự
     * @param {string} wordId - ID của từ cần xóa
     * @param {HTMLElement} rowElement - Dòng <tr> tương ứng trong bảng
     */
    async function deleteWord(wordId, rowElement) {
        try {
            const response = await fetch(`/delete_word/${wordId}`, {
                method: 'DELETE',
            });
            const result = await response.json();

            if (response.ok && result.status === 'success') {
                // Nếu xóa thành công, xóa hàng đó khỏi bảng trên giao diện
                if (rowElement) {
                    rowElement.remove();
                }
                // Có thể thêm một toast notification ở đây để thông báo thành công
                // alert(result.message); // Tạm thời dùng alert
            } else {
                alert(result.message || 'Failed to delete word.');
            }
        } catch (error) {
            console.error('Delete error:', error);
            alert('An error occurred while trying to delete the word.');
        }
    }
});