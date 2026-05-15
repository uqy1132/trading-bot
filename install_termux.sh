#!/data/data/com.termux/files/usr/bin/bash
# Install Trading Bot dependencies di Termux (Android)
# Jalankan: bash install_termux.sh

set -e
echo "=== Install dependencies untuk Termux ==="

# Step 1: Install heavy packages via pkg (pre-compiled, cepat)
echo "[1/3] Install numpy & pandas via pkg..."
pkg install -y python-numpy python-pandas

# Step 2: Install sisanya via pip (ringan, tidak perlu kompilasi)
echo "[2/3] Install paket lainnya via pip..."
pip install \
    fastapi \
    "uvicorn[standard]" \
    ccxt \
    ta \
    python-dotenv \
    groq \
    requests \
    schedule \
    pydantic \
    httpx \
    aiofiles \
    anthropic

echo "[3/3] Selesai!"
echo ""
echo "Langkah selanjutnya:"
echo "  1. Buat config/.env dengan API keys kamu"
echo "  2. cd frontend && npm install && npm run build"
echo "  3. termux-wake-lock && python api_server.py"
