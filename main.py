from flask import (
    Flask,
    render_template_string,
    request,
    abort,
    jsonify,
    redirect,
    url_for
)
import random, string, os, json, csv
import asyncio, threading
from datetime import date
import nest_asyncio
nest_asyncio.apply()

# -----------------------
# MongoDB Setup for Link Storage (Personal Use)
# -----------------------
from pymongo import MongoClient

# MongoDB for storing TeraLink and Redirection links
mongo_links_client = MongoClient("mongodb+srv://kunalrepowala7:ntDj85lF5JPJvz0a@cluster0.fgq1r.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db_links = mongo_links_client["Cluster0"]
col_teralink = db_links["teralink"]
col_redirection = db_links["redirection"]

# -----------------------
# MongoDB Setup for Subscription Data (Read-Only)
# -----------------------
users_client = MongoClient("mongodb+srv://kunalrepowala2:LCLIBQxW8IOdZpeF@cluster0.awvns.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db_users = users_client["Cluster0"]
col_users = db_users["users"]

# -----------------------
# Telegram Bot Imports
# -----------------------
import logging
import requests  # for auto-extracting bot username
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# -----------------------
# Global Variables for Verification and Daily Limit
# -----------------------
# For TeraLink embed pages only (not for redirection)
pending_verifications = {}   # token -> { session_id, original_url, verified, telegram_user_id }
verified_users = {}          # telegram_user_id -> session_id
user_last_access = {}        # telegram_user_id -> (code, date_str)

# -----------------------
# Bot Constants
# -----------------------
BOT_TOKEN = "7660007316:AAHis4NuPllVzH-7zsYhXGfgokiBxm_Tml0"

# -----------------------
# Utility Functions
# -----------------------
def generate_code(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_bot_username():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        r = requests.get(url, timeout=10)
        data = r.json()
        return data["result"]["username"]
    except Exception as e:
        print("Error getting bot username:", e)
        return "YourBot"

BOT_USERNAME = get_bot_username()

# -----------------------
# Flask Application Setup
# -----------------------
app = Flask(__name__)

# -----------------------
# Main Page ("/") – Landing page with top menu
# -----------------------
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
    body {
      background: linear-gradient(135deg, #e0f7e9, #f8f9fa);
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    }
    /* Top navigation menu */
    .navbar {
      background-color: #007bff;
    }
    .navbar-nav .nav-link {
      color: #fff !important;
      font-size: 18px;
      margin-right: 15px;
    }
    .navbar-nav .nav-link:hover {
      color: #dcdcdc !important;
    }
    .container { margin-top: 80px; text-align: center; }
    h1 {
      font-size: 48px;
      color: #2c3e50;
      text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    .animated-caption {
      margin-top: 20px;
      font-size: 24px;
      color: #2c3e50;
      animation: fadeIn 2s ease-in-out infinite alternate;
    }
    @keyframes fadeIn { from { opacity: 0.6; } to { opacity: 1; } }
    .btn-telegram, .btn-instagram {
      border: none;
      padding: 15px 30px;
      font-size: 20px;
      border-radius: 50px;
      text-decoration: none;
      display: inline-block;
      transition: transform 0.2s ease;
      margin: 10px;
    }
    .btn-telegram {
      background: linear-gradient(45deg, #007bff, #0056b3);
      color: #fff;
    }
    .btn-telegram:hover { transform: scale(1.05); text-decoration: none; }
    .btn-instagram {
      background: linear-gradient(45deg, #833ab4, #fd1d1d, #fcb045);
      color: #fff;
    }
    .btn-instagram:hover { transform: scale(1.05); text-decoration: none; }
  </style>
</head>
<body>
  <!-- Top menu -->
  <nav class="navbar navbar-expand-lg">
    <div class="container">
      <a class="navbar-brand text-white" href="/">HotError</a>
      <div class="collapse navbar-collapse">
        <ul class="navbar-nav ml-auto">
          <li class="nav-item"><a class="nav-link" href="/support">Support</a></li>
          <li class="nav-item"><a class="nav-link" href="/info">Check Plan</a></li>
          <li class="nav-item"><a class="nav-link" href="/detail">Detail</a></li>
          <li class="nav-item"><a class="nav-link" href="#" onclick="logout();">Logout</a></li>
        </ul>
      </div>
    </div>
  </nav>
  <div class="container">
    <h1>Welcome to HotError!</h1>
    <p class="animated-caption">Experience a classic connection with Telegram and Instagram.</p>
    <a href="https://t.me/hoterror" class="btn-telegram">Join HotError on Telegram</a>
    <a href="https://instagram.com/HotError.in" class="btn-instagram">Follow HotError on Instagram</a>
  </div>
  <script>
    function logout() {
      document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      window.location.href = "/";
    }
  </script>
</body>
</html>
''')

# -----------------------
# /TeraLink Page – Create TeraLink links (Terabox embed only)
# -----------------------
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

# -----------------------
# /generate Endpoint – Process TeraLink creation (returns /p/<code>) using MongoDB
# -----------------------
@app.route('/generate', methods=['POST'])
def generate_teralink():
    data = request.get_json()
    link = data.get('link', '')
    if "/sharing/embed" not in link:
        return jsonify(success=False, error="Invalid link. Only /sharing/embed links are accepted."), 400
    code = generate_code(10)
    col_teralink.insert_one({"code": code, "link": link})
    return jsonify(success=True, generated="/p/" + code)

# -----------------------
# /Redirection Page – Create a redirection link from any text input
# -----------------------
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

# -----------------------
# /create_redirection Endpoint – Process redirection creation (returns /s/<code>) using MongoDB
# -----------------------
@app.route('/create_redirection', methods=['POST'])
def create_redirection():
    data = request.get_json()
    link = data.get('link', '')
    if not link:
        return jsonify(success=False, error="Empty link provided."), 400
    code = generate_code(10)
    col_redirection.insert_one({"code": code, "link": link})
    return jsonify(success=True, generated="/s/" + code)

# -----------------------
# /s/<code> Endpoint – Redirect to stored redirection link.
# -----------------------
@app.route('/s/<code>')
def redirection_redirect(code):
    doc = col_redirection.find_one({"code": code})
    if not doc:
        abort(404, description="Redirection link not found.")
    return redirect(doc["link"])

# -----------------------
# /info Endpoint – Show subscription details for the verified user (using col_users from MongoDB)
# -----------------------
@app.route('/info')
def info():
    # Require verification first
    tg_user = request.cookies.get("tg_user")
    session_id = request.cookies.get("session_id")
    if not tg_user or not session_id or verified_users.get(int(tg_user)) != session_id:
        return redirect(url_for('verify', next="/info"))
    # Get subscription details from col_users using the user id as a string
    user_id_str = str(tg_user)
    subscription = col_users.find_one({"user_id": user_id_str})
    if not subscription:
        info_text = "No subscription information found."
    else:
        # Format the subscription details
        purchased = subscription.get("purchased", "N/A")
        expiry = subscription.get("expiry", "N/A")
        plan = subscription.get("plan", "basic")
        upgraded = subscription.get("upgraded", False)
        expired_notified = subscription.get("expired_notified", False)
        info_text = f"User ID: {user_id_str}\nPlan: {plan}\nPurchased: {purchased}\nExpiry: {expiry}\nUpgraded: {upgraded}\nExpired Notified: {expired_notified}"
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subscription Info</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body {
      background: linear-gradient(135deg, #d4fc79, #96e6a1);
      font-family: "Georgia", serif;
    }
    .info-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: left;
      white-space: pre-wrap;
    }
    .info-container h3 {
      text-align: center;
      margin-bottom: 20px;
      color: #2d3436;
    }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 8px 16px;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 20px;
    }
    .logout-btn:hover {
      background: #c82333;
    }
  </style>
</head>
<body>
  <div class="info-container">
    <h3>Subscription Info</h3>
    <pre>{{ info_text }}</pre>
    <button class="logout-btn" onclick="logout()">Logout</button>
  </div>
  <script>
    function logout() {
      document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      window.location.href = "/";
    }
  </script>
</body>
</html>
''', info_text=info_text)

# -----------------------
# /detail Endpoint – A placeholder detail page (you can adjust as needed)
# -----------------------
@app.route('/detail')
def detail():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Detail</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; font-family: "Georgia", serif; }
    .detail-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="detail-container">
    <h3>Detail</h3>
    <p>This is a placeholder for additional details.</p>
    <button class="btn btn-primary" onclick="window.location.href='/'">Back to Home</button>
  </div>
</body>
</html>
''')

# -----------------------
# /p/<code> Endpoint – TeraLink embed page with Telegram verification, daily limit, and loading animation.
# Admin (id 6773787379) is not limited.
# -----------------------
@app.route('/p/<code>')
def embed_page(code):
    tg_user_cookie = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user_cookie or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        tg_user_val = int(tg_user_cookie)
    except ValueError:
        return redirect(url_for('verify', next=request.url))
    if verified_users.get(tg_user_val) != session_cookie:
        return redirect(url_for('verify', next=request.url))
    original_link = link_mapping.get(code)
    if not original_link:
        abort(404, description="Link not found.")
    today_str = str(date.today())
    # Enforce daily limit only for non-admin users.
    if tg_user_val != 6773787379:
        if tg_user_val in user_last_access:
            last_code, last_date = user_last_access[tg_user_val]
            if last_date == today_str and last_code != code:
                return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upgrade to Premium</title>
  <style>
    body {
      background: linear-gradient(135deg, #2C3E50, #34495E);
      font-family: "Georgia", serif;
      color: #ECF0F1;
      margin: 0;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }
    .upgrade-container {
      background: #34495E;
      padding: 30px;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
      width: 90%;
      max-width: 500px;
    }
    .upgrade-container h3 { font-size: 28px; margin-bottom: 20px; }
    .upgrade-container p { font-size: 16px; margin-bottom: 20px; }
    .upgrade-btn {
      background: linear-gradient(45deg, #2980B9, #1ABC9C);
      color: #ECF0F1;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .upgrade-btn:hover { background: #16a085; }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .logout-btn:hover { background: #c82333; }
    .reverify-btn {
      background: #ffc107;
      color: #333;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
    }
    .reverify-btn:hover { background: #e0a800; }
  </style>
</head>
<body>
  <div class="upgrade-container">
    <h3>Upgrade to Premium</h3>
    <p>You have exceeded your daily limit for your current plan. Upgrade to enjoy unlimited access or reverify your account.</p>
    <a href="https://t.me/payagain" class="upgrade-btn">Upgrade Now</a>
    <a href="/verify" class="reverify-btn">Reverify</a>
    <button class="logout-btn" onclick="logout()">Logout</button>
    <script>
      function logout() {
          document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          window.location.href = "/";
      }
    </script>
  </div>
</body>
</html>
                ''')
        user_last_access[tg_user_val] = (code, today_str)
    # For admin, no daily limit check.
    if 'hide_logo=1' not in original_link:
        embed_url = original_link + ("&hide_logo=1" if "?" in original_link else "?hide_logo=1")
    else:
        embed_url = original_link
    ua = request.headers.get('User-Agent', '').lower()
    template = MOBILE_EMBED_TEMPLATE if any(k in ua for k in ['iphone','android','ipad','mobile']) else DESKTOP_EMBED_TEMPLATE
    return render_template_string(template, embed_url=embed_url)

# -----------------------
# Embed Templates with Loading Animation
# -----------------------
DESKTOP_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Embedded Terabox Video - Desktop</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

MOBILE_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Embedded Terabox Video - Mobile</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

# -----------------------
# Telegram Bot Admin Command Handlers
# -----------------------
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
    docs = list(col_teralink.find())
    if not docs:
        await update.message.reply_text("No TeraLink links created yet.")
        return
    lines = [f"/p/{doc['code']}  =>  {doc['link']}" for doc in docs]
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def admin_redirection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    docs = list(col_redirection.find())
    if not docs:
        await update.message.reply_text("No redirection links created yet.")
        return
    lines = [f"/s/{doc['code']}  =>  {doc['link']}" for doc in docs]
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
    verified_users[update.effective_user.id] = pending_verifications[token]["session_id"]
    await update.message.reply_text(f"Verification complete. You can now access your link: {pending_verifications[token]['original_url']}")

async def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("TeraLink", admin_teralink_handler))
    application.add_handler(CommandHandler("Redirection", admin_redirection_handler))
    await application.run_polling()

def start_bot():
    new_loop = asyncio.new_event_loop()
    new_loop.add_signal_handler = lambda sig, handler: None
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(run_telegram_bot())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

# -----------------------
# /info Endpoint – Show subscription details from MongoDB (read-only)
# -----------------------
@app.route('/info')
def info():
    tg_user = request.cookies.get("tg_user")
    session_id = request.cookies.get("session_id")
    if not tg_user or not session_id or verified_users.get(int(tg_user)) != session_id:
        return redirect(url_for('verify', next="/info"))
    user_id_str = str(tg_user)
    subscription = col_users.find_one({"user_id": user_id_str})
    if not subscription:
        info_text = "No subscription information found."
    else:
        purchased = subscription.get("purchased", "N/A")
        expiry = subscription.get("expiry", "N/A")
        plan = subscription.get("plan", "basic")
        upgraded = subscription.get("upgraded", False)
        expired_notified = subscription.get("expired_notified", False)
        info_text = (f"User ID: {user_id_str}\nPlan: {plan}\nPurchased: {purchased}\n"
                     f"Expiry: {expiry}\nUpgraded: {upgraded}\nExpired Notified: {expired_notified}")
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subscription Info</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body {
      background: linear-gradient(135deg, #d4fc79, #96e6a1);
      font-family: "Georgia", serif;
    }
    .info-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: left;
      white-space: pre-wrap;
    }
    .info-container h3 {
      text-align: center;
      margin-bottom: 20px;
      color: #2d3436;
    }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 8px 16px;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 20px;
    }
    .logout-btn:hover { background: #c82333; }
  </style>
</head>
<body>
  <div class="info-container">
    <h3>Subscription Info</h3>
    <pre>{{ info_text }}</pre>
    <button class="logout-btn" onclick="logout()">Logout</button>
  </div>
  <script>
    function logout() {
      document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      window.location.href = "/";
    }
  </script>
</body>
</html>
''', info_text=info_text)

# -----------------------
# /detail Endpoint – Placeholder detail page
# -----------------------
@app.route('/detail')
def detail():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Detail</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; font-family: "Georgia", serif; }
    .detail-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="detail-container">
    <h3>Detail</h3>
    <p>This is a placeholder for additional details.</p>
    <button class="btn btn-primary" onclick="window.location.href='/'">Back to Home</button>
  </div>
</body>
</html>
''')

# -----------------------
# /p/<code> Endpoint – TeraLink embed page with Telegram verification, daily limit, and loading animation.
# Admin (id 6773787379) is not limited.
# -----------------------
@app.route('/p/<code>')
def embed_page(code):
    tg_user_cookie = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user_cookie or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        tg_user_val = int(tg_user_cookie)
    except ValueError:
        return redirect(url_for('verify', next=request.url))
    if verified_users.get(tg_user_val) != session_cookie:
        return redirect(url_for('verify', next=request.url))
    original_link = link_mapping.get(code)
    if not original_link:
        abort(404, description="Link not found.")
    today_str = str(date.today())
    # Enforce daily limit only for non-admin users.
    if tg_user_val != 6773787379:
        if tg_user_val in user_last_access:
            last_code, last_date = user_last_access[tg_user_val]
            if last_date == today_str and last_code != code:
                return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upgrade to Premium</title>
  <style>
    body {
      background: linear-gradient(135deg, #2C3E50, #34495E);
      font-family: "Georgia", serif;
      color: #ECF0F1;
      margin: 0;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }
    .upgrade-container {
      background: #34495E;
      padding: 30px;
      border-radius: 10px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
      width: 90%;
      max-width: 500px;
    }
    .upgrade-container h3 { font-size: 28px; margin-bottom: 20px; }
    .upgrade-container p { font-size: 16px; margin-bottom: 20px; }
    .upgrade-btn {
      background: linear-gradient(45deg, #2980B9, #1ABC9C);
      color: #ECF0F1;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .upgrade-btn:hover { background: #16a085; }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .logout-btn:hover { background: #c82333; }
    .reverify-btn {
      background: #ffc107;
      color: #333;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
    }
    .reverify-btn:hover { background: #e0a800; }
  </style>
</head>
<body>
  <div class="upgrade-container">
    <h3>Upgrade to Premium</h3>
    <p>You have exceeded your daily limit for your current plan. Upgrade now to enjoy more links or reverify your account.</p>
    <a href="https://t.me/payagain" class="upgrade-btn">Upgrade Now</a>
    <a href="/verify" class="reverify-btn">Reverify</a>
    <button class="logout-btn" onclick="logout()">Logout</button>
    <script>
      function logout() {
          document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          window.location.href = "/";
      }
    </script>
  </div>
</body>
</html>
                ''')
        user_last_access[tg_user_val] = (code, today_str)
    # For admin, no daily limit check.
    if 'hide_logo=1' not in original_link:
        embed_url = original_link + ("&hide_logo=1" if "?" in original_link else "?hide_logo=1")
    else:
        embed_url = original_link
    ua = request.headers.get('User-Agent', '').lower()
    template = MOBILE_EMBED_TEMPLATE if any(k in ua for k in ['iphone','android','ipad','mobile']) else DESKTOP_EMBED_TEMPLATE
    return render_template_string(template, embed_url=embed_url)

# -----------------------
# Embed Templates with Loading Animation
# -----------------------
DESKTOP_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Embedded Terabox Video - Desktop</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

MOBILE_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Embedded Terabox Video - Mobile</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

# -----------------------
# Telegram Bot Admin Command Handlers
# -----------------------
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
    docs = list(col_teralink.find())
    if not docs:
        await update.message.reply_text("No TeraLink links created yet.")
        return
    lines = [f"/p/{doc['code']}  =>  {doc['link']}" for doc in docs]
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def admin_redirection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    docs = list(col_redirection.find())
    if not docs:
        await update.message.reply_text("No redirection links created yet.")
        return
    lines = [f"/s/{doc['code']}  =>  {doc['link']}" for doc in docs]
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
    verified_users[update.effective_user.id] = pending_verifications[token]["session_id"]
    await update.message.reply_text(f"Verification complete. You can now access your link: {pending_verifications[token]['original_url']}")

async def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("TeraLink", admin_teralink_handler))
    application.add_handler(CommandHandler("Redirection", admin_redirection_handler))
    await application.run_polling()

def start_bot():
    new_loop = asyncio.new_event_loop()
    new_loop.add_signal_handler = lambda sig, handler: None
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(run_telegram_bot())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

# -----------------------
# /info Endpoint – Show subscription details from MongoDB (read-only)
# -----------------------
@app.route('/info')
def info():
    tg_user = request.cookies.get("tg_user")
    session_id = request.cookies.get("session_id")
    if not tg_user or not session_id or verified_users.get(int(tg_user)) != session_id:
        return redirect(url_for('verify', next="/info"))
    user_id_str = str(tg_user)
    subscription = col_users.find_one({"user_id": user_id_str})
    if not subscription:
        info_text = "No subscription information found."
    else:
        purchased = subscription.get("purchased", "N/A")
        expiry = subscription.get("expiry", "N/A")
        plan = subscription.get("plan", "basic")
        upgraded = subscription.get("upgraded", False)
        expired_notified = subscription.get("expired_notified", False)
        info_text = (f"User ID: {user_id_str}\nPlan: {plan}\nPurchased: {purchased}\n"
                     f"Expiry: {expiry}\nUpgraded: {upgraded}\nExpired Notified: {expired_notified}")
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subscription Info</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body {
      background: linear-gradient(135deg, #d4fc79, #96e6a1);
      font-family: "Georgia", serif;
    }
    .info-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: left;
      white-space: pre-wrap;
    }
    .info-container h3 {
      text-align: center;
      margin-bottom: 20px;
      color: #2d3436;
    }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 8px 16px;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 20px;
    }
    .logout-btn:hover { background: #c82333; }
  </style>
</head>
<body>
  <div class="info-container">
    <h3>Subscription Info</h3>
    <pre>{{ info_text }}</pre>
    <button class="logout-btn" onclick="logout()">Logout</button>
  </div>
  <script>
    function logout() {
      document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      window.location.href = "/";
    }
  </script>
</body>
</html>
''', info_text=info_text)

# -----------------------
# /detail Endpoint – Placeholder detail page
# -----------------------
@app.route('/detail')
def detail():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Detail</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; font-family: "Georgia", serif; }
    .detail-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="detail-container">
    <h3>Detail</h3>
    <p>This is a placeholder for additional details.</p>
    <button class="btn btn-primary" onclick="window.location.href='/'">Back to Home</button>
  </div>
</body>
</html>
''')

# -----------------------
# /p/<code> Endpoint – TeraLink embed page with Telegram verification, daily limit, and loading animation.
# Admin (ID 6773787379) is not limited.
# -----------------------
@app.route('/p/<code>')
def embed_page(code):
    tg_user_cookie = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user_cookie or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        tg_user_val = int(tg_user_cookie)
    except ValueError:
        return redirect(url_for('verify', next=request.url))
    if verified_users.get(tg_user_val) != session_cookie:
        return redirect(url_for('verify', next=request.url))
    original_link = link_mapping.get(code)
    if not original_link:
        abort(404, description="Link not found.")
    today_str = str(date.today())
    # Enforce daily limit for non-admin users.
    if tg_user_val != 6773787379:
        if tg_user_val in user_last_access:
            last_code, last_date = user_last_access[tg_user_val]
            if last_date == today_str and last_code != code:
                return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upgrade to Premium</title>
  <style>
    body {
      background: linear-gradient(135deg, #2C3E50, #34495E);
      font-family: "Georgia", serif;
      color: #ECF0F1;
      margin: 0;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }
    .upgrade-container {
      background: #34495E;
      padding: 30px;
      border-radius: 10px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
      width: 90%;
      max-width: 500px;
    }
    .upgrade-container h3 { font-size: 28px; margin-bottom: 20px; }
    .upgrade-container p { font-size: 16px; margin-bottom: 20px; }
    .upgrade-btn {
      background: linear-gradient(45deg, #2980B9, #1ABC9C);
      color: #ECF0F1;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .upgrade-btn:hover { background: #16a085; }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .logout-btn:hover { background: #c82333; }
    .reverify-btn {
      background: #ffc107;
      color: #333;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
    }
    .reverify-btn:hover { background: #e0a800; }
  </style>
</head>
<body>
  <div class="upgrade-container">
    <h3>Upgrade to Premium</h3>
    <p>You have exceeded your daily limit for your current plan. Upgrade now to enjoy more links or reverify your account.</p>
    <a href="https://t.me/payagain" class="upgrade-btn">Upgrade Now</a>
    <a href="/verify" class="reverify-btn">Reverify</a>
    <button class="logout-btn" onclick="logout()">Logout</button>
    <script>
      function logout() {
          document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          window.location.href = "/";
      }
    </script>
  </div>
</body>
</html>
                ''')
        user_last_access[tg_user_val] = (code, today_str)
    # For admin, no daily limit check.
    if 'hide_logo=1' not in original_link:
        embed_url = original_link + ("&hide_logo=1" if "?" in original_link else "?hide_logo=1")
    else:
        embed_url = original_link
    ua = request.headers.get('User-Agent', '').lower()
    template = MOBILE_EMBED_TEMPLATE if any(k in ua for k in ['iphone','android','ipad','mobile']) else DESKTOP_EMBED_TEMPLATE
    return render_template_string(template, embed_url=embed_url)

# -----------------------
# Embed Templates with Loading Animation (Desktop and Mobile)
# -----------------------
DESKTOP_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Embedded Terabox Video - Desktop</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

MOBILE_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Embedded Terabox Video - Mobile</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

# -----------------------
# Telegram Bot Admin Command Handlers
# -----------------------
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
    docs = list(col_teralink.find())
    if not docs:
        await update.message.reply_text("No TeraLink links created yet.")
        return
    lines = [f"/p/{doc['code']}  =>  {doc['link']}" for doc in docs]
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def admin_redirection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    docs = list(col_redirection.find())
    if not docs:
        await update.message.reply_text("No redirection links created yet.")
        return
    lines = [f"/s/{doc['code']}  =>  {doc['link']}" for doc in docs]
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
    verified_users[update.effective_user.id] = pending_verifications[token]["session_id"]
    await update.message.reply_text(f"Verification complete. You can now access your link: {pending_verifications[token]['original_url']}")

async def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("TeraLink", admin_teralink_handler))
    application.add_handler(CommandHandler("Redirection", admin_redirection_handler))
    await application.run_polling()

def start_bot():
    new_loop = asyncio.new_event_loop()
    new_loop.add_signal_handler = lambda sig, handler: None
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(run_telegram_bot())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

# -----------------------
# /info Endpoint – Show subscription details (read-only from MongoDB)
# -----------------------
@app.route('/info')
def info():
    tg_user = request.cookies.get("tg_user")
    session_id = request.cookies.get("session_id")
    if not tg_user or not session_id or verified_users.get(int(tg_user)) != session_id:
        return redirect(url_for('verify', next="/info"))
    user_id_str = str(tg_user)
    subscription = col_users.find_one({"user_id": user_id_str})
    if not subscription:
        info_text = "No subscription information found."
    else:
        purchased = subscription.get("purchased", "N/A")
        expiry = subscription.get("expiry", "N/A")
        plan = subscription.get("plan", "basic")
        upgraded = subscription.get("upgraded", False)
        expired_notified = subscription.get("expired_notified", False)
        info_text = (f"User ID: {user_id_str}\nPlan: {plan}\nPurchased: {purchased}\n"
                     f"Expiry: {expiry}\nUpgraded: {upgraded}\nExpired Notified: {expired_notified}")
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subscription Info</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body {
      background: linear-gradient(135deg, #d4fc79, #96e6a1);
      font-family: "Georgia", serif;
    }
    .info-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: left;
      white-space: pre-wrap;
    }
    .info-container h3 {
      text-align: center;
      margin-bottom: 20px;
      color: #2d3436;
    }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 8px 16px;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 20px;
    }
    .logout-btn:hover { background: #c82333; }
  </style>
</head>
<body>
  <div class="info-container">
    <h3>Subscription Info</h3>
    <pre>{{ info_text }}</pre>
    <button class="logout-btn" onclick="logout()">Logout</button>
  </div>
  <script>
    function logout() {
      document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      window.location.href = "/";
    }
  </script>
</body>
</html>
''', info_text=info_text)

# -----------------------
# /detail Endpoint – Placeholder detail page
# -----------------------
@app.route('/detail')
def detail():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Detail</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; font-family: "Georgia", serif; }
    .detail-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="detail-container">
    <h3>Detail</h3>
    <p>This is a placeholder for additional details.</p>
    <button class="btn btn-primary" onclick="window.location.href='/'">Back to Home</button>
  </div>
</body>
</html>
''')

# -----------------------
# /p/<code> Endpoint – TeraLink embed page with Telegram verification, daily limit, and loading animation.
# Admin (ID 6773787379) is not limited.
# -----------------------
@app.route('/p/<code>')
def embed_page(code):
    tg_user_cookie = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user_cookie or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        tg_user_val = int(tg_user_cookie)
    except ValueError:
        return redirect(url_for('verify', next=request.url))
    if verified_users.get(tg_user_val) != session_cookie:
        return redirect(url_for('verify', next=request.url))
    original_link = link_mapping.get(code)
    if not original_link:
        abort(404, description="Link not found.")
    today_str = str(date.today())
    # Enforce daily limit only for non-admin users.
    if tg_user_val != 6773787379:
        if tg_user_val in user_last_access:
            last_code, last_date = user_last_access[tg_user_val]
            if last_date == today_str and last_code != code:
                return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upgrade to Premium</title>
  <style>
    body {
      background: linear-gradient(135deg, #2C3E50, #34495E);
      font-family: "Georgia", serif;
      color: #ECF0F1;
      margin: 0;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }
    .upgrade-container {
      background: #34495E;
      padding: 30px;
      border-radius: 10px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
      width: 90%;
      max-width: 500px;
    }
    .upgrade-container h3 { font-size: 28px; margin-bottom: 20px; }
    .upgrade-container p { font-size: 16px; margin-bottom: 20px; }
    .upgrade-btn {
      background: linear-gradient(45deg, #2980B9, #1ABC9C);
      color: #ECF0F1;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .upgrade-btn:hover { background: #16a085; }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .logout-btn:hover { background: #c82333; }
    .reverify-btn {
      background: #ffc107;
      color: #333;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
    }
    .reverify-btn:hover { background: #e0a800; }
  </style>
</head>
<body>
  <div class="upgrade-container">
    <h3>Upgrade to Premium</h3>
    <p>You have exceeded your daily limit for your current plan. Upgrade now to enjoy more links or reverify your account.</p>
    <a href="https://t.me/payagain" class="upgrade-btn">Upgrade Now</a>
    <a href="/verify" class="reverify-btn">Reverify</a>
    <button class="logout-btn" onclick="logout()">Logout</button>
    <script>
      function logout() {
          document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          window.location.href = "/";
      }
    </script>
  </div>
</body>
</html>
                ''')
        user_last_access[tg_user_val] = (code, today_str)
    # For admin, no daily limit check.
    if 'hide_logo=1' not in original_link:
        embed_url = original_link + ("&hide_logo=1" if "?" in original_link else "?hide_logo=1")
    else:
        embed_url = original_link
    ua = request.headers.get('User-Agent', '').lower()
    template = MOBILE_EMBED_TEMPLATE if any(k in ua for k in ['iphone','android','ipad','mobile']) else DESKTOP_EMBED_TEMPLATE
    return render_template_string(template, embed_url=embed_url)

# -----------------------
# Embed Templates with Loading Animation
# -----------------------
DESKTOP_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Embedded Terabox Video - Desktop</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

MOBILE_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Embedded Terabox Video - Mobile</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

# -----------------------
# Telegram Bot Admin Command Handlers
# -----------------------
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
    docs = list(col_teralink.find())
    if not docs:
        await update.message.reply_text("No TeraLink links created yet.")
        return
    lines = [f"/p/{doc['code']}  =>  {doc['link']}" for doc in docs]
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def admin_redirection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    docs = list(col_redirection.find())
    if not docs:
        await update.message.reply_text("No redirection links created yet.")
        return
    lines = [f"/s/{doc['code']}  =>  {doc['link']}" for doc in docs]
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
    verified_users[update.effective_user.id] = pending_verifications[token]["session_id"]
    await update.message.reply_text(f"Verification complete. You can now access your link: {pending_verifications[token]['original_url']}")

async def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("TeraLink", admin_teralink_handler))
    application.add_handler(CommandHandler("Redirection", admin_redirection_handler))
    await application.run_polling()

def start_bot():
    new_loop = asyncio.new_event_loop()
    new_loop.add_signal_handler = lambda sig, handler: None
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(run_telegram_bot())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

# -----------------------
# /info Endpoint – Show subscription details from MongoDB (read-only)
# -----------------------
@app.route('/info')
def info():
    tg_user = request.cookies.get("tg_user")
    session_id = request.cookies.get("session_id")
    if not tg_user or not session_id or verified_users.get(int(tg_user)) != session_id:
        return redirect(url_for('verify', next="/info"))
    user_id_str = str(tg_user)
    subscription = col_users.find_one({"user_id": user_id_str})
    if not subscription:
        info_text = "No subscription information found."
    else:
        purchased = subscription.get("purchased", "N/A")
        expiry = subscription.get("expiry", "N/A")
        plan = subscription.get("plan", "basic")
        upgraded = subscription.get("upgraded", False)
        expired_notified = subscription.get("expired_notified", False)
        info_text = (f"User ID: {user_id_str}\nPlan: {plan}\nPurchased: {purchased}\n"
                     f"Expiry: {expiry}\nUpgraded: {upgraded}\nExpired Notified: {expired_notified}")
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subscription Info</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body {
      background: linear-gradient(135deg, #d4fc79, #96e6a1);
      font-family: "Georgia", serif;
    }
    .info-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: left;
      white-space: pre-wrap;
    }
    .info-container h3 {
      text-align: center;
      margin-bottom: 20px;
      color: #2d3436;
    }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 8px 16px;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 20px;
    }
    .logout-btn:hover { background: #c82333; }
  </style>
</head>
<body>
  <div class="info-container">
    <h3>Subscription Info</h3>
    <pre>{{ info_text }}</pre>
    <button class="logout-btn" onclick="logout()">Logout</button>
  </div>
  <script>
    function logout() {
      document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      window.location.href = "/";
    }
  </script>
</body>
</html>
''', info_text=info_text)

# -----------------------
# /detail Endpoint – Placeholder detail page
# -----------------------
@app.route('/detail')
def detail():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Detail</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; font-family: "Georgia", serif; }
    .detail-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="detail-container">
    <h3>Detail</h3>
    <p>This is a placeholder for additional details.</p>
    <button class="btn btn-primary" onclick="window.location.href='/'">Back to Home</button>
  </div>
</body>
</html>
''')

# -----------------------
# /p/<code> Endpoint – TeraLink embed page with Telegram verification, daily limit, and loading animation.
# Admin (ID 6773787379) is not limited.
# -----------------------
@app.route('/p/<code>')
def embed_page(code):
    tg_user_cookie = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user_cookie or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        tg_user_val = int(tg_user_cookie)
    except ValueError:
        return redirect(url_for('verify', next=request.url))
    if verified_users.get(tg_user_val) != session_cookie:
        return redirect(url_for('verify', next=request.url))
    original_link = link_mapping.get(code)
    if not original_link:
        abort(404, description="Link not found.")
    today_str = str(date.today())
    # Enforce daily limit for non-admin users.
    if tg_user_val != 6773787379:
        if tg_user_val in user_last_access:
            last_code, last_date = user_last_access[tg_user_val]
            if last_date == today_str and last_code != code:
                return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upgrade to Premium</title>
  <style>
    body {
      background: linear-gradient(135deg, #2C3E50, #34495E);
      font-family: "Georgia", serif;
      color: #ECF0F1;
      margin: 0;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }
    .upgrade-container {
      background: #34495E;
      padding: 30px;
      border-radius: 10px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
      width: 90%;
      max-width: 500px;
    }
    .upgrade-container h3 { font-size: 28px; margin-bottom: 20px; }
    .upgrade-container p { font-size: 16px; margin-bottom: 20px; }
    .upgrade-btn {
      background: linear-gradient(45deg, #2980B9, #1ABC9C);
      color: #ECF0F1;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .upgrade-btn:hover { background: #16a085; }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .logout-btn:hover { background: #c82333; }
    .reverify-btn {
      background: #ffc107;
      color: #333;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
    }
    .reverify-btn:hover { background: #e0a800; }
  </style>
</head>
<body>
  <div class="upgrade-container">
    <h3>Upgrade to Premium</h3>
    <p>You have exceeded your daily limit for your current plan. Upgrade now to enjoy more links or reverify your account.</p>
    <a href="https://t.me/payagain" class="upgrade-btn">Upgrade Now</a>
    <a href="/verify" class="reverify-btn">Reverify</a>
    <button class="logout-btn" onclick="logout()">Logout</button>
    <script>
      function logout() {
          document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          window.location.href = "/";
      }
    </script>
  </div>
</body>
</html>
                ''')
        user_last_access[tg_user_val] = (code, today_str)
    if 'hide_logo=1' not in original_link:
        embed_url = original_link + ("&hide_logo=1" if "?" in original_link else "?hide_logo=1")
    else:
        embed_url = original_link
    ua = request.headers.get('User-Agent', '').lower()
    template = MOBILE_EMBED_TEMPLATE if any(k in ua for k in ['iphone','android','ipad','mobile']) else DESKTOP_EMBED_TEMPLATE
    return render_template_string(template, embed_url=embed_url)

# -----------------------
# Embed Templates with Loading Animation
# -----------------------
DESKTOP_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Embedded Terabox Video - Desktop</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

MOBILE_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Embedded Terabox Video - Mobile</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

# -----------------------
# Telegram Bot Admin Command Handlers
# -----------------------
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
    docs = list(col_teralink.find())
    if not docs:
        await update.message.reply_text("No TeraLink links created yet.")
        return
    lines = [f"/p/{doc['code']}  =>  {doc['link']}" for doc in docs]
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def admin_redirection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    docs = list(col_redirection.find())
    if not docs:
        await update.message.reply_text("No redirection links created yet.")
        return
    lines = [f"/s/{doc['code']}  =>  {doc['link']}" for doc in docs]
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
    verified_users[update.effective_user.id] = pending_verifications[token]["session_id"]
    await update.message.reply_text(f"Verification complete. You can now access your link: {pending_verifications[token]['original_url']}")

async def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("TeraLink", admin_teralink_handler))
    application.add_handler(CommandHandler("Redirection", admin_redirection_handler))
    await application.run_polling()

def start_bot():
    new_loop = asyncio.new_event_loop()
    new_loop.add_signal_handler = lambda sig, handler: None
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(run_telegram_bot())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

# -----------------------
# /info Endpoint – Show subscription details from MongoDB (read-only)
# -----------------------
@app.route('/info')
def info():
    tg_user = request.cookies.get("tg_user")
    session_id = request.cookies.get("session_id")
    if not tg_user or not session_id or verified_users.get(int(tg_user)) != session_id:
        return redirect(url_for('verify', next="/info"))
    user_id_str = str(tg_user)
    subscription = col_users.find_one({"user_id": user_id_str})
    if not subscription:
        info_text = "No subscription information found."
    else:
        purchased = subscription.get("purchased", "N/A")
        expiry = subscription.get("expiry", "N/A")
        plan = subscription.get("plan", "basic")
        upgraded = subscription.get("upgraded", False)
        expired_notified = subscription.get("expired_notified", False)
        info_text = (f"User ID: {user_id_str}\nPlan: {plan}\nPurchased: {purchased}\n"
                     f"Expiry: {expiry}\nUpgraded: {upgraded}\nExpired Notified: {expired_notified}")
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subscription Info</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body {
      background: linear-gradient(135deg, #d4fc79, #96e6a1);
      font-family: "Georgia", serif;
    }
    .info-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: left;
      white-space: pre-wrap;
    }
    .info-container h3 {
      text-align: center;
      margin-bottom: 20px;
      color: #2d3436;
    }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 8px 16px;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 20px;
    }
    .logout-btn:hover { background: #c82333; }
  </style>
</head>
<body>
  <div class="info-container">
    <h3>Subscription Info</h3>
    <pre>{{ info_text }}</pre>
    <button class="logout-btn" onclick="logout()">Logout</button>
  </div>
  <script>
    function logout() {
      document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
      window.location.href = "/";
    }
  </script>
</body>
</html>
''', info_text=info_text)

# -----------------------
# /detail Endpoint – Placeholder detail page
# -----------------------
@app.route('/detail')
def detail():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Detail</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; font-family: "Georgia", serif; }
    .detail-container {
      max-width: 600px;
      margin: 80px auto;
      padding: 30px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="detail-container">
    <h3>Detail</h3>
    <p>This is a placeholder for additional details.</p>
    <button class="btn btn-primary" onclick="window.location.href='/'">Back to Home</button>
  </div>
</body>
</html>
''')

