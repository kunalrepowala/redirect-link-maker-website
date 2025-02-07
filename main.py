from flask import Flask, request, render_template_string
import uuid
import os

app = Flask(__name__)

# In-memory dictionary to store unique code -> URL mapping.
url_mapping = {}

# Template for the main page where the user generates the unique link.
MAIN_TEMPLATE = """
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
        // Copies the content of the input field to the clipboard
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

# Template for the redirect page that shows a button
REDIRECT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Redirect Page</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 50px; }
      button { padding: 8px 12px; }
    </style>
    <script>
       function redirectUser() {
         // Redirect the user to the target URL
         window.location.href = "{{ target_url }}";
       }
    </script>
</head>
<body>
  <h1>Ready to Redirect?</h1>
  <p>Click the button below to continue to your destination.</p>
  <button onclick="redirectUser()">Redirect</button>
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
            # Build the unique URL using request.url_root which reflects the deployed domain on Koyeb
            unique_url = request.url_root.rstrip("/") + "/" + unique_code
    return render_template_string(MAIN_TEMPLATE, unique_url=unique_url)

@app.route("/<unique_code>")
def show_redirect(unique_code):
    # Instead of automatically redirecting, show a page with a "Redirect" button.
    if unique_code in url_mapping:
        target_url = url_mapping[unique_code]
        return render_template_string(REDIRECT_TEMPLATE, target_url=target_url)
    return "Invalid or expired URL.", 404

if __name__ == "__main__":
    # Use the PORT environment variable provided by Koyeb (default to 5000 if not set)
    port = int(os.environ.get("PORT", 5000))
    # Bind to 0.0.0.0 so the app is accessible externally
    app.run(debug=True, host="0.0.0.0", port=port)
