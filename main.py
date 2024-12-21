from flask import Flask, request, redirect, render_template_string
import random
import string
import os

app = Flask(__name__)

# In-memory database to store original URLs and their shortened versions
url_db = {}

# Generate a random 6-character string for short links
def generate_short_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

# HTML Template for the frontend with improved styling and interactivity
html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>URL Shortener</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background-color: #f0f2f5;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }

        .container {
            background-color: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 600px;
            text-align: center;
        }

        h1 {
            color: #333;
            font-size: 2em;
        }

        .url-form {
            margin-top: 30px;
        }

        .url-form input {
            padding: 10px;
            width: 80%;
            font-size: 16px;
            margin-right: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }

        .url-form button {
            padding: 10px 20px;
            background-color: #3498db;
            border: none;
            border-radius: 5px;
            color: white;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s ease;
        }

        .url-form button:hover {
            background-color: #2980b9;
        }

        .shortened-url {
            margin-top: 30px;
            background-color: #f7f7f7;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }

        .shortened-url a {
            text-decoration: none;
            color: #3498db;
            font-size: 18px;
        }

        .copy-btn {
            padding: 10px 20px;
            background-color: #2ecc71;
            border: none;
            border-radius: 5px;
            color: white;
            font-size: 14px;
            cursor: pointer;
            margin-top: 10px;
            transition: background-color 0.3s ease;
        }

        .copy-btn:hover {
            background-color: #27ae60;
        }

        .copy-btn:active {
            transform: scale(0.98);
        }

        .notification {
            margin-top: 10px;
            font-size: 14px;
            color: #27ae60;
            display: none;
        }

        .notification.show {
            display: block;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>URL Shortener</h1>
        <form class="url-form" action="/shorten" method="POST">
            <input type="url" name="originalUrl" id="url-input" placeholder="Enter a URL" required>
            <button type="submit">Shorten</button>
        </form>

        {% if short_url %}
        <div class="shortened-url" style="animation: fadeIn 1s;">
            <p>Your shortened URL is:</p>
            <a href="{{ short_url }}" target="_blank">{{ short_url }}</a>
            <button class="copy-btn" onclick="copyToClipboard()">Copy URL</button>
            <p class="notification" id="notification">Copied to clipboard!</p>
        </div>
        {% endif %}
    </div>

    <script>
        // Function to copy the shortened URL to the clipboard
        function copyToClipboard() {
            const urlText = document.querySelector('.shortened-url a').textContent;
            navigator.clipboard.writeText(urlText).then(function() {
                const notification = document.getElementById('notification');
                notification.classList.add('show');
                setTimeout(function() {
                    notification.classList.remove('show');
                }, 2000);
            });
        }
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(html_template, short_url=None)

@app.route('/shorten', methods=['POST'])
def shorten():
    original_url = request.form['originalUrl']
    
    # Check if URL is already in the database
    short_code = None
    for code, url in url_db.items():
        if url == original_url:
            short_code = code
            break
    
    if not short_code:
        # Generate a new short code
        short_code = generate_short_code()
        url_db[short_code] = original_url
    
    # Get the base URL dynamically from the request host (works on Koyeb or any cloud platform)
    base_url = request.host_url
    short_url = f'{base_url}{short_code}'

    # Display the shortened URL on the frontend
    return render_template_string(html_template, short_url=short_url)

@app.route('/<short_code>')
def redirect_url(short_code):
    original_url = url_db.get(short_code)
    
    if original_url:
        return redirect(original_url)
    else:
        return 'URL not found', 404

if __name__ == '__main__':
    # Koyeb will set the host and port automatically, so we don't need to specify them manually
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
