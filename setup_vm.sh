#!/bin/bash
# Скрипт установки зависимостей для Twitch Cutter на Ubuntu/Debian
# Запуск: sudo ./setup_vm.sh

set -e

echo "=== Twitch Cutter: установка зависимостей ==="

# Проверка root/sudo
if [ "$(id -u)" -ne 0 ]; then
  echo "Запустите скрипт с sudo: sudo ./setup_vm.sh"
  exit 1
fi

# Определение дистрибутива
if [ -f /etc/os-release ]; then
  . /etc/os-release
  DISTRO="${ID:-unknown}"
else
  echo "Не удалось определить дистрибутив."
  exit 1
fi

echo "Обнаружен дистрибутив: $DISTRO"
echo ""

# 1. Обновление системы
echo ">>> Обновление пакетов..."
apt update && apt upgrade -y

# 2. Базовые пакеты
echo ">>> Установка базовых пакетов (curl, unzip, build-essential)..."
apt install -y curl unzip build-essential

# 3. Node.js 20 (NodeSource)
if ! command -v node &>/dev/null || [ "$(node -v | cut -d. -f1 | tr -d 'v')" -lt 20 ]; then
  echo ">>> Установка Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y nodejs
else
  echo ">>> Node.js уже установлен: $(node -v)"
fi

# 4. Yarn 3+ (corepack)
echo ">>> Включение Yarn через Corepack..."
corepack enable 2>/dev/null || true
corepack prepare yarn@stable --activate 2>/dev/null || true

# 5. Python 3.9+, pip, venv
echo ">>> Установка Python 3 и pip..."
apt install -y python3 python3-pip python3-venv

# 6. FFmpeg
echo ">>> Установка FFmpeg..."
apt install -y ffmpeg

# 7. MediaInfo
echo ">>> Установка MediaInfo..."
apt install -y mediainfo

# 8. Pip-пакеты (глобально для удобства; в продакшене лучше venv)
echo ">>> Установка pip-пакетов: streamlink, yt-dlp, vcsi..."
pip3 install --break-system-packages streamlink yt-dlp vcsi 2>/dev/null || \
  pip3 install --user streamlink yt-dlp vcsi

echo ""
echo "=== Установка завершена ==="
echo ""
echo "Проверка версий:"
node -v
npm -v
yarn -v 2>/dev/null || echo "yarn: проверьте вручную (corepack)"
python3 --version
pip3 --version
ffmpeg -version | head -1
mediainfo --version | head -1
streamlink --version 2>/dev/null || true
echo ""
echo "Что сделать вручную:"
echo "  1. Nginx + Let's Encrypt — см. SETUP_VM.md (раздел 9)"
echo "  2. TwitchDownloader (опционально) — см. SETUP_VM.md (раздел 7)"
echo "  3. Рекомендуется создать venv и установить зависимости:"
echo "     python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
echo ""
