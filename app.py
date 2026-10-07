import os
from datetime import datetime, timedelta, timezone

# Local runs keep credentials in a .env file; on Vercel the same names arrive as
# project Environment Variables and there is nothing to load. This has to run
# before the imports below, which read os.environ at module scope.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from handle_request import get_dictionary_data, choose_topic, OK, SKIPPED
from practice import DEFAULT_COUNT, MAX_COUNT, make_exercises, check_answer, check_grammar, give_up
from practice import SKILL as PRACTICE_SKILL
from listening import POINTS_PER_ANSWER, WRONG_LOSES, episodes_with_scores, save_score
from listening import SKILL as LISTENING_SKILL
from reading import POINTS_RIGHT, WRONG_LOSES as READING_WRONG_LOSES, MINUTES_PER_PART, PARTS_BY_ID, public_part, plan as reading_plan
from reading import submit as submit_reading, SKILL as READING_SKILL
from writing import KINDS as WRITING_KINDS, MAX_SCORE as WRITING_MAX, SKILL as WRITING_SKILL
from writing import prompt_for as writing_prompt, check as check_writing, retry as retry_writing
import updates
from database import (
    get_writing_history,
    get_writing_piece,
    SKILLS,
    PAST_WEEKS_SHOWN,
    get_progress,
    get_word_of_the_day,
    set_weekly_targets,
    save_word,
    get_word_for_exam,
    update_word_score,
    get_all_saved_words,
    delete_word_by_id,
    get_correct_answer_by_id,
    get_all_topics,
    add_new_topic,
    delete_topic_by_id
)

# --- FLASK APP SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            static_folder=os.path.join(BASE_DIR, 'static'),
            template_folder=os.path.join(BASE_DIR, 'templates'))

# A secret key is required for Flask sessions to work. On Vercel every instance
# must sign cookies with the same key, so it has to come from the environment --
# the fallback below is only good enough for a local run.
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    print("WARN: FLASK_SECRET_KEY is not set. Using an insecure development key -- "
          "anyone could forge the /data session cookie. Set it in your Vercel "
          "project's Environment Variables.")
    app.secret_key = "a_super_secret_key_for_local_development_only"

def has_data_access():
    """My Words needs the password, except on your own computer: ./run.sh starts
    Flask's debug server, and a request to it from this same machine is you.
    Vercel never runs in debug mode, so online the password is always asked."""
    if session.get('data_access_granted'):
        return True
    return app.debug and request.remote_addr in ('127.0.0.1', '::1')

@app.route('/')
def index():
    """Renders the main dictionary page."""
    return render_template('index.html')

@app.route('/exam')
def exam_page():
    """Renders the exam page."""
    return render_template('exam.html')

@app.route('/data')
def data_page():
    if not has_data_access():
        # ?unlock makes the dictionary page open its password prompt.
        return redirect(url_for('index', unlock=1))
    return render_template('data.html')

@app.route('/practice')
def practice_page():
    """Renders the grammar and vocabulary practice page."""
    return render_template('practice.html')

@app.route('/listening')
def listening_page():
    """Renders the listening practice page: BBC 6 Minute English episodes."""
    return render_template('listening.html', points_per_answer=POINTS_PER_ANSWER, wrong_loses=WRONG_LOSES)

@app.route('/reading')
def reading_page():
    """Renders the reading practice page: 50 IELTS-style parts, one a day."""
    return render_template('reading.html', points_right=POINTS_RIGHT, wrong_loses=READING_WRONG_LOSES,
                           minutes=MINUTES_PER_PART, parts=len(PARTS_BY_ID))

@app.route('/writing')
def writing_page():
    """Renders the writing practice page: a diary, IELTS Task 1 or Task 2, marked out of 80."""
    return render_template('writing.html', kinds=WRITING_KINDS, max_score=WRITING_MAX)

@app.route('/tracking')
def tracking_page():
    """Renders the Tracking page: the weekly score of every skill, one band each."""
    return render_template('tracking.html', bands=BANDS,
                           min_target=MIN_WEEKLY_TARGET, max_target=MAX_WEEKLY_TARGET)

@app.route('/manage_topics')
def manage_topics_page():
    """Renders the topic management page."""
    return render_template('manage_topics.html')

