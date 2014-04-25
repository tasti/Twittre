import os
import sqlite3
import sys
import time
import calendar
from datetime import datetime
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, Markup

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

@app.template_filter('inject_hash_tag')
def getSafeTweet(tweet):
    safeTweet = str(Markup.escape(tweet))
    injectedTweet = ''
    
    # Inject <a href> for hashtags
    HASH_TAG_STATE = 1
    IGNORE_NEXT_STATE = 2
    state = 0
    hashTagText = ''
    for c in safeTweet:
        if state == HASH_TAG_STATE:
            if (c < 'A' or c > 'Z') and (c < 'a' or c > 'z') and (c < '0' or c > '9'):
                injectedTweet += '<a href="/hash/%s">#%s</a>%s' % (hashTagText.lower(), hashTagText, c)
                state = 0
            else:
                hashTagText += c
        elif state == IGNORE_NEXT_STATE:
            injectedTweet += c
            state = 0
        else:
            if c == '#':
                hashTagText = ''
                state = HASH_TAG_STATE
            elif c == '&':
                injectedTweet += c
                state = IGNORE_NEXT_STATE
            else:
                injectedTweet += c

    # Close hash if still in hashTagState
    if state == HASH_TAG_STATE:
        injectedTweet += '<a href="/hash/%s">#%s</a>' % (hashTagText.lower(), hashTagText)
        state = 0

    return Markup(injectedTweet)

@app.route('/')
def index():
    db = get_db()
    cur = db.execute('select id, text, user_id, time from tweets order by id desc')
    tweets = cur.fetchall()
    return render_template('index.html', tweets=tweets, title="Home")

@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # Add the tweet to the database if not empty
    if request.form['tweet'].strip() != '':
        db = get_db()
        db.execute('insert into tweets (text, user_id, time) values (?, ?, ?)', [request.form['tweet'].strip(), session.get('username').lower(), int(round(time.time() * 1000))])
        db.commit()

        flash('New entry was successfully posted')
    else:
        flash('Tweet cannot be empty')

    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not session.get('logged_in'):
        error = None

        if request.method == 'POST':
            username = request.form['username'].strip().lower()
            password = request.form['password']

            user = query_db('select * from users where username_lower = ?', [username], one=True)

            # Check for valid username and password
            if user is None:
                error = 'Invalid username'
            elif password != user['password']:
                error = 'Invalid password'
            else:
                session['logged_in'] = True
                session['username'] = user['username']
                session['admin'] = False
                if user['admin'] == 1:
                    session['admin'] = True

                flash('You were logged in')

                return redirect(url_for('index'))

        return render_template('login.html', error=error, title="Login")
    else:
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You were logged out')

    return redirect(url_for('index'))

def isUsernameValid(username):
    for c in username:
        if (c < 'a' or c > 'z') and (c < '0' or c > '9'):
            return False

    return True

@app.route('/register', methods=['GET', 'POST'])
def register():
    if not session.get('logged_in'):
        error = None

        if request.method == 'POST':
            username = request.form['username'].strip()
            username_lower = username.lower()
            password = request.form['password']
            password2 = request.form['password2']

            # Ceck for valid username and password
            if username != '':
                if isUsernameValid(username_lower):
                    user = query_db('select * from users where username_lower = ?', [username_lower], one=True)

                    if user is None and username_lower != 'adminconsole':
                        if password != password2:
                            error = 'Passwords do not match'
                        else:
                            db = get_db()
                            db.execute('insert into users (username, username_lower, password, admin) values (?, ?, ?, ?)', [username, username_lower, password, 0])
                            db.commit()

                            session['logged_in'] = True
                            session['username'] = username
                            session['admin'] = False

                            flash('Welcome to Twittre!')

                            return redirect(url_for('index'))
                    else:
                        error = 'Username has already been taken'
                else:
                    error = 'Username can only contain letters and numbers'    
            else:
                error = 'Username cannot be left blank'

        return render_template('register.html', error=error, title="Register")
    else:
        return redirect(url_for('index'))

@app.route('/<username>', methods=['GET'])
def user(username):
    user = query_db('select * from users where username_lower = ?', [username.lower()], one=True)

    # Display username's tweets if valid user
    if user is None:
        return redirect(url_for('index'))
    else:
        db = get_db()
        cur = db.execute('select id, text, user_id, time from tweets where user_id = ? order by id desc', [username.lower()])
        tweets = cur.fetchall()

        return render_template('user.html', tweets=tweets, username=user['username'], title=user['username'])

@app.route('/tweet/<int:tweet_id>', methods=['GET'])
def tweet(tweet_id):
    tweet = query_db('select * from tweets where id = ?', [tweet_id], one=True)

    # Display tweet if valid tweet
    if tweet is None:
        return redirect(url_for('index'))
    else:
        return render_template('tweet.html', tweet=tweet, title="Tweet #%d" % tweet_id)

@app.route('/hashtag/<hashtag>', methods=['GET'])
def hashTag(hashtag):
    tweet = query_db('select * from tweets where id = ?', [tweet_id], one=True)

    # Display tweet if valid tweet
    if tweet is None:
        return redirect(url_for('index'))
    else:
        return render_template('tweet.html', tweet=tweet, title="Tweet #%d" % tweet_id)

@app.route('/adminconsole')
def admin():
    # Open admin console if admin is logged in
    if not session.get('logged_in') or not session.get('admin'):
        return redirect(url_for('index'))
    else:
        db = get_db()
        users = db.execute('select username, username_lower, password, admin from users order by id asc').fetchall()
        tweets = db.execute('select id, text, user_id, time from tweets order by id asc').fetchall()

        return render_template('admin.html', users=users, tweets=tweets, title="Admin Console")

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
