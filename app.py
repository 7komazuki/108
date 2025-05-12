import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, emit, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.pool import QueuePool

import uuid
import json
import sqlite3
from nanatori import NanatoridoriGame, load_game, Player


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "poolclass": QueuePool,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30
}

# Initialize the database and SocketIO
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active game sessions
game_sessions = {}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))  # hashed password

    # Game statistics
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    games_played = db.Column(db.Integer, default=0)

    # Favorite cards (comma-separated list of card numbers, e.g. "1,3,7")
    favorite_cards = db.Column(db.String(20), default="8,8,8")  # Default to card 8 (back card)

class SessionData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_code = db.Column(db.String(36), unique=True)
    data = db.Column(db.Text)
    description = db.Column(db.String(200))
    password = db.Column(db.String(100))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_public = db.Column(db.Boolean, default=True)


@app.route('/')
def landing():
    # If user is logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    # Otherwise show landing page
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard():
    # Require login
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))
    
    # Get recent sessions (if you have this functionality)
    recent_sessions = []
    # You can uncomment and implement this if you want to show recent sessions
    # recent_sessions = SessionData.query.filter(...).limit(5).all()
    
    return render_template('dashboard.html', user=user, recent_sessions=recent_sessions)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Check if passwords match
        if password != confirm_password:
            error = "Passwords don't match"
        # Check if username or email already exists in the database
        elif User.query.filter_by(username=username).first():
            error = 'Username already exists'
        elif User.query.filter_by(email=email).first():
            error = 'Email already registered'
        else:
            # If no errors, hash password and create new user
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, email=email, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            return redirect('/login')

    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)  # Also clear admin status
    return redirect(url_for('landing'))

@app.route('/account')
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))

    # Calculate win rate
    win_rate = 0
    if user.games_played > 0:
        win_rate = round((user.wins / user.games_played) * 100, 1)

    # Parse favorite cards
    favorite_cards = []
    if user.favorite_cards:
        favorite_cards = [int(card) for card in user.favorite_cards.split(',')]

    # Ensure we have 3 cards (fill with card 8 if needed)
    while len(favorite_cards) < 3:
        favorite_cards.append(8)

    # Limit to first 3 cards
    favorite_cards = favorite_cards[:3]

    return render_template('account.html', user=user, win_rate=win_rate, favorite_cards=favorite_cards)

@app.route('/update_password', methods=['POST'])
def update_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))

    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    error = None
    success = None

    # Verify current password
    if not check_password_hash(user.password, current_password):
        error = "Current password is incorrect"
    # Check if new passwords match
    elif new_password != confirm_password:
        error = "New passwords don't match"
    # Check password strength (optional)
    elif len(new_password) < 6:
        error = "Password must be at least 6 characters long"
    else:
        # Update password
        user.password = generate_password_hash(new_password)
        db.session.commit()
        success = "Password updated successfully"

    # Calculate win rate and prepare favorite cards for render
    win_rate = 0
    if user.games_played > 0:
        win_rate = round((user.wins / user.games_played) * 100, 1)

    favorite_cards = []
    if user.favorite_cards:
        favorite_cards = [int(card) for card in user.favorite_cards.split(',')]

    while len(favorite_cards) < 3:
        favorite_cards.append(8)

    favorite_cards = favorite_cards[:3]

    return render_template('account.html', user=user, error=error, success=success,
                          win_rate=win_rate, favorite_cards=favorite_cards)

@app.route('/update_favorite_cards', methods=['POST'])
def update_favorite_cards():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))

    # Get favorite cards from form
    card1 = request.form.get('card1', '8')
    card2 = request.form.get('card2', '8')
    card3 = request.form.get('card3', '8')

    # Validate card values (1-8)
    for card in [card1, card2, card3]:
        try:
            card_val = int(card)
            if card_val < 1 or card_val > 8:
                return render_template('account.html', user=user,
                                     error="Card values must be between 1 and 8")
        except ValueError:
            return render_template('account.html', user=user,
                                 error="Invalid card value")

    # Update favorite cards
    user.favorite_cards = f"{card1},{card2},{card3}"
    db.session.commit()

    # Calculate win rate for rendering
    win_rate = 0
    if user.games_played > 0:
        win_rate = round((user.wins / user.games_played) * 100, 1)

    # Parse favorite cards for rendering
    favorite_cards = [int(card1), int(card2), int(card3)]

    return render_template('account.html', user=user,
                          success="Favorite cards updated successfully",
                          win_rate=win_rate, favorite_cards=favorite_cards)

