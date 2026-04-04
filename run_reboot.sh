killall openclaw 2>/dev/null
nohup /home/naithick/.nvm/versions/node/v22.16.0/bin/openclaw gateway run --force > gateway.log 2>&1 &
echo "Booting gateway..."
sleep 5
venv/bin/python scripts/demo_blocked_trade.py > out3.txt 2>&1
