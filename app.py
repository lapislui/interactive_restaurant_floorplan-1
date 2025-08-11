from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-your-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Server-side authoritative table state
# For each table id: { id: int, capacity: int, billed: bool, start: int|null }
tables = {}
recent_cleared = []  # list of strings e.g. "Table 3 (4 pac)"

# Initialize table layout consistent with client (skip 13 and 17 as before)
def init_tables():
    global tables
    if tables:
        return
    rows = [(1,8),(9,14),(15,22)]
    for r in rows:
        start, end = r
        for tid in range(start, end+1):
            if tid in (13,17):
                continue
            cap = 2
            if 9 <= tid <= 14:
                cap = 4
            elif 15 <= tid <= 19:
                cap = 8
            elif tid % 2 == 0:
                cap = 3
            tables[str(tid)] = {
                "id": tid,
                "capacity": cap,
                "billed": False,
                "start": None  # epoch ms when billing started
            }

init_tables()

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("connect")
def handle_connect():
    # send current state to the connecting client
    emit("init", {"tables": tables, "recentCleared": recent_cleared})

@socketio.on("start_table")
def handle_start(data):
    """
    data: { id: <number> }
    Server will set billed=true and record start timestamp
    Broadcast updated tables state to all clients
    """
    tid = str(data.get("id"))
    if tid in tables:
        tables[tid]["billed"] = True
        tables[tid]["start"] = int(time.time() * 1000)
        socketio.emit("tables_update", {"tables": {tid: tables[tid]}})
    else:
        emit("error", {"message": "invalid table id"})

@socketio.on("clear_table")
def handle_clear(data):
    """
    data: { id: <number> }
    Server clears billed flag and resets start. Adds to recent_cleared list.
    """
    tid = str(data.get("id"))
    if tid in tables:
        tables[tid]["billed"] = False
        tables[tid]["start"] = None
        recent_cleared.insert(0, f"Table {tid} ({tables[tid]['capacity']} pac)")
        # keep recent_cleared bounded to e.g. 10 entries
        if len(recent_cleared) > 10:
            recent_cleared.pop()
        socketio.emit("tables_update", {"tables": {tid: tables[tid]}, "recentCleared": recent_cleared})
    else:
        emit("error", {"message": "invalid table id"})

@socketio.on("reset_all")
def handle_reset():
    for tid in tables:
        tables[tid]["billed"] = False
        tables[tid]["start"] = None
    recent_cleared.clear()
    socketio.emit("full_reset", {"tables": tables, "recentCleared": recent_cleared})

if __name__ == "__main__":
    # Use eventlet for WebSocket concurrency
    socketio.run(app, host="0.0.0.0", port=5000)
