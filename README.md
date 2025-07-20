# MyVocab

[MyVocab](https://my-vocab-xi.vercel.app/)

<table>
<tr>
<td width="70%" style="vertical-align: top;">

**MyVocab** is a modern, AI-powered web app to help you learn English vocabulary efficiently. It provides definitions, Vietnamese translations, example sentences, pronunciation, synonyms, related words, and images for any English word. You can save words, organize them by topics, and test yourself with quizzes. Powered by Google Gemini AI and built with Flask.

</td>
<td width="30%" style="vertical-align: top; text-align: center;">

<img src="./images/MyVocabQR.png" alt="MyVocab QR" width="350" height="350" style="display: block; margin: 0 auto;">

</td>
</tr>
</table>

---

## Tech Stack

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)
![HTML5](https://img.shields.io/badge/html5-%23E34F26.svg?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/css3-%231572B6.svg?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![Vercel](https://img.shields.io/badge/vercel-%23000000.svg?style=for-the-badge&logo=vercel&logoColor=white)

---

## Features

- **Smart Dictionary**: Get English definitions, Vietnamese meanings, example sentences, IPA pronunciation, synonyms, related words, and an image for any English word.
- **Topic Management**: Organize your vocabulary by custom topics.
- **Save Words**: Save words to your personal database and manage them easily.
- **Quiz Mode**: Test your knowledge with topic-based quizzes.
- **Modern UI**: Responsive, clean, and intuitive interface.
- **AI Integration**: Uses Google Gemini for rich, contextual word data.
- **Image Support**: Fetches relevant images for words (if Pexels API key is provided).

---

## Demo

![screenshot or gif here if available]

---

## Usage

- **Search**: Enter an English word and press Enter.
- **View Details**: See definition, translation, example, IPA, synonyms, related words, and image.
- **Save**: Click "Save Word" and assign it to topics.
- **Manage Topics**: Add or remove topics as you like.
- **Quiz**: Go to "Exam" to test yourself on saved words by topic.
- **Data**: View and manage all your saved words.

---

## Project Structure

```
MyVocab/
│
├── api/                  # Vercel/production entrypoint
│   └── index.py
│
├── my_website/           # Main Flask app
│   ├── app.py            # Flask app and routes
│   ├── handle_request.py # AI, translation, and API logic
│   ├── database.py       # SQLite DB logic
│   ├── static/           # JS, CSS, client assets
│   └── templates/        # HTML templates (Jinja2)
│
├── requirements.txt      # Python dependencies
├── myvocab.db            # SQLite database (auto-created)
└── README.md
```

## API & Database

- **Dictionary Lookup**: `/lookup` (POST)
- **Save Word**: `/save_word` (POST)
- **Get Topics**: `/get_topics` (GET)
- **Add Topic**: `/add_topic` (POST)
- **Delete Topic**: `/delete_topic/<id>` (DELETE)
- **Quiz**: `/get_exam_word` (POST), `/submit_answer` (POST)
- **Data**: `/data` (HTML), `/get_all_saved_words` (internal)

**Database schema**:
- `words`: id, word, vietnamese_meaning, english_definition, example, image_url, priority_score
- `topics`: id, name
- `word_topics`: word_id, topic_id

---

## Dependencies

- Flask
- gunicorn
- python-dotenv
- google-generativeai
- googletrans==4.0.0-rc1
- requests

---

## Troubleshooting

- **Python not found**: Ensure Python 3.12+ is installed and in your PATH.
- **Module not found**: Run `pip install -r requirements.txt` again.
- **API key error**: Check your `.env` file for typos or missing keys.
- **App not loading**: Check terminal for errors and ensure you are in the correct folder.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Enjoy learning with MyVocab!**

