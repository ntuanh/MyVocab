document.addEventListener('DOMContentLoaded', () => {
    // --- 1. GRAB ALL THE ELEMENTS ---
    // Topic selection screen
    const topicSelectionContainer = document.getElementById('topic-selection-container');
    const topicForm = document.getElementById('topic-form');

    // Exam screen
    const examContainer = document.getElementById('exam-container');
    const questionWordEl = document.getElementById('question-word');
    const hintCard = document.getElementById('hint-card');
    const hintImageEl = document.getElementById('hint-image');
    const answerForm = document.getElementById('answer-form');
    const answerInput = document.getElementById('answer-input');
    const feedbackCard = document.getElementById('feedback-card');
    const motivationalQuote = document.getElementById('motivational-quote');
    const answerFeedback = document.getElementById('answer-feedback');
    const feedbackTitleEl = document.getElementById('feedback-title');
    const feedbackTextEl = document.getElementById('feedback-text');
    const nextWordBtn = document.getElementById('next-word-btn');
    const changeTopicsBtn = document.getElementById('change-topics-btn');

    // --- 2. STATE VARIABLES ---
    let currentWord = null;
    let selectedTopicIds = [];

    // --- 3. ALL THE HANDLER FUNCTIONS ---

    /**
     * Reset the UI for a new question. (Keeps things tidy!)
     */
    function resetExamUI() {
        answerFeedback.classList.add('hidden');
        motivationalQuote.classList.remove('hidden');
        feedbackCard.className = 'panel';
        hintCard.style.display = 'none';
        const img = hintCard.querySelector('img');
        if (img) img.style.display = 'none';
        answerInput.value = '';
        answerInput.disabled = false;
        questionWordEl.textContent = 'Loading...';
        answerInput.focus();
    }

    /**
     * Fetch a new word from the server, based on the topics the user picked.
     */
    async function getNewWord() {
        resetExamUI();
        try {
            const response = await fetch('/get_exam_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic_ids: selectedTopicIds })
            });
            const data = await response.json();
            if (!response.ok) {
                questionWordEl.textContent = data.error || 'Error loading word!';
                answerInput.disabled = true;
                return;
            }
            currentWord = data;
            questionWordEl.textContent = currentWord.word;
            if (currentWord.image_url) {
                hintImageEl.src = currentWord.image_url;
                hintCard.style.display = 'block';
            }
        } catch (error) {
            console.error('Error fetching word:', error);
            questionWordEl.textContent = 'Could not load a word for the quiz.';
        }
    }

    /**
     * Tell the server to update the score for this word (right or wrong answer)
     */
    async function updateScoreOnServer(wordId, isCorrect) {
        try {
            await fetch('/submit_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: wordId, is_correct: isCorrect })
            });
            console.log(`Score updated for word ID ${wordId}. Correct: ${isCorrect}`);
        } catch (error) {
            console.error("Failed to update score:", error);
        }
    }

    /**
     * Handle what happens when the user submits an answer.
     */
    async function handleAnswerSubmit(e) {
        e.preventDefault();
        if (!currentWord || answerInput.disabled) return;
        const userAnswer = answerInput.value.trim();
        if (userAnswer === '') {
            answerInput.classList.add('shake');
            setTimeout(() => answerInput.classList.remove('shake'), 500);
            return;
        }
        answerInput.disabled = true;
        try {
            const response = await fetch(`/get_answer/${currentWord.id}`);
            const result = await response.json();
            if (!response.ok) throw new Error(result.error);

            const correctAnswer = result.correct_answer.toLowerCase();
            const userAnswerLower = userAnswer.toLowerCase();
            const correctParts = correctAnswer.split(/,|;/).map(part => part.trim().toLowerCase());
            const isCorrect = correctParts.includes(userAnswerLower);

            motivationalQuote.classList.add('hidden');
            answerFeedback.classList.remove('hidden');

            if (isCorrect) {
                feedbackTitleEl.textContent = "Correct!";
                feedbackCard.className = 'panel feedback-card correct';
                feedbackTextEl.textContent = "Good job!";
            } else {
                feedbackTitleEl.textContent = "Incorrect!";
                feedbackCard.className = 'panel feedback-card incorrect';
                feedbackTextEl.textContent = `The correct answer is: ${result.correct_answer}`;
            }
            updateScoreOnServer(currentWord.id, isCorrect);
        } catch (error) {
            console.error('Error submitting answer:', error);
            alert(error.message || "Something went wrong while checking the answer.");
            answerInput.disabled = false;
        }
    }

    // --- 4. WIRE UP ALL THE EVENTS ---

    // When the user submits the topic selection form
    topicForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const checkedBoxes = document.querySelectorAll('input[name="topics"]:checked');
        selectedTopicIds = Array.from(checkedBoxes).map(cb => cb.value);
        topicSelectionContainer.classList.add('hidden');
        examContainer.classList.remove('hidden');
        getNewWord();
    });

    // When the user submits their answer
    answerForm.addEventListener('submit', handleAnswerSubmit);

    // Button events
    nextWordBtn.addEventListener('click', getNewWord);
    changeTopicsBtn.addEventListener('click', () => {
        examContainer.classList.add('hidden');
        topicSelectionContainer.classList.remove('hidden');
        selectedTopicIds = [];
    });
    hintCard.addEventListener('click', () => {
        const img = hintCard.querySelector('img');
        if (img) {
            const isHidden = img.style.display === 'none' || img.style.display === '';
            img.style.display = isHidden ? 'block' : 'none';
        }
    });
});
