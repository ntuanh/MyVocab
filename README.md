# MyVocab

<table>
<tr>
<td width="70%" style="vertical-align: top;">

[MyVocab](https://my-vocab-xi.vercel.app/) is a modern, AI-powered web app to help you learn English vocabulary efficiently. It provides definitions, Vietnamese translations, example sentences, pronunciation, synonyms, related words, and images for any English word. You can save words, organize them by topics, and test yourself with quizzes .
[&rarr; Access it here](https://my-vocab-xi.vercel.app/)

</td>
<td width="30%" style="vertical-align: top; text-align: center;">

<img src="./images/MyVocabQR.png" alt="MyVocab QR" width="350" height="350" style="display: block; margin: 0 auto;">

</td>
</tr>
</table>

---

## What Makes MyVocab Special?

| Feature | Description |
| :--- | :--- |
| 📸 **Visual Learning** | Don't just read definitions—see them! Every word is paired with a vivid image, helping you build stronger memory connections. |
| 🧠 **AI-Powered Context** | Get more than just a translation. Our AI provides rich details like clear definitions, practical examples, synonyms, and related "family words". |
| 🎯 **Smart Exam Mode** | Stop wasting time on words you already know. The exam mode intelligently tests you more on the vocabulary you find difficult, making your practice sessions incredibly efficient. |
| 📚 **Personalized Collection**| Save any word with a single click. Organize your personal dictionary into custom topics to focus your learning on what's important to you. |
---

## Tech Stack

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgresql-%23336791.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![HTML5](https://img.shields.io/badge/html5-%23E34F26.svg?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/css3-%231572B6.svg?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![Vercel](https://img.shields.io/badge/vercel-%23000000.svg?style=for-the-badge&logo=vercel&logoColor=white)

---

## Demo
[Click hiaaaa:))](./images)

![search](./images/search.png)

---

## Usage

- **Search**: Enter an English word and press Enter.
- **View Details**: See definition, translation, example, IPA, synonyms, related words, and image.
- **Save**: Click "Save Word" and assign it to topics.
- **Manage Topics**: Add or remove topics as you like.
- **Quiz**: Go to "Exam" to test yourself on saved words by topic.
- **Data**: View and manage all your saved words (password-protected).

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
│   ├── database.py       # PostgreSQL DB logic
│   ├── static/           # JS, CSS, client assets
│   │   ├── style.css
│   │   ├── script.js
│   │   ├── data.js
│   │   ├── exam.js
│   │   └── manage_topics.js
│   └── templates/        # HTML templates (Jinja2)
│       ├── index.html
│       ├── exam.html
│       ├── data.html
│       └── manage_topics.html
│
├── requirements.txt      # Python dependencies
├── myvocab.db            # (Legacy) SQLite database (not used if PostgreSQL is configured)
├── LICENSE
└── README.md
```

---

### Database Schema

- `words`: id, word, vietnamese_meaning, english_definition, example, image_url, priority_score, pronunciation_ipa, synonyms_json, family_words_json
- `topics`: id, name
- `word_topics`: word_id, topic_id

---


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Enjoy learning with MyVocab!**


