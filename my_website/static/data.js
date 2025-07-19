// my_website/static/data.js
document.addEventListener('DOMContentLoaded', () => {
    // Grab all the modal elements I'll need
    const confirmModal = document.getElementById('confirm-modal');
    const modalText = document.getElementById('modal-text');
    const cancelBtn = document.getElementById('modal-btn-cancel');
    const confirmBtn = document.getElementById('modal-btn-confirm');

    // I'll use this to store whatever function should run when the user hits "Confirm"
    let onConfirmAction = null;

    // Show the confirmation modal with a custom message and action
    function showConfirmModal(word, onConfirm) {
        modalText.textContent = `Are you sure you want to delete the word "${word}"? This action cannot be undone.`;
        onConfirmAction = onConfirm; // Save the action for later
        confirmModal.classList.remove('hidden');
    }

    // Hide the modal and reset the action
    function hideConfirmModal() {
        confirmModal.classList.add('hidden');
        onConfirmAction = null; // Just in case
    }

    // Wire up the modal buttons
    cancelBtn.addEventListener('click', hideConfirmModal);
    confirmBtn.addEventListener('click', () => {
        if (onConfirmAction) {
            onConfirmAction(); // Do whatever the user wanted
        }
        hideConfirmModal(); // Always hide the modal after
    });
    // Also let users close the modal by clicking the overlay
    confirmModal.addEventListener('click', (event) => {
        if(event.target === confirmModal) {
            hideConfirmModal();
        }
    });

    // Find all the delete buttons in the table
    const deleteButtons = document.querySelectorAll('.delete-btn');

    // Attach a click event to each delete button
    deleteButtons.forEach(button => {
        button.addEventListener('click', (event) => {
            const wordId = event.target.dataset.id;
            const row = document.querySelector(`tr[data-id="${wordId}"]`);
            const word = row ? row.querySelector('td:first-child').textContent : 'this word';

            // Instead of using confirm(), show my custom modal
            showConfirmModal(word, () => {
                // This runs if the user confirms the delete
                deleteWord(wordId, row);
            });
        });
    });

    /**
     * Actually delete the word from the server and UI
     * @param {string} wordId - The ID of the word to delete
     * @param {HTMLElement} rowElement - The <tr> for that word in the table
     */
    async function deleteWord(wordId, rowElement) {
        try {
            const response = await fetch(`/delete_word/${wordId}`, {
                method: 'DELETE',
            });
            const result = await response.json();

            if (response.ok && result.status === 'success') {
                // If it worked, remove the row from the table
                if (rowElement) {
                    rowElement.remove();
                }
                // You could show a toast here if you want
                // alert(result.message); // For now, just an alert
            } else {
                alert(result.message || 'Failed to delete word.');
            }
        } catch (error) {
            console.error('Delete error:', error);
            alert('An error occurred while trying to delete the word.');
        }
    }
});