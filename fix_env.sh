killall openclaw 2>/dev/null
sleep 2
nohup /home/naithick/.nvm/versions/node/v22.16.0/bin/openclaw gateway run --force > gateway.log 2>&1 &
echo "Booted."
