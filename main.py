from flask import Flask, render_template_string
import os

app = Flask(__name__)

# HTML template with embedded CSS and JS
@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Animated Website</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f0f0f0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                flex-direction: column;
            }

            .container {
                text-align: center;
            }

            h1 {
                color: #3498db;
            }

            .animate-btn {
                padding: 10px 20px;
                margin-top: 20px;
                background-color: #3498db;
                color: white;
                border: none;
                cursor: pointer;
                border-radius: 5px;
            }

            .animate-btn:hover {
                background-color: #2980b9;
                animation: scaleUp 0.5s ease;
            }

            @keyframes scaleUp {
                0% {
                    transform: scale(1);
                }
                100% {
                    transform: scale(1.1);
                }
            }

            .box {
                width: 100px;
                height: 100px;
                background-color: #e74c3c;
                margin-top: 20px;
                display: none;
            }

            .animate {
                display: block;
                animation: moveBox 2s infinite alternate;
            }

            @keyframes moveBox {
                0% {
                    transform: translateX(0);
                }
                100% {
                    transform: translateX(300px);
                }
            }
        </style>
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                const btn = document.querySelector('.animate-btn');
                const box = document.querySelector('.box');

                btn.addEventListener('click', function() {
                    box.classList.toggle('animate');
                });
            });
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Welcome to My Animated Website!</h1>
            <p>This is a simple Flask web page with animations.</p>
            <button class="animate-btn">Click Me</button>
            <div class="box"></div>
        </div>
    </body>
    </html>
    """)

if __name__ == '__main__':
    # Get the port from the environment variable Koyeb sets (or default to 8080 if not set)
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
