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

        const userAnswer = answerInput.value.trim();
        answerInput.disabled = true; // Vô hiệu hóa ô nhập liệu khi đang chờ kết quả

        // --- LOGIC KIỂM TRA ĐÚNG/SAI (SỬA LỖI Ở ĐÂY) ---
        // Chúng ta cần server cho biết đáp án đúng là gì.
        // Nhưng để đơn giản hóa, chúng ta sẽ gửi câu trả lời của người dùng lên,
        // và yêu cầu server cập nhật điểm dựa trên logic so sánh (tạm thời)
        // Đây là một cách tiếp cận khác:

        try {
            // Lấy đáp án đúng từ server và cập nhật điểm
            const response = await fetch('/submit_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: currentWord.id,
                    // is_correct sẽ được quyết định sau khi có đáp án đúng
                    // Để đơn giản, ta vẫn gửi 1 giá trị tạm
                    is_correct: false // Giá trị này sẽ được tính lại
                })
            });
            const result = await response.json();

            if (result.status !== 'success') {
                throw new Error(result.message || 'Lỗi khi cập nhật điểm.');
            }

            const correctAnswer = result.correct_answer;
            let isCorrect = false;

            // Logic so sánh câu trả lời (có thể cải tiến)
            // So sánh không phân biệt hoa thường và bỏ qua các chi tiết nhỏ
            if (userAnswer.toLowerCase().includes(correctAnswer.toLowerCase().substring(0, 10))) {
                isCorrect = true;
            }

            // Hiển thị phản hồi
            feedbackCard.classList.remove('hidden');
            if (isCorrect) {
                feedbackTitleEl.textContent = "Correct!";
                feedbackCard.className = 'panel feedback-card correct';
                feedbackTextEl.textContent = `Good job!`;
                // Gửi yêu cầu cập nhật điểm thực sự
                updateScoreOnServer(currentWord.id, true);
            } else {
                feedbackTitleEl.textContent = "Incorrect!";
                feedbackCard.className = 'panel feedback-card incorrect';
                feedbackTextEl.textContent = `Đáp án đúng là: ${correctAnswer}`;
                // Gửi yêu cầu cập nhật điểm thực sự
                updateScoreOnServer(currentWord.id, false);
            }

        } catch (error) {
            console.error('Error submitting answer:', error);
            alert('Không thể gửi câu trả lời.');
            answerInput.disabled = false;
        }
    });

    /**
     * Hàm gửi yêu cầu cập nhật điểm lên server sau khi đã biết đúng/sai
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