from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key

# MySQL configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'flask_app'
}

# External chatbot API endpoint
API_URL = "http://localhost:3000/api/v1/prediction/a4311e7f-8185-4653-9d54-cfec653b3041"

def query_api(question):
    response = requests.post(API_URL, json={"question": question})
    return response.json()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password_input = request.form['password']

        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password_input):
                session['user_id'] = user['id']
                session['name'] = user['name']
                return redirect(url_for('home'))
            else:
                flash('Invalid email or password', 'error')
        except Error as e:
            print("Error:", e)
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                           (name, email, password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except Error as e:
            flash("Error: " + str(e), "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    return render_template('register.html')

@app.route('/home')
def home():
    if 'user_id' in session:
        return render_template('home.html', name=session['name'])
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if 'messages' not in session:
        session['messages'] = []

    if request.method == 'POST':
        user_input = request.form['question']
        session['messages'].append({'sender': 'user', 'text': user_input})

        try:
            api_response = query_api(user_input)
            bot_reply = api_response.get('text', 'Sorry, no response.')
        except Exception as e:
            bot_reply = f"Error: {str(e)}"

        # Store chat in the database
        store_chat(session['user_id'], user_input, bot_reply)

        session['messages'].append({'sender': 'bot', 'text': bot_reply})
        session.modified = True

    return render_template('chatbot.html', messages=session.get('messages', []))

def store_chat(user_id, user_message, bot_response):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chats (user_id, user_message, bot_response) VALUES (%s, %s, %s)",
                       (user_id, user_message, bot_response))
        conn.commit()
    except Error as e:
        print("Error storing chat:", e)
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@app.route('/suggestion', methods=['GET', 'POST'])
def suggestion():
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401

    # 1. Fetch chat history
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT user_message FROM chats WHERE user_id = %s ORDER BY id DESC LIMIT 10", (user_id,))
        messages = cursor.fetchall()
    except Error as e:
        print("Error fetching chat history:", e)
        return "Database error", 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

    # 2. Combine recent user messages for context
    combined_text = ' '.join(msg[0] for msg in messages)

    # 3. Send to suggestion API
    try:
        response = requests.post("http://localhost:3000/api/v1/prediction/e4abb1a6-b374-481f-afbe-530caffd20e9", json={"condition": combined_text})
        data = response.json()
        suggestions = [data.get('text', 'No suggestions found.')]

    except Exception as e:
        suggestions = [f"Error getting suggestions: {e}"]

    # 4. Render template with suggestions
    return render_template('suggestion.html', suggestions=suggestions)

@app.route('/report', methods=['GET', 'POST'])
def report_generator():
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401

    # 1. Fetch full chat history
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT user_message FROM chats WHERE user_id = %s ORDER BY id", (user_id,))
        messages = cursor.fetchall()
    except Error as e:
        print("Error fetching chat history:", e)
        return "Database error", 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

    # 2. Combine messages into one input
    full_chat = ' '.join(msg[0] for msg in messages)

    # 3. Send to report generation API
    try:
        response = requests.post("http://localhost:3000/api/v1/prediction/12e5a24b-f5ed-4a28-8d37-c92f0109d89b", json={"chat_history": full_chat})
        data = response.json()
        report_text = data.get('text', 'No report generated.')
    except Exception as e:
        report_text = f"Error generating report: {e}"

    # 4. Render the report
    return render_template('report.html', report=report_text)


# Optional: clear chat
@app.route('/clear_chat')
def clear_chat():
    session.pop('messages', None)
    return redirect(url_for('chatbot'))

if __name__ == '__main__':
    app.run(debug=True)
