// my_website/static/data.js

document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.getElementById('data-table-body');

    // Function to fetch and display saved words
    async function loadSavedWords() {
        try {
            const response = await fetch('/api/all_data');
            if (!response.ok) {
                // If unauthorized (password not entered), redirect to home
                if (response.status === 401) {
                    window.location.href = '/';
                }
                throw new Error('Failed to fetch data');
            }
            const words = await response.json();
            
            tableBody.innerHTML = ''; // Clear the "Loading..." message

            if (words.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">You have not saved any words yet.</td></tr>';
                return;
            }

            words.forEach(word => {
                const row = document.createElement('tr');
                row.setAttribute('data-word-id', word.id);
                row.innerHTML = `
                    <td>${word.word}</td>
                    <td>${word.english_definition || 'N/A'}</td>
                    <td>${word.priority_score}</td>
                    <td><button class="delete-btn" data-id="${word.id}">Delete</button></td>
                `;
                tableBody.appendChild(row);
            });
        } catch (error) {
            console.error('Error loading words:', error);
            tableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Could not load data. Please try again.</td></tr>';
        }
    }

    // Event listener for delete buttons (using event delegation)
    tableBody.addEventListener('click', async (event) => {
        if (event.target.classList.contains('delete-btn')) {
            const button = event.target;
            const wordId = button.dataset.id;
            
            const confirmed = confirm('Are you sure you want to delete this word?');
            
            if (confirmed) {
                try {
                    const response = await fetch(`/api/delete_word/${wordId}`, {
                        method: 'DELETE'
                    });
                    const result = await response.json();
                    
                    if (result.status === 'success') {
                        // Remove the row from the table smoothly
                        const rowToDelete = document.querySelector(`tr[data-word-id='${wordId}']`);
                        if (rowToDelete) {
                            rowToDelete.style.opacity = '0';
                            setTimeout(() => rowToDelete.remove(), 300);
                        }
                    } else {
                        alert('Failed to delete the word.');
                    }
                } catch (error) {
                    console.error('Error deleting word:', error);
                    alert('An error occurred while deleting the word.');
                }
            }
        }
    });

    // Initial load of data when the page opens
    loadSavedWords();
});