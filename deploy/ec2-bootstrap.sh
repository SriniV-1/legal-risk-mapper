#!/usr/bin/env bash
# EC2 User Data bootstrap script for Legal Risk Mapper.
# Paste this verbatim into the "User data" field when launching an EC2 instance.
# Runs as root on first boot — installs Docker, clones the repo, starts the app.
set -euo pipefail

# ── 1. System update & Docker install ────────────────────────────────────────
yum update -y
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# ── 2. Clone repo ─────────────────────────────────────────────────────────────
# Replace with your fork URL if you've pushed to GitHub.
REPO_URL="https://github.com/SriniV-1/legal-risk-mapper.git"
APP_DIR="/home/ec2-user/legal-risk-mapper"

if [ ! -d "$APP_DIR" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi
chown -R ec2-user:ec2-user "$APP_DIR"

# ── 3. Write .env from EC2 Parameter Store values ─────────────────────────────
# These must be set in AWS Systems Manager → Parameter Store BEFORE launching.
# Names: /lrm/SUPABASE_URL, /lrm/SUPABASE_KEY, /lrm/ANTHROPIC_API_KEY
#        /lrm/LRM_EXTRACTION_MODEL, /lrm/LRM_API_KEY (optional)
#
# If you haven't set up Parameter Store yet, comment this block out and
# manually write /home/ec2-user/legal-risk-mapper/.env after SSH-ing in.

# Install AWS CLI v2 (included on Amazon Linux 2023, skip if already present)
if ! command -v aws &>/dev/null; then
  yum install -y awscli
fi

get_param() {
  aws ssm get-parameter --name "/lrm/$1" --with-decryption \
      --query "Parameter.Value" --output text 2>/dev/null || echo ""
}

SUPABASE_URL=$(get_param SUPABASE_URL)
SUPABASE_KEY=$(get_param SUPABASE_KEY)
ANTHROPIC_API_KEY=$(get_param ANTHROPIC_API_KEY)
LRM_EXTRACTION_MODEL=$(get_param LRM_EXTRACTION_MODEL)
LRM_API_KEY=$(get_param LRM_API_KEY)

cat > "$APP_DIR/.env" <<EOF
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_KEY=${SUPABASE_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
LRM_EXTRACTION_MODEL=${LRM_EXTRACTION_MODEL:-claude-haiku-4-5-20251001}
LRM_API_KEY=${LRM_API_KEY}
PORT=8000
EOF

chown ec2-user:ec2-user "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

# ── 4. Build & run Docker container ──────────────────────────────────────────
cd "$APP_DIR"
docker build -t legal-risk-mapper .

# Stop any previous container
docker rm -f lrm-backend 2>/dev/null || true

docker run -d \
  --name lrm-backend \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  legal-risk-mapper

# ── 5. Install & configure nginx as reverse proxy ────────────────────────────
yum install -y nginx

cat > /etc/nginx/conf.d/lrm.conf <<'NGINX'
server {
    listen 80;
    server_name _;

    # Backend API
    location /api/ {
        rewrite ^/api/(.*) /$1 break;
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # Direct FastAPI access at root (Swagger docs, health, all endpoints)
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
}
NGINX

systemctl start nginx
systemctl enable nginx

echo "=== Legal Risk Mapper deployed. Backend running on port 80 via nginx. ==="
