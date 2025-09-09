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

                if (currentWord && currentWord.vietnamese_meaning) {
                    const meaningWordCount = currentWord.vietnamese_meaning.split(' ').length;

                    if (meaningWordCount > 3) {
                        setupSelfAssessmentQuestion();
                    } else {
                        setupFillInBlankQuestion();
                    }
                } else {
                    setupFillInBlankQuestion();
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

    function setupFillInBlankQuestion() {
        questionPrompt.textContent = "What is the Vietnamese meaning of this word?";
        answerForm.classList.remove('hidden');
        selfAssessmentAnswer.classList.add('hidden');
        selfAssessmentButtons.classList.add('hidden');
    }

    function setupSelfAssessmentQuestion() {
        questionPrompt.textContent = "Do you know the Vietnamese meaning of this word?";
        answerForm.classList.add('hidden');
        selfAssessmentAnswer.classList.remove('hidden');
        selfAssessmentAnswer.classList.remove('revealed');
        revealMeaningBtn.classList.remove('hidden');
        selfAssessmentButtons.classList.remove('hidden');
        hiddenMeaning.textContent = currentWord.vietnamese_meaning;
    }

    async function submitResult(isCorrect, correctAnswerText) {
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

        feedbackCard.classList.remove('hidden');
        motivationalQuote.classList.add('hidden');
        feedbackCard.className = 'panel';
        feedbackCard.classList.add(isCorrect ? 'correct' : 'incorrect');

        feedbackTitle.textContent = isCorrect ? "Correct!" : "Keep Practicing!";
        // [FIX] Use the correctAnswerText passed into this function
        feedbackText.textContent = `The meaning of "${currentWord.word}" is "${correctAnswerText}".`;
    }

    async function checkAnswer() {
        const userAnswer = answerInput.value.trim();
        if (!userAnswer || !currentWord) return;

        try {
            const answerRes = await fetch(`/api/get_answer/${currentWord.id}`);
            const answerData = await answerRes.json();
            console.log("--- DEBUG: Inside checkAnswer ---");
            console.log("Response from /api/get_answer:", answerData);

            const correctAnswer = answerData.correct_answer;
            console.log("Value of correctAnswer:", correctAnswer);
            const keywords = answerData.keywords;

            let isCorrect = false;

            if (keywords) {
                const keywordList = keywords.split(',').map(kw => kw.trim().toLowerCase());
                isCorrect = keywordList.some(kw => userAnswer.toLowerCase().includes(kw));
            } else if (correctAnswer) {
                isCorrect = userAnswer.toLowerCase() === correctAnswer.toLowerCase();
            }

            submitResult(isCorrect, correctAnswer);

        } catch (error) {
            console.error("Error checking answer:", error);
        }
    }

    function resetExamUI() {
        answerInput.value = '';
        feedbackCard.classList.add('hidden');
        motivationalQuote.classList.remove('hidden');
        hintImage.classList.add('hidden');
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

    revealMeaningBtn.addEventListener('click', () => {
        selfAssessmentAnswer.classList.add('revealed');
        revealMeaningBtn.classList.add('hidden');
    });

    btnKnowIt.addEventListener('click', () => {
        // --- THÊM DÒNG DEBUG Ở ĐÂY ---
        console.log("--- DEBUG: btnKnowIt clicked ---");
        console.log("Value of currentWord:", currentWord);
        console.log("Value of currentWord.vietnamese_meaning:", currentWord.vietnamese_meaning);
        submitResult(true, currentWord.vietnamese_meaning);
    });

    btnDontKnow.addEventListener('click', () => {
            // --- THÊM DÒNG DEBUG Ở ĐÂY ---
        console.log("--- DEBUG: btnDontKnow clicked ---");
        console.log("Value of currentWord:", currentWord);
        console.log("Value of currentWord.vietnamese_meaning:", currentWord.vietnamese_meaning);
        submitResult(false, currentWord.vietnamese_meaning);
    });

    // --- 4. INITIALIZATION ---
    loadTopics();
});