@app.route('/join', methods=['GET', 'POST'])
def join():
    error = None
    session_info = None
    
    if request.method == 'POST':
        session_id = request.form['session_id']
        
        try:
            # Use direct SQLite connection
            import sqlite3
            import json
            
            conn = sqlite3.connect('instance/users.db')
            cursor = conn.cursor()
            
            # Query for the session
            cursor.execute("SELECT session_code, data FROM session_data WHERE session_code = ?", (session_id,))
            result = cursor.fetchone()
            
            if result:
                session_code, data = result
                session_json = json.loads(data)
                
                # Extract password from JSON if it exists
                password = session_json.get('password', '')
                
                # If session has no password, redirect directly to join-game route
                if not password:
                    conn.close()
                    print(f"No password, redirecting directly to join-game: {session_id}")
                    # Use the direct join-game route
                    return redirect(url_for('join_game_direct', session_code=session_id))
                
                # If session has a password, show password form
                session_info = {
                    'code': session_code,
                    'name': session_json.get('name', 'Unnamed Session'),
                    'description': session_json.get('description', '')
                }
            else:
                error = 'Session not found. Please check the Session ID.'
                
            conn.close()
            
        except Exception as e:
            print(f"Error in join route: {e}")
            error = 'An error occurred. Please try again.'
            
    return render_template('session.html', error=error, session_info=session_info)

