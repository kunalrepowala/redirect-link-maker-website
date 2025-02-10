import random
import string
import requests
import threading
from flask import Flask, request, url_for, render_template_string, abort
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from pymongo import MongoClient

app = Flask(__name__)
# This setting ensures that _external URLs are generated using https.
app.config['PREFERRED_URL_SCHEME'] = 'https'
# If you know your Koyeb domain, you can set it here so that url_for generates proper links.
# For example:
# app.config['SERVER_NAME'] = 'your-koyeb-app.koyeb.app'

# Connect to MongoDB using the provided connection URL and use the "Cluster0" database.
mongo_url = "mongodb+srv://kunalrepowala6:dcRXaBdz0MFQEOxB@cluster0.yu0rr.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_url)
db = client['Cluster0']
links_collection = db['links']

def generate_unique_id(length=9):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def compute_aspect_ratio(data):
    if data.get('preview_width') and data.get('preview_height'):
        try:
            return (data['preview_height'] / data['preview_width']) * 100
        except Exception:
            return 56.25
    return 56.25

def fetch_metadata(unique_id, embed_link):
    """Fetch metadata (page title and preview image dimensions) in a background thread."""
    try:
        resp = requests.get(embed_link, timeout=5)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Get scraped title.
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            scraped_title = meta_title["content"].strip()
        else:
            title_tag = soup.find("title")
            scraped_title = title_tag.text.strip() if title_tag else "Video"
        
        # Get preview image dimensions.
        preview_width, preview_height = None, None
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
        
        # Update the record in MongoDB.
        links_collection.update_one(
            {"identifier": unique_id},
            {"$set": {
                "scraped_title": scraped_title,
                "preview_width": preview_width,
                "preview_height": preview_height
            }}
        )
    except Exception:
        pass

