# HƯỚNG DẪN PULL CODE MỚI VỀ VM

## Bước 1: Tìm thư mục project

```bash
# Tìm thư mục ForexBOT
find ~ -name "ForexBOT" -type d 2>/dev/null

# Hoặc tìm file main.py
find ~ -name "main.py" -path "*/ForexBOT/*" 2>/dev/null

# Liệt kê thư mục home
ls -la ~
```

## Bước 2: Sau khi tìm thấy thư mục (giả sử ~/ForexBOT)

```bash
# Di chuyển vào thư mục
cd ~/ForexBOT

# Kiểm tra git status
git status

# Pull code mới
git pull origin main

# Cài dependencies mới
pip install -r requirements.txt

# Restart bot
pkill -f "python main.py"
nohup python main.py > bot.log 2>&1 &

# Xem log
tail -f bot.log
```

## Lệnh nhanh (sau khi biết đường dẫn):

```bash
cd ~/ForexBOT && git pull origin main && pip install -r requirements.txt && pkill -f "python main.py" && nohup python main.py > bot.log 2>&1 & tail -f bot.log
```

## Check bot đang chạy:

```bash
ps aux | grep "python main.py"
```