# -----------------------
# /p/<code> Endpoint – TeraLink embed page with Telegram verification, daily limit, and loading animation.
# Admin (ID 6773787379) is not limited.
# -----------------------
@app.route('/p/<code>')
def embed_page(code):
    tg_user_cookie = request.cookies.get("tg_user")
    session_cookie = request.cookies.get("session_id")
    if not tg_user_cookie or not session_cookie:
        return redirect(url_for('verify', next=request.url))
    try:
        tg_user_val = int(tg_user_cookie)
    except ValueError:
        return redirect(url_for('verify', next=request.url))
    if verified_users.get(tg_user_val) != session_cookie:
        return redirect(url_for('verify', next=request.url))
    original_link = link_mapping.get(code)
    if not original_link:
        abort(404, description="Link not found.")
    today_str = str(date.today())
    # Enforce daily limit for non-admin users.
    if tg_user_val != 6773787379:
        if tg_user_val in user_last_access:
            last_code, last_date = user_last_access[tg_user_val]
            if last_date == today_str and last_code != code:
                return render_template_string('''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upgrade to Premium</title>
  <style>
    body {
      background: linear-gradient(135deg, #2C3E50, #34495E);
      font-family: "Georgia", serif;
      color: #ECF0F1;
      margin: 0;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }
    .upgrade-container {
      background: #34495E;
      padding: 30px;
      border-radius: 10px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      text-align: center;
      width: 90%;
      max-width: 500px;
    }
    .upgrade-container h3 { font-size: 28px; margin-bottom: 20px; }
    .upgrade-container p { font-size: 16px; margin-bottom: 20px; }
    .upgrade-btn {
      background: linear-gradient(45deg, #2980B9, #1ABC9C);
      color: #ECF0F1;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .upgrade-btn:hover { background: #16a085; }
    .logout-btn {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
      margin-right: 10px;
    }
    .logout-btn:hover { background: #c82333; }
    .reverify-btn {
      background: #ffc107;
      color: #333;
      border: none;
      padding: 12px 24px;
      font-size: 18px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.3s;
      text-decoration: none;
    }
    .reverify-btn:hover { background: #e0a800; }
  </style>
</head>
<body>
  <div class="upgrade-container">
    <h3>Upgrade to Premium</h3>
    <p>You have exceeded your daily limit for your current plan. Upgrade now to enjoy more links or reverify your account.</p>
    <a href="https://t.me/payagain" class="upgrade-btn">Upgrade Now</a>
    <a href="/verify" class="reverify-btn">Reverify</a>
    <button class="logout-btn" onclick="logout()">Logout</button>
    <script>
      function logout() {
          document.cookie = "tg_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
          window.location.href = "/";
      }
    </script>
  </div>
</body>
</html>
                ''')
        user_last_access[tg_user_val] = (code, today_str)
    # For admin, no daily limit check.
    if 'hide_logo=1' not in original_link:
        embed_url = original_link + ("&hide_logo=1" if "?" in original_link else "?hide_logo=1")
    else:
        embed_url = original_link
    ua = request.headers.get('User-Agent', '').lower()
    template = MOBILE_EMBED_TEMPLATE if any(k in ua for k in ['iphone','android','ipad','mobile']) else DESKTOP_EMBED_TEMPLATE
    return render_template_string(template, embed_url=embed_url)

