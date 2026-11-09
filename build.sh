#!/usr/bin/env bash
pip install -r requirements.txt

# Vá lỗi zlapi để lấy được QR
ZLAPI_PATH=$(python -c "import zlapi, os; print(os.path.dirname(zlapi.__file__))")
STATE_FILE="$ZLAPI_PATH/_state.py"

# Sửa endpoint login để lấy secret_key
sed -i 's|cls._get("https://wpa.chat.zalo.me/api/login/getLoginInfo", params=params)|cls._get("https://wpa.chat.zalo.me/api/login/getLoginInfo", params=params)|g' "$STATE_FILE"
sed -i 's|data\["data"\]\["secret_key"\] = data\["data"\]\["zpw_enk"\]|data["data"]["secret_key"] = data["data"]["zpw_enk"]|g' "$STATE_FILE"
