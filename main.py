from flask import Flask, request, redirect, render_template_string
import uuid

app = Flask(__name__)

# In-memory dictionary to store unique code -> URL mapping.
url_mapping = {}

# HTML template (using render_template_string for a single file script)
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>URL Shortener</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 50px; }
        input[type="text"] { padding: 8px; width: 300px; }
        button { padding: 8px 12px; }
        .result { margin-top: 20px; }
    </style>
    <script>
        // Copies the content of the input field to clipboard
        function copyLink() {
            var copyText = document.getElementById("uniqueLink");
            navigator.clipboard.writeText(copyText.value);
        }
    </script>
</head>
<body>
    <h1>URL Shortener</h1>
    <form method="post" action="/">
        <input type="text" name="url" placeholder="Enter URL" required>
        <button type="submit">Generate</button>
    </form>
    {% if unique_url %}
    <div class="result">
        <p>Your unique link:</p>
        <input type="text" id="uniqueLink" value="{{ unique_url }}" readonly>
        <button onclick="copyLink()">Copy</button>
    </div>
    {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    unique_url = None
    if request.method == "POST":
        original_url = request.form.get("url")
        if original_url:
            # Generate a unique code (first 6 characters of a UUID)
            unique_code = uuid.uuid4().hex[:6]
            url_mapping[unique_code] = original_url
            # Build the unique URL (Flask's request.url_root ends with a slash)
            unique_url = request.url_root + unique_code
    return render_template_string(TEMPLATE, unique_url=unique_url)

@app.route("/<unique_code>")
def redirect_to_url(unique_code):
    # Redirect to the original URL if the unique code exists.
    if unique_code in url_mapping:
        return redirect(url_mapping[unique_code])
    return "Invalid or expired URL.", 404

if __name__ == "__main__":
    app.run(debug=True)
    