# -----------------------
# Embed Templates with Loading Animation
# -----------------------
DESKTOP_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Embedded Terabox Video - Desktop</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

MOBILE_EMBED_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Embedded Terabox Video - Mobile</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
    #loader {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background-color: #f8f9fa;
      display: flex; align-items: center; justify-content: center;
      z-index: 9999;
    }
    .spinner-border {
      width: 3rem; height: 3rem;
      border: 0.25em solid #007bff;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spinner 0.75s linear infinite;
    }
    @keyframes spinner { to { transform: rotate(360deg); } }
    iframe { width: 100%; height: 100%; border: none; }
  </style>
</head>
<body>
  <div id="loader"><div class="spinner-border"></div></div>
  <iframe src="{{ embed_url }}" allowfullscreen sandbox="allow-same-origin allow-scripts" onload="document.getElementById('loader').style.display='none';"></iframe>
</body>
</html>
'''

# -----------------------
# Telegram Bot Admin Command Handlers
# -----------------------
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
    docs = list(col_teralink.find())
    if not docs:
        await update.message.reply_text("No TeraLink links created yet.")
        return
    lines = [f"/p/{doc['code']}  =>  {doc['link']}" for doc in docs]
    message = "\n".join(lines)
    for chunk in split_message(message):
        await update.message.reply_text(chunk)

async def admin_redirection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = 6773787379
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return
    docs = list(col_redirection.find())
    if not docs:
        await update.message.reply_text("No redirection links created yet.")
        return
    lines = [f"/s/{doc['code']}  =>  {doc['link']}" for doc in docs]
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
    verified_users[update.effective_user.id] = pending_verifications[token]["session_id"]
    await update.message.reply_text(f"Verification complete. You can now access your link: {pending_verifications[token]['original_url']}")

async def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("TeraLink", admin_teralink_handler))
    application.add_handler(CommandHandler("Redirection", admin_redirection_handler))
    await application.run_polling()

def start_bot():
    new_loop = asyncio.new_event_loop()
    new_loop.add_signal_handler = lambda sig, handler: None
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(run_telegram_bot())

bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8080, use_reloader=False)
