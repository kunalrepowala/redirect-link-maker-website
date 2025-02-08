# --- Gevent monkey-patching for cooperative I/O ---
from gevent import monkey
monkey.patch_all()

# --- Standard Imports ---
from flask import (
    Flask,
    render_template_string,
    request,
    abort,
    jsonify,
    redirect,
    url_for
)
import random, string, asyncio, threading, time
from datetime import date, datetime, timezone
import nest_asyncio
nest_asyncio.apply()

# --- Additional Imports for Title Extraction and MongoDB ---
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

# --- Telegram Bot Imports ---
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- SQLite for Verified Sessions ---
import sqlite3
import os

# Use a SQLite database file to store verified sessions.
# (They will persist while the script is running but will be cleared on startup.)
DB_FILE = "verified_sessions.db"
MAX_SESSIONS = 3  # Change this value to increase or decrease the max sessions per user.

def init_session_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = conn.cursor()
    # Create the sessions table if it doesn't exist.
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER,
            session_id TEXT,
            created_at DATETIME
        )
    ''')
    conn.commit()
    # Clear all sessions on startup.
    cur.execute('DELETE FROM sessions')
    conn.commit()
    return conn

session_db = init_session_db()

def add_session(user_id, session_id):
    cur = session_db.cursor()
    now = datetime.now(timezone.utc)
    cur.execute('INSERT INTO sessions (user_id, session_id, created_at) VALUES (?, ?, ?)',
                (user_id, session_id, now))
    session_db.commit()
    enforce_max_sessions(user_id)

def get_sessions(user_id):
    cur = session_db.cursor()
    cur.execute('SELECT session_id FROM sessions WHERE user_id=? ORDER BY created_at ASC', (user_id,))
    rows = cur.fetchall()
    return [row[0] for row in rows]

def enforce_max_sessions(user_id):
    cur = session_db.cursor()
    cur.execute('SELECT session_id FROM sessions WHERE user_id=? ORDER BY created_at ASC', (user_id,))
    rows = cur.fetchall()
    sessions = [row[0] for row in rows]
    if len(sessions) > MAX_SESSIONS:
        # Remove the oldest sessions beyond MAX_SESSIONS.
        to_delete = sessions[0: len(sessions) - MAX_SESSIONS]
        cur.executemany('DELETE FROM sessions WHERE user_id=? AND session_id=?',
                        [(user_id, sess) for sess in to_delete])
        session_db.commit()

def is_session_valid(user_id, session_id):
    cur = session_db.cursor()
    cur.execute('SELECT session_id FROM sessions WHERE user_id=? AND session_id=?', (user_id, session_id))
    row = cur.fetchone()
    return row is not None

# --- MongoDB Connections ---
usage_client = MongoClient("mongodb+srv://kunalrepowala7:ntDj85lF5JPJvz0a@cluster0.fgq1r.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db_usage = usage_client["Cluster0"]
col_links = db_usage["links"]
col_redirections = db_usage["redirections"]
col_usage = db_usage["usage"]

users_client = MongoClient("mongodb+srv://kunalrepowala2:LCLIBQxW8IOdZpeF@cluster0.awvns.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db_users = users_client["Cluster0"]
col_users = db_users["users"]

# --- In-Memory Data for Pending Verification ---
pending_verifications = {}  # token -> { session_id, original_url, verified, telegram_user_id }

# --- Global Subscriptions Dictionary ---
subscriptions = {}

def update_subscriptions():
    global subscriptions
    while True:
        doc = col_users.find_one({"_id": "users"})
        if doc and "subscriptions" in doc:
            subscriptions = doc["subscriptions"]
        else:
            subscriptions = {}
        time.sleep(2)

sub_thread = threading.Thread(target=update_subscriptions, daemon=True)
sub_thread.start()

# --- Bot Constants and Global Setting ---
BOT_TOKEN = "8031663240:AAFBLk9xBIrceFT4zTtKHSWeJ8iYq5cOdyA"
daily_limit_enabled = True  # When False, no daily limit is applied.

# --- Utility Functions ---
def generate_code(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_bot_username():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        r = requests.get(url, timeout=10)
        data = r.json()
        return data["result"]["username"]
    except Exception as e:
        logging.error("Error getting bot username: %s", e)
        return "YourBot"

BOT_USERNAME = get_bot_username()

def extract_title(url):
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            title_tag = soup.find("title")
            if title_tag:
                return title_tag.text.strip()
    except Exception as e:
        logging.error("Error extracting title from %s: %s", url, e)
    return "Embedded Video"

# --- Flask Application Setup ---
app = Flask(__name__)

# --- Routes ---

@app.route("/")
def home():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Welcome to HotError</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background: linear-gradient(135deg, #e0f7e9, #f8f9fa); font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }
    .container { margin-top: 100px; text-align: center; }
    h1 { font-size: 48px; color: #2c3e50; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
    .animated-caption { margin-top: 20px; font-size: 24px; color: #2c3e50; animation: fadeIn 2s ease-in-out infinite alternate; }
    @keyframes fadeIn { from { opacity: 0.6; } to { opacity: 1; } }
    .btn-telegram, .btn-instagram, .btn-admin {
       border: none; padding: 15px 30px; font-size: 20px; border-radius: 50px; text-decoration: none;
       display: inline-block; transition: transform 0.2s ease; margin: 10px;
    }
    .btn-telegram { background: linear-gradient(45deg, #007bff, #0056b3); color: #fff; }
    .btn-telegram:hover { transform: scale(1.05); }
    .btn-instagram { background: linear-gradient(45deg, #833ab4, #fd1d1d, #fcb045); color: #fff; }
    .btn-instagram:hover { transform: scale(1.05); }
    .btn-admin { background: linear-gradient(45deg, #6c757d, #343a40); color: #fff; }
    .btn-admin:hover { transform: scale(1.05); }
  </style>
</head>
<body>
  <div class="container">
    <h1>Welcome to HotError!</h1>
    <p class="animated-caption">Experience a classic connection with Telegram and Instagram.</p>
    <a href="https://t.me/hoterror" class="btn-telegram">Join HotError on Telegram</a>
    <a href="https://instagram.com/HotError.in" class="btn-instagram">Follow HotError on Instagram</a>
    <a href="https://t.me/admin" class="btn-admin">Contact Admin</a>
  </div>
</body>
</html>
''')

