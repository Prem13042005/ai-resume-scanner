from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from db import get_db_connection
import PyPDF2
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load NLP model once
nlp = spacy.load("en_core_web_sm")

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # change this in production
app.config['UPLOAD_FOLDER'] = 'uploads'

# -------------------- Homepage --------------------
@app.route('/')
def home():
    return render_template('index.html')

# -------------------- Register --------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return "Email already exists. Try logging in."

        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, password)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/login')
    return render_template('register.html')

# -------------------- Login --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect('/dashboard')
        else:
            return "Invalid credentials"
    return render_template('login.html')

# -------------------- Logout --------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# -------------------- Dashboard --------------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    cursor.execute("SELECT * FROM uploads WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    uploads = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'dashboard.html',
        name=user['name'],
        email=user['email'],
        created_at=user['created_at'].strftime("%d %B %Y"),
        uploads=uploads
    )

# -------------------- Upload Resume --------------------
@app.route('/upload', methods=['POST'])
def upload_resume():
    if 'user_id' not in session:
        return redirect('/login')

    if 'resume' not in request.files or request.files['resume'].filename == '':
        return "No resume uploaded."

    file = request.files['resume']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    job_desc = request.form['jobdesc']
    resume_text = extract_text_from_pdf(filepath)
    score = calculate_match_score(resume_text, job_desc)

    # Save to DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
    "INSERT INTO uploads (user_id, filename, job_description, match_score) VALUES (%s, %s, %s, %s)",
    (session['user_id'], filename, job_desc, score)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return f'''
    <h2>✅ Resume Uploaded Successfully!</h2>
    <p><strong>Filename:</strong> {filename}</p>
    <p><strong>Match Score:</strong> {score}%</p>
    <br><a href="/dashboard">🔙 Back to Dashboard</a>
    '''

# -------------------- AI NLP --------------------
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = ''
        for page in reader.pages:
            text += page.extract_text() or ''
    return text

def calculate_match_score(resume_text, job_desc):
    documents = [resume_text, job_desc]
    tfidf = TfidfVectorizer().fit_transform(documents)
    score = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    return round(score * 100, 2)

# -------------------- Run App --------------------
if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)
