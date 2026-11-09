#!/usr/bin/env bash
# Cài đặt thư viện như bình thường
pip install -r requirements.txt

# Tìm đường dẫn đến file _state.py của thư viện zlapi và vá lỗi
ZLAPI_PATH=$(python -c "import zlapi, os; print(os.path.dirname(zlapi.__file__))")
STATE_FILE="$ZLAPI_PATH/_state.py"

# Sửa dòng 60 (endpoint) và dòng 66 (secret_key) theo bản vá của cộng đồng
sed -i 's|cls._get("https://wpa.chat.zalo.me/api/login/getLoginInfo", params=params)|cls._get("https://wpa.chat.zalo.me/api/login/getLoginInfo", params=params)|g' "$STATE_FILE"
sed -i 's|data\["data"\]\["secret_key"\] = data\["data"\]\["zpw_enk"\]|data["data"]["secret_key"] = data["data"]["zpw_enk"]|g' "$STATE_FILE"
