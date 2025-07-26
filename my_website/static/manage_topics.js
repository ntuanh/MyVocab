document.addEventListener('DOMContentLoaded', () => {
    // --- 1. ELEMENT SELECTION ---
    const tableBody = document.getElementById('topics-table-body');
    if (!tableBody) {
        console.error("Error: Could not find the element with id='topics-table-body'.");
        return; // Stop the script if the main element is missing
    }

    // --- 2. LOGIC FUNCTIONS ---

    async function loadTopics() {
        try {
            const response = await fetch('/api/get_topics');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const topics = await response.json();

            tableBody.innerHTML = ''; // Clear the "Loading..." message

            if (topics.length === 0) {
                // If there are no topics, display a user-friendly message
                const emptyRow = document.createElement('tr');
                emptyRow.innerHTML = `<td colspan="3" class="empty-table-cell">No topics found. You can add new topics when saving a word.</td>`;
                tableBody.appendChild(emptyRow);
                return;
            }

            topics.forEach(topic => {
                const row = document.createElement('tr');
                row.setAttribute('data-topic-id', topic.id); // Add an attribute for easy selection
                row.innerHTML = `
                    <td>${topic.name}</td>
                    <td>${topic.word_count}</td>
                    <td><button class="delete-btn" data-id="${topic.id}">Delete</button></td>
                `;
                tableBody.appendChild(row);
            });

        } catch (error) {
            console.error('Error loading topics:', error);
            const errorRow = document.createElement('tr');
            errorRow.innerHTML = `<td colspan="3" class="empty-table-cell">Failed to load topics. Please try again.</td>`;
            tableBody.appendChild(errorRow);
        }
    }

    /**
     * Handles the deletion of a topic when a delete button is clicked.
     * @param {string} topicId The ID of the topic to delete.
     */
    async function deleteTopic(topicId) {
        // Ask for confirmation before deleting
        const confirmed = confirm('Are you sure you want to delete this topic? This action cannot be undone.');

        if (confirmed) {
            try {
                const response = await fetch(`/api/delete_topic/${topicId}`, {
                    method: 'DELETE'
                });
                const result = await response.json();

                if (result.status === 'success') {
                    // Find the row in the table and remove it with a smooth animation
                    const rowToDelete = document.querySelector(`tr[data-topic-id='${topicId}']`);
                    if (rowToDelete) {
                        rowToDelete.style.transition = 'opacity 0.3s ease';
                        rowToDelete.style.opacity = '0';
                        setTimeout(() => rowToDelete.remove(), 300);
                    }
                } else {
                    alert(result.message || 'Failed to delete the topic.');
                }
            } catch (error) {
                console.error('Error deleting topic:', error);
                alert('An error occurred while deleting the topic.');
            }
        }
    }

    // --- 3. EVENT LISTENERS ---

    tableBody.addEventListener('click', (event) => {
        // Check if the clicked element is a delete button
        if (event.target.classList.contains('delete-btn')) {
            const button = event.target;
            const topicId = button.dataset.id;
            deleteTopic(topicId);
        }
    });

    // --- 4. INITIALIZATION ---
    // Load the topics as soon as the page is ready
    loadTopics();
});