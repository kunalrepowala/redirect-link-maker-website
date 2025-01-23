import os
from flask import Flask, request, render_template_string, redirect, url_for
import hashlib

app = Flask(__name__)

# In-memory storage for unique links (you can replace this with a database if needed)
link_storage = {}

# Function to generate a unique code from the provided URL
def generate_unique_code(url):
    return hashlib.md5(url.encode()).hexdigest()[:10]

# HTML templates (inline within Python script)
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terabox Link Generator</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
        }
        h1 {
            color: #333;
        }
        form {
            margin-bottom: 20px;
        }
        input {
            padding: 10px;
            width: 300px;
            margin-right: 10px;
        }
        button {
            padding: 10px;
        }
        .result {
            margin-top: 20px;
            background-color: #f1f1f1;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #ddd;
        }
        a {
            color: #007bff;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <h1>Paste your Terabox or Terashare link</h1>
    <form method="POST">
        <input type="text" name="link" placeholder="Paste your link here" required>
        <button type="submit">Generate Unique Link</button>
    </form>
    {% if unique_link %}
        <div class="result">
            <p>Your unique link is ready! You can access the video by clicking the link below:</p>
            <a href="{{ unique_link }}" target="_blank">{{ unique_link }}</a>
        </div>
    {% endif %}
</body>
</html>
"""

video_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Embedded Video</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #000;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            overflow: auto;  /* Allow scrolling for long videos */
        }
        iframe {
            width: 100vw;  /* Fullscreen width */
            height: 100vh;  /* Fullscreen height */
            border: none;
        }
    </style>
</head>
<body>
    <iframe id="video" src="{{ video_url }}&autoplay=1"></iframe>
</body>
</html>
"""

# Route for the main page where the user pastes the link
@app.route('/', methods=['GET', 'POST'])
def index():
    unique_link = None  # Default to None, will be updated if the link is generated
    if request.method == 'POST':
        user_link = request.form['link']
        
        # Validate if the link is from Terabox or Terashare
        if '1024terabox' in user_link or 'terasharelink' in user_link:
            # Generate a unique code for the link
            unique_code = generate_unique_code(user_link)
            
            # Save the mapping of the unique code to the original link
            link_storage[unique_code] = user_link
            
            # Generate the unique link for the user to visit
            unique_link = url_for('unique_link', code=unique_code, _external=True)
        else:
            return "Only 1024Terabox or Terashare links are accepted", 400
    
    return render_template_string(index_html, unique_link=unique_link)

# Route to handle the unique link and show the embedded video
@app.route('/<code>')
def unique_link(code):
    if code in link_storage:
        video_url = link_storage[code]
        return render_template_string(video_html, video_url=video_url)
    else:
        return "Link not found", 404

# Get the port and host from environment variables
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))  # Default to 8080 if no PORT is set
    app.run(host='0.0.0.0', port=port, debug=True)
