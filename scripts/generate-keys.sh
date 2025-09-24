#!/bin/bash

echo "🔑 Checking application keys for Dashtam..."
echo ""

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"

# Function to generate a secure random key
generate_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(32))"
}

# Check if we should generate new keys
GENERATE_NEW=false
KEYS_NEEDED=false

# Check if .env exists
if [ -f "$ENV_FILE" ]; then
    echo "📄 Found existing .env file"
    
    # Check if keys exist and are not placeholder values
    CURRENT_SECRET_KEY=$(grep "^SECRET_KEY=" "$ENV_FILE" | cut -d'=' -f2-)
    CURRENT_ENCRYPTION_KEY=$(grep "^ENCRYPTION_KEY=" "$ENV_FILE" | cut -d'=' -f2-)
    
    if [ -z "$CURRENT_SECRET_KEY" ] || 
       [ "$CURRENT_SECRET_KEY" = "your-secret-key-change-in-production" ] || 
       [ "$CURRENT_SECRET_KEY" = "your-secret-key-will-be-generated-by-make-keys" ]; then
        echo "  ⚠️  SECRET_KEY needs to be generated"
        KEYS_NEEDED=true
    else
        echo "  ✅ SECRET_KEY already exists (length: ${#CURRENT_SECRET_KEY} chars)"
    fi
    
    if [ -z "$CURRENT_ENCRYPTION_KEY" ] || 
       [ "$CURRENT_ENCRYPTION_KEY" = "your-encryption-key-change-in-production" ] || 
       [ "$CURRENT_ENCRYPTION_KEY" = "your-encryption-key-will-be-generated-by-make-keys" ]; then
        echo "  ⚠️  ENCRYPTION_KEY needs to be generated"
        KEYS_NEEDED=true
    else
        echo "  ✅ ENCRYPTION_KEY already exists (length: ${#CURRENT_ENCRYPTION_KEY} chars)"
    fi
    
    if [ "$KEYS_NEEDED" = true ]; then
        echo ""
        echo "🔑 Generating new secure keys..."
        
        # Generate only the keys we need
        if [ -z "$CURRENT_SECRET_KEY" ] || 
           [ "$CURRENT_SECRET_KEY" = "your-secret-key-change-in-production" ] || 
           [ "$CURRENT_SECRET_KEY" = "your-secret-key-will-be-generated-by-make-keys" ]; then
            SECRET_KEY=$(generate_key)
            echo "  Generated SECRET_KEY: ${SECRET_KEY:0:20}..."
            if grep -q "^SECRET_KEY=" "$ENV_FILE"; then
                sed -i '' "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
            else
                echo "SECRET_KEY=$SECRET_KEY" >> "$ENV_FILE"
            fi
        fi
        
        if [ -z "$CURRENT_ENCRYPTION_KEY" ] || 
           [ "$CURRENT_ENCRYPTION_KEY" = "your-encryption-key-change-in-production" ] || 
           [ "$CURRENT_ENCRYPTION_KEY" = "your-encryption-key-will-be-generated-by-make-keys" ]; then
            ENCRYPTION_KEY=$(generate_key)
            echo "  Generated ENCRYPTION_KEY: ${ENCRYPTION_KEY:0:20}..."
            if grep -q "^ENCRYPTION_KEY=" "$ENV_FILE"; then
                sed -i '' "s/^ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$ENCRYPTION_KEY/" "$ENV_FILE"
            else
                echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> "$ENV_FILE"
            fi
        fi
        
        echo ""
        echo "✅ Keys have been set in .env file"
    fi
else
    echo "📝 Creating new .env file with secure keys..."
    
    # Generate new keys
    SECRET_KEY=$(generate_key)
    ENCRYPTION_KEY=$(generate_key)
    
    echo "  Generated SECRET_KEY: ${SECRET_KEY:0:20}..."
    echo "  Generated ENCRYPTION_KEY: ${ENCRYPTION_KEY:0:20}..."
    
    # Create .env from example if it exists, otherwise create from scratch
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        sed -i '' "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
        sed -i '' "s/^ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$ENCRYPTION_KEY/" "$ENV_FILE"
    else
        cat > "$ENV_FILE" << EOF
# Database Configuration
POSTGRES_DB=dashtam
POSTGRES_USER=dashtam_user
POSTGRES_PASSWORD=secure_password_change_me
POSTGRES_PORT=5432

# Redis Configuration  
REDIS_PORT=6379

# Application Configuration
APP_PORT=8000
SECRET_KEY=$SECRET_KEY
ENCRYPTION_KEY=$ENCRYPTION_KEY
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# API URLs
API_BASE_URL=https://localhost:8000
CALLBACK_BASE_URL=https://127.0.0.1:8182

# Schwab OAuth Configuration (add your actual values)
# SCHWAB_CLIENT_ID=your_client_id
# SCHWAB_CLIENT_SECRET=your_client_secret
# SCHWAB_REDIRECT_URI=https://127.0.0.1:8182
EOF
    fi
    
    echo "✅ .env file created with secure keys"
    KEYS_NEEDED=true
fi

if [ "$KEYS_NEEDED" = false ]; then
    echo ""
    echo "✨ All keys are already properly configured. No changes made."
    echo ""
    echo "To force regeneration of keys:"
    echo "  1. Edit .env and remove the key values (or set them to placeholder text)"
    echo "  2. Run: make keys"
    echo ""
    echo "⚠️  WARNING: Regenerating ENCRYPTION_KEY will make existing encrypted tokens unreadable!"
else
    echo ""
    echo "🔒 Security Notes:"
    echo "  • Keep your .env file private and never commit it to version control"
    echo "  • The SECRET_KEY is used for session management and JWT tokens"
    echo "  • The ENCRYPTION_KEY is used to encrypt OAuth tokens in the database"
    echo ""
    echo "⚠️  Important:"
    echo "  • These keys are now set and should not be changed unless necessary"
    echo "  • Changing ENCRYPTION_KEY will make existing encrypted tokens unreadable"
    echo "  • In production, store these keys in a secure secrets manager"
fi
