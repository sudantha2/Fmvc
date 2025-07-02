from flask import Flask
from threading import Thread
import time
import logging

# Create Flask app
app = Flask(__name__)

# Suppress Flask logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>FM Player Bot</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                padding: 50px;
                margin: 0;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: rgba(255,255,255,0.1);
                padding: 30px;
                border-radius: 15px;
                backdrop-filter: blur(10px);
            }
            h1 {
                font-size: 2.5em;
                margin-bottom: 20px;
            }
            .status {
                font-size: 1.2em;
                margin: 20px 0;
            }
            .features {
                text-align: left;
                margin: 30px 0;
            }
            .features li {
                margin: 10px 0;
                padding: 5px 0;
            }
            .footer {
                margin-top: 30px;
                font-size: 0.9em;
                opacity: 0.8;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 FM Player Bot</h1>
            <div class="status">
                <span style="color: #4CAF50;">● ONLINE</span>
            </div>
            <p>Your Telegram FM Player Bot is running successfully!</p>
            
            <div class="features">
                <h3>Features:</h3>
                <ul>
                    <li>🎵 Play FM streams in Telegram voice chats</li>
                    <li>📻 Add and manage FM stations</li>
                    <li>🎛️ Control playback with simple commands</li>
                    <li>📊 MongoDB database integration</li>
                    <li>🤖 Userbot for voice chat functionality</li>
                </ul>
            </div>
            
            <div class="features">
                <h3>Commands:</h3>
                <ul>
                    <li><code>/playfm &lt;fm_name&gt;</code> - Play FM in voice chat</li>
                    <li><code>/stopfm</code> - Stop current FM</li>
                    <li><code>/listfm</code> - List available FMs</li>
                    <li><code>/currentfm</code> - Show current playing FM</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>Bot Status: Active | Server Time: <span id="time"></span></p>
            </div>
        </div>
        
        <script>
            function updateTime() {
                document.getElementById('time').textContent = new Date().toLocaleString();
            }
            updateTime();
            setInterval(updateTime, 1000);
        </script>
    </body>
    </html>
    '''

@app.route('/status')
def status():
    return {
        'status': 'online',
        'timestamp': time.time(),
        'message': 'FM Player Bot is running'
    }

@app.route('/health')
def health():
    return {'status': 'healthy', 'service': 'fm-player-bot'}

def run():
    """Run the Flask app"""
    try:
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Keep-alive server error: {e}")

def keep_alive():
    """Start the keep-alive server in a separate thread"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print("Keep-alive server started on port 8080")
    return 
