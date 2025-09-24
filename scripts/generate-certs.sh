#!/bin/bash

echo "🔐 Checking SSL certificates for Dashtam HTTPS services..."

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="$PROJECT_ROOT/certs"

# Track if any certs were created
CERTS_CREATED=false

# Create certs directory if it doesn't exist
mkdir -p "$CERTS_DIR"

# Generate certificate for Main App (localhost:8000)
if [ ! -f "$CERTS_DIR/cert.pem" ] || [ ! -f "$CERTS_DIR/key.pem" ]; then
    echo "📜 Creating certificate for Main App (localhost:8000)..."
    openssl req -x509 -newkey rsa:4096 \
        -keyout "$CERTS_DIR/key.pem" -out "$CERTS_DIR/cert.pem" \
        -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Dashtam/CN=localhost" 2>/dev/null
    echo "✅ Main app certificate created"
    CERTS_CREATED=true
else
    echo "✅ Main app certificate already exists (skipping)"
fi

# Generate certificate for callback server (127.0.0.1:8182)
if [ ! -f "$CERTS_DIR/callback_cert.pem" ] || [ ! -f "$CERTS_DIR/callback_key.pem" ]; then
    echo "📜 Creating certificate for OAuth callback server (127.0.0.1:8182)..."
    openssl req -x509 -newkey rsa:4096 \
        -keyout "$CERTS_DIR/callback_key.pem" -out "$CERTS_DIR/callback_cert.pem" \
        -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Dashtam/CN=127.0.0.1" 2>/dev/null
    echo "✅ Callback server certificate created"
    CERTS_CREATED=true
else
    echo "✅ Callback server certificate already exists (skipping)"
fi

# Set appropriate permissions only if certs were created
if [ "$CERTS_CREATED" = true ]; then
    chmod 600 "$CERTS_DIR"/*.pem 2>/dev/null || true
fi

echo ""
if [ "$CERTS_CREATED" = true ]; then
    echo "🎉 SSL certificates generated in $CERTS_DIR"
    echo ""
    echo "Certificates created:"
    echo "  • Main App:      cert.pem & key.pem (for localhost:8000)"
    echo "  • Callback:      callback_cert.pem & callback_key.pem (for 127.0.0.1:8182)"
    echo ""
    echo "⚠️  Note: These are self-signed certificates."
    echo "    Your browser will show security warnings - this is normal."
    echo "    Just accept the certificates to proceed."
else
    echo "✨ All SSL certificates already exist. No changes made."
    echo ""
    echo "To regenerate certificates, first remove existing ones:"
    echo "  rm -f certs/*.pem"
    echo "  make certs"
fi
