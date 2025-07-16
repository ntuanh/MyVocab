// my_website/static/exam.js

document.addEventListener('DOMContentLoaded', () => {
    // 1. Lấy tất cả các elements cần thiết từ DOM
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

    const topicSelectionContainer = document.getElementById('topic-selection-container');
    const topicForm = document.getElementById('topic-form');

    const examContainer = document.getElementById('exam-container');
    const questionWordEl = document.getElementById('question-word');

    const answerForm = document.getElementById('answer-form');
    const changeTopicsBtn = document.getElementById('change-topics-btn');

    let currentWord = null;
    let selectedTopicIds = [];

    // Biến toàn cục để lưu thông tin từ hiện tại
    let currentWord = null;

    // 2. Định nghĩa tất cả các hàm sẽ được sử dụng

    /**
     * Dọn dẹp và reset giao diện về trạng thái bắt đầu một câu hỏi mới.
     */

     async function startExam() {
        // Ẩn màn hình chọn, hiện màn hình kiểm tra
        topicSelectionContainer.classList.add('hidden');
        examContainer.classList.remove('hidden');

        await getNewWord(); // Tải từ đầu tiên
    }

     async function getNewWord() {
        // ... (hàm resetExamUI và getNewWord giữ nguyên như cũ,
        // nhưng lời gọi fetch sẽ được sửa đổi) ...

        try {
            // Sửa lại lời gọi fetch để gửi topic_ids
            const response = await fetch('/get_exam_word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic_ids: selectedTopicIds }) // Gửi danh sách ID
            });

            if (!response.ok) {
                // ... (xử lý lỗi như cũ) ...
            }
            // ... (xử lý kết quả như cũ) ...
        } catch (error) {
            // ...
        }
    }

    topicForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Lấy tất cả các checkbox đã được tick
        const checkedBoxes = document.querySelectorAll('input[name="topics"]:checked');

        // Chuyển NodeList thành một mảng các giá trị (ID)
        selectedTopicIds = Array.from(checkedBoxes).map(cb => cb.value);

        console.log("Starting exam with topic IDs:", selectedTopicIds);

        // Bắt đầu bài kiểm tra
        startExam();
    });

    changeTopicsBtn.addEventListener('click', () => {
        examContainer.classList.add('hidden');
        topicSelectionContainer.classList.remove('hidden');
        selectedTopicIds = []; // Reset lại danh sách đã chọn
    });

    function resetExamUI() {
        // Ẩn phần phản hồi và hiện lại câu trích dẫn
        answerFeedback.classList.add('hidden');
        motivationalQuote.classList.remove('hidden');
        feedbackCard.className = 'panel'; // Reset màu nền về mặc định

        // Ẩn hint
        hintCard.style.display = 'none';
        const img = hintCard.querySelector('img');
        if (img) img.style.display = 'none';

        // Reset ô nhập liệu
        answerInput.value = '';
        answerInput.disabled = false;
        questionWordEl.textContent = 'Loading...';
        
        answerInput.focus(); // Focus vào ô nhập liệu
    }

    /**
     * Gửi yêu cầu cập nhật điểm lên server.
     * @param {number} wordId - ID của từ.
     * @param {boolean} isCorrect - Kết quả kiểm tra.
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
     * Lấy một từ mới từ server để bắt đầu câu hỏi.
     */
    async function getNewWord() {
        resetExamUI();
        try {
            const response = await fetch('/get_exam_word');
            if (!response.ok) {
                const errData = await response.json();
                questionWordEl.textContent = errData.error || 'Lỗi khi tải từ!';
                answerInput.disabled = true;
                return;
            }
            currentWord = await response.json();
            questionWordEl.textContent = currentWord.word;
            
            if (currentWord.image_url) {
                hintImageEl.src = currentWord.image_url;
                hintCard.style.display = 'block';
            }
        } catch (error) {
            console.error('Error fetching word:', error);
            questionWordEl.textContent = 'Không thể tải từ để kiểm tra.';
        }
    }
    
    /**
     * Hàm xử lý khi người dùng nhấn Submit.
     * @param {Event} e - Sự kiện submit của form.
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
                feedbackTextEl.textContent = `Đáp án đúng là: ${result.correct_answer}`;
            }

            updateScoreOnServer(currentWord.id, isCorrect);
        } catch (error) {
            console.error('Error submitting answer:', error);
            alert(error.message || "Có lỗi xảy ra khi kiểm tra đáp án.");
            answerInput.disabled = false;
        }
    }

    // 3. Gán các sự kiện cho các element trên trang

    answerForm.addEventListener('submit', handleAnswerSubmit);
    nextWordBtn.addEventListener('click', getNewWord);
    
    hintCard.addEventListener('click', () => {
        const img = hintCard.querySelector('img');
        if (img) {
            const isHidden = img.style.display === 'none' || img.style.display === '';
            img.style.display = isHidden ? 'block' : 'none';
        }
    });

    // 4. Bắt đầu quy trình bằng cách gọi hàm để lấy từ đầu tiên
    getNewWord();
});