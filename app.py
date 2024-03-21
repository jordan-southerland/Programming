import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * FROM trades WHERE user_id = ? GROUP BY symbol HAVING shares > 0", session["user_id"])

    portfolio = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = portfolio[0]['cash']
    total_cash = cash
    if rows:
        for row in rows:
            stock = lookup(row['symbol'])
            row['symbol'] = stock['symbol']
            row['price'] = stock['price']
            row['total'] = row['price'] * row['shares']

            total_cash += row['total']
            row['total'] = usd(row['total'])

    return render_template("index.html", rows=rows, cash=usd(cash), total_cash=usd(total_cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares_str = request.form.get("shares")

        try:
            shares = int(shares_str)
        except ValueError:
            try:
                shares = int(shares_str)
                return apology("must provide whole number of shares", 400)
            except ValueError:
                return apology("shares must be a number", 400)

        stock = lookup(symbol)

        if not symbol:
            return apology("invalid symbol", 400)
        if not shares:
            return apology("must provide shares", 400)
        if shares <= 0:
            return apology("must provide positive interger", 400)
        if not int(shares):
            return apology("no", 400)
        if stock == None:
            return apology("invalid stock", 400)

        cost = stock['price'] * shares

        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = balance[0]['cash']

        if cash < cost:
            return apology("insufficient funds")

        newcash = cash - cost

        portfolio = db.execute("SELECT * FROM trades WHERE user_id = ? AND symbol = ?", session["user_id"], stock['symbol'])
        if len(portfolio) != 0:
            owned = portfolio[0]['shares']
            newshares = owned + shares
            db.execute("UPDATE trades SET shares = ? WHERE user_id = ? AND symbol = ?", newshares, session["user_id"], stock['symbol'])
        else:
            db.execute("INSERT INTO trades (user_id, symbol, shares, price) VALUES(?, ?, ?, ?)", session["user_id"], stock['symbol'], shares, stock['price'])

        timestamp=datetime.datetime.now()

        db.execute("UPDATE users SET cash = ? WHERE id = ?", newcash, session["user_id"])

        db.execute("INSERT INTO history (user_id, symbol, method, shares, price, transacted) VALUES (?, ?, ?, ?, ?, ?)", session["user_id"], stock['symbol'], "bought", shares, stock['price'], timestamp)
        flash('Bought!')
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transaction = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])
    for row in transaction:
        row['price'] = usd(row['price'])

    return render_template("history.html", transaction=transaction)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)


        if not symbol:
            return apology("missing symbol", 400)
        if stock == None:
            return apology("invalid stock", 400)

        cost = usd(stock['price'])

        return render_template("quoted.html", stock=stock, cost=cost)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = :username", username=username)

        # Ensure username doesnt exist
        if len(rows) != 0:
            return apology("this username already exists", 400)

        #register user to db
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

        # Remember which user has logged in
        user_id = db.execute("SELECT id FROM users WHERE username = ?", (username,)) [0]["id"]

        session["user_id"] = user_id


        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock = lookup(symbol)

        rows = db.execute("SELECT * FROM trades WHERE user_id = ? AND symbol = ?", session["user_id"], stock['symbol'])

        if not shares:
            return apology("must provide shares", 400)
        elif len(rows) != 1:
            return apology("no trades found", 400)
        elif symbol == None:
            return apology("invalid, select symbol")

        owned = rows[0]['shares']
        shares = int(shares)

        if shares > owned:
            return apology("not enough shares", 400)

        cost = stock['price'] * shares
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = cash[0]['cash']
        newcash = cash + cost
        db.execute("UPDATE users SET cash = ? WHERE id = ?", newcash, session["user_id"])

        timestamp=datetime.datetime.now()
        aftershares = owned - shares
        db.execute("UPDATE trades SET shares = ? WHERE user_id = ? AND symbol = ?", aftershares, session["user_id"], stock['symbol'])

        db.execute("INSERT INTO history (user_id, symbol, method, shares, price, transacted) VALUES (?, ?, ?, ?, ?, ?)", session["user_id"], stock['symbol'], "sold", shares, stock['price'], timestamp)
        flash('Sold!')
        return redirect("/")

    else:

        stocks = db.execute("SELECT  symbol FROM trades WHERE user_id = ?", session["user_id"])
        return render_template("sell.html", stocks=stocks)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == 'POST':
        deposit = int(request.form.get("amount"))
        if deposit <= 0:
            return apology("Deposit must be greater than 0", 400)

        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = rows[0]['cash']

        cash = cash + deposit

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
        flash('Deposit processed!')
        return redirect("/")
    else:
        return render_template("deposit.html")
