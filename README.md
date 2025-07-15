# MyVocab - Gemini-Powered Smart Dictionary

A modern web-based English vocabulary assistant. Instantly look up English words, see their definitions, Vietnamese meanings, example sentences, pronunciation (IPA), related words, and even an image—all in a beautiful, easy-to-use interface powered by Google Gemini AI.

## 🛠️ Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Google AI](https://img.shields.io/badge/Google%20AI-4285F4?style=for-the-badge&logo=google&logoColor=white)

---

## 👩‍💻 How to Use MyVocab (For Clients & End-Users)

### 1. Requirements
- **A modern web browser** (Chrome, Edge, Firefox, Safari, etc.)
- **Python 3.7+** installed on your computer
- **A Google Gemini API key** (see below)

### 2. One-Time Setup

#### a. Download the App
- Get the project files from your provider (or download from GitHub if public).

#### b. Get a Gemini API Key
- Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
- Sign in with your Google account and create a new API key
- Copy the key

#### c. Start the App
1. **Open a terminal/command prompt** in the project folder (`MyVocab`).
2. **Create a file named `.env`** (if not already present) and add this line:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   Replace `your_gemini_api_key_here` with your actual key.
3. **(First time only) Install requirements:**
   ```bash
   python -m venv .venv
   # Activate the virtual environment:
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   pip install flask google-generativeai python-dotenv
   ```
4. **Run the app:**
   ```bash
   cd my_website
   python app.py
   ```

### 3. Open the App in Your Browser
- Go to [http://localhost:5000](http://localhost:5000)

---

## 🌟 What Can You Do With MyVocab?

- **Search for any English word** in the search box.
- Instantly see:
  - **English definition** (clear, modern, and easy to understand)
  - **Vietnamese meaning** (hidden by default—click to reveal)
  - **Example sentence**
  - **IPA pronunciation**
  - **Related words** (family words)
  - **Image** representing the word (if available)
  - **Similar meaning words** (synonyms, if available)
- **Mobile-friendly**: Works on phones, tablets, and computers.

---

## 🖼️ App Interface Overview

- **Left panel**: Search bar and image for the word
- **Center panel**: English definition, example, and Vietnamese meaning (click to reveal)
- **Right panel**: Pronunciation (IPA), similar words, and family words

---

## ❓ FAQ & Troubleshooting

- **"GEMINI_API_KEY not found"**: Make sure your `.env` file is in the main project folder and contains your API key.
- **App doesn't load or shows errors**: Check that Python is installed, dependencies are installed, and the API key is valid.
- **No image or some fields show N/A**: Not all words have images or all data available.

---

**Enjoy learning new words with MyVocab!**

---

_For advanced customization or developer setup, see the original README or contact your provider._