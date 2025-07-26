document.addEventListener('DOMContentLoaded', () => {
    // --- 1. ELEMENT SELECTION ---
    const topicSelectionContainer = document.getElementById('topic-selection-container');
    const examContainer = document.getElementById('exam-container');
    const topicListContainer = document.getElementById('topic-list-container');
    const startExamBtn = document.getElementById('start-exam-btn');

    const examWordEl = document.getElementById('exam-word');
    const hintCard = document.getElementById('hint-card');
    const hintImage = document.getElementById('hint-image');
    const answerForm = document.getElementById('answer-form');
    const answerInput = document.getElementById('answer-input');
    const feedbackCard = document.getElementById('feedback-card');
    const feedbackTitle = document.getElementById('feedback-title');
    const feedbackText = document.getElementById('feedback-text');
    const motivationalQuote = document.getElementById('motivational-quote');
    const nextWordBtn = document.getElementById('next-word-btn');
    const changeTopicsBtn = document.getElementById('change-topics-btn');

    let currentWord = null;

    // --- 2. LOGIC FUNCTIONS ---

    // Function to load topics into the selection screen
    async function loadTopics() {
        try {
            const response = await fetch('/api/get_topics');
            const topics = await response.json();
            topicListContainer.innerHTML = ''; // Clear loading message
            topics.forEach(topic => {
                const topicDiv = document.createElement('div');
                topicDiv.className = 'topic-checkbox';
                topicDiv.innerHTML = `
                    <input type="checkbox" id="topic-${topic.id}" name="topics" value="${topic.id}">
                    <label for="topic-${topic.id}">${topic.name} (${topic.word_count})</label>
                `;
                topicListContainer.appendChild(topicDiv);
            });
        } catch (error) {
            topicListContainer.innerHTML = '<p>Error loading topics.</p>';
        }
    }

    // Function to fetch the next exam word from the backend
    async function getNextWord() {
        const selectedCheckboxes = document.querySelectorAll('input[name="topics"]:checked');
        const selectedTopicIds = Array.from(selectedCheckboxes).map(cb => cb.value);

        resetExamUI();
        examWordEl.textContent = 'Loading...';
        
        try {
            const response = await fetch('/api/get_exam_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic_ids: selectedTopicIds })
            });

            if (response.ok) {
                currentWord = await response.json();
                examWordEl.textContent = currentWord.word;
                hintImage.src = currentWord.image_url || '';
            } else {
                examWordEl.textContent = 'No words found for these topics!';
                answerForm.classList.add('hidden');
            }
        } catch (error) {
            examWordEl.textContent = 'Error fetching word.';
        }
    }

    // Function to check the user's answer
    async function checkAnswer() {
        const userAnswer = answerInput.value.trim();
        if (!userAnswer || !currentWord) return;

        try {
            // First, get the correct answer
            const answerRes = await fetch(`/api/get_answer/${currentWord.id}`);
            const answerData = await answerRes.json();
            const correctAnswer = answerData.correct_answer;

            // Normalize answers for comparison
            const isCorrect = userAnswer.toLowerCase() === correctAnswer.toLowerCase();
            
            // Show feedback
            feedbackCard.classList.remove('hidden', 'correct', 'incorrect');
            motivationalQuote.classList.add('hidden');
            answerForm.classList.add('hidden');

            if (isCorrect) {
                feedbackCard.classList.add('correct');
                feedbackTitle.textContent = "Correct!";
                feedbackText.textContent = `The meaning of "${currentWord.word}" is "${correctAnswer}".`;
            } else {
                feedbackCard.classList.add('incorrect');
                feedbackTitle.textContent = "Incorrect";
                feedbackText.textContent = `The correct answer is "${correctAnswer}".`;
            }
            
            // Update the word's score in the database
            await fetch('/api/submit_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: currentWord.id, is_correct: isCorrect })
            });

        } catch (error) {
            feedbackTitle.textContent = 'Error checking answer.';
        }
    }
    
    // Function to reset the exam UI for the next question
    function resetExamUI() {
        answerInput.value = '';
        feedbackCard.classList.add('hidden');
        motivationalQuote.classList.remove('hidden');
        hintImage.classList.add('hidden');
        answerForm.classList.remove('hidden');
        answerInput.focus();
    }

    // --- 3. EVENT LISTENERS ---

    // When the "Start Exam" button is clicked
    startExamBtn.addEventListener('click', () => {
        topicSelectionContainer.classList.add('hidden');
        examContainer.classList.remove('hidden');
        getNextWord();
    });
    
    // When the "Change Topics" button is clicked
    changeTopicsBtn.addEventListener('click', () => {
        examContainer.classList.add('hidden');
        topicSelectionContainer.classList.remove('hidden');
    });

    // When the answer form is submitted
    answerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        checkAnswer();
    });
    
    // When the "Next Word" button is clicked
    nextWordBtn.addEventListener('click', getNextWord);
    
    // When the hint card is clicked
    hintCard.addEventListener('click', () => {
        if(currentWord && currentWord.image_url) {
            hintImage.classList.toggle('hidden');
        }
    });

    // Initial load
    loadTopics();
});