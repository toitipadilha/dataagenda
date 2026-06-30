#!/bin/bash
# ─────────────────────────────────────────
# DEPLOY DentaAgenda — AWS Lightsail
# Rode como: bash deploy.sh
# ─────────────────────────────────────────

set -e

APP_DIR="/home/ubuntu/dentaagenda"
PORTA=5003
VENV="$APP_DIR/venv"
SERVICE="dentaagenda"

echo "=== [1/7] Atualizando pacotes ==="
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-venv postgresql postgresql-contrib nginx

echo "=== [2/7] Criando banco PostgreSQL ==="
sudo -u postgres psql -c "CREATE USER dentauser WITH PASSWORD 'TROQUE_AQUI';" 2>/dev/null || echo "usuário já existe"
sudo -u postgres psql -c "CREATE DATABASE dentaagenda OWNER dentauser;" 2>/dev/null || echo "banco já existe"

echo "=== [3/7] Copiando arquivos ==="
sudo mkdir -p $APP_DIR
sudo cp -r . $APP_DIR/
sudo chown -R ubuntu:ubuntu $APP_DIR

echo "=== [4/7] Criando virtualenv e instalando dependências ==="
cd $APP_DIR
python3 -m venv venv
$VENV/bin/pip install --quiet -r requirements.txt

echo "=== [5/7] Criando .env ==="
if [ ! -f $APP_DIR/.env ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > $APP_DIR/.env <<EOF
SECRET_KEY=$SECRET
DATABASE_URL=postgresql://dentauser:TROQUE_AQUI@localhost/dentaagenda
EOF
  echo ".env criado — edite a senha do banco em $APP_DIR/.env"
fi

echo "=== [6/7] Criando serviço systemd ==="
sudo tee /etc/systemd/system/$SERVICE.service > /dev/null <<EOF
[Unit]
Description=DentaAgenda Flask
After=network.target postgresql.service

[Service]
User=ubuntu
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV/bin/gunicorn --workers 1 --threads 2 --bind 0.0.0.0:$PORTA app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE
sudo systemctl restart $SERVICE

echo "=== [7/7] Configurando Nginx ==="
# Defina seu domínio ou IP abaixo
DOMAIN="${DOMAIN:-_}"

sudo tee /etc/nginx/sites-available/$SERVICE > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$PORTA;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        client_max_body_size 5M;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/$SERVICE /etc/nginx/sites-enabled/$SERVICE
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "========================================"
echo " DentaAgenda rodando na porta $PORTA"
echo " Acesse: http://SEU_IP/setup"
echo " (para criar a primeira clínica e usuário)"
echo "========================================"
