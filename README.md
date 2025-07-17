# MyVocab - Beginner's Guide

Welcome to **MyVocab**! This is a simple, modern web app to help you learn English vocabulary, powered by Google Gemini AI.

---

## 🚀 Quick Start (For Beginners)

### 1. What You Need
- **A computer with Windows, macOS, or Linux**
- **Python 3.7 or newer** ([Download Python here](https://www.python.org/downloads/))
- **A Google Gemini API key** (see below)
- **Internet connection**

---

### 2. Download the Project
- Download or clone the project files to a folder on your computer (e.g., `MyVocab`).

---

### 3. Get Your Gemini API Key
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create a new API key and copy it

---

### 4. Set Up Your Python Environment

#### a. Open a Terminal or Command Prompt
- On Windows: Press `Win + R`, type `cmd`, and press Enter
- On macOS: Open `Terminal` from Applications
- On Linux: Open your terminal app

#### b. Go to the Project Folder
Type the following command (replace the path if needed):
```sh
cd path/to/MyVocab
```

#### c. Create a Virtual Environment (Recommended)
```sh
python -m venv .venv
```

#### d. Activate the Virtual Environment
- **On Windows:**
  ```sh
  .venv\Scripts\activate
  ```
- **On macOS/Linux:**
  ```sh
  source .venv/bin/activate
  ```

#### e. Install the Required Packages
```sh
pip install -r requirements.txt
```

---

### 5. Add Your API Key
1. In the main project folder, create a file named `.env`
2. Open `.env` in a text editor and add this line:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   Replace `your_gemini_api_key_here` with your actual key.

---

### 6. Run the App
1. Make sure your virtual environment is activated
2. Start the app:
   ```sh
   cd my_website
   python app.py
   ```
3. Open your web browser and go to [http://localhost:5000](http://localhost:5000)

---

## 📝 How to Use
- Type an English word in the search box and press Enter
- See the definition, Vietnamese meaning, example sentence, pronunciation, related words, and an image
- Save words, manage topics, and test yourself with quizzes

---

## ❓ Troubleshooting
- **Python not found?** Make sure you installed Python and added it to your PATH
- **Module not found?** Run `pip install -r requirements.txt` again
- **API key error?** Double-check your `.env` file and make sure there are no spaces or typos
- **App not loading?** Check the terminal for errors and make sure you are in the correct folder

---

## 💡 Tips
- Always activate your virtual environment before running the app
- You can stop the app anytime by pressing `Ctrl + C` in the terminal
- If you want to install new packages, use `pip install package_name` while your virtual environment is active

---

**Enjoy learning with MyVocab!**