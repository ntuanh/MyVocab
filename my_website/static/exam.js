// my_website/static/exam.js

document.addEventListener('DOMContentLoaded', () => {
    // Lấy các elements
    const questionWordEl = document.getElementById('question-word');
    const hintCard = document.getElementById('hint-card');
    const hintImageEl = document.getElementById('hint-image');
    const answerForm = document.getElementById('answer-form');
    const answerInput = document.getElementById('answer-input');
    const feedbackCard = document.getElementById('feedback-card');
    const feedbackTitleEl = document.getElementById('feedback-title');
    const feedbackTextEl = document.getElementById('feedback-text');
    const nextWordBtn = document.getElementById('next-word-btn');

    let currentWord = null;

    /**
     * Hàm để lấy một từ mới từ database để kiểm tra.
     * Đây là những từ bạn đã lưu.
     */
    async function getNewWord() {
        // Reset giao diện về trạng thái bắt đầu một câu hỏi mới
        feedbackCard.classList.add('hidden');
        answerInput.value = '';
        answerInput.disabled = false;
        hintCard.classList.add('hidden');
        hintCard.classList.remove('revealed'); // Đảm bảo hint bị ẩn
        questionWordEl.textContent = 'Loading...';

        try {
            // Gọi API để lấy một từ ngẫu nhiên từ những từ đã lưu
            const response = await fetch('/get_exam_word');
            if (!response.ok) {
                const errData = await response.json();
                questionWordEl.textContent = errData.error || 'Lỗi khi tải từ!';
                answerInput.disabled = true;
                return;
            }
            currentWord = await response.json();
            questionWordEl.textContent = currentWord.word;

            // Nếu từ có hình ảnh, hiển thị nút gợi ý
            if (currentWord.image_url) {
                hintImageEl.src = currentWord.image_url;
                hintCard.style.display = 'block';
            } else {
                hintCard.style.display = 'none';
            }
        } catch (error) {
            console.error('Error fetching word:', error);
            questionWordEl.textContent = 'Không thể tải từ để kiểm tra.';
        }
    }

    /**
     * Hàm xử lý khi người dùng gửi câu trả lời
     */
    answerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!currentWord || answerInput.disabled) return;

        const userAnswer_1 = answerInput.value.trim(); // Lấy và làm sạch input
        if (userAnswer_1 === '') {
            alert("Please enter your answer!"); // Hoặc có thể hiển thị một thông báo tinh tế hơn
            return;
        }

        const userAnswer = answerInput.value.trim().toLowerCase(); // Chuyển câu trả lời về chữ thường
        if (!userAnswer) return; // Không làm gì nếu người dùng không nhập

        answerInput.disabled = true;

        try {
            // Gọi server để lấy đáp án đúng
            const response = await fetch(`/get_answer/${currentWord.id}`); // Giả sử có một endpoint mới
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || "Không thể lấy đáp án.");
            }

            const correctAnswer = result.correct_answer.toLowerCase(); // Lấy đáp án đúng và chuyển về chữ thường
            let isCorrect = false;

            // --- LOGIC SO SÁNH LINH HOẠT ---
            // Tách đáp án đúng thành các phần riêng lẻ (dựa trên dấu phẩy hoặc dấu chấm phẩy)
            const correctParts = correctAnswer.split(/,|;/).map(part => part.trim());

            // Kiểm tra xem câu trả lời của người dùng có trùng với BẤT KỲ phần nào của đáp án đúng không
            if (correctParts.includes(userAnswer)) {
                isCorrect = true;
            }

            // --- Hiển thị phản hồi ---
            feedbackCard.classList.remove('hidden');
            if (isCorrect) {
                feedbackTitleEl.textContent = "Correct!";
                feedbackCard.className = 'panel feedback-card correct';
                // Chỉ hiển thị "Good job!" khi đúng
                feedbackTextEl.textContent = "Good job!";
            } else {
                feedbackTitleEl.textContent = "Incorrect!";
                feedbackCard.className = 'panel feedback-card incorrect';
                // Chỉ hiển thị đáp án đúng khi sai
                feedbackTextEl.textContent = `Đáp án đúng là: ${result.correct_answer}`;
            }

            // Gửi kết quả đúng/sai lên server để cập nhật điểm
            updateScoreOnServer(currentWord.id, isCorrect);

        } catch (error) {
            console.error('Error submitting answer:', error);
            alert(error.message);
            answerInput.disabled = false;
        }
    });

    /**
     * update score to server
     */
    async function updateScoreOnServer(wordId, isCorrect) {
        try {
            await fetch('/submit_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: wordId, is_correct: isCorrect })
            });
        } catch (error) {
            console.error("Failed to update score:", error);
        }
    }


    // Sự kiện cho các nút khác
    hintCard.addEventListener('click', () => {
        hintCard.classList.toggle('revealed');
        // Thay đổi logic class 'hidden' bằng 'revealed' để CSS xử lý
        const img = hintCard.querySelector('img');
        if (hintCard.classList.contains('revealed')) {
            img.style.display = 'block';
        } else {
            img.style.display = 'none';
        }
    });

    nextWordBtn.addEventListener('click', getNewWord);

    // Bắt đầu bài kiểm tra bằng cách lấy từ đầu tiên
    getNewWord();
});