#!/usr/bin/env python3
"""
Spotify Refresh Token Generator

This script starts a local web server, opens your browser to authorize with Spotify,
and then exchanges the authorization code for a Refresh Token. It will then automatically
save the Refresh Token into your .env file.
"""

import os
import sys
import webbrowser
import urllib.parse
import base64
import httpx
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv, set_key

# Load credentials from .env
load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "user-modify-playback-state user-read-playback-state user-read-currently-playing"

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Error: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not found in .env")
    print("Please add them to your server/.env file before running this script.")
    sys.exit(1)

auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body style='font-family: sans-serif; text-align: center; margin-top: 50px; background: #121212; color: #fff;'>")
            self.wfile.write(b"<h2 style='color: #1DB954;'>Authorization Successful \xe2\x9c\x94</h2>")
            self.wfile.write(b"<p>You can close this tab and return to the terminal.</p>")
            self.wfile.write(b"</body></html>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization failed.")
            
    def log_message(self, format, *args):
        pass # Suppress logging

def get_tokens(code):
    """Exchange the auth code for access and refresh tokens."""
    print("🔄 Exchanging code for tokens...")
    
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    
    with httpx.Client() as client:
        response = client.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
        
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Failed to get tokens: {response.text}")
        return None

def main():
    print("🎵 Beetel Spotify Token Generator")
    print("===================================")
    
    # 1. Generate Auth URL
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI
    })
    
    print("\n🌐 Opening your browser to authorize with Spotify...")
    print("If it doesn't open automatically, click here:")
    print(auth_url)
    print("\n⏳ Waiting for authorization...")
    
    # 2. Start local server to catch callback
    server_address = ('127.0.0.1', 8888)
    httpd = HTTPServer(server_address, CallbackHandler)
    
    webbrowser.open(auth_url)
    
    # Wait for exactly one request
    while not auth_code:
        httpd.handle_request()
        
    print("✅ Authorization received!")
    
    # 3. Get the tokens
    tokens = get_tokens(auth_code)
    
    if tokens and "refresh_token" in tokens:
        refresh_token = tokens["refresh_token"]
        print("\n🎉 Success! Got your Refresh Token.")
        
        # 4. Save to .env
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        set_key(env_path, "SPOTIFY_REFRESH_TOKEN", refresh_token)
        
        print(f"\n💾 Saved SPOTIFY_REFRESH_TOKEN to your server/.env file.")
        print("You can now restart your Uvicorn server to apply it.")
    else:
        print("\n❌ Failed to obtain refresh token. Make sure your App has the correct Redirect URI set in the Spotify Dashboard:")
        print(f"-> {REDIRECT_URI}")

if __name__ == "__main__":
    main()