@app.route('/api/verify_password', methods=['POST'])
def verify_password():
    """Verifies the password for accessing the data page."""
    correct_password = os.environ.get('VIEW_DATA_PASSWORD')
    if not correct_password:
        return jsonify({'error': 'Server configuration error'}), 500

    data = request.get_json(silent=True) or {}
    submitted_password = data.get('password')

    if submitted_password == correct_password:
        session['data_access_granted'] = True
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'error': 'Incorrect password'}), 401

@app.route('/api/all_data')
def get_all_data():
    """API endpoint to fetch all saved data (protected by session)."""
    if not has_data_access():
        return jsonify({'error': 'Unauthorized'}), 401
    words = get_all_saved_words()
    return jsonify(words)

@app.route('/api/lookup', methods=['POST'])
def lookup_route():
    """API endpoint to look up a word."""
    data = request.get_json(silent=True) or {}
    user_word = data.get('word') # Assuming the key is 'word' now
    if not user_word:
        return jsonify({'error': 'No word provided'}), 400
    return get_dictionary_data(user_word)

def _ai_topic(word_data):
    """Asks AI for the one topic a word belongs in, creating it when none of the
    saved topics fits. Returns {"topic_id", "topic", "is_new"} or {"error"}."""
    word = str(word_data.get('word') or '').strip()[:100]
    definition = str(word_data.get('english_definition') or '').strip()[:500]
    topics = get_all_topics()
    choice, status = choose_topic(word, definition, [t['name'] for t in topics])
    if status == SKIPPED:
        return {"error": "AI is not set up (no GEMINI_API_KEY)."}
    if status != OK:
        return {"error": "AI could not choose a topic right now."}
    if not choice['is_new']:
        topic_id = next(t['id'] for t in topics if t['name'] == choice['topic'])
        return {"topic_id": topic_id, "topic": choice['topic'], "is_new": False}
    created = add_new_topic(choice['topic'])
    if not created:
        return {"error": f"Could not create the topic '{choice['topic']}'."}
    return {"topic_id": created['id'], "topic": created['name'], "is_new": True}

@app.route('/api/save_word', methods=['POST'])
def save_word_route():
    """API endpoint to save a word. With "ai_topic" set, AI also files it under
    the one topic it fits best; the word is saved even when the AI fails."""
    data = request.get_json(silent=True) or {}
    word_data = data.get('word_data')
    topic_ids = _topic_ids(data.get('topic_ids'))
    if not word_data:
        return jsonify({"error": "Word data is missing."}), 400
    ai = _ai_topic(word_data) if data.get('ai_topic') else None
    if ai and ai.get('topic_id') and ai['topic_id'] not in topic_ids:
        topic_ids.append(ai['topic_id'])
    result = save_word(word_data, topic_ids)
    if ai is not None:
        result['ai'] = ai
    return jsonify(result)

@app.route('/api/get_exam_word', methods=['POST'])
def get_exam_word_route():
    """API endpoint to get a word for the exam."""
    data = request.get_json(silent=True) or {}
    topic_ids = data.get('topic_ids', None)
    word = get_word_for_exam(topic_ids)
    if word:
        return jsonify(word)
    return jsonify({"error": "No words found for the selected topics."}), 404

@app.route('/api/submit_answer', methods=['POST'])
def submit_answer_route():
    """API endpoint to submit an exam answer."""
    data = request.get_json(silent=True) or {}
    word_id = data.get('id')
    is_correct = data.get('is_correct')
    result = update_word_score(word_id, is_correct)
    return jsonify(result)


@app.route('/api/get_answer', methods=['GET'])  # Bỏ <int:word_id> khỏi URL
def get_answer_route():
    # Lấy 'id' từ query parameter của URL
    word_id = request.args.get('id', type=int)

    if not word_id:
        return jsonify({"error": "Word ID is required."}), 400

    answer_data = get_correct_answer_by_id(word_id)

    if answer_data:
        return jsonify(answer_data)

    return jsonify({"error": "Word not found."}), 404

@app.route('/api/delete_word/<int:word_id>', methods=['DELETE'])
def delete_word_route(word_id):
    """API endpoint to delete a saved word."""
    result = delete_word_by_id(word_id)
    return jsonify(result)

@app.route('/api/get_topics', methods=['GET'])
def get_topics_route():
    """API endpoint to get the list of all topics."""
    topics = get_all_topics()
    return jsonify(topics)