@app.route('/TeraLink')
def teralink_page():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TeraLink Generator</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; }
    .container { max-width: 600px; margin: 50px auto; padding: 15px; }
    .card { box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    .btn-classic { background-color: #007bff; border: none; color: #fff; font-size: 18px; padding: 12px 25px; border-radius: 4px; }
    .btn-classic:hover { background-color: #0056b3; }
    #generatedLink { display: none; margin-top: 15px; }
    #errorMsg { margin-top: 10px; color: #dc3545; }
  </style>
</head>
<body>
  <div class="container">
    <div class="card p-4">
      <h2 class="text-center">TeraLink Generator</h2>
      <p class="text-center">Paste your Terabox <code>/sharing/embed</code> link below:</p>
      <div class="form-group">
        <input type="text" id="linkInput" class="form-control form-control-lg" placeholder="https://terabox.com/sharing/embed?...">
      </div>
      <div class="text-center">
        <button id="generateBtn" class="btn btn-classic btn-lg">Generate Link</button>
      </div>
      <div id="generatedLink" class="mt-3">
        <div class="input-group">
          <input type="text" id="genLinkText" class="form-control form-control-lg" readonly>
          <div class="input-group-append">
            <button id="copyBtn" class="btn btn-outline-secondary btn-lg" type="button">Copy</button>
          </div>
        </div>
      </div>
      <div id="errorMsg" class="text-center"></div>
    </div>
  </div>
  <script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
  <script>
    $(document).ready(function(){
        $('#generateBtn').click(function(){
            var link = $('#linkInput').val().trim();
            $('#errorMsg').text('');
            if(link.indexOf("/sharing/embed") === -1){
                $('#errorMsg').text("Invalid link. Please provide a valid /sharing/embed link.");
                return;
            }
            $.ajax({
                url: '/generate',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({link: link}),
                success: function(resp){
                    if(resp.success){
                        var genLink = window.location.origin + resp.generated;
                        $('#genLinkText').val(genLink);
                        $('#generatedLink').show();
                    }
                },
                error: function(xhr){
                    $('#errorMsg').text("Error: " + xhr.responseText);
                }
            });
        });
        $('#copyBtn').click(function(){
            var text = $('#genLinkText').val();
            navigator.clipboard ? navigator.clipboard.writeText(text) : (function(){
                var $temp = $("<input>");
                $("body").append($temp);
                $temp.val(text).select();
                document.execCommand("copy");
                $temp.remove();
            })();
        });
    });
  </script>
</body>
</html>
''')

@app.route('/generate', methods=['POST'])
def generate_teralink():
    data = request.get_json()
    link = data.get('link', '')
    if "/sharing/embed" not in link:
        return jsonify(success=False, error="Invalid link. Only /sharing/embed links are accepted."), 400
    code = generate_code(10)
    title = extract_title(link)
    doc = {"code": code, "link": link, "title": title, "created_at": datetime.now(timezone.utc)}
    col_links.insert_one(doc)
    return jsonify(success=True, generated="/p/" + code)

@app.route('/Redirection')
def redirection_page():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Redirection Link Generator</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; }
    .container { max-width: 600px; margin: 50px auto; padding: 15px; }
    .card { box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    .btn-classic { background-color: #28a745; border: none; color: #fff; font-size: 18px; padding: 12px 25px; border-radius: 4px; }
    .btn-classic:hover { background-color: #1e7e34; }
    #generatedRedirection { display: none; margin-top: 15px; }
    #errorMsgRedirection { margin-top: 10px; color: #dc3545; }
  </style>
</head>
<body>
  <div class="container">
    <div class="card p-4">
      <h2 class="text-center">Redirection Generator</h2>
      <p class="text-center">Enter any full URL or text link:</p>
      <div class="form-group">
        <input type="text" id="redirectionInput" class="form-control form-control-lg" placeholder="https://example.com/somepage">
      </div>
      <div class="text-center">
        <button id="generateRedirectionBtn" class="btn btn-classic btn-lg">Create Redirection</button>
      </div>
      <div id="generatedRedirection" class="mt-3">
        <div class="input-group">
          <input type="text" id="redirectionLinkText" class="form-control form-control-lg" readonly>
          <div class="input-group-append">
            <button id="copyRedirectionBtn" class="btn btn-outline-secondary btn-lg" type="button">Copy</button>
          </div>
        </div>
      </div>
      <div id="errorMsgRedirection" class="text-center"></div>
    </div>
  </div>
  <script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
  <script>
    $(document).ready(function(){
        $('#generateRedirectionBtn').click(function(){
            var link = $('#redirectionInput').val().trim();
            $('#errorMsgRedirection').text('');
            if(link === ""){
                $('#errorMsgRedirection').text("Please enter a valid link.");
                return;
            }
            $.ajax({
                url: '/create_redirection',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({link: link}),
                success: function(resp){
                    if(resp.success){
                        var genLink = window.location.origin + resp.generated;
                        $('#redirectionLinkText').val(genLink);
                        $('#generatedRedirection').show();
                    }
                },
                error: function(xhr){
                    $('#errorMsgRedirection').text("Error: " + xhr.responseText);
                }
            });
        });
        $('#copyRedirectionBtn').click(function(){
            var text = $('#redirectionLinkText').val();
            navigator.clipboard ? navigator.clipboard.writeText(text) : (function(){
                var $temp = $("<input>");
                $("body").append($temp);
                $temp.val(text).select();
                document.execCommand("copy");
                $temp.remove();
            })();
        });
    });
  </script>
</body>
</html>
''')

@app.route('/create_redirection', methods=['POST'])
def create_redirection():
    data = request.get_json()
    link = data.get('link', '')
    if not link:
        return jsonify(success=False, error="Empty link provided."), 400
    code = generate_code(10)
    doc = {"code": code, "link": link, "created_at": datetime.now(timezone.utc)}
    col_redirections.insert_one(doc)
    return jsonify(success=True, generated="/s/" + code)

@app.route('/s/<code>')
def redirection_redirect(code):
    record = col_redirections.find_one({"code": code})
    if not record:
        abort(404, description="Redirection link not found.")
    tg_user = request.cookies.get("tg_user")
    try:
        tg_user_val = int(tg_user) if tg_user is not None else "guest"
    except:
        tg_user_val = "guest"
    usage_record = {
        "user_id": str(tg_user_val),
        "code": code,
        "timestamp": datetime.now(timezone.utc),
        "type": "s"
    }
    col_usage.insert_one(usage_record)
    return redirect(record["link"])

# --- Verification Endpoints ---
@app.route('/verify')
def verify():
    next_url = request.args.get('next') or url_for('teralink_page')
    tg_user = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if tg_user and session_cookie:
        try:
            uid = int(tg_user)
        except:
            uid = None
        if uid is not None and is_session_valid(uid, session_cookie):
            return redirect(next_url)
    token = generate_code(15)
    session_id = generate_code(15)
    pending_verifications[token] = {
        "session_id": session_id,
        "original_url": next_url,
        "verified": False,
        "telegram_user_id": None
    }
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Telegram Verification</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { background: linear-gradient(135deg, #2C3E50, #34495E); font-family: "Georgia", serif; color: #ECF0F1; margin: 0; padding: 0;
          display: flex; align-items: center; justify-content: center; height: 100vh; }
    .verify-container { background: #34495E; padding: 30px; border-radius: 10px;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.3); text-align: center; width: 90%; max-width: 500px; }
    .verify-container h3 { font-size: 28px; margin-bottom: 20px; }
    .verify-container p { font-size: 16px; margin-bottom: 20px; }
    .verify-btn { background: linear-gradient(45deg, #007bff, #0056b3); color: #ECF0F1; border: none;
                  padding: 12px 24px; font-size: 18px; border-radius: 4px; text-decoration: none;
                  cursor: pointer; transition: background 0.3s; }
    .verify-btn:hover { background: #1ABC9C; }
  </style>
</head>
<body>
  <div class="verify-container">
    <h3>Telegram Verification</h3>
    <p>Please verify your Telegram account to access the link.</p>
    <a href="https://t.me/{{ bot_username }}?start={{ token }}" class="verify-btn">Verify with Telegram</a>
    <p id="statusMsg" style="margin-top: 20px;">Waiting for verification...</p>
  </div>
  <script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
  <script>
    function checkVerification() {
      $.getJSON("/check_verification", { token: "{{ token }}" }, function(data) {
        if(data.verified) {
          document.cookie = "tg_user=" + data.telegram_user_id + "; path=/";
          document.cookie = "session_id=" + data.session_id + "; path=/";
          window.location.href = data.original_url;
        }
      });
    }
    setInterval(checkVerification, 3000);
  </script>
</body>
</html>
''', bot_username=BOT_USERNAME, token=token)

@app.route('/check_verification')
def check_verification():
    token = request.args.get('token')
    if not token or token not in pending_verifications:
        return jsonify({"error": "Invalid token"}), 400
    data = pending_verifications[token]
    return jsonify({
        "verified": data["verified"],
        "telegram_user_id": data["telegram_user_id"],
        "session_id": data["session_id"],
        "original_url": data["original_url"]
    })

# --- /p/<code> Endpoint (requires verification) ---
@app.route('/p/<code>')
def embed_page(code):
    tg_user = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        uid = int(tg_user)
    except:
        return redirect(url_for('verify', next=request.url))
    if not is_session_valid(uid, session_cookie):
        return redirect(url_for('verify', next=request.url))
    record = col_links.find_one({"code": code})
    if not record:
        abort(404, description="Link not found.")
    original_link = record["link"]
    video_title = record["title"]
    today_str = str(date.today())
    global daily_limit_enabled
    sub = subscriptions.get(str(uid))
    expiry_dt = None
    if sub and sub.get("expiry"):
        try:
            expiry_dt = datetime.fromisoformat(sub.get("expiry")) if isinstance(sub.get("expiry"), str) else sub.get("expiry")
        except:
            expiry_dt = None
    if sub and expiry_dt and datetime.now(timezone.utc) > expiry_dt:
        sub = None
    if not daily_limit_enabled:
        allowed = float("inf")
    else:
        if sub:
            if sub.get("plan", "limited") == "full" or sub.get("upgraded", False):
                allowed = float("inf")
            else:
                allowed = 3
        else:
            allowed = 1
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day.replace(hour=23, minute=59, second=59, microsecond=999999)
    usage_count = col_usage.count_documents({
        "user_id": str(uid),
        "type": "p",
        "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
    })
    if usage_count >= allowed:
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upgrade to Premium</title>
  <style>
    body { background: linear-gradient(135deg, #2C3E50, #34495E); font-family: "Georgia", serif; color: #ECF0F1;
          margin: 0; padding: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; }
    .upgrade-container { background: #34495E; padding: 30px; border-radius: 10px;
                         box-shadow: 0 4px 15px rgba(0,0,0,0.3); text-align: center; width: 90%; max-width: 500px; }
    .upgrade-container h3 { font-size: 28px; margin-bottom: 20px; }
    .upgrade-container p { font-size: 16px; margin-bottom: 20px; }
    .upgrade-btn { background: linear-gradient(45deg, #2980B9, #1ABC9C); color: #ECF0F1; border: none; padding: 12px 24px;
                   font-size: 18px; border-radius: 4px; cursor: pointer; transition: background 0.3s; text-decoration: none; }
    .upgrade-btn:hover { background: #16a085; }
    .reverify-btn { background: linear-gradient(45deg, #007bff, #0056b3); color: #ECF0F1; border: none; padding: 6px 12px;
                    font-size: 14px; border-radius: 4px; cursor: pointer; transition: background 0.3s; text-decoration: none; }
    .reverify-btn:hover { background: #1ABC9C; }
    .reverify-container { margin-top: 20px; text-align: center; }
  </style>
</head>
<body>
  <div class="upgrade-container">
    <h3>Upgrade to Premium</h3>
    <p>You have exceeded your daily access limit.</p>
    <a href="https://t.me/pay" class="upgrade-btn">Upgrade Now via Telegram</a>
  </div>
  <div class="reverify-container">
    <button class="reverify-btn" id="reverifyBtn">Reverify?</button>
  </div>
  <script>
    document.getElementById('reverifyBtn').addEventListener('click', function(){
       document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
       document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
       window.location.reload();
    });
  </script>
</body>
</html>
        ''')
    # Record the usage.
    usage_record = {
        "user_id": str(uid),
        "code": code,
        "timestamp": datetime.now(timezone.utc),
        "type": "p"
    }
    col_usage.insert_one(usage_record)
    if 'hide_logo=1' not in original_link:
        embed_url = original_link + ("&hide_logo=1" if "?" in original_link else "?hide_logo=1")
    else:
        embed_url = original_link
    ua = request.headers.get('User-Agent', '').lower()
    template = MOBILE_EMBED_TEMPLATE if any(k in ua for k in ['iphone','android','ipad','mobile']) else DESKTOP_EMBED_TEMPLATE
    return render_template_string(template, embed_url=embed_url, video_title=video_title)

# --- Embed Templates ---
DESKTOP_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{{ video_title }}</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts"></iframe>
</body>
</html>
'''

MOBILE_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ video_title }}</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts"></iframe>
</body>
</html>
'''

# --- /info Endpoint ---
@app.route("/info")
def info():
    tg_user = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        uid = int(tg_user)
    except:
        return redirect(url_for('verify', next=request.url))
    if not is_session_valid(uid, session_cookie):
        return redirect(url_for('verify', next=request.url))
    sub = subscriptions.get(str(uid))
    expiry_dt = None
    if sub and sub.get("expiry"):
        try:
            expiry_dt = datetime.fromisoformat(sub.get("expiry")) if isinstance(sub.get("expiry"), str) else sub.get("expiry")
        except:
            expiry_dt = None
    if sub and expiry_dt and datetime.now(timezone.utc) > expiry_dt:
        sub = None
    if not sub:
        plan_info = "<p>You are on the Basic Free Plan (1 link per day).</p>"
    else:
        purchased_val = sub.get("purchased")
        try:
            purchased_dt = datetime.fromisoformat(purchased_val) if isinstance(purchased_val, str) else purchased_val
        except:
            purchased_dt = None
        purchased_str = purchased_dt.strftime("%Y-%m-%d %H:%M:%S") if purchased_dt else str(purchased_val)
        expiry_str = expiry_dt.strftime("%Y-%m-%d %H:%M:%S") if expiry_dt else str(sub.get("expiry"))
        if expiry_dt:
            delta = expiry_dt - datetime.now(timezone.utc)
            if delta.total_seconds() < 0:
                time_left_str = "Expired"
            else:
                days = delta.days
                hours = (delta.seconds // 3600)
                time_left_str = f"{days} days, {hours} hours left"
        else:
            time_left_str = "N/A"
        if sub.get("plan", "limited") == "limited":
            start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day.replace(hour=23, minute=59, second=59, microsecond=999999)
            usage_count = col_usage.count_documents({
                "user_id": str(uid),
                "type": "p",
                "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
            })
            plan_info = (f"<p><strong>Plan:</strong> Limited (3 accesses per day)</p>"
                         f"<p><strong>Purchased:</strong> {purchased_str}</p>"
                         f"<p><strong>Expiry:</strong> {expiry_str}</p>"
                         f"<p><strong>Time Left:</strong> {time_left_str}</p>"
                         f"<p><strong>Usage Today:</strong> {usage_count} / 3</p>")
        elif sub.get("plan") == "full":
            plan_info = (f"<p><strong>Plan:</strong> Full (Ultimate Access)</p>"
                         f"<p><strong>Purchased:</strong> {purchased_str}</p>"
                         f"<p><strong>Expiry:</strong> {expiry_str}</p>"
                         f"<p><strong>Time Left:</strong> {time_left_str}</p>")
            if sub.get("upgraded"):
                plan_info = plan_info.replace("Ultimate Access", "Upgraded to Ultimate")
        else:
            plan_info = "<p>Plan details unavailable.</p>"
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>User Info</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { background: linear-gradient(135deg, #e0f7e9, #f8f9fa); font-family: "Georgia", serif; color: #2c3e50;
           margin: 0; padding: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }
    .info-container { background: #ffffff; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                      padding: 30px; max-width: 500px; width: 90%; text-align: center; }
    h2 { font-size: 32px; margin-bottom: 20px; }
    p { font-size: 18px; margin: 10px 0; }
  </style>
</head>
<body>
  <div class="info-container">
    <h2>User Info</h2>
    <p><strong>Telegram User ID:</strong> {{ tg_user }}</p>
    {{ plan_info|safe }}
  </div>
</body>
</html>
    ''', tg_user=tg_user, plan_info=plan_info)

# --- Telegram Bot Command Handlers ---

def split_message(text, max_length=4000):
    lines = text.splitlines(keepends=True)
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) > max_length:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks

async def admin_teralink_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    cursor = col_links.find({})
    lines = []
    for doc in cursor:
        code = doc.get("code")
        title = doc.get("title", "No Title")
        lines.append(f"/p/{code}  =>  {title}")
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def admin_redirection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    cursor = col_redirections.find({})
    lines = []
    for doc in cursor:
        code = doc.get("code")
        link = doc.get("link", "No Link")
        lines.append(f"/s/{code}  =>  {link}")
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Please start via a proper verification link.")
        return
    token = args[0]
    if token not in pending_verifications:
        await update.message.reply_text("Invalid or expired token.")
        return
    pending_verifications[token]["verified"] = True
    pending_verifications[token]["telegram_user_id"] = update.effective_user.id
    uid = update.effective_user.id
    session = pending_verifications[token]["session_id"]
    add_session(uid, session)
    await update.message.reply_text(f"Verification complete. You can now access your link: {pending_verifications[token]['original_url']}")

async def setting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    global daily_limit_enabled
    button_text = "Turn Off Limit OFF📴" if daily_limit_enabled else "Turn On Limit ON🔛"
    text = f"Daily limit is currently: {'ON' if daily_limit_enabled else 'OFF'}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data="toggle_limit")]])
    await update.message.reply_text(text, reply_markup=keyboard)

async def toggle_limit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await query.edit_message_text("Unauthorized.")
        return
    global daily_limit_enabled
    daily_limit_enabled = not daily_limit_enabled
    button_text = "Turn Off Limit OFF📴" if daily_limit_enabled else "Turn On Limit ON🔛"
    text = f"Daily limit is now: {'ON' if daily_limit_enabled else 'OFF'}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data="toggle_limit")]])
    await query.edit_message_text(text, reply_markup=keyboard)

async def mongo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    import json
    subs_text = json.dumps(subscriptions, default=str, indent=2)
    for chunk in split_message(subs_text):
        await update.message.reply_text(chunk)

async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sub = subscriptions.get(str(uid))
    if not sub:
        text = "You are on the Basic Free Plan (1 link per day)."
    else:
        # Format the plan details in a classic style.
        try:
            purchased_dt = datetime.fromisoformat(sub.get("purchased")) if isinstance(sub.get("purchased"), str) else sub.get("purchased")
        except:
            purchased_dt = None
        purchased_str = purchased_dt.strftime("%Y-%m-%d %H:%M:%S") if purchased_dt else "N/A"
        try:
            expiry_dt = datetime.fromisoformat(sub.get("expiry")) if isinstance(sub.get("expiry"), str) else sub.get("expiry")
        except:
            expiry_dt = None
        expiry_str = expiry_dt.strftime("%Y-%m-%d %H:%M:%S") if expiry_dt else "N/A"
        if expiry_dt:
            delta = expiry_dt - datetime.now(timezone.utc)
            if delta.total_seconds() < 0:
                time_left = "Expired"
            else:
                days = delta.days
                hours = delta.seconds // 3600
                time_left = f"{days} days, {hours} hours left"
        else:
            time_left = "N/A"
        plan_type = sub.get("plan", "limited").capitalize()
        upgraded = sub.get("upgraded", False)
        if upgraded:
            plan_type += " (Upgraded)"
        text = f"Your Plan Details:\nPlan: {plan_type}\nPurchased: {purchased_str}\nExpiry: {expiry_str}\nTime Left: {time_left}"
    await update.message.reply_text(text)

async def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("TeraLink", admin_teralink_handler))
    application.add_handler(CommandHandler("Redirection", admin_redirection_handler))
    application.add_handler(CommandHandler("setting", setting_handler))
    application.add_handler(CommandHandler("mongo", mongo_handler))
    application.add_handler(CommandHandler("plan", plan_handler))
    application.add_handler(CallbackQueryHandler(toggle_limit_callback, pattern="^toggle_limit$"))
    await application.run_polling()

def start_bot():
    new_loop = asyncio.new_event_loop()
    new_loop.add_signal_handler = lambda sig, handler: None
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(run_telegram_bot())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

# --- Endpoints for TeraLink / Info ---

@app.route('/p/<code>')
def embed_page(code):
    tg_user = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        uid = int(tg_user)
    except:
        return redirect(url_for('verify', next=request.url))
    if not is_session_valid(uid, session_cookie):
        return redirect(url_for('verify', next=request.url))
    record = col_links.find_one({"code": code})
    if not record:
        abort(404, description="Link not found.")
    original_link = record["link"]
    video_title = record["title"]
    today_str = str(date.today())
    global daily_limit_enabled
    sub = subscriptions.get(str(uid))
    expiry_dt = None
    if sub and sub.get("expiry"):
        try:
            expiry_dt = datetime.fromisoformat(sub.get("expiry")) if isinstance(sub.get("expiry"), str) else sub.get("expiry")
        except:
            expiry_dt = None
    if sub and expiry_dt and datetime.now(timezone.utc) > expiry_dt:
        sub = None
    if not daily_limit_enabled:
        allowed = float("inf")
    else:
        if sub:
            if sub.get("plan", "limited") == "full" or sub.get("upgraded", False):
                allowed = float("inf")
            else:
                allowed = 3
        else:
            allowed = 1
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day.replace(hour=23, minute=59, second=59, microsecond=999999)
    usage_count = col_usage.count_documents({
        "user_id": str(uid),
        "type": "p",
        "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
    })
    if usage_count >= allowed:
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upgrade to Premium</title>
  <style>
    body { background: linear-gradient(135deg, #2C3E50, #34495E); font-family: "Georgia", serif; color: #ECF0F1;
           margin: 0; padding: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; }
    .upgrade-container { background: #34495E; padding: 30px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                         text-align: center; width: 90%; max-width: 500px; }
    .upgrade-container h3 { font-size: 28px; margin-bottom: 20px; }
    .upgrade-container p { font-size: 16px; margin-bottom: 20px; }
    .upgrade-btn { background: linear-gradient(45deg, #2980B9, #1ABC9C); color: #ECF0F1; border: none;
                   padding: 12px 24px; font-size: 18px; border-radius: 4px; cursor: pointer; transition: background 0.3s; text-decoration: none; }
    .upgrade-btn:hover { background: #16a085; }
    .reverify-btn { background: linear-gradient(45deg, #007bff, #0056b3); color: #ECF0F1; border: none;
                    padding: 6px 12px; font-size: 14px; border-radius: 4px; cursor: pointer; transition: background 0.3s; text-decoration: none; }
    .reverify-btn:hover { background: #1ABC9C; }
    .reverify-container { margin-top: 20px; text-align: center; }
  </style>
</head>
<body>
  <div class="upgrade-container">
    <h3>Upgrade to Premium</h3>
    <p>You have exceeded your daily access limit.</p>
    <a href="https://t.me/pay" class="upgrade-btn">Upgrade Now via Telegram</a>
  </div>
  <div class="reverify-container">
    <button class="reverify-btn" id="reverifyBtn">Reverify?</button>
  </div>
  <script>
    document.getElementById('reverifyBtn').addEventListener('click', function(){
       document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
       document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
       window.location.reload();
    });
  </script>
</body>
</html>
        ''')
    # Record usage.
    usage_record = {
        "user_id": str(uid),
        "code": code,
        "timestamp": datetime.now(timezone.utc),
        "type": "p"
    }
    col_usage.insert_one(usage_record)
    if 'hide_logo=1' not in original_link:
        embed_url = original_link + ("&hide_logo=1" if "?" in original_link else "?hide_logo=1")
    else:
        embed_url = original_link
    ua = request.headers.get('User-Agent', '').lower()
    template = MOBILE_EMBED_TEMPLATE if any(k in ua for k in ['iphone','android','ipad','mobile']) else DESKTOP_EMBED_TEMPLATE
    return render_template_string(template, embed_url=embed_url, video_title=video_title)

# --- Embed Templates ---
DESKTOP_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{{ video_title }}</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts"></iframe>
</body>
</html>
'''

MOBILE_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ video_title }}</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts"></iframe>
</body>
</html>
'''

# --- /info Endpoint ---
@app.route("/info")
def info():
    tg_user = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        uid = int(tg_user)
    except:
        return redirect(url_for('verify', next=request.url))
    if not is_session_valid(uid, session_cookie):
        return redirect(url_for('verify', next=request.url))
    sub = subscriptions.get(str(uid))
    expiry_dt = None
    if sub and sub.get("expiry"):
        try:
            expiry_dt = datetime.fromisoformat(sub.get("expiry")) if isinstance(sub.get("expiry"), str) else sub.get("expiry")
        except:
            expiry_dt = None
    if sub and expiry_dt and datetime.now(timezone.utc) > expiry_dt:
        sub = None
    if not sub:
        plan_info = "<p>You are on the Basic Free Plan (1 link per day).</p>"
    else:
        purchased_val = sub.get("purchased")
        try:
            purchased_dt = datetime.fromisoformat(purchased_val) if isinstance(purchased_val, str) else purchased_val
        except:
            purchased_dt = None
        purchased_str = purchased_dt.strftime("%Y-%m-%d %H:%M:%S") if purchased_dt else "N/A"
        expiry_str = expiry_dt.strftime("%Y-%m-%d %H:%M:%S") if expiry_dt else "N/A"
        if expiry_dt:
            delta = expiry_dt - datetime.now(timezone.utc)
            if delta.total_seconds() < 0:
                time_left_str = "Expired"
            else:
                days = delta.days
                hours = (delta.seconds // 3600)
                time_left_str = f"{days} days, {hours} hours left"
        else:
            time_left_str = "N/A"
        if sub.get("plan", "limited") == "limited":
            start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day.replace(hour=23, minute=59, second=59, microsecond=999999)
            usage_count = col_usage.count_documents({
                "user_id": str(uid),
                "type": "p",
                "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
            })
            plan_info = (f"<p><strong>Plan:</strong> Limited (3 accesses per day)</p>"
                         f"<p><strong>Purchased:</strong> {purchased_str}</p>"
                         f"<p><strong>Expiry:</strong> {expiry_str}</p>"
                         f"<p><strong>Time Left:</strong> {time_left_str}</p>"
                         f"<p><strong>Usage Today:</strong> {usage_count} / 3</p>")
        elif sub.get("plan") == "full":
            plan_info = (f"<p><strong>Plan:</strong> Full (Ultimate Access)</p>"
                         f"<p><strong>Purchased:</strong> {purchased_str}</p>"
                         f"<p><strong>Expiry:</strong> {expiry_str}</p>"
                         f"<p><strong>Time Left:</strong> {time_left_str}</p>")
            if sub.get("upgraded"):
                plan_info = plan_info.replace("Ultimate Access", "Upgraded to Ultimate")
        else:
            plan_info = "<p>Plan details unavailable.</p>"
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>User Info</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { background: linear-gradient(135deg, #e0f7e9, #f8f9fa); font-family: "Georgia", serif; color: #2c3e50;
           margin: 0; padding: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }
    .info-container { background: #ffffff; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                      padding: 30px; max-width: 500px; width: 90%; text-align: center; }
    h2 { font-size: 32px; margin-bottom: 20px; }
    p { font-size: 18px; margin: 10px 0; }
  </style>
</head>
<body>
  <div class="info-container">
    <h2>User Info</h2>
    <p><strong>Telegram User ID:</strong> {{ tg_user }}</p>
    {{ plan_info|safe }}
  </div>
</body>
</html>
    ''', tg_user=tg_user, plan_info=plan_info)

# --- Telegram Bot Command Handlers ---

def split_message(text, max_length=4000):
    lines = text.splitlines(keepends=True)
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) > max_length:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks

async def admin_teralink_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    cursor = col_links.find({})
    lines = []
    for doc in cursor:
        code = doc.get("code")
        title = doc.get("title", "No Title")
        lines.append(f"/p/{code}  =>  {title}")
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def admin_redirection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    cursor = col_redirections.find({})
    lines = []
    for doc in cursor:
        code = doc.get("code")
        link = doc.get("link", "No Link")
        lines.append(f"/s/{code}  =>  {link}")
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Please start via a proper verification link.")
        return
    token = args[0]
    if token not in pending_verifications:
        await update.message.reply_text("Invalid or expired token.")
        return
    pending_verifications[token]["verified"] = True
    pending_verifications[token]["telegram_user_id"] = update.effective_user.id
    uid = update.effective_user.id
    session = pending_verifications[token]["session_id"]
    add_session(uid, session)
    await update.message.reply_text(f"Verification complete. You can now access your link: {pending_verifications[token]['original_url']}")

async def setting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    global daily_limit_enabled
    button_text = "Turn Off Limit OFF📴" if daily_limit_enabled else "Turn On Limit ON🔛"
    text = f"Daily limit is currently: {'ON' if daily_limit_enabled else 'OFF'}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data="toggle_limit")]])
    await update.message.reply_text(text, reply_markup=keyboard)

async def toggle_limit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await query.edit_message_text("Unauthorized.")
        return
    global daily_limit_enabled
    daily_limit_enabled = not daily_limit_enabled
    button_text = "Turn Off Limit OFF📴" if daily_limit_enabled else "Turn On Limit ON🔛"
    text = f"Daily limit is now: {'ON' if daily_limit_enabled else 'OFF'}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data="toggle_limit")]])
    await query.edit_message_text(text, reply_markup=keyboard)

async def mongo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    import json
    subs_text = json.dumps(subscriptions, default=str, indent=2)
    for chunk in split_message(subs_text):
        await update.message.reply_text(chunk)

async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sub = subscriptions.get(str(uid))
    if not sub:
        text = "You are on the Basic Free Plan (1 link per day)."
    else:
        try:
            purchased_dt = datetime.fromisoformat(sub.get("purchased")) if isinstance(sub.get("purchased"), str) else sub.get("purchased")
        except:
            purchased_dt = None
        purchased_str = purchased_dt.strftime("%Y-%m-%d %H:%M:%S") if purchased_dt else "N/A"
        try:
            expiry_dt = datetime.fromisoformat(sub.get("expiry")) if isinstance(sub.get("expiry"), str) else sub.get("expiry")
        except:
            expiry_dt = None
        expiry_str = expiry_dt.strftime("%Y-%m-%d %H:%M:%S") if expiry_dt else "N/A"
        if expiry_dt:
            delta = expiry_dt - datetime.now(timezone.utc)
            if delta.total_seconds() < 0:
                time_left = "Expired"
            else:
                days = delta.days
                hours = delta.seconds // 3600
                time_left = f"{days} days, {hours} hours left"
        else:
            time_left = "N/A"
        plan_type = sub.get("plan", "limited").capitalize()
        if sub.get("upgraded"):
            plan_type += " (Upgraded)"
        text = (f"Your Plan Details:\n"
                f"Plan: {plan_type}\n"
                f"Purchased: {purchased_str}\n"
                f"Expiry: {expiry_str}\n"
                f"Time Left: {time_left}")
    await update.message.reply_text(text)

async def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("TeraLink", admin_teralink_handler))
    application.add_handler(CommandHandler("Redirection", admin_redirection_handler))
    application.add_handler(CommandHandler("setting", setting_handler))
    application.add_handler(CommandHandler("mongo", mongo_handler))
    application.add_handler(CommandHandler("plan", plan_handler))
    application.add_handler(CallbackQueryHandler(toggle_limit_callback, pattern="^toggle_limit$"))
    await application.run_polling()

def start_bot():
    new_loop = asyncio.new_event_loop()
    new_loop.add_signal_handler = lambda sig, handler: None
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(run_telegram_bot())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

# --- Run Flask App ---
if __name__ == '__main__':
    # Run Flask in threaded mode so that multiple requests can be processed concurrently.
    app.run(host="0.0.0.0", debug=True, use_reloader=False, port=8080)
