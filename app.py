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
# Update the table structure in init_tables() function
def init_tables():
    global tables
    if tables:
        return
    rows = [(1,8),(9,14),(15,22)]
    for r in rows:
        start, end = r
        for tid in range(start, end+1):
            if tid in (13,17):  # Skip these table numbers
                continue
                
            # Default capacity
            cap = 4  # Default for table 20-22
            
            # Special capacity assignments
            if tid == 1:
                cap = 4
            elif tid in (2,3,4,5):
                cap = 6
            elif tid == 6:
                cap = 2
            elif tid == 7:
                cap = 6
            elif tid == 8:
                cap = 8
            elif tid in (9,10,11,12,14):
                cap = 4
            elif tid in (15,16,18,19):
                cap = 6
                
            tables[str(tid)] = {
                "id": tid,
                "capacity": cap,
                "billed": False,
                "cleared": False,
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
    Also removes table from recently cleared list if present
    """
    tid = str(data.get("id"))
    if tid in tables:
        tables[tid]["billed"] = True
        tables[tid]["cleared"] = False
        tables[tid]["start"] = int(time.time() * 1000)
        
        # Remove from recently cleared list if present
        for entry in recent_cleared[:]:
            if f"Table {tid}" in entry or f"Table 0{tid}" in entry:
                recent_cleared.remove(entry)
                break
                
        socketio.emit("tables_update", {"tables": {tid: tables[tid]}, "recentCleared": recent_cleared})
    else:
        emit("error", {"message": "invalid table id"})

@socketio.on("bill_table")
def handle_bill(data):
    """
    data: { id: <number>, tableIdentifier: <string> }
    Server changes state from billed to cleared (red to green)
    Also resets the timer to start counting from zero
    """
    tid = str(data.get("id"))
    if tid in tables:
        tables[tid]["billed"] = False
        tables[tid]["cleared"] = True
        # Reset the timer to start counting from zero
        tables[tid]["start"] = int(time.time() * 1000)
        socketio.emit("tables_update", {"tables": {tid: tables[tid]}})
    else:
        emit("error", {"message": "invalid table id"})

# Update the clear_table handler to reset both states
@socketio.on("clear_table")
def handle_clear(data):
    """
    data: { id: <number>, tableIdentifier: <string> }
    Server clears all flags and resets start. Adds to recent_cleared list.
    """
    tid = str(data.get("id"))
    if tid in tables:
        tables[tid]["billed"] = False
        tables[tid]["cleared"] = False
        tables[tid]["start"] = None
        recent_cleared.insert(0, data.get("tableIdentifier", f"Table {tid} ({tables[tid]['capacity']} pac)"))
        # keep recent_cleared bounded to e.g. 10 entries
        if len(recent_cleared) > 10:
            recent_cleared.pop()
        socketio.emit("tables_update", {"tables": {tid: tables[tid]}, "recentCleared": recent_cleared})
    else:
        emit("error", {"message": "invalid table id"})

# Update reset_all to clear both states
@socketio.on("reset_all")
def handle_reset():
    for tid in tables:
        tables[tid]["billed"] = False
        tables[tid]["cleared"] = False
        tables[tid]["start"] = None
    recent_cleared.clear()
    socketio.emit("full_reset", {"tables": tables, "recentCleared": recent_cleared})

@socketio.on("remove_from_cleared")
def handle_remove_cleared(data):
    """
    Remove table from recently cleared list and notify all clients
    """
    tid = str(data.get("id"))
    if tid in tables:
        # Find and remove from recent_cleared
        for entry in recent_cleared[:]:
            if f"Table {tid}" in entry:
                recent_cleared.remove(entry)
                break
        # Reset table state
        tables[tid]["billed"] = False
        tables[tid]["start"] = None
        # Notify ALL clients about both table and cleared list updates
        socketio.emit("tables_update", {
            "tables": {tid: tables[tid]}, 
            "recentCleared": recent_cleared
        })

# Add these constants near the top of the file
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# Add new authentication endpoint
@socketio.on("authenticate")
def handle_auth(data):
    username = data.get("username")
    password = data.get("password")
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        emit("auth_response", {"success": True})
    else:
        emit("auth_response", {"success": False, "message": "Invalid username or password"})

if __name__ == "__main__":
    # Use eventlet for WebSocket concurrency
    socketio.run(app, host="0.0.0.0", port=5000)