@app.route('/TeraLink', methods=['GET', 'POST'])
def teralink():
    error = None
    generated_link = None
    if request.method == 'POST':
        user_title = request.form.get('user_title', '').strip()
        user_description = request.form.get('user_description', '').strip()
        embed_link = request.form.get('embed_link', '').strip()
        
        # Validate: the URL must include either '/sharing/embed', '/s/', or '/wap/share/'.
        if not embed_link:
            error = "Embed link is required."
        elif '/sharing/embed' not in embed_link and '/s/' not in embed_link and '/wap/share/' not in embed_link:
            error = "Embed link must include '/sharing/embed', '/s/' or '/wap/share/'."
        
        # If the provided link is a short link (/s/ or /wap/share/) but not already an embed link, convert it.
        if not error and ('/s/' in embed_link or '/wap/share/' in embed_link) and '/sharing/embed' not in embed_link:
            if '/wap/share/' in embed_link:
                parts = embed_link.split('/wap/share/')
            else:
                parts = embed_link.split('/s/')
            code = parts[-1].strip() if parts[-1] else ""
            if code and code[0].isdigit():
                code = code[1:]
            embed_link = (
                f"https://www.1024terabox.com/sharing/embed?surl={code}"
                "&resolution=1080&autoplay=true&mute=false&uk=4400105884193"
                "&fid=91483455887823&slid="
            )
        
        # Final check: the embed_link must now include '/sharing/embed'.
        if not error and '/sharing/embed' not in embed_link:
            error = "Embed link must include '/sharing/embed' after conversion."
        
        if not error:
            unique_id = generate_unique_id()
            # Ensure uniqueness in MongoDB.
            while links_collection.find_one({"identifier": unique_id}):
                unique_id = generate_unique_id()
            
            doc = {
                "identifier": unique_id,
                "embed_link": embed_link,
                "scraped_title": "Video",   # default title until metadata is fetched
                "preview_width": None,
                "preview_height": None,
                "user_title": user_title,
                "user_description": user_description
            }
            links_collection.insert_one(doc)
            
            # Generate the external URL; when hosted on Koyeb this will use your Koyeb domain.
            generated_link = url_for('play_link', identifier=unique_id, _external=True)
            threading.Thread(target=fetch_metadata, args=(unique_id, embed_link), daemon=True).start()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
      <title>Create TeraLink</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
         body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
         .container { max-width: 600px; margin: auto; background: #fff; padding: 20px; border-radius: 4px; }
         h1 { text-align: center; }
         label { display: block; margin-top: 10px; font-weight: bold; }
         input[type="text"], textarea {
            width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px;
         }
         button { width: 100%; padding: 10px; margin-top: 20px; background: #007BFF; color: #fff;
                  border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }
         button:hover { background: #0056b3; }
         .result { margin-top: 20px; padding: 10px; background: #e9ecef; border: 1px solid #ccc;
                   border-radius: 4px; text-align: center; }
         .result input[type="text"] { width: 100%; padding: 8px; font-size: 16px; text-align: center; }
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
            
            <label for="embed_link">
              Embed Link (enter a '/sharing/embed' URL, a short '/s/' URL, or a '/wap/share/' URL):
            </label>
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

@app.route('/s/<identifier>')
def play_link(identifier):
    # Try to retrieve the record from MongoDB.
    data = links_collection.find_one({"identifier": identifier})
    if not data:
        # Otherwise, assume the identifier is a short code.
        code = identifier.strip()
        if code and code[0].isdigit():
            code = code[1:]
        embed_link = (
            f"https://www.1024terabox.com/sharing/embed?surl={code}"
            "&resolution=1080&autoplay=true&mute=false&uk=4400105884193"
            "&fid=91483455887823&slid="
        )
        data = {
            'identifier': identifier,
            'embed_link': embed_link,
            'scraped_title': "Video",
            'preview_width': None,
            'preview_height': None,
            'user_title': "",
            'user_description': ""
        }
    aspect_ratio = compute_aspect_ratio(data)
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
      <title>{{ data.scraped_title|safe }}</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
         body { margin: 0; padding: 0; background: #000; color: #fff; font-family: Arial, sans-serif; }
         body.light-mode { background: #fff; color: #000; }
         .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 20px;
            border-bottom: 1px solid #555;
            background: inherit;
         }
         .header-bar .hoterror {
            font-family: 'Times New Roman', Georgia, serif;
            font-size: 28px;
            font-weight: bold;
            color: #800000;
         }
         .header-bar .mode-toggle { cursor: pointer; font-size: 24px; user-select: none; }
         .user-title { margin: 15px 20px; font-family: 'Times New Roman', Georgia, serif; font-size: 24px; text-align: left; }
         .video-container { width: 100%; position: relative; overflow: hidden; }
         .video-container::before { content: ""; display: block; padding-bottom: {{ aspect_ratio if aspect_ratio > 0 else 56.25 }}%; }
         .video-container iframe { position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0; object-fit: contain; }
         .description-container { margin: 15px 20px; }
         .description-toggle {
            cursor: pointer; font-size: 16px; color: #ccc; user-select: none;
            display: flex; align-items: center;
         }
         .description-toggle span.arrow {
            display: inline-block; transition: transform 0.3s ease; margin-right: 5px;
         }
         .description {
            max-height: 0; overflow: hidden; transition: max-height 0.3s ease;
            font-size: 16px; margin-top: 5px; color: #aaa;
         }
         .description.open { max-height: 300px; }
         body.light-mode .header-bar { border-bottom: 1px solid #ccc; }
         body.light-mode .description-toggle { color: #666; }
         body.light-mode .description { color: #444; }
      </style>
      <script>
         function toggleDescription() {
            var desc = document.getElementById("description");
            var arrow = document.getElementById("arrow");
            if (desc.classList.contains("open")) {
               desc.classList.remove("open");
               arrow.style.transform = "rotate(0deg)";
            } else {
               desc.classList.add("open");
               arrow.style.transform = "rotate(180deg)";
            }
         }
         function toggleMode() {
            document.body.classList.toggle('light-mode');
            var toggleBtn = document.getElementById("mode-toggle");
            if(document.body.classList.contains('light-mode')) {
               toggleBtn.innerHTML = "☀️";
            } else {
               toggleBtn.innerHTML = "🌙";
            }
         }
         window.onload = function() {
            var toggleBtn = document.getElementById("mode-toggle");
            if(document.body.classList.contains('light-mode')) {
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
            <!-- The sandbox attribute prevents the embedded content from redirecting the parent page -->
            <iframe src="{{ data.embed_link }}" allowfullscreen scrolling="no"
                    sandbox="allow-same-origin allow-scripts"></iframe>
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
    return render_template_string(html, data=data, aspect_ratio=aspect_ratio)

# Also support direct visits via /wap/share/<identifier>
@app.route('/wap/share/<identifier>')
def wap_share(identifier):
    # Reuse the same logic as for /s/<identifier>
    return play_link(identifier)

if __name__ == '__main__':
    # Run the app on port 8080 and listen on all interfaces.
    app.run(host="0.0.0.0", debug=True, use_reloader=False, port=8080)
