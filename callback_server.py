#!/usr/bin/env python3
"""
OAuth callback server for Dashtam.
Listens on https://127.0.0.1:8182 and forwards auth codes to the main API.

This server handles the OAuth redirect from providers (like Schwab) and 
forwards the authorization code along with the state parameter (provider_id)
to the main FastAPI application.
"""
import ssl
import requests
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib3
import os

# Disable SSL warnings for internal container communication
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CALLBACK_HOST = os.getenv("CALLBACK_HOST", "0.0.0.0")  # Listen on all interfaces for Docker
CALLBACK_PORT = int(os.getenv("CALLBACK_PORT", "8182"))
# Main API callback endpoint - note we use a generic endpoint now
FASTAPI_URL = os.getenv("FASTAPI_CALLBACK_URL", "https://app:8000/api/v1/auth/callback")


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callbacks and forward to FastAPI."""
    
    def do_GET(self):
        """Handle GET request with auth code and state."""
        # Parse the query parameters
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        # Extract parameters
        code = params.get('code', [None])[0]
        state = params.get('state', [None])[0]  # This is our provider_id
        error = params.get('error', [None])[0]
        error_description = params.get('error_description', [None])[0]
        
        if error:
            # OAuth error from provider
            self._send_error_response(
                f"Authorization failed: {error}",
                error_description or "The provider denied authorization"
            )
            return
        
        if not code:
            # No authorization code
            self._send_error_response(
                "No authorization code received",
                "The OAuth provider did not send an authorization code"
            )
            return
        
        if not state:
            # No state parameter (provider_id)
            self._send_error_response(
                "Missing state parameter",
                "Cannot identify which provider connection this is for. Please try again."
            )
            return
        
        # Forward to FastAPI with provider_id
        try:
            # Build the callback URL with provider_id in path
            callback_url = f"{FASTAPI_URL.replace('/callback', '')}/{state}/callback"
            
            # Forward all parameters
            forward_params = {
                'code': code,
                'state': state
            }
            
            # Make request to FastAPI
            response = requests.get(
                callback_url,
                params=forward_params,
                verify=False  # Disable SSL verification for internal communication
            )
            
            if response.status_code == 200:
                # Success!
                result = response.json()
                self._send_success_response(
                    provider_alias=result.get('alias', 'Provider'),
                    provider_id=state,
                    code_preview=code[:20] if len(code) > 20 else code,
                    api_response=result
                )
            else:
                # Error from FastAPI
                try:
                    error_detail = response.json().get('detail', response.text)
                except:
                    error_detail = response.text
                
                self._send_error_response(
                    f"API Error ({response.status_code})",
                    error_detail
                )
                
        except requests.exceptions.ConnectionError:
            self._send_error_response(
                "Connection Error",
                f"Could not connect to the Dashtam API at {callback_url}. "
                "Make sure the backend is running."
            )
        except Exception as e:
            self._send_error_response(
                "Unexpected Error",
                f"An unexpected error occurred: {str(e)}"
            )
    
    def _send_success_response(self, provider_alias, provider_id, code_preview, api_response):
        """Send a success HTML response."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        success_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authorization Successful - Dashtam</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 48px;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.15);
                    max-width: 520px;
                    width: 90%;
                    animation: slideUp 0.5s ease-out;
                }}
                @keyframes slideUp {{
                    from {{ opacity: 0; transform: translateY(30px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
                .success-icon {{
                    color: #10b981;
                    font-size: 64px;
                    margin-bottom: 24px;
                    animation: bounce 1s ease-out;
                }}
                @keyframes bounce {{
                    0%, 100% {{ transform: translateY(0); }}
                    50% {{ transform: translateY(-10px); }}
                }}
                h1 {{
                    color: #1f2937;
                    margin-bottom: 16px;
                    font-size: 28px;
                }}
                .provider-name {{
                    color: #6366f1;
                    font-weight: 600;
                }}
                .message {{
                    color: #6b7280;
                    margin-bottom: 24px;
                    line-height: 1.6;
                }}
                .details {{
                    background: #f9fafb;
                    padding: 16px;
                    border-radius: 8px;
                    margin-bottom: 24px;
                    border-left: 4px solid #6366f1;
                }}
                .detail-row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 8px;
                    font-size: 14px;
                }}
                .detail-row:last-child {{ margin-bottom: 0; }}
                .detail-label {{
                    color: #6b7280;
                    font-weight: 500;
                }}
                .detail-value {{
                    color: #1f2937;
                    font-family: 'Courier New', monospace;
                    font-size: 13px;
                }}
                .close-message {{
                    text-align: center;
                    padding-top: 16px;
                    border-top: 1px solid #e5e7eb;
                    color: #6b7280;
                    font-size: 14px;
                }}
                .close-message strong {{
                    color: #1f2937;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div style="text-align: center;">
                    <div class="success-icon">✨</div>
                    <h1>Successfully Connected!</h1>
                </div>
                <p class="message">
                    Your <span class="provider-name">{provider_alias}</span> account 
                    has been successfully connected to Dashtam.
                </p>
                <div class="details">
                    <div class="detail-row">
                        <span class="detail-label">Provider:</span>
                        <span class="detail-value">{provider_alias}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Connection ID:</span>
                        <span class="detail-value">{provider_id[:8]}...</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Status:</span>
                        <span class="detail-value" style="color: #10b981;">✓ Active</span>
                    </div>
                </div>
                <div class="close-message">
                    <strong>You can now close this window</strong><br>
                    and return to your terminal or application.
                </div>
            </div>
        </body>
        </html>
        """
        self.wfile.write(success_html.encode())
    
    def _send_error_response(self, error_title, error_detail):
        """Send an error HTML response."""
        self.send_response(400)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authorization Failed - Dashtam</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                }}
                .container {{
                    background: white;
                    padding: 48px;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.15);
                    max-width: 520px;
                    width: 90%;
                }}
                .error-icon {{
                    color: #ef4444;
                    font-size: 64px;
                    margin-bottom: 24px;
                }}
                h1 {{
                    color: #1f2937;
                    margin-bottom: 16px;
                    font-size: 28px;
                }}
                .error-detail {{
                    background: #fef2f2;
                    color: #991b1b;
                    padding: 16px;
                    border-radius: 8px;
                    margin: 24px 0;
                    border-left: 4px solid #ef4444;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .action {{
                    text-align: center;
                    padding-top: 16px;
                    border-top: 1px solid #e5e7eb;
                    color: #6b7280;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div style="text-align: center;">
                    <div class="error-icon">⚠️</div>
                    <h1>{error_title}</h1>
                </div>
                <div class="error-detail">
                    {error_detail}
                </div>
                <div class="action">
                    Please close this window and try again,<br>
                    or contact support if the problem persists.
                </div>
            </div>
        </body>
        </html>
        """
        self.wfile.write(error_html.encode())
    
    def log_message(self, format, *args):
        """Override to customize logging."""
        print(f"[Callback Server] {format % args}")


def get_ssl_certificates():
    """Get SSL certificate paths."""
    # Check for certificates in certs directory first
    cert_file = "certs/callback_cert.pem"
    key_file = "certs/callback_key.pem"
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("✅ Using SSL certificates from certs/")
        return cert_file, key_file
    
    # Fallback to current directory (for Docker)
    cert_file = "callback_cert.pem"
    key_file = "callback_key.pem"
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("✅ Using SSL certificates from current directory")
        return cert_file, key_file
    
    print("❌ SSL certificates not found!")
    print("   Run: make generate-certs to create them")
    raise FileNotFoundError("SSL certificates not found")


def run_callback_server():
    """Run the HTTPS callback server."""
    print("\n" + "="*60)
    print("🚀 Dashtam OAuth Callback Server")
    print("="*60)
    print(f"📡 Listening on: https://{CALLBACK_HOST}:{CALLBACK_PORT}")
    print(f"🔄 Forwarding to: {FASTAPI_URL}")
    print("\n⚠️  Note: Your browser will show a security warning about")
    print("    the self-signed certificate. This is expected.")
    print("    Click 'Advanced' and 'Proceed to 127.0.0.1 (unsafe)'\n")
    
    # Get SSL certificates
    cert_file, key_file = get_ssl_certificates()
    
    # Create and configure the server
    httpd = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), CallbackHandler)
    
    # Wrap with SSL
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    print("✅ Server ready and waiting for OAuth callbacks...")
    print("\nPress Ctrl+C to stop the server\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down callback server...")
        httpd.shutdown()
        print("✅ Server stopped")


if __name__ == "__main__":
    run_callback_server()