@app.route('/api/add_topic', methods=['POST'])
def add_topic_route():
    """API endpoint to add a new topic."""
    data = request.get_json(silent=True) or {}
    topic_name = data.get('topic_name')
    if not topic_name:
        return jsonify({"error": "Topic name cannot be empty."}), 400
    new_topic = add_new_topic(topic_name.strip())
    if new_topic:
        return jsonify(new_topic), 201
    return jsonify({"error": "Failed to create topic."}), 500

@app.route('/api/delete_topic/<int:topic_id>', methods=['DELETE'])
def delete_topic_route(topic_id):
    """API endpoint to delete a topic."""
    result = delete_topic_by_id(topic_id)
    return jsonify(result)


def _topic_ids(raw):
    """Topic ids from a request body, dropping anything that is not a whole number."""
    ids = []
    for value in raw if isinstance(raw, list) else []:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            pass
    return ids

@app.route('/api/practice/exercises', methods=['POST'])
def practice_exercises_route():
    """API endpoint to get a batch of practice exercises."""
    data = request.get_json(silent=True) or {}
    try:
        count = min(MAX_COUNT, max(1, int(data.get('count', DEFAULT_COUNT))))
    except (TypeError, ValueError):
        count = DEFAULT_COUNT
    body, status = make_exercises(data.get('mode'), _topic_ids(data.get('topic_ids')), count)
    return jsonify(body), status

MIN_WEEKLY_TARGET = 10
MAX_WEEKLY_TARGET = 5000

# The Tracking page shows one band per skill, each with its own weekly target.
# practice_url is the page that earns the skill's points; a skill without one
# can still have a target, and its tracking starts with its first points.
BANDS = [
    {"skill": "vocab", "name": "Vocab", "icon": "fa-font", "practice_url": "/practice"},
    {"skill": "listening", "name": "Listening", "icon": "fa-headphones", "practice_url": "/listening"},
    {"skill": "reading", "name": "Reading", "icon": "fa-book-reader", "practice_url": "/reading"},
    {"skill": "writing", "name": "Writing", "icon": "fa-pen-fancy", "practice_url": "/writing"},
]
BAND_NAMES = {band["skill"]: band["name"] for band in BANDS}
TRACKING_WEEKS = 8  # this week and the seven before it

def _past_weeks(raw):
    """How many finished weeks a page wants back with its progress."""
    try:
        return max(0, min(TRACKING_WEEKS - 1, int(raw)))
    except (TypeError, ValueError):
        return PAST_WEEKS_SHOWN

def _skill_error(skill):
    """Why a skill's score can't be read or set, or None when it can."""
    return None if skill in SKILLS else f"Unknown skill '{skill}'."

def _target_or_error(skill, raw):
    """A weekly target as whole points, or (None, why it was refused)."""
    if error := _skill_error(skill):
        return None, error
    try:
        target = int(raw)
    except (TypeError, ValueError):
        target = 0
    if not MIN_WEEKLY_TARGET <= target <= MAX_WEEKLY_TARGET:
        return None, (f"Pick a {BAND_NAMES.get(skill, skill)} target from "
                      f"{MIN_WEEKLY_TARGET} to {MAX_WEEKLY_TARGET} points a week.")
    return target, None

def _all_bands(offset):
    """Every band's week and its last weeks, for the Tracking page; None if the
    database could not be read."""
    bands = []
    for band in BANDS:
        progress = get_progress(band['skill'], offset, TRACKING_WEEKS - 1)
        if progress is None:
            return None
        bands.append({"skill": band['skill'], "has_practice": bool(band['practice_url']), "progress": progress})
    return bands

def _utc_offset(raw):
    """The learner's clock as minutes ahead of UTC (420 in Vietnam), sent by the
    browser, so the goal's weeks start on their Monday, not the server's."""
    try:
        return max(-720, min(840, int(raw)))
    except (TypeError, ValueError):
        return 0

@app.route('/api/practice/check', methods=['POST'])
def practice_check_route():
    """API endpoint to mark one practice answer for grammar and vocabulary."""
    data = request.get_json(silent=True) or {}
    body, status = check_answer(data.get('mode'), data.get('item'), data.get('answer'))
    if body.get('points'):
        body['progress'] = get_progress(PRACTICE_SKILL, _utc_offset(data.get('utc_offset')))
    return jsonify(body), status

