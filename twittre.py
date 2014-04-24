import os
import sqlite3
import sys
import time
import calendar
from datetime import datetime
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
    db = get_db()
    cur = db.execute('select text, user_id, time from tweets order by id desc')
    tweets = cur.fetchall()
    return render_template('index.html', tweets=tweets)

@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.form['tweet'].strip() != '':
        db = get_db()
        db.execute('insert into tweets (text, user_id, time) values (?, ?, ?)', [request.form['tweet'].strip(), session.get('username').lower(), int(round(time.time() * 1000))])
        db.commit()

        flash('New entry was successfully posted')
    else:
        flash('Tweet cannot be empty')

    return redirect(url_for('show_entries'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not session.get('logged_in'):
        error = None

        if request.method == 'POST':
            username = request.form['username'].strip().lower()
            password = request.form['password']

            user = query_db('select * from users where username_lower = ?', [username], one=True)

            if user is None:
                error = 'Invalid username'
            elif password != user['password']:
                error = 'Invalid password'
            else:
                session['logged_in'] = True
                session['username'] = user['username']
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
            username = request.form['username'].strip()
            username_lower = username.lower()
            password = request.form['password']
            password2 = request.form['password2']

            if username != '':
                user = query_db('select * from users where username_lower = ?', [username_lower], one=True)

                if user is None:
                    if password != password2:
                        error = 'Passwords do not match'
                    else:
                        db = get_db()
                        db.execute('insert into users (username, username_lower, password, admin) values (?, ?, ?, ?)', [username, username_lower, password, 0])
                        db.commit()

                        session['logged_in'] = True
                        session['username'] = username
                        flash('Welcome to Twittre!')

                        return redirect(url_for('show_entries'))
                else:
                    error = 'Username has already been taken'
            else:
                error = 'Username cannot be left blank'

        return render_template('register.html', error=error)
    else:
        return redirect(url_for('show_entries'))

@app.route('/<username>', methods=['GET'])
def user(username):
    user = query_db('select * from users where username_lower = ?', [username.lower()], one=True)

    if user is None:
        return redirect(url_for('show_entries'))
    else:
        db = get_db()
        cur = db.execute('select text, user_id, time from tweets where user_id = ? order by id desc', [username.lower()])
        tweets = cur.fetchall()
        return render_template('user.html', tweets=tweets, username=user['username'])

@app.template_filter('datetime_format')
def formatTime(millis):
    d = datetime.fromtimestamp(millis/1000)

    return d.strftime('%b %-d, %Y @ %-I:%M %p')

@app.before_first_request
def initialize():
    app.logger.debug('Initializing...')

    # Initialize database
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        init_db()

        # Initialize administrator
        db = get_db()
        db.execute('insert into users (username, username_lower, password, admin) values (?, ?, ?, ?)', [admin_username, admin_username.lower(), admin_password, 1])
        db.commit()

        app.logger.debug('Database has been initialized.')

    app.logger.debug('Done!')

if __name__ == '__main__':
    app.run()
