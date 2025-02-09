import os, random, string, requests
from flask import Flask, request, url_for, render_template_string, abort, redirect
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from pymongo import MongoClient

app = Flask(__name__)

# ----------------------------
# MongoDB Connection
# ----------------------------
MONGO_URI = "mongodb+srv://kunalrepowala6:dcRXaBdz0MFQEOxB@cluster0.yu0rr.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["Cluster0"]
video_collection = db["videos"]
image_collection = db["images"]

# ----------------------------
# Utility Functions
# ----------------------------
def generate_unique_id(length=9):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def compute_aspect_ratio(data):
    if data.get('preview_width') and data.get('preview_height'):
        try:
            return (data['preview_height'] / data['preview_width']) * 100
        except Exception:
            return 56.25
    return 56.25

# ----------------------------
# No-Caching Headers
# ----------------------------
@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ----------------------------
# Video Creation Page (/TeraLink)
# ----------------------------
@app.route('/TeraLink', methods=['GET', 'POST'])
def teralink():
    error = None
    generated_link = None
    if request.method == 'POST':
        user_title = request.form.get('user_title', '').strip()
        user_description = request.form.get('user_description', '').strip()
        embed_link = request.form.get('embed_link', '').strip()
        if not embed_link:
            error = "Embed link is required."
        elif '/sharing/embed' not in embed_link:
            error = "Embed link must include '/sharing/embed'."
        if not error:
            try:
                resp = requests.get(embed_link, timeout=5)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
            except Exception:
                soup = None
            if soup:
                meta_title = soup.find("meta", property="og:title")
                if meta_title and meta_title.get("content"):
                    scraped_title = meta_title["content"].strip()
                else:
                    title_tag = soup.find("title")
                    scraped_title = title_tag.text.strip() if title_tag else "Video"
            else:
                scraped_title = "Video"
            preview_width, preview_height = None, None
            if soup:
                meta_image = soup.find("meta", property="og:image")
                if meta_image and meta_image.get("content"):
                    preview_image_url = meta_image["content"].strip()
                    try:
                        img_resp = requests.get(preview_image_url, timeout=5)
                        img_resp.raise_for_status()
                        img = Image.open(BytesIO(img_resp.content))
                        preview_width, preview_height = img.size
                    except Exception:
                        preview_width, preview_height = None, None
            uid = generate_unique_id()
            while video_collection.find_one({"uid": uid}):
                uid = generate_unique_id()
            record = {
                "uid": uid,
                "embed_link": embed_link,
                "scraped_title": scraped_title,
                "preview_width": preview_width,
                "preview_height": preview_height,
                "user_title": user_title,
                "user_description": user_description
            }
            video_collection.insert_one(record)
            # Use the secure video playback route (/s/)
            generated_link = url_for('play_video_secure', unique_id=uid, _external=True)
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
      <title>Create TeraLink</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
         body { font-family: Arial, sans-serif; background: #f5f5f5; margin:0; padding:20px; }
         .container { max-width:600px; margin:auto; background:#fff; padding:20px; border-radius:4px; }
         h1 { text-align:center; }
         label { display:block; margin-top:10px; font-weight:bold; }
         input[type="text"], textarea { width:100%; padding:8px; margin-top:5px; border:1px solid #ccc; border-radius:4px; }
         button { width:100%; padding:10px; margin-top:20px; background:#007BFF; color:#fff; border:none; border-radius:4px; font-size:16px; cursor:pointer; }
         button:hover { background:#0056b3; }
         .result { margin-top:20px; padding:10px; background:#e9ecef; border:1px solid #ccc; border-radius:4px; text-align:center; }
         .result input[type="text"] { width:100%; padding:8px; font-size:16px; text-align:center; }
      </style>
      <script>
         function copyLink() {
            var copyText = document.getElementById("generatedLink");
            copyText.select();
            document.execCommand("copy");
         }
      </script>
    </head>
    <body>
      <div class="container">
         <h1>Create TeraLink</h1>
         {% if error %}<div style="color:red; text-align:center;">{{ error }}</div>{% endif %}
         <form method="post">
            <label for="user_title">Title (for page content):</label>
            <input type="text" id="user_title" name="user_title" placeholder="Enter title for page">
            <label for="user_description">Description (for page content):</label>
            <textarea id="user_description" name="user_description" placeholder="Enter description" rows="4"></textarea>
            <label for="embed_link">Embed Link (must include /sharing/embed):</label>
            <input type="text" id="embed_link" name="embed_link" placeholder="Enter embed link" required>
            <button type="submit">Generate Link</button>
         </form>
         {% if generated_link %}
         <div class="result">
            <p>Your generated link:</p>
            <input type="text" id="generatedLink" value="{{ generated_link }}" readonly>
            <br>
            <button type="button" onclick="copyLink()">Copy Link</button>
            <br><br>
            <a href="{{ generated_link }}" target="_blank" style="text-decoration:none; color:#007BFF;">View Video</a>
         </div>
         {% endif %}
      </div>
    </body>
    </html>
    '''
    return render_template_string(html, error=error, generated_link=generated_link)

# ----------------------------
# Secure Video Playback Page (/s/<unique_id>)
# Blocks redirection but allows interactive controls.
@app.route('/s/<unique_id>')
def play_video_secure(unique_id):
    data = video_collection.find_one({"uid": unique_id})
    if not data:
        abort(404)
    aspect_ratio = compute_aspect_ratio(data)
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
      <title>{{ data.scraped_title|safe }}</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
         body { margin:0; padding:0; background:#000; color:#fff; font-family:Arial, sans-serif; }
         body.light-mode { background:#fff; color:#000; }
         .header-bar {
            display: flex; justify-content: space-between; align-items: center;
            padding:10px 20px; border-bottom:1px solid #555; background:inherit;
         }
         .header-bar .hoterror {
            font-family:'Times New Roman', Georgia, serif; font-size:36px; font-weight:bold; color:#400000;
         }
         .header-bar .mode-toggle { cursor:pointer; font-size:28px; user-select:none; }
         .user-title { margin:15px 20px; font-family:'Times New Roman', Georgia, serif; font-size:28px; text-align:left; }
         .video-container { width:100%; position:relative; overflow:hidden; }
         .video-container::before { content:""; display:block; padding-bottom:{{ aspect_ratio if aspect_ratio > 0 else 56.25 }}%; }
         .video-container iframe {
            position:absolute; top:0; left:0; width:100%; height:100%; border:0; object-fit:contain;
         }
         .description-container { margin:15px 20px; }
         .description-toggle {
            cursor:pointer; font-size:16px; color:#ccc; display:flex; align-items:center;
         }
         .description-toggle span.arrow {
            display:inline-block; transition:transform 0.3s ease; margin-right:5px;
         }
         .description { max-height:0; overflow:hidden; transition:max-height 0.3s ease; font-size:16px; margin-top:5px; color:#aaa; }
         .description.open { max-height:300px; }
         body { overflow-y:auto; }
      </style>
      <script>
         function toggleDescription(){
            var desc = document.getElementById("description");
            var arrow = document.getElementById("arrow");
            if(desc.classList.contains("open")){
                desc.classList.remove("open");
                arrow.style.transform = "rotate(0deg)";
                desc.style.maxHeight = "0";
            } else {
                desc.classList.add("open");
                arrow.style.transform = "rotate(180deg)";
                desc.style.maxHeight = "300px";
            }
         }
         function toggleMode(){
            document.body.classList.toggle('light-mode');
            var toggleBtn = document.getElementById("mode-toggle");
            if(document.body.classList.contains('light-mode')){
               toggleBtn.innerHTML = "☀️";
            } else {
               toggleBtn.innerHTML = "🌙";
            }
         }
         window.onload = function(){
            var toggleBtn = document.getElementById("mode-toggle");
            if(document.body.classList.contains('light-mode')){
               toggleBtn.innerHTML = "☀️";
            } else {
               toggleBtn.innerHTML = "🌙";
            }
         };
      </script>
    </head>
    <body>
         <div class="header-bar">
            <div class="hoterror">HOTERROR</div>
            <div id="mode-toggle" class="mode-toggle" onclick="toggleMode()">🌙</div>
         </div>
         {% if data.user_title %}
         <div class="user-title">{{ data.user_title|safe }}</div>
         {% endif %}
         <div class="video-container">
            <!-- The sandbox attribute blocks top navigation while allowing interactive controls -->
            <iframe sandbox="allow-same-origin allow-scripts allow-forms" src="{{ data.embed_link }}" allowfullscreen scrolling="no"></iframe>
         </div>
         {% if data.user_description %}
         <div class="description-container">
            <div class="description-toggle" onclick="toggleDescription()" style="cursor:pointer; font-size:16px; color:#ccc; display:flex; align-items:center;">
               <span class="arrow" id="arrow" style="display:inline-block; transition:transform 0.3s ease; margin-right:5px;">&#9660;</span>
               <span>Show Description</span>
            </div>
            <div class="description" id="description">
               {{ data.user_description|safe }}
            </div>
         </div>
         {% endif %}
    </body>
    </html>
    '''
    return render_template_string(html, data=data, aspect_ratio=aspect_ratio)

# ----------------------------
# Image Creation Page (/image)
# ----------------------------
@app.route('/image', methods=['GET', 'POST'])
def image_creation():
    error = None
    generated_link = None
    if request.method == 'POST':
        user_title = request.form.get('user_title', '').strip()
        user_description = request.form.get('user_description', '').strip()
        image_html_list = request.form.getlist('image_html[]')
        image_html_list = [s.strip() for s in image_html_list if s.strip()]
        if not image_html_list:
            error = "At least one image HTML is required."
        else:
            for html_input in image_html_list:
                if "https://ibb.co/" not in html_input:
                    error = "Only URLs from https://ibb.co/ are accepted."
                    break
        if not error:
            uid = generate_unique_id()
            while image_collection.find_one({"uid": uid}):
                uid = generate_unique_id()
            record = {
                "uid": uid,
                "user_title": user_title,
                "user_description": user_description,
                "image_html": image_html_list
            }
            image_collection.insert_one(record)
            generated_link = url_for('play_image', unique_id=uid, _external=True)
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
      <title>Create Image Link</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
         body { font-family: Arial, sans-serif; background: #f5f5f5; margin:0; padding:20px; }
         .container { max-width:600px; margin:auto; background:#fff; padding:20px; border-radius:4px; }
         h1 { text-align:center; }
         label { display:block; margin-top:10px; font-weight:bold; }
         input[type="text"], textarea { width:100%; padding:8px; margin-top:5px; border:1px solid #ccc; border-radius:4px; }
         button { width:100%; padding:10px; margin-top:20px; background:#007BFF; color:#fff; border:none; border-radius:4px; font-size:16px; cursor:pointer; }
         button:hover { background:#0056b3; }
         .result { margin-top:20px; padding:10px; background:#e9ecef; border:1px solid #ccc; border-radius:4px; text-align:center; }
         .result input[type="text"] { width:100%; padding:8px; font-size:16px; text-align:center; }
         .add-button { margin-top:10px; padding:8px; background:#28a745; color:#fff; border:none; border-radius:4px; cursor:pointer; }
         .add-button:hover { background:#218838; }
      </style>
      <script>
         function copyLink() {
            var copyText = document.getElementById("generatedLink");
            copyText.select();
            document.execCommand("copy");
         }
         function addField() {
            var container = document.getElementById("image_fields");
            var input = document.createElement("input");
            input.type = "text";
            input.name = "image_html[]";
            input.placeholder = "Enter image HTML (must contain https://ibb.co/)";
            input.style.width = "100%";
            input.style.padding = "8px";
            input.style.marginTop = "5px";
            input.style.border = "1px solid #ccc";
            input.style.borderRadius = "4px";
            container.appendChild(input);
         }
      </script>
    </head>
    <body>
      <div class="container">
         <h1>Create Image Link</h1>
         {% if error %}<div style="color:red; text-align:center;">{{ error }}</div>{% endif %}
         <form method="post">
            <label for="user_title">Title (for page content):</label>
            <input type="text" id="user_title" name="user_title" placeholder="Enter title for page">
            <label for="user_description">Description (for page content):</label>
            <textarea id="user_description" name="user_description" placeholder="Enter description" rows="4"></textarea>
            <label>Image HTML (must contain https://ibb.co/):</label>
            <div id="image_fields">
              <input type="text" name="image_html[]" placeholder="Enter image HTML" required>
            </div>
            <button type="button" class="add-button" onclick="addField()">+</button>
            <button type="submit">Generate Link</button>
         </form>
         {% if generated_link %}
         <div class="result">
            <p>Your generated link:</p>
            <input type="text" id="generatedLink" value="{{ generated_link }}" readonly>
            <br>
            <button type="button" onclick="copyLink()">Copy Link</button>
            <br><br>
            <a href="{{ generated_link }}" target="_blank" style="text-decoration:none; color:#007BFF;">View Image</a>
         </div>
         {% endif %}
      </div>
    </body>
    </html>
    '''
    return render_template_string(html, error=error, generated_link=generated_link)

# ----------------------------
# Image Playback Page (/i/<unique_id>)
# ----------------------------
@app.route('/i/<unique_id>')
def play_image(unique_id):
    data = image_collection.find_one({"uid": unique_id})
    if not data:
        abort(404)
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
      <title>{{ data.user_title if data.user_title else "Image" }}</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
         body { margin:0; padding:0; background:#000; color:#fff; font-family:Arial, sans-serif; }
         body.light-mode { background:#fff; color:#000; }
         .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding:10px 20px;
            border-bottom:1px solid #555;
            background:inherit;
         }
         .header-bar .hoterror {
            font-family:'Times New Roman', Georgia, serif;
            font-size:32px;
            font-weight:bold;
            color:#800000;
         }
         .header-bar .mode-toggle { cursor:pointer; font-size:28px; user-select:none; }
         .user-title { margin:15px 20px; font-family:'Times New Roman', Georgia, serif; font-size:26px; text-align:left; }
         .image-container { margin:0 20px; text-align:center; }
         .image-container a { pointer-events: none; }
         .image-container img { max-width:100%; height:auto; margin-bottom:15px; object-fit:contain; }
         .description-container { margin:15px 20px; }
         .description-toggle { cursor:pointer; font-size:16px; color:#ccc; user-select:none; display:flex; align-items:center; }
         .description-toggle span.arrow { display:inline-block; transition:transform 0.3s ease; margin-right:5px; }
         .description { max-height:0; overflow:hidden; transition:max-height 0.3s ease; font-size:16px; margin-top:5px; color:#aaa; }
         .description.open { max-height:300px; }
      </style>
      <script>
         function toggleDescription() {
            var desc = document.getElementById("description");
            var arrow = document.getElementById("arrow");
            if(desc.classList.contains("open")){
               desc.classList.remove("open");
               arrow.style.transform = "rotate(0deg)";
               desc.style.maxHeight = "0";
            } else {
               desc.classList.add("open");
               arrow.style.transform = "rotate(180deg)";
               desc.style.maxHeight = "300px";
            }
         }
         function toggleMode() {
            document.body.classList.toggle('light-mode');
            var toggleBtn = document.getElementById("mode-toggle");
            if(document.body.classList.contains('light-mode')){
               toggleBtn.innerHTML = "☀️";
            } else {
               toggleBtn.innerHTML = "🌙";
            }
         }
         window.onload = function() {
            var toggleBtn = document.getElementById("mode-toggle");
            if(document.body.classList.contains('light-mode')){
               toggleBtn.innerHTML = "☀️";
            } else {
               toggleBtn.innerHTML = "🌙";
            }
         };
      </script>
    </head>
    <body>
         <div class="header-bar">
            <div class="hoterror">HOTERROR</div>
            <div id="mode-toggle" class="mode-toggle" onclick="toggleMode()">🌙</div>
         </div>
         {% if data.user_title %}
         <div class="user-title">{{ data.user_title|safe }}</div>
         {% endif %}
         <div class="image-container">
            {% for html_str in data.image_html %}
               {{ html_str|safe }}
            {% endfor %}
         </div>
         {% if data.user_description %}
         <div class="description-container">
            <div class="description-toggle" onclick="toggleDescription()">
               <span class="arrow" id="arrow">&#9660;</span>
               <span>Show Description</span>
            </div>
            <div class="description" id="description">
               {{ data.user_description|safe }}
            </div>
         </div>
         {% endif %}
    </body>
    </html>
    '''
    return render_template_string(html, data=data)

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, use_reloader=False, port=8080)