@app.route('/verify_session_password', methods=['POST'])
def verify_session_password():
    session_id = request.form['session_id']
    input_password = request.form['password']

    try:
        # Use direct SQLite connection
        import sqlite3
        import json

        conn = sqlite3.connect('instance/users.db')
        cursor = conn.cursor()

        # Query for the session
        cursor.execute("SELECT session_code, data FROM session_data WHERE session_code = ?", (session_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return redirect(url_for('join', error='Session not found'))

        session_code, data = result
        session_json = json.loads(data)

        # Extract password from JSON
        password = session_json.get('password', '')

        # Check if admin password was used
        is_admin = (input_password == '5507')

        # Check if password matches or if admin password was used
        if input_password != password and not is_admin:
            # If the password is incorrect, reload the join page with an error
            session_info = {
                'code': session_code,
                'name': session_json.get('name', 'Unnamed Session'),
                'description': session_json.get('description', '')
            }

            conn.close()
            return render_template('session.html',
                                error='Incorrect password',
                                session_info=session_info)

        conn.close()

        # Set admin flag in session if admin password was used
        if is_admin:
            session['is_admin'] = True
            print(f"Admin access granted for session: {session_id}")

        # Password is correct, redirect to join-game route
        print(f"Password correct, redirecting directly to join-game: {session_id}")
        # Use the direct join-game route
        return redirect(url_for('join_game_direct', session_code=session_id))

    except Exception as e:
        print(f"Error in verify_password route: {e}")
        return redirect(url_for('join', error='An error occurred. Please try again.'))

@app.route('/create_session', methods=['GET', 'POST'])
def create_session():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # If GET request, show the hosting form
    if request.method == 'GET':
        return render_template('host.html')
    
    # If POST request, process the form data
    session_name = request.form.get('session_name', 'Unnamed Session')
    description = request.form.get('description', '')
    password = request.form.get('password', '')
    visibility = request.form.get('visibility', 'public')
    
    # Generate a unique session code
    import uuid
    session_code = str(uuid.uuid4())[:8]  # First 8 characters of a UUID
    
    # Prepare data JSON
    import json
    session_data = json.dumps({
        "name": session_name,
        "description": description,
        "password": password,
        "is_public": (visibility == 'public')
    })
    
    # Directly use SQLite connection to avoid SQLAlchemy issues
    try:
        import sqlite3
        conn = sqlite3.connect('instance/users.db')
        cursor = conn.cursor()
        
        # Check table structure
        cursor.execute("PRAGMA table_info(session_data)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if all(col in columns for col in ['description', 'password', 'created_by', 'is_public']):
            # Use all columns if they exist
            cursor.execute('''
                INSERT INTO session_data 
                (session_code, data, description, password, created_by, is_public) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_code,
                session_data,
                description,
                password,
                session.get('user_id'),
                1 if visibility == 'public' else 0
            ))
        else:
            # Fallback to basic structure
            cursor.execute('''
                INSERT INTO session_data 
                (session_code, data) 
                VALUES (?, ?)
            ''', (session_code, session_data))
            
        conn.commit()
        conn.close()
        print(f"Successfully created session: {session_code}")
        
        # Redirect to the join-game route
        print(f"Session created, redirecting to join-game: {session_code}")
        return redirect(url_for('join_game_direct', session_code=session_code))
        
    except Exception as e:
        print(f"Error creating session: {e}")
        return render_template('host.html', error=f"Failed to create session. Please try again later.")

@app.route('/sessions')
def session_list():
    try:
        # Get query parameters
        search_query = request.args.get('search', '')
        sessions = []
        current_user_id = session.get('user_id')
        is_admin = session.get('is_admin', False)
        
        try:
            # First attempt - use full schema
            # Query sessions from database
            query = SessionData.query.filter_by(is_public=True)
            
            # Apply search filter if provided
            if search_query:
                # Search in description and data field (for the name)
                query = query.filter(
                    (SessionData.description.ilike(f'%{search_query}%')) |
                    (SessionData.data.ilike(f'%{search_query}%'))
                )
            
            # Get results ordered by creation time (newest first)
            session_results = query.order_by(SessionData.created_at.desc()).all()
            
            # Format results for the template
            for s in session_results:
                import json
                import datetime
                session_json = json.loads(s.data)
                
                # Get fields from either column or JSON data
                has_password = bool(getattr(s, 'password', None))
                description = getattr(s, 'description', None) or session_json.get('description', '')
                created_at = getattr(s, 'created_at', None) or datetime.datetime.now()
                created_by = getattr(s, 'created_by', None)
                
                # Check if the user can delete this session
                can_delete = is_admin or (current_user_id and current_user_id == created_by)
                
                # Get active player count if the session is in game_sessions
                active_players = 0
                if s.session_code in game_sessions:
                    active_players = len(game_sessions[s.session_code].active_players)

                sessions.append({
                    'code': s.session_code,
                    'name': session_json.get('name', 'Unnamed Session'),
                    'description': description,
                    'created_at': created_at,
                    'has_password': has_password or ('password' in session_json and session_json['password']),
                    'can_delete': can_delete,
                    'player_count': active_players
                })
                
        except Exception as e:
            print(f"Error using full schema: {e}")
            
            # Fallback - just use the data JSON field
            from sqlalchemy import text, func
            
            # Simple query without using the new columns
            fallback_query = "SELECT session_code, data, created_by FROM session_data"
            if search_query:
                fallback_query += f" WHERE data LIKE '%{search_query}%'"
                
            result = db.session.execute(text(fallback_query))
            
            # Process results
            import json
            import datetime
            for row in result:
                try:
                    session_json = json.loads(row.data)
                    
                    # Check if the user can delete this session
                    row_created_by = getattr(row, 'created_by', None)
                    can_delete = is_admin or (current_user_id and current_user_id == row_created_by)
                    
                    # Get active player count if the session is in game_sessions
                    active_players = 0
                    if row.session_code in game_sessions:
                        active_players = len(game_sessions[row.session_code].active_players)

                    # Get all session data from the JSON
                    sessions.append({
                        'code': row.session_code,
                        'name': session_json.get('name', 'Unnamed Session'),
                        'description': session_json.get('description', ''),
                        'created_at': datetime.datetime.now(),  # Use current time as fallback
                        'has_password': bool(session_json.get('password', '')),
                        'can_delete': can_delete,
                        'player_count': active_players
                    })
                except Exception as e:
                    print(f"Error processing session data: {e}")
                    continue
            
        return render_template('sessions_list.html',
                            sessions=sessions,
                            search_query=search_query,
                            is_admin=is_admin)
                            
    except Exception as main_error:
        print(f"Error in session listing: {main_error}")
        # Complete fallback - show empty list with error message
        return render_template('sessions_list.html',
                            sessions=[],
                            search_query=search_query,
                            error="Could not retrieve sessions. Please try again later.")

@app.route('/game/<session_code>')
def game_page(session_code):
    try:
        # Use direct SQLite connection
        conn = sqlite3.connect('instance/users.db')
        cursor = conn.cursor()

        # Query for the session
        cursor.execute("SELECT session_code, data FROM session_data WHERE session_code = ?", (session_code,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return redirect(url_for('join', error='Session not found'))

        # Get session data
        session_code, data = result
        session_json = json.loads(data)

        # Get username for the player
        username = "Guest"
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            if user:
                username = user.username

        # Check if user is admin
        is_admin = session.get('is_admin', False)

        conn.close()
        print(f"Rendering game.html for session {session_code}")
        # Render the game page
        return render_template('game.html',
                                code=session_code,
                                session_name=session_json.get('name', 'Unnamed Session'),
                                username=username,
                                is_admin=is_admin)

    except Exception as e:
        print(f"Error in game_page route: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('join', error='An error occurred loading the session.'))

@app.route('/join-game/<session_code>')
def join_game_direct(session_code):
    """Direct route to join a game without any redirects"""
    try:
        # Use direct SQLite connection
        conn = sqlite3.connect('instance/users.db')
        cursor = conn.cursor()

        # Query for the session
        cursor.execute("SELECT session_code, data FROM session_data WHERE session_code = ?", (session_code,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return redirect(url_for('join', error='Session not found'))

        # Get session data
        session_code, data = result
        session_json = json.loads(data)

        # Get username for the player
        username = "Guest"
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            if user:
                username = user.username

        # Check if user is admin
        is_admin = session.get('is_admin', False)

        conn.close()
        print(f"Direct join-game route: rendering game.html for session {session_code}")
        # Render the game page directly
        return render_template('game.html',
                            code=session_code,
                            session_name=session_json.get('name', 'Unnamed Session'),
                            username=username,
                            is_admin=is_admin)

    except Exception as e:
        print(f"Error in join_game_direct route: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('join', error='An error occurred loading the session.'))

@app.route('/session/<session_code>')
def session_page(session_code):
    # Debug print
    print(f"Session page called for session {session_code}")
    # Just render session.html again - this is clearly not working as a redirect
    return render_template('session.html', code=session_code)


@socketio.on('join_game')
def handle_join_game(data):
    room = data.get('session_id')
    player_name = data.get('player_name')

    if not room or not player_name:
        emit('error', {'message': 'Missing session ID or player name'})
        return

    join_room(room)

    # Store player-to-room mapping for disconnect handling
    session['room'] = room
    session['player_name'] = player_name

    # Initialize or get the game session
    if room not in game_sessions:
        # Get players already in the room
        connected_players = []

        try:
            # Get session data to see if there are already players
            conn = sqlite3.connect('instance/users.db')
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM session_data WHERE session_code = ?", (room,))
            result = cursor.fetchone()

            if result:
                session_data = json.loads(result[0])
                connected_players = session_data.get('players', [])

                # Add this player if not already in the list
                if player_name not in connected_players:
                    connected_players.append(player_name)

                    # Update the session data
                    session_data['players'] = connected_players
                    cursor.execute("UPDATE session_data SET data = ? WHERE session_code = ?",
                                  (json.dumps(session_data), room))
                    conn.commit()
            else:
                # Session doesn't exist yet in DB
                connected_players = [player_name]

            conn.close()

        except Exception as e:
            print(f"Error getting/updating session data: {e}")
            connected_players = [player_name]

        # Create a new game - make sure we have at least one player
        if not connected_players:
            connected_players = [player_name]
        game = NanatoridoriGame(connected_players)
        game.deal_cards()
        game_sessions[room] = game

        print(f"New game created in room {room} with players: {connected_players}")
    else:
        # Get existing game
        game = game_sessions[room]

        # Check if player is rejoining
        rejoining = player_name in game.player_names

        # If the game is over and player is rejoining, reset it
        if game.game_over and rejoining:
            # Only reset the game if it's still marked as game over
            print(f"Player {player_name} rejoining after game over, resetting game")
            game.new_round()
        elif not rejoining:
            # Add player if not already in the game
            print(f"New player {player_name} joining game in room {room}")
            game.player_names.append(player_name)
            game.players[player_name] = Player(player_name)
            game.players[player_name].hand = [game.deck.pop() for _ in range(8)] if len(game.deck) >= 8 else []
        else:
            print(f"Player {player_name} rejoining game in room {room}")

        # Always mark the player as active when joining
        game.mark_player_active(player_name)

    # Send join notification
    emit('user_joined', {
        'player': player_name,
        'message': f"{player_name} joined the game"
    }, room=room)

    # Send game state to all players
    emit('game_update', game.get_game_state(), room=room)

@socketio.on('play_card')
def handle_play_card(data):
    player = data.get('player')
    cards = data.get('card_indices', [])
    room = data.get('room')

    if not player or not room or not cards:
        emit('error', {'message': 'Missing required data for playing cards'})
        return

    if room not in game_sessions:
        emit('error', {'message': 'Game session not found'})
        return

    game = game_sessions[room]

    # Try to play the cards
    success, old_table = game.play_card(player, cards)

    if success:
        # If cards were played successfully, update all clients
        emit('game_update', game.get_game_state(), room=room)

        # If there are cards on the table to pick up, send a notification
        if old_table and len(old_table) > 0:
            emit('table_update', {
                'cards': old_table,
                'message': f"{player} played cards, there are cards to pick up"
            }, room=room)
    else:
        # Send error message to the player who tried to play
        emit('error', {'message': old_table})  # old_table contains error message in this case

@socketio.on('pass_turn')
def handle_pass_turn(data):
    player = data.get('player')
    room = data.get('room')

    if not player or not room:
        emit('error', {'message': 'Missing required data for passing turn'})
        return

    if room not in game_sessions:
        emit('error', {'message': 'Game session not found'})
        return

    game = game_sessions[room]

    # Try to pass turn
    success, new_card = game.pass_turn(player)

    if success:
        # Update all clients with new game state
        emit('game_update', game.get_game_state(), room=room)

        # Notify the player about the card they drew
        emit('card_drawn', {
            'card': new_card,
            'message': f"You drew a {new_card}"
        })
    else:
        # Send error message
        emit('error', {'message': new_card})  # new_card contains error message in this case

@socketio.on('take_cards')
def handle_take_cards(data):
    player = data.get('player')
    room = data.get('room')

    if not player or not room:
        emit('error', {'message': 'Missing required data for taking cards'})
        return

    if room not in game_sessions:
        emit('error', {'message': 'Game session not found'})
        return

    game = game_sessions[room]

    # Try to take cards
    success, taken_cards = game.take_cards(player)

    if success:
        # Update all clients
        emit('game_update', game.get_game_state(), room=room)
        emit('cards_taken', {
            'player': player,
            'cards': taken_cards,
            'message': f"{player} took {len(taken_cards)} card(s) from the table"
        }, room=room)
    else:
        # Send error message
        emit('error', {'message': taken_cards})  # taken_cards contains error message

@socketio.on('discard_cards')
def handle_discard_cards(data):
    player = data.get('player')
    room = data.get('room')

    if not player or not room:
        emit('error', {'message': 'Missing required data for discarding cards'})
        return

    if room not in game_sessions:
        emit('error', {'message': 'Game session not found'})
        return

    game = game_sessions[room]

    # Try to discard cards
    success, _ = game.discard_cards(player)

    if success:
        # Update all clients
        emit('game_update', game.get_game_state(), room=room)
        emit('cards_discarded', {
            'player': player,
            'message': f"{player} discarded the cards from the table"
        }, room=room)
    else:
        # Send error message
        emit('error', {'message': _})  # _ contains error message

@socketio.on('new_game')
def handle_new_game(data):
    room = data.get('room')

    if not room:
        emit('error', {'message': 'Missing session ID'})
        return

    if room not in game_sessions:
        emit('error', {'message': 'Game session not found'})
        return

    game = game_sessions[room]

    # Check if game was already reset (to avoid double reset)
    was_game_over = game.game_over

    # Reset the game
    game.new_round()

    # Make sure game_over is reset
    game.game_over = False
    game.winner = None

    # Log the action
    print(f"New game started in room {room}. Previous state was game over: {was_game_over}")

    # Update all clients
    emit('game_update', game.get_game_state(), room=room)
    emit('game_restart', {
        'message': 'New game started'
    }, room=room)

@socketio.on('admin_force_win')
def handle_admin_force_win(data):
    player = data.get('player')
    room = data.get('room')
    admin_password = data.get('admin_password')

    if not player or not room:
        emit('error', {'message': 'Missing required data'})
        return

    # Check admin password
    if admin_password != '5507':
        emit('error', {'message': 'Admin access denied'})
        return

    if room not in game_sessions:
        emit('error', {'message': 'Game session not found'})
        return

    game = game_sessions[room]

    # Force win for the player
    success, message = game.admin_force_win(player)

    if success:
        # Update player stats
        try:
            user = User.query.filter_by(username=player).first()
            if user:
                user.wins += 1
                user.games_played += 1
                db.session.commit()
                print(f"Updated stats for {player}: +1 win")

            # Update loss stats for other players
            for other_player in game.player_names:
                if other_player != player and other_player in game.active_players:
                    other_user = User.query.filter_by(username=other_player).first()
                    if other_user:
                        other_user.losses += 1
                        other_user.games_played += 1
                        db.session.commit()
                        print(f"Updated stats for {other_player}: +1 loss")
        except Exception as e:
            print(f"Error updating player stats: {e}")

        # Update all clients with new game state
        emit('game_update', game.get_game_state(), room=room)
        emit('admin_action', {
            'action': 'force_win',
            'player': player,
            'message': message
        }, room=room)
    else:
        # Send error message
        emit('error', {'message': message})

@socketio.on('admin_force_loss')
def handle_admin_force_loss(data):
    player = data.get('player')
    room = data.get('room')
    admin_password = data.get('admin_password')

    if not player or not room:
        emit('error', {'message': 'Missing required data'})
        return

    # Check admin password
    if admin_password != '5507':
        emit('error', {'message': 'Admin access denied'})
        return

    if room not in game_sessions:
        emit('error', {'message': 'Game session not found'})
        return

    game = game_sessions[room]

    # Force loss for the player
    success, message = game.admin_force_loss(player)

    if success:
        # Update player stats
        try:
            user = User.query.filter_by(username=player).first()
            if user:
                user.losses += 1
                user.games_played += 1
                db.session.commit()
                print(f"Updated stats for {player}: +1 loss")

            # If there's only one remaining player with lives, they win
            remaining_players = [name for name in game.active_players if name != player and game.players[name].lives > 0]
            if len(remaining_players) == 1:
                winner = remaining_players[0]
                # Update winner stats
                winner_user = User.query.filter_by(username=winner).first()
                if winner_user:
                    winner_user.wins += 1
                    winner_user.games_played += 1
                    db.session.commit()
                    print(f"Updated stats for {winner}: +1 win")
        except Exception as e:
            print(f"Error updating player stats: {e}")

        # Update all clients with new game state
        emit('game_update', game.get_game_state(), room=room)
        emit('admin_action', {
            'action': 'force_loss',
            'player': player,
            'message': message
        }, room=room)
    else:
        # Send error message
        emit('error', {'message': message})

@socketio.on('player_exit')
def handle_player_exit(data):
    player = data.get('player')
    room = data.get('room')

    if not player or not room:
        return

    # Leave the room
    leave_room(room)

    print(f"Player {player} exited from room {room}")

    # Notify other players
    emit('player_left', {
        'player': player,
        'message': f"{player} has left the game"
    }, room=room)

    # Check if the player was in a game
    if room in game_sessions:
        game = game_sessions[room]

        # Mark the player as inactive so they don't appear for other players
        if player in game.player_names:
            game.mark_player_inactive(player)
            print(f"Player {player} marked as inactive in game")

            # If game is over, and players start exiting, prepare for a fresh round
            if game.game_over:
                # Only start a new round when the first player exits after game over
                # This avoids multiple resets if multiple players exit
                game.new_round()
                print(f"Game reset in room {room} due to player exit after game over")

            # Send updated game state to all remaining players
            emit('game_update', game.get_game_state(), room=room)

@socketio.on('disconnect')
def handle_disconnect():
    # Get player info from session
    player_name = session.get('player_name')
    room = session.get('room')

    # If we have player info, handle their disconnection
    if player_name and room and room in game_sessions:
        print(f"Player {player_name} disconnected from room {room}")

        game = game_sessions[room]

        # Mark player as inactive
        if player_name in game.player_names:
            game.mark_player_inactive(player_name)

            # Notify other players
            emit('player_left', {
                'player': player_name,
                'message': f"{player_name} has disconnected"
            }, room=room)

            # Send updated game state
            emit('game_update', game.get_game_state(), room=room)
    else:
        print("Client disconnected (no session data available)")


def create_tables():
    db.create_all()

# Import database migration script
from migrate_db import migrate_database

# Run the migration immediately to ensure the schema is up to date
print("Running database migration...")
migrate_database()

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        admin_pin = request.form.get('admin_pin')
        if admin_pin == '5507':
            session['is_admin'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('account.html', admin_error='Invalid admin PIN')
    
    return render_template('account.html')

@app.route('/delete_session/<session_code>', methods=['POST'])
def delete_session(session_code):
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user_id = session.get('user_id')
    is_admin = session.get('is_admin', False)
    success = False
    error_message = None
    
    try:
        # Get the session
        session_data = SessionData.query.filter_by(session_code=session_code).first()
        
        if not session_data:
            error_message = "Session not found"
        elif is_admin or session_data.created_by == current_user_id:
            # User has permission to delete
            db.session.delete(session_data)
            db.session.commit()
            success = True
        else:
            error_message = "You don't have permission to delete this session"
            
    except Exception as e:
        print(f"Error deleting session: {e}")
        # Fallback to direct SQLite if ORM approach fails
        try:
            import sqlite3
            conn = sqlite3.connect('instance/users.db')
            cursor = conn.cursor()
            
            # First check permissions if not admin
            if not is_admin:
                cursor.execute("SELECT created_by FROM session_data WHERE session_code = ?", (session_code,))
                result = cursor.fetchone()
                
                if not result:
                    error_message = "Session not found"
                elif result[0] != current_user_id:
                    error_message = "You don't have permission to delete this session"
                else:
                    # Delete the session
                    cursor.execute("DELETE FROM session_data WHERE session_code = ?", (session_code,))
                    conn.commit()
                    success = True
            else:
                # Admin can delete any session
                cursor.execute("DELETE FROM session_data WHERE session_code = ?", (session_code,))
                conn.commit()
                success = True
                
            conn.close()
            
        except Exception as e2:
            print(f"Error in fallback delete: {e2}")
            error_message = "Failed to delete session. Please try again."
    
    if success:
        return redirect(url_for('session_list'))
    else:
        return render_template('sessions_list.html', error=error_message)

# Run the app


import os
import eventlet.wsgi
from flask_socketio import SocketIO
from app import app, db


# Initialize SocketIO
socketio = SocketIO(app, async_mode='eventlet')

# Deploy with socketio.run for better async support
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port)

