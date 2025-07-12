document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatBox = document.getElementById('chat-box');

    // Hàm để thêm tin nhắn vào giao diện
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `${sender}-message`);

        const messageP = document.createElement('p');
        messageP.textContent = text;

        messageDiv.appendChild(messageP);
        chatBox.appendChild(messageDiv);

        // Tự động cuộn xuống tin nhắn mới nhất
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // Hàm để xử lý khi form được gửi
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault(); // Ngăn trang web tải lại

        const userMessage = userInput.value.trim();
        if (userMessage === '') return;

        // Hiển thị ngay tin nhắn của người dùng
        addMessage(userMessage, 'user');

        // Xóa nội dung trong ô nhập liệu
        userInput.value = '';

        try {
            // Gửi request đến backend (endpoint /chat)
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                // Gửi tin nhắn dưới dạng JSON
                body: JSON.stringify({
                    message: userMessage,
                    user_id: 'default_user' // Trong ứng dụng thực tế, đây nên là một ID duy nhất cho mỗi người dùng
                }),
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            const botResponse = data.response;

            // Hiển thị câu trả lời của bot
            addMessage(botResponse, 'bot');

        } catch (error) {
            console.error('Error:', error);
            addMessage('Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại.', 'bot');
        }
    });
});