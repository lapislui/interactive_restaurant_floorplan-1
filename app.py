from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

# Initialize tables (skipping 13 and 17)
tables = {str(i): {'id': i, 'capacity': 4, 'billed': False, 'start': None}
          for i in list(range(1, 23)) if i not in (13, 17)}

recentCleared = []

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    emit('init', {'tables': tables, 'recentCleared': recentCleared})

@socketio.on('start_table')
def handle_start_table(data):
    tid = str(data.get('id'))
    if tid in tables:
        tables[tid]['billed'] = True
        tables[tid]['start'] = int(time.time() * 1000)
        socketio.emit('tables_update', {
            'tables': tables,
            'recentCleared': recentCleared
        }, broadcast=True)

@socketio.on('clear_table')
def handle_clear_table(data):
    tid = str(data.get('id'))
    if tid in tables:
        tables[tid]['billed'] = False
        tables[tid]['start'] = None
        label = f"Table {tables[tid]['id']} cleared"
        recentCleared.insert(0, label)
        if len(recentCleared) > 10:
            recentCleared.pop()
        socketio.emit('tables_update', {
            'tables': tables,
            'recentCleared': recentCleared
        }, broadcast=True)

@socketio.on('reset_all')
def handle_reset_all():
    for t in tables.values():
        t['billed'] = False
        t['start'] = None
    recentCleared.clear()
    socketio.emit('full_reset', {
        'tables': tables,
        'recentCleared': recentCleared
    }, broadcast=True)

@socketio.on('remove_cleared_item')
def handle_remove_cleared_item(item):
    if item in recentCleared:
        recentCleared.remove(item)
        socketio.emit('tables_update', {
            'tables': tables,
            'recentCleared': recentCleared
        }, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
