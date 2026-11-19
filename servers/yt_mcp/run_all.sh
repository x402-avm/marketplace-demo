#!/bin/bash
source venv/bin/activate
python runtime_server.py &
PID1=$!
python mcp_server_1.py &
PID2=$!
python mcp_server_2.py &
PID3=$!

echo "Waiting for servers to start..."
sleep 5

python test_client.py

echo "Killing servers..."
kill $PID1 $PID2 $PID3
