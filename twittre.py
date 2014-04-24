import os
import sqlite3
import sys
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash

secret = open('secret.txt', 'r').read().split('\n')
secret_key = secret[0]
admin_username = secret[1]
admin_password = secret[2]

app = Flask(__name__)
app.config.from_object(__name__)
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'twittre.db'),
    DEBUG=True,
    SECRET_KEY=secret_key,
    USERNAME='admin',
    PASSWORD='default'
))
app.config.from_envvar('TWITTRE_SETTINGS', silent=True)

def connect_db():
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row

    return rv

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())

        db.commit()

def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    
    return g.sqlite_db

def query_db(query, args=(), one=False):
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()

    return (rv[0] if rv else None) if one else rv

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.route('/')
def show_entries():
    for s in session:
        app.logger.debug(s)

    db = get_db()
    cur = db.execute('select title, text from tweets order by id desc')
    entries = cur.fetchall()
    return render_template('show_entries.html', entries=entries)

@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
        abort(401)

    db = get_db()
    db.execute('insert into tweets (title, text) values (?, ?)', [request.form['title'], request.form['text']])
    db.commit()

    flash('New entry was successfully posted')

    return redirect(url_for('show_entries'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not session.get('logged_in'):
        error = None

        if request.method == 'POST':
            username = request.form['username'].trim().lower()
            password = request.form['password']

            user = query_db('select * from users where username_lower = ?', [username], one=True)

            if user is None:
                error = 'Invalid username'
            elif password != user['password']:
                error = 'Invalid password'
            else:
                session['logged_in'] = True
                session['username'] = username
                flash('You were logged in')

                return redirect(url_for('show_entries'))

        return render_template('login.html', error=error)
    else:
        return redirect(url_for('show_entries'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You were logged out')

    return redirect(url_for('show_entries'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if not session.get('logged_in'):
        error = None

        if request.method == 'POST':
            username = request.form['username'].trim()
            username_lower = username.lower()
            password = request.form['password']
            password2 = request.form['password2']

            user = query_db('select * from users where username_lower = ?', [username_lower], one=True)

            if user is None:
                if password != password2:
                    error = 'Passwords do not match'
                else:
                    db = get_db()
                    db.execute('insert into users (username, username_lower, password, admin) values (?, ?, ?, ?)', [username, username_lower, password, 0])
                    db.commit()

                    session['logged_in'] = True
                    session['username'] = username_lower
                    flash('Welcome to Twittre!')

                    return redirect(url_for('show_entries'))
            else:
                error = 'Username has already been taken'

        return render_template('register.html', error=error)
    else:
        return redirect(url_for('show_entries'))

@app.before_first_request
def initialize():
    app.logger.debug('Initializing...')

    # Initialize database
    if len(sys.argv) > 1 and sys.argv[1] == "true":
        init_db()

        # Initialize administrator
        db = get_db()
        db.execute('insert into users (username, username_lower, password, admin) values (?, ?, ?, ?)', [admin_username, admin_username.lower(), admin_password, 1])
        db.commit()

        app.logger.debug('Database has been initialized.')

    app.logger.debug('Done!')

if __name__ == '__main__':
    app.run()
