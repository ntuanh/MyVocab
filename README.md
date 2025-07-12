# MyVocab - Gemini-Powered Chatbot

A modern web-based chatbot application built with Flask and Google's Gemini AI. This project provides an interactive chat interface where users can have conversations with an AI assistant powered by Gemini's advanced language model.

## 🚀 Features

- **Real-time Chat Interface**: Clean and responsive web-based chat UI
- **AI-Powered Responses**: Powered by Google's Gemini 1.5 Flash model
- **Chat History Management**: Maintains conversation context for each user
- **Modern UI/UX**: Beautiful, mobile-friendly interface with smooth animations
- **Session Management**: Supports multiple concurrent users with separate chat histories
- **Error Handling**: Robust error handling for API failures and network issues

## 🛠️ Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Google AI](https://img.shields.io/badge/Google%20AI-4285F4?style=for-the-badge&logo=google&logoColor=white)

### Backend
- **Python 3.x**: Core programming language
- **Flask**: Lightweight web framework for API endpoints
- **Google Generative AI**: Integration with Gemini AI model
- **python-dotenv**: Environment variable management

### Frontend
- **HTML5**: Semantic markup structure
- **CSS3**: Modern styling with flexbox and responsive design
- **Vanilla JavaScript**: Client-side interactivity and API communication
- **Fetch API**: Asynchronous HTTP requests

### Development & Deployment
- **Virtual Environment**: Isolated Python dependencies
- **Environment Variables**: Secure API key management
- **Debug Mode**: Development-friendly error reporting

## 📁 Project Structure

```
MyVocab/
├── my_website/
│   ├── app.py                 # Main Flask application
│   ├── handle_request.py      # Gemini AI integration logic
│   ├── __init__.py           # Python package initialization
│   ├── static/
│   │   ├── style.css         # CSS styling
│   │   └── script.js         # Frontend JavaScript
│   └── templates/
│       └── index.html        # Main HTML template
├── .venv/                    # Virtual environment
└── README.md                # Project documentation
```

## 🚀 Getting Started

### Prerequisites

- Python 3.7 or higher
- Google Gemini API key
- Git (for cloning the repository)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd MyVocab
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv .venv
   
   # On Windows
   .venv\Scripts\activate
   
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install flask google-generativeai python-dotenv
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

   To get a Gemini API key:
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Copy the key to your `.env` file

5. **Run the application**
   ```bash
   cd my_website
   python app.py
   ```

6. **Access the application**
   
   Open your browser and navigate to: `http://localhost:5000`

## 💻 Usage

1. **Start a Conversation**: The chatbot will greet you with a welcome message
2. **Send Messages**: Type your message in the input field and press Enter or click "Gửi"
3. **View Responses**: The AI will respond with contextual and helpful information
4. **Continue Chatting**: The conversation maintains context, so you can have natural back-and-forth discussions

## 🔧 Configuration

### Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini API key (required)

### Customization

You can customize the application by modifying:

- **Chat Interface**: Edit `templates/index.html` for UI changes
- **Styling**: Modify `static/style.css` for visual customization
- **AI Behavior**: Adjust prompts and parameters in `handle_request.py`
- **Server Settings**: Configure Flask settings in `app.py`

## 🐛 Troubleshooting

### Common Issues

1. **"GEMINI_API_KEY not found"**
   - Ensure your `.env` file exists in the project root
   - Verify the API key is correctly copied from Google AI Studio

2. **"Model is not initialized"**
   - Check your internet connection
   - Verify your API key is valid and has sufficient quota

3. **Chat not responding**
   - Check browser console for JavaScript errors
   - Verify the Flask server is running on the correct port

## 🔒 Security Notes

- Never commit your `.env` file to version control
- Keep your API keys secure and rotate them regularly
- Consider implementing rate limiting for production use
- Add proper authentication for multi-user environments

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- Google Gemini AI for providing the powerful language model
- Flask community for the excellent web framework
- Contributors and users of this project

---

**Happy Chatting! 🤖💬**