@app.route('/api/practice/give_up', methods=['POST'])
def practice_give_up_route():
    """API endpoint for "Show answer": scored as a wrong answer."""
    data = request.get_json(silent=True) or {}
    body, status = give_up(data.get('mode'), data.get('item'))
    if body.get('points'):
        body['progress'] = get_progress(PRACTICE_SKILL, _utc_offset(data.get('utc_offset')))
    return jsonify(body), status

@app.route('/api/progress', methods=['GET'])
def progress_route():
    """API endpoint for a skill's points this week against its weekly goal."""
    skill = request.args.get('skill', PRACTICE_SKILL)
    if error := _skill_error(skill):
        return jsonify({"error": error}), 400
    progress = get_progress(skill, _utc_offset(request.args.get('utc_offset')),
                            _past_weeks(request.args.get('past_weeks')))
    if progress is None:
        return jsonify({"error": "Could not load your progress."}), 500
    return jsonify(progress)

@app.route('/api/progress/all', methods=['GET'])
def progress_all_route():
    """API endpoint for the Tracking page: every band's week and its last weeks."""
    bands = _all_bands(_utc_offset(request.args.get('utc_offset')))
    if bands is None:
        return jsonify({"error": "Could not load your scores."}), 500
    return jsonify({"bands": bands})

@app.route('/api/today', methods=['GET'])
def today_route():
    """API endpoint for the home page's Today section: a word of the day and
    how every band's week is going."""
    offset = _utc_offset(request.args.get('utc_offset'))
    word = get_word_of_the_day(offset)
    bands = []
    for band in BANDS:
        progress = get_progress(band['skill'], offset, 0)
        if progress is None:
            return jsonify({"error": "Could not load today."}), 500
        bands.append({"skill": band['skill'], "name": band['name'], "icon": band['icon'],
                      "points": progress['points'], "due": progress['due'], "started": progress['started'],
                      "reached": progress['started'] and progress['remaining'] == 0})
    return jsonify({"word": word or None, "bands": bands})

@app.route('/api/progress/target', methods=['POST'])
def progress_target_route():
    """API endpoint to set one skill's weekly target, from this week on."""
    data = request.get_json(silent=True) or {}
    skill = data.get('skill', PRACTICE_SKILL)
    target, error = _target_or_error(skill, data.get('target'))
    if error:
        return jsonify({"error": error}), 400
    offset = _utc_offset(data.get('utc_offset'))
    if not set_weekly_targets({skill: target}, offset):
        return jsonify({"error": "Could not save the target."}), 500
    return jsonify(get_progress(skill, offset, _past_weeks(data.get('past_weeks'))))

@app.route('/api/progress/targets', methods=['POST'])
def progress_targets_route():
    """API endpoint for the Tracking page's "Set targets": several skills' weekly
    targets at once ({"targets": {"vocab": 300, ...}}), from this week on.
    Nothing is saved unless every one of them is valid."""
    data = request.get_json(silent=True) or {}
    raw = data.get('targets')
    if not isinstance(raw, dict) or not raw:
        return jsonify({"error": "No targets were sent."}), 400
    targets = {}
    for skill, value in raw.items():
        target, error = _target_or_error(skill, value)
        if error:
            return jsonify({"error": error, "skill": skill}), 400
        targets[skill] = target
    offset = _utc_offset(data.get('utc_offset'))
    if not set_weekly_targets(targets, offset):
        return jsonify({"error": "Could not save the targets."}), 500
    bands = _all_bands(offset)
    if bands is None:
        return jsonify({"error": "The targets are saved, but your scores could not be loaded."}), 500
    return jsonify({"bands": bands})

@app.route('/api/listening/episodes', methods=['GET'])
def listening_episodes_route():
    """API endpoint for the listening episodes, newest first, with your scores."""
    episodes = episodes_with_scores()
    if episodes is None:
        return jsonify({"error": "Could not load your scores."}), 500
    return jsonify({"episodes": episodes})

@app.route('/api/listening/score', methods=['POST'])
def listening_score_route():
    """API endpoint to keep your score on an episode's BBC quiz or worksheet.
    The first score of an episode earns listening points."""
    data = request.get_json(silent=True) or {}
    body, status = save_score(data.get('episode_id'), data.get('correct'), data.get('total'))
    if status == 200:
        body['progress'] = get_progress(LISTENING_SKILL, _utc_offset(data.get('utc_offset')))
    return jsonify(body), status

