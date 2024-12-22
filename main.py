from flask import Flask, render_template_string, request, redirect
import random
import string
import os

app = Flask(__name__)

# In-memory "database" to store generated links and their mappings
link_database = {}

# Function to generate a unique identifier (8 random characters)
def generate_unique_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

# Route to handle the main form
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        message = request.form.get('message', '')
        
        if username:
            # Generate a unique code for the shortened link
            unique_code = generate_unique_code()
            
            # Create the tg://resolve link
            if message:
                generated_link = f"tg://resolve?domain={username}&text={message}"
            else:
                generated_link = f"tg://resolve?domain={username}"

            # Save this in the link database with the unique code
            link_database[unique_code] = generated_link

            # Use Koyeb URL instead of localhost for the shortened link
            base_url = request.host_url  # Dynamic Koyeb URL
            short_link = f"{base_url}{unique_code}"

            return render_template_string(TEMPLATE, short_link=short_link)

    return render_template_string(TEMPLATE, short_link=None)

# Route to handle the shortened URL redirection
@app.route('/<unique_code>')
def redirect_to_telegram(unique_code):
    # Check if the unique code exists in the database
    if unique_code in link_database:
        # Get the corresponding tg://resolve link
        generated_link = link_database[unique_code]
        return redirect(generated_link)
    else:
        # If the link is not found, show an error
        return "Link not found!", 404

# Template with HTML form and link display
TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Link Generator</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500&display=swap" rel="stylesheet">
    <script>
        function copyToClipboard() {
            var copyText = document.getElementById("shortLink");
            var range = document.createRange();
            range.selectNode(copyText);
            window.getSelection().removeAllRanges(); // clear current selection
            window.getSelection().addRange(range); // select the text
            document.execCommand("copy");

            // Animate the copy button to show feedback
            var copyBtn = document.getElementById("copyBtn");
            copyBtn.innerHTML = "✔ Copied!";
            copyBtn.classList.add("copied");
            
            // Reset the copy button after animation
            setTimeout(function() {
                copyBtn.innerHTML = "Copy Link";
                copyBtn.classList.remove("copied");
            }, 1000);
        }
    </script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Poppins', sans-serif;
            background-color: #f4f7fc;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .container {
            background-color: #fff;
            padding: 40px;
            width: 100%;
            max-width: 500px;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
            border-radius: 12px;
            animation: slideIn 1s ease-out;
        }
        h1 {
            text-align: center;
            font-size: 2rem;
            margin-bottom: 10px;
            color: #333;
        }
        .description {
            text-align: center;
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 20px;
        }
        input[type="text"], input[type="submit"] {
            width: 100%;
            padding: 14px;
            margin: 12px 0;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1rem;
            outline: none;
            transition: 0.3s ease;
        }
        input[type="text"]:focus, input[type="submit"]:hover {
            border-color: #007bff;
            transform: translateY(-3px);
        }
        input[type="submit"] {
            background-color: #007bff;
            color: #fff;
            cursor: pointer;
            font-weight: 600;
            border: none;
            transition: background-color 0.3s ease;
        }
        input[type="submit"]:hover {
            background-color: #0056b3;
        }
        .result {
            text-align: center;
            margin-top: 20px;
        }
        .result a {
            color: #007bff;
            text-decoration: none;
            font-weight: bold;
            cursor: pointer;
        }
        .result a:hover {
            text-decoration: underline;
        }
        .animated-box {
            animation: fadeIn 1s ease-in-out;
        }
        @keyframes slideIn {
            0% {
                transform: translateY(50px);
                opacity: 0;
            }
            100% {
                transform: translateY(0);
                opacity: 1;
            }
        }
        @keyframes fadeIn {
            0% {
                opacity: 0;
            }
            100% {
                opacity: 1;
            }
        }
        #copyBtn {
            padding: 10px 20px;
            background-color: #007bff;
            color: #fff;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            margin-top: 10px;
            transition: background-color 0.3s ease;
        }
        #copyBtn:hover {
            background-color: #0056b3;
        }
        .copied {
            background-color: #28a745;
            color: white;
        }
    </style>
</head>
<body>

    <div class="container animated-box">
        <h1>Telegram Link Generator</h1>
        <div class="description">
            <p>Create a custom link with message.</p>
        </div>
        <form method="POST">
            <input type="text" id="username" name="username" placeholder="Enter Username" required>
            <input type="text" id="message" name="message" placeholder="Enter Message (optional)">
            <input type="submit" value="Generate Link 🔗">
        </form>

        {% if short_link %}
        <div class="result animated-box">
            <h3>Your Generated Shortened Link:</h3>
            <a id="shortLink" href="{{ short_link }}" target="_blank">{{ short_link }}</a>
            <button id="copyBtn" onclick="copyToClipboard()">Copy Link</button>
        </div>
        {% endif %}
    </div>

</body>
</html>
'''

if __name__ == '__main__':
    # Koyeb assigns the PORT variable dynamically
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
