cleanup() {
    echo "Stopping servers..."
    kill $RECEIVE_PID $CALLCENTER_PID 2>/dev/null
    wait
}
trap cleanup EXIT INT TERM

uv run ./receive_server.py &
RECEIVE_PID=$!
uv run call_center.py &
CALLCENTER_PID=$!

echo "receive_server.py PID: $RECEIVE_PID"
echo "call_center.py PID: $CALLCENTER_PID"
echo "All servers started"

wait