@app.route('/api/reading/plan', methods=['GET'])
def reading_plan_route():
    """API endpoint for the 50-day reading plan: every part with your scores,
    today's part and your day streak."""
    body = reading_plan(_utc_offset(request.args.get('utc_offset')))
    if body is None:
        return jsonify({"error": "Could not load your reading plan."}), 500
    return jsonify(body)

@app.route('/api/reading/part/<int:part_id>', methods=['GET'])
def reading_part_route(part_id):
    """API endpoint for one reading part: the passage and questions, no answers."""
    part = PARTS_BY_ID.get(part_id)
    if part is None:
        return jsonify({"error": "That reading part does not exist."}), 404
    return jsonify(public_part(part))

@app.route('/api/reading/submit', methods=['POST'])
def reading_submit_route():
    """API endpoint to mark a reading part. The first submission of a part
    earns reading points; the answer key comes back with the marks."""
    data = request.get_json(silent=True) or {}
    body, status = submit_reading(data.get('part_id'), data.get('answers'))
    if status == 200:
        body['progress'] = get_progress(READING_SKILL, _utc_offset(data.get('utc_offset')))
    return jsonify(body), status

def _day_number(offset):
    """Today's date on the learner's clock, as a number that goes up by one a day."""
    return (datetime.now(timezone.utc) + timedelta(minutes=offset)).date().toordinal()

@app.route('/api/writing/prompt', methods=['GET'])
def writing_prompt_route():
    """API endpoint for something to write about: today's diary idea and words
    to try, or the next IELTS question (?after=<id> for a different one)."""
    offset = _utc_offset(request.args.get('utc_offset'))
    body, status = writing_prompt(request.args.get('kind'), offset, _day_number(offset), request.args.get('after'))
    return jsonify(body), status

@app.route('/api/writing/check', methods=['POST'])
def writing_check_route():
    """API endpoint to have a piece of writing marked out of 80, like a teacher would."""
    data = request.get_json(silent=True) or {}
    offset = _utc_offset(data.get('utc_offset'))
    body, status = check_writing(data, offset, _day_number(offset))
    if status == 200:
        body['progress'] = get_progress(WRITING_SKILL, offset)
    return jsonify(body), status

@app.route('/api/writing/retry/<int:piece_id>', methods=['POST'])
def writing_retry_route(piece_id):
    """API endpoint to mark a piece that was kept while the AI was unavailable."""
    data = request.get_json(silent=True) or {}
    offset = _utc_offset(data.get('utc_offset'))
    body, status = retry_writing(piece_id, offset)
    if status == 200:
        body['progress'] = get_progress(WRITING_SKILL, offset)
    return jsonify(body), status

@app.route('/api/writing/history', methods=['GET'])
def writing_history_route():
    """API endpoint for past writing, newest first. A diary is private, so this
    needs the same access as My Words."""
    if not has_data_access():
        return jsonify({"error": "Unlock My Words to see your past writing.", "locked": True}), 403
    pieces = get_writing_history()
    if pieces is None:
        return jsonify({"error": "Could not load your writing."}), 500
    return jsonify({"pieces": pieces})

@app.route('/api/writing/piece/<int:piece_id>', methods=['GET'])
def writing_piece_route(piece_id):
    """API endpoint for one past piece with its marks and feedback (private, like the history)."""
    if not has_data_access():
        return jsonify({"error": "Unlock My Words to see your past writing.", "locked": True}), 403
    piece = get_writing_piece(piece_id)
    if piece is None:
        return jsonify({"error": "That piece of writing was not found."}), 404
    return jsonify(piece)

@app.route('/api/grammar_check', methods=['POST'])
def grammar_check_route():
    """API endpoint to correct a free piece of English writing."""
    data = request.get_json(silent=True) or {}
    body, status = check_grammar(data.get('text'))
    return jsonify(body), status


@app.route('/api/update/status', methods=['GET'])
def update_status_route():
    """Whether a newer MyVocab is out, and how far an update has got (static/update.js)."""
    return jsonify(updates.status())


@app.route('/api/update/start', methods=['POST'])
def update_start_route():
    """Starts the update to the newest release. JSON only, so another site cannot send it."""
    if not request.is_json:
        return jsonify({'error': 'Send JSON.'}), 400
    error = updates.start(str((request.get_json(silent=True) or {}).get('tag') or ''))
    if error:
        return jsonify({'error': error}), 409
    return jsonify({'ok': True}), 202
