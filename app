from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database and SocketIO
db = SQLAlchemy(app)
socketio = SocketIO(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))  # hashed password

class SessionData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_code = db.Column(db.String(36), unique=True)
    data = db.Column(db.Text)


@app.route('/')
def landing():
    return render_template('landing.html')

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
            return redirect('/join')
        else:
            error = 'Invalid username or password'
    return render_template('login.html', error=error)

@app.route('/join', methods=['GET', 'POST'])
def join():
    error = None
    if request.method == 'POST':
        session_id = request.form['session_id']
        session_data = SessionData.query.filter_by(session_code=session_id).first()
        if session_data:
            
            return redirect(f'/session/{session_id}')
        else:
            error = 'Session not found. Please check the Session ID.'
    return render_template('join_session.html', error=error)

@app.route('/session/<session_code>')
def session_page(session_code):
    return render_template('session.html', code=session_code)


@socketio.on('join_session')
def handle_join(data):
    room = data['room']
    join_room(room)
    emit('user_joined', {'msg': f"User {session.get('user_id')} joined"}, room=room)

@socketio.on('send_update')
def handle_update(data):
    emit('receive_update', data, room=data['room'])


def create_tables():
    db.create_all()

# Run the app
if __name__ == '__main__':
    
    with app.app_context():
        create_tables()
    socketio.run(app, debug=True)
