import random
from datetime import datetime, timedelta
import os
import json
import subprocess
from io import BytesIO
import base64

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import requests
import qrcode

from .data_reader import DataReader
from .parser import NYTFormatParser
from .database import db, init_db, CompletedPuzzle

# Get the directory containing this file
current_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
           template_folder=os.path.join(current_dir, 'templates'),
           static_folder=os.path.join(current_dir, 'static'))

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('CROSSWORD_DATABASE_URI', 'sqlite:///crossword.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)
init_db(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Game Session Store
game_sessions = {}

class GameSession:
    def __init__(self, room_id, puzzle_date):
        self.room_id = room_id
        self.puzzle_date = puzzle_date
        self.grid = {} # (row, col) -> value
        self.players = {
            'across': None, # socket_id
            'down': None    # socket_id
        }
    
    def update_cell(self, row, col, value):
        self.grid[(row, col)] = value
        
    def to_dict(self):
        return {
            'room_id': self.room_id,
            'puzzle_date': self.puzzle_date,
            'grid': {f"{r},{c}": v for (r, c), v in self.grid.items()},
            'players': self.players
        }

# Built React frontend (apps/react, built by `make run` / `make react-assets`).
REACT_DIST = os.path.join(current_dir, 'static', 'react')

def _react_index():
    """Serve React explicitly; a missing build must not silently select Vue."""
    if not os.path.exists(os.path.join(REACT_DIST, 'index.html')):
        return 'React build missing. Run make react-assets, then reload.', 503
    response = send_from_directory(REACT_DIST, 'index.html')
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/')
def index():
    """Daily crossword interface: the React port served by Flask."""
    return _react_index()

@app.route('/legacy')
@app.route('/legacy/')
def legacy_index():
    """Legacy Vue frontend: parity reference and fallback, not the default."""
    return render_template('newapp.html')

@app.route('/legacy/mobile/<room_id>/<role>')
def legacy_mobile_client(room_id, role):
    return render_template('mobile.html', room_id=room_id, role=role)

@app.route('/assets/<path:filename>')
def react_assets(filename):
    """Hashed Vite bundle assets; content-addressed, so cache indefinitely."""
    response = send_from_directory(os.path.join(REACT_DIST, 'assets'), filename,
                                   max_age=31536000)
    response.cache_control.immutable = True
    return response

@app.route('/crossword/<date>')
def get_crossword(date):
    content = requests.get(f'https://nytsyn.pzzl.com/nytsyn-crossword-mh/nytsyncrossword?date={date}').text
    return content


@app.route('/crossword_by_date/<date>')
def get_crossword_by_date(date):
    """Get a specific crossword puzzle by date (YYMMDD format)."""
    try:
        reader = DataReader(base_url=base_url)
        print(f"Fetching crossword for date {date}")
        
        # Fetch and parse crossword
        api_text = reader._fetch_data(date)
        crossword = NYTFormatParser.parse(api_text)
        
        print(f'Crossword for {date} parsed: {len(crossword.entries)} entries')
        
        # Serialize crossword data
        response_data = {
            "metadata": crossword.metadata.model_dump(),
            "entries": [entry.model_dump() for entry in crossword.entries]
        }
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Error fetching crossword for date {date}: {e}")
        return jsonify({"error": str(e)}), 400


def daterange(begin, end):
    current_date = begin
    while current_date < end:
        yield current_date
        current_date += timedelta(days=1)


base_url = "https://nytsyn.pzzl.com/nytsyn-crossword-mh/nytsyncrossword"


@app.route('/random_crossword/<weekday>')
def get_random_crossword(weekday):
    """Get a random crossword puzzle for the specified weekday."""
    begin = datetime(2010, 1, 1)
    end = datetime.today()
    weekday = weekday.lower()
    weekday_map = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }
    if weekday not in weekday_map:
        return jsonify({"error": "Invalid weekday"}), 400
    
    random_date = random.choice([date for date in daterange(begin, end) if date.weekday() == weekday_map[weekday]])
    reader = DataReader(base_url=base_url)
    formatted_date = random_date.strftime("%y%m%d")
    print(f"Fetching crossword for {weekday} {formatted_date}")
    
    # Fetch and parse crossword
    api_text = reader._fetch_data(formatted_date)
    crossword = NYTFormatParser.parse(api_text)
    
    print(f'Crossword for {formatted_date} parsed: {len(crossword.entries)} entries')
    
    # Validate that the crossword date is the correct weekday
    assert datetime.strptime(crossword.metadata.date, "%y%m%d").weekday() == weekday_map[weekday]
    
    # Serialize crossword data
    response_data = {
        "metadata": crossword.metadata.model_dump(),
        "entries": [entry.model_dump() for entry in crossword.entries]
    }
    
    return jsonify(response_data)


@app.route('/grid')
def grid():
    # Example black cells - you can modify this pattern
    black_cells = {(0, 4), (1, 1), (2, 2), (3, 3), (4, 0)}
    return render_template('grid.html', black_cells=black_cells)


@app.route('/api/completed_puzzles', methods=['GET'])
def get_completed_puzzles():
    """Get all completed puzzles."""
    try:
        completed = CompletedPuzzle.query.order_by(CompletedPuzzle.completed_at.desc()).all()
        return jsonify([puzzle.to_dict() for puzzle in completed])
    except Exception as e:
        print(f"Error fetching completed puzzles: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/completed_puzzles/<puzzle_date>', methods=['GET'])
def check_puzzle_completed(puzzle_date):
    """Check if a specific puzzle is completed."""
    try:
        puzzle = CompletedPuzzle.query.filter_by(puzzle_date=puzzle_date).first()
        if puzzle:
            return jsonify({"completed": True, "data": puzzle.to_dict()})
        return jsonify({"completed": False})
    except Exception as e:
        print(f"Error checking puzzle completion: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/completed_puzzles', methods=['POST'])
def mark_puzzle_completed():
    """Mark a puzzle as completed."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'puzzle_date' not in data:
            return jsonify({"error": "puzzle_date is required"}), 400
        
        puzzle_date = data['puzzle_date']
        
        # Check if already exists
        existing = CompletedPuzzle.query.filter_by(puzzle_date=puzzle_date).first()
        if existing:
            return jsonify({
                "message": "Puzzle already marked as completed",
                "data": existing.to_dict()
            }), 200
        
        # Create new completed puzzle record
        completed_puzzle = CompletedPuzzle(
            puzzle_date=puzzle_date,
            title=data.get('title', ''),
            authors=json.dumps(data.get('authors', [])),
            weekday=data.get('weekday', ''),
            time_taken=data.get('time_taken'),
            score=data.get('score')
        )
        
        db.session.add(completed_puzzle)
        db.session.commit()
        
        print(f"Marked puzzle {puzzle_date} as completed")
        
        return jsonify({
            "message": "Puzzle marked as completed",
            "data": completed_puzzle.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error marking puzzle as completed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/completed_puzzles/<puzzle_date>', methods=['DELETE'])
def delete_completed_puzzle(puzzle_date):
    """Delete a completed puzzle record (for testing/reset)."""
    try:
        puzzle = CompletedPuzzle.query.filter_by(puzzle_date=puzzle_date).first()
        if not puzzle:
            return jsonify({"error": "Puzzle not found"}), 404
        
        db.session.delete(puzzle)
        db.session.commit()
        
        return jsonify({"message": "Puzzle completion record deleted"}), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting completed puzzle: {e}")
        return jsonify({"error": str(e)}), 500


# --- Multiplayer Routes & Events ---

@app.route('/api/multiplayer/create', methods=['POST'])
def create_session():
    data = request.json
    puzzle_date = data.get('date')
    room_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
    game_sessions[room_id] = GameSession(room_id, puzzle_date)
    return jsonify({'room_id': room_id})

@app.route('/api/multiplayer/qr/<room_id>/<role>')
def get_qr(room_id, role):
    # Get local IP
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
        
    # Use the port from the request if possible, or default to 5000
    host_with_port = request.host
    # If running on localhost, replace with IP
    if 'localhost' in host_with_port or '127.0.0.1' in host_with_port:
        port = host_with_port.split(':')[-1] if ':' in host_with_port else '5000'
        host_with_port = f"{IP}:{port}"
    
    url = f"http://{host_with_port}/mobile/{room_id}/{role}"
    
    img = qrcode.make(url)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({'qr_image': f"data:image/png;base64,{img_str}", 'url': url})

@app.route('/mobile/<room_id>/<role>')
def mobile_client(room_id, role):
    """Mobile solve view: the React port (same build, mobile route)."""
    return _react_index()

@app.route('/api/system/wifi', methods=['POST'])
def open_wifi_settings():
    try:
        subprocess.run(["open", "x-apple.systempreferences:com.apple.Sharing-Settings.extension"])
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@socketio.on('join')
def on_join(data):
    room = data['room']
    role = data.get('role')
    join_room(room)
    
    session = game_sessions.get(room)
    if session:
        if role in ['across', 'down']:
            session.players[role] = request.sid
        
        # Send current state
        emit('game_state', session.to_dict(), to=request.sid)
        emit('player_joined', {'role': role}, to=room)

@socketio.on('update_cell')
def on_update_cell(data):
    room = data['room']
    row = data['row']
    col = data['col']
    value = data['value']
    
    session = game_sessions.get(room)
    if session:
        session.update_cell(row, col, value)
        emit('cell_updated', data, to=room, include_self=False)

@socketio.on('request_swap')
def on_request_swap(data):
    room = data['room']
    emit('swap_requested', data, to=room, include_self=False)

@socketio.on('confirm_swap')
def on_confirm_swap(data):
    room = data['room']
    emit('swap_confirmed', data, to=room)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
