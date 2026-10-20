from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3, hashlib, os, re, difflib
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'dataguard.db')
app = Flask(__name__)
app.secret_key = 'dataguard-local-demo-key-change-before-deployment'

SIMILARITY_THRESHOLD = 0.55  # conservative review threshold; tune for real data


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    with connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            fingerprint TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL
        )''')


def normalized(title, category, content):
    return ' '.join((title or '').lower().split()) + '\n' + ' '.join((category or '').lower().split()) + '\n' + ' '.join((content or '').lower().split())


def fingerprint(title, category, content):
    return hashlib.sha256(normalized(title, category, content).encode('utf-8')).hexdigest()


def tokens(text):
    return set(re.findall(r'[a-z0-9]+', (text or '').lower()))


def similarity(a, b):
    # Combine character similarity and token overlap so appended sentences are caught.
    a_norm = ' '.join((a or '').lower().split())
    b_norm = ' '.join((b or '').lower().split())
    char_score = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()
    ta, tb = tokens(a_norm), tokens(b_norm)
    token_score = len(ta & tb) / max(1, len(ta | tb))
    containment = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return max(char_score, 0.65 * token_score + 0.35 * containment)


def find_matches(title, category, content):
    with connect() as conn:
        rows = conn.execute('SELECT * FROM records ORDER BY id DESC').fetchall()
    incoming_fp = fingerprint(title, category, content)
    matches = []
    for row in rows:
        if row['fingerprint'] == incoming_fp:
            return 'duplicate', 1.0, row
        # Compare content plus title/category; content receives most of the weight.
        content_score = similarity(content, row['content'])
        title_score = similarity(title, row['title'])
        category_score = 1.0 if category.strip().lower() == row['category'].strip().lower() else 0.0
        score = 0.78 * content_score + 0.17 * title_score + 0.05 * category_score
        if score >= SIMILARITY_THRESHOLD:
            matches.append((score, row))
    if matches:
        matches.sort(key=lambda item: item[0], reverse=True)
        return 'review', matches[0][0], matches[0][1]
    return 'unique', 0.0, None


def log(action, details):
    with connect() as conn:
        conn.execute('INSERT INTO audit_log(action, details, created_at) VALUES (?, ?, ?)',
                     (action, details, datetime.now().isoformat(timespec='seconds')))


def save_record(title, category, content):
    fp = fingerprint(title, category, content)
    try:
        with connect() as conn:
            cur = conn.execute('INSERT INTO records(title, category, content, fingerprint, created_at) VALUES (?, ?, ?, ?, ?)',
                               (title.strip(), category.strip(), content.strip(), fp, datetime.now().isoformat(timespec='seconds')))
            record_id = cur.lastrowid
        log('RECORD_SAVED', f"Saved record #{record_id}: {title.strip()}")
        return record_id
    except sqlite3.IntegrityError:
        return None


@app.route('/', methods=['GET'])
def index():
    with connect() as conn:
        records = conn.execute('SELECT * FROM records ORDER BY id DESC').fetchall()
        logs = conn.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 12').fetchall()
    return render_template('index.html', records=records, logs=logs, count=len(records))


@app.route('/submit', methods=['POST'])
def submit():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not category or not content:
        flash('Please fill in all three fields.', 'error')
        return redirect(url_for('index'))
    kind, score, match = find_matches(title, category, content)
    if kind == 'duplicate':
        log('DUPLICATE_BLOCKED', f"Exact duplicate blocked: {title}")
        flash('Exact duplicate detected. Nothing was saved.', 'warning')
        return redirect(url_for('index'))
    if kind == 'review':
        return render_template('review.html', title=title, category=category, content=content,
                               match=match, similarity=round(score * 100, 1))
    record_id = save_record(title, category, content)
    if record_id is None:
        flash('This exact record already exists. Nothing was saved.', 'warning')
    else:
        flash(f'Record saved successfully (ID {record_id}).', 'success')
    return redirect(url_for('index'))


@app.route('/review/confirm', methods=['POST'])
def confirm_distinct():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not category or not content:
        flash('Review data was missing. Please submit the record again.', 'error')
        return redirect(url_for('index'))
    kind, _, _ = find_matches(title, category, content)
    if kind == 'duplicate':
        log('DUPLICATE_BLOCKED', f"Exact duplicate blocked during review: {title}")
        flash('This is an exact duplicate and cannot be saved.', 'warning')
        return redirect(url_for('index'))
    record_id = save_record(title, category, content)
    if record_id is None:
        flash('This exact record already exists. Nothing was saved.', 'warning')
    else:
        log('REVIEW_CONFIRMED_DISTINCT', f"Human reviewer confirmed distinct record #{record_id}: {title}")
        flash(f'Reviewer confirmed it as distinct; record saved (ID {record_id}).', 'success')
    return redirect(url_for('index'))


@app.route('/review/reject', methods=['POST'])
def reject_candidate():
    title = request.form.get('title', '').strip()
    log('REVIEW_REJECTED', f"Candidate rejected and not saved: {title or '(untitled)'}")
    flash('Candidate rejected. No record was saved.', 'info')
    return redirect(url_for('index'))


@app.route('/api/check', methods=['POST'])
def api_check():
    data = request.get_json(silent=True) or {}
    title = str(data.get('title', '')).strip()
    category = str(data.get('category', '')).strip()
    content = str(data.get('content', '')).strip()
    if not title or not category or not content:
        return jsonify({'status': 'error', 'message': 'title, category, and content are required'}), 400
    kind, score, match = find_matches(title, category, content)
    if kind == 'duplicate':
        log('API_DUPLICATE_CHECK', f"API exact duplicate detected: {title}")
        return jsonify({'classification': 'duplicate', 'status': 'blocked', 'similarity_percent': 100.0,
                        'matching_record': {'id': match['id'], 'title': match['title']},
                        'message': 'Exact duplicate detected. No record was saved.'}), 200
    if kind == 'review':
        log('API_REVIEW_CHECK', f"API similar record flagged for review: {title}")
        return jsonify({'classification': 'similar', 'status': 'review_required',
                        'similarity_percent': round(score * 100, 1),
                        'matching_record': {'id': match['id'], 'title': match['title']},
                        'message': 'Similar record found. Manual review required; no record was saved.'}), 200
    # Important: check API classifies only. It never silently saves data.
    log('API_UNIQUE_CHECK', f"API found unique candidate (not saved): {title}")
    return jsonify({'classification': 'unique', 'status': 'not_saved', 'similarity_percent': 0.0,
                    'message': 'No similar record found. This check endpoint does not save records.'}), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/records', methods=['GET'])
def api_records():
    with connect() as conn:
        rows = conn.execute('SELECT id, title, category, content, created_at FROM records ORDER BY id DESC').fetchall()
    return jsonify({'count': len(rows), 'records': [dict(row) for row in rows]})


init_db()

if __name__ == '__main__':
    print('DataGuard is starting...')
    print('Database:', DB_PATH)
    print('Open http://127.0.0.1:5000 in your browser.')
    app.run(host='127.0.0.1', port=5000, debug=False)
