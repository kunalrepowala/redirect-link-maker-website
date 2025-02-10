import os
from flask import Flask, render_template_string, make_response

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Needed for sessions if you use them

# Optional heartbeat endpoint for connectivity testing.
@app.route('/heartbeat')
def heartbeat():
    return "OK", 200

# This route accepts URLs with or without extra segments after the code.
@app.route('/v/<code>/', defaults={'extra': None})
@app.route('/v/<code>/<path:extra>')
def video_embed(code, extra):
    # Build the Terabox embed URL using the provided code.
    embed_url = (
        f"https://www.1024terabox.com/sharing/embed?"
        f"surl={code}&resolution=1080&autoplay=true&mute=false"
        f"&uk=4400105884193&fid=91483455887823&slid="
    )
    
    # HTML content includes meta tags that tell the browser not to cache the page.
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>@HotEror Telegram</title>
       <!-- Content Security Policy to restrict resource loading -->
       <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-src https://www.1024terabox.com;">
       <!-- These meta tags tell the browser not to cache this page -->
       <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
       <meta http-equiv="Pragma" content="no-cache">
       <meta http-equiv="Expires" content="0">
       <style>
           html, body {{
               margin: 0;
               padding: 0;
               width: 100%;
               height: 100%;
               overflow: hidden;
           }}
           iframe {{
               border: none;
               width: 100%;
               height: 100%;
           }}
       </style>
    </head>
    <body>
       <!-- The sandboxed iframe loads the embedded video -->
       <iframe src="{embed_url}" sandbox="allow-scripts allow-same-origin" allow="autoplay; fullscreen"></iframe>
       
       <!-- Optionally, JavaScript can periodically test connectivity -->
       <script>
         setInterval(function() {{
             fetch('/heartbeat', {{ cache: 'no-cache' }})
               .then(function(response) {{
                   if (!response.ok) {{
                       console.error("Heartbeat failed.");
                   }}
               }})
               .catch(function(error) {{
                   console.error("Server unreachable.");
               }});
         }}, 5000);
       </script>
    </body>
    </html>
    """
    
    # Create the response and set headers to disable caching.
    response = make_response(render_template_string(html_content))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == '__main__':
    # Use the PORT environment variable if available, defaulting to 8080.
    port = int(os.environ.get("PORT", 8080))
    # Listen on all interfaces so Koyeb can access the application.
    app.run(host="0.0.0.0", debug=True, use_reloader=False, port=8080)
