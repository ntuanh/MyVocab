// File: my_website/static/exam.js
// This script handles all logic for the Exam page, including two different question types.

document.addEventListener('DOMContentLoaded', () => {
    // --- 1. ELEMENT SELECTION ---
    // Screen containers
    const topicSelectionContainer = document.getElementById('topic-selection-container');
    const examContainer = document.getElementById('exam-container');

    // Topic selection elements
    const topicListContainer = document.getElementById('topic-list-container');
    const startExamBtn = document.getElementById('start-exam-btn');

    // General exam elements
    const examWordEl = document.getElementById('exam-word');
    const questionPrompt = document.getElementById('question-prompt');
    const hintCard = document.getElementById('hint-card');
    const hintImage = document.getElementById('hint-image');

    // Fill-in-the-blank question elements
    const answerForm = document.getElementById('answer-form');
    const answerInput = document.getElementById('answer-input');

    // Self-assessment question elements
    const selfAssessmentAnswer = document.getElementById('self-assessment-answer');
    const hiddenMeaning = document.getElementById('hidden-meaning');
    const revealMeaningBtn = document.getElementById('reveal-meaning-btn');
    const selfAssessmentButtons = document.getElementById('self-assessment-buttons');
    const btnKnowIt = document.getElementById('btn-know-it');
    const btnDontKnow = document.getElementById('btn-dont-know');

    // Feedback elements
    const feedbackCard = document.getElementById('feedback-card');
    const feedbackTitle = document.getElementById('feedback-title');
    const feedbackText = document.getElementById('feedback-text');
    const motivationalQuote = document.getElementById('motivational-quote');
    const nextWordBtn = document.getElementById('next-word-btn');
    const changeTopicsBtn = document.getElementById('change-topics-btn');

    // State variable
    let currentWord = null;

    // --- 2. LOGIC FUNCTIONS ---

    async function loadTopics() {
        try {
            const response = await fetch('/api/get_topics');
            const topics = await response.json();
            topicListContainer.innerHTML = '';
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

                // [NEW LOGIC] Determine question type based on Vietnamese meaning length
                if (currentWord && currentWord.vietnamese_meaning) {
                    const meaningWordCount = currentWord.vietnamese_meaning.split(' ').length;

                    if (meaningWordCount > 3) {
                        setupSelfAssessmentQuestion();
                    } else {
                        setupFillInBlankQuestion();
                    }
                } else {
                    setupFillInBlankQuestion(); // Default to fill-in-blank if meaning is missing
                }

                examWordEl.textContent = currentWord.word;
                hintImage.src = currentWord.image_url || '';
            } else {
                examWordEl.textContent = 'No words found!';
                answerForm.classList.add('hidden');
                selfAssessmentButtons.classList.add('hidden');
            }
        } catch (error) {
            examWordEl.textContent = 'Error fetching word.';
        }
    }

    // [NEW] Setup UI for fill-in-the-blank questions
    function setupFillInBlankQuestion() {
        questionPrompt.textContent = "What is the Vietnamese meaning of this word?";
        answerForm.classList.remove('hidden');
        selfAssessmentAnswer.classList.add('hidden');
        selfAssessmentButtons.classList.add('hidden');
    }

    // [NEW] Setup UI for self-assessment questions
    function setupSelfAssessmentQuestion() {
        questionPrompt.textContent = "Do you know the Vietnamese meaning of this word?";
        answerForm.classList.add('hidden');
        selfAssessmentAnswer.classList.remove('hidden');
        selfAssessmentAnswer.classList.remove('revealed');
        revealMeaningBtn.classList.remove('hidden');
        selfAssessmentButtons.classList.remove('hidden');
        hiddenMeaning.textContent = currentWord.vietnamese_meaning;
    }

    // [REFACTORED] Central function to submit the result and show feedback
    async function submitResult(isCorrect) {
        // Hide all input controls
        answerForm.classList.add('hidden');
        selfAssessmentButtons.classList.add('hidden');
        selfAssessmentAnswer.classList.add('hidden');

        try {
            await fetch('/api/submit_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: currentWord.id, is_correct: isCorrect })
            });
        } catch (error) {
            console.error("Failed to update score:", error);
        }

        // Show feedback card
        feedbackCard.classList.remove('hidden');
        motivationalQuote.classList.add('hidden');
        feedbackCard.className = 'panel'; // Reset classes
        feedbackCard.classList.add(isCorrect ? 'correct' : 'incorrect');

        feedbackTitle.textContent = isCorrect ? "Correct!" : "Keep Practicing!";
        feedbackText.textContent = `The meaning of "${currentWord.word}" is "${currentWord.vietnamese_meaning}".`;
    }

    // Handles answer for fill-in-the-blank questions
    async function checkAnswer() {
        const userAnswer = answerInput.value.trim();
        if (!userAnswer || !currentWord) return;

        try {
            const answerRes = await fetch(`/api/get_answer/${currentWord.id}`);
            const answerData = await answerRes.json();

            let isCorrect = false;
            const keywords = answerData.keywords;

            // Check against keywords if they exist, otherwise check full meaning
            if (keywords) {
                const keywordList = keywords.split(',').map(kw => kw.trim().toLowerCase());
                isCorrect = keywordList.some(kw => userAnswer.toLowerCase().includes(kw));
            } else {
                isCorrect = userAnswer.toLowerCase() === answerData.correct_answer.toLowerCase();
            }

            submitResult(isCorrect);
        } catch (error) {
            console.error("Error checking answer:", error);
            feedbackTitle.textContent = 'Error checking answer.';
        }
    }

    function resetExamUI() {
        answerInput.value = '';
        feedbackCard.classList.add('hidden');
        motivationalQuote.classList.remove('hidden');
        hintImage.classList.add('hidden');
        // Let the setup functions handle showing/hiding the correct inputs
        answerForm.classList.add('hidden');
        selfAssessmentButtons.classList.add('hidden');
        selfAssessmentAnswer.classList.add('hidden');
        answerInput.focus();
    }

    // --- 3. EVENT LISTENERS ---

    startExamBtn.addEventListener('click', () => {
        topicSelectionContainer.classList.add('hidden');
        examContainer.classList.remove('hidden');
        getNextWord();
    });

    changeTopicsBtn.addEventListener('click', () => {
        examContainer.classList.add('hidden');
        topicSelectionContainer.classList.remove('hidden');
    });

    answerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        checkAnswer();
    });

    nextWordBtn.addEventListener('click', getNextWord);

    hintCard.addEventListener('click', () => {
        if (currentWord && currentWord.image_url) {
            hintImage.classList.toggle('hidden');
        }
    });

    // [NEW] Event listeners for the new self-assessment buttons
    revealMeaningBtn.addEventListener('click', () => {
        selfAssessmentAnswer.classList.add('revealed');
        revealMeaningBtn.classList.add('hidden');
    });

    btnKnowIt.addEventListener('click', () => {
        submitResult(true); // User says they knew it -> is_correct = true
    });

    btnDontKnow.addEventListener('click', () => {
        submitResult(false); // User says they didn't know it -> is_correct = false
    });

    // --- 4. INITIALIZATION ---
    loadTopics();
});