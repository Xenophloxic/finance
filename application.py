import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)

API_KEY = "pk_f507f61009fb484eb46457ad1314dc4f"

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.globals.update(usd=usd, lookup=lookup, int=int)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

os.environ["API_KEY"] = "pk_f507f61009fb484eb46457ad1314dc4f"

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # get user cash total
    result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = result[0]['cash']

    # pull all transactions belonging to user
    portfolio = db.execute("SELECT stock, quantity FROM portfolio")

    if not portfolio:
        return apology("sorry you have no holdings")

    grand_total = cash

    # determine current price, stock total value and grand total value
    for stock in portfolio:
        price = lookup(stock['stock'])['price']
        total = stock['quantity'] * price
        stock.update({'price': price, 'total': total})
        grand_total += total

    return render_template("index.html", stocks=portfolio, cash=cash, total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html") # check for GET

    else: # Check for POST
        if not request.form.get("symbol"): # Check for a symbol
            return apology("please choose a symbol")

        elif not request.form.get("shares"): # Check for a vaild number of shares
            return apology("please choose an amount of shares")

        else:
            quote = lookup(request.form.get("symbol")) # lookup a quote
            if not quote:
                return apology("Symbol not found") # see if symbol is found
            else:
                cost = quote["price"] * int(request.form.get('shares')) # get the price
                money = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"]) # find money
                if cost > money[0]["cash"]:
                    return apology("you do not have enough cash for this transaction") # check for enough money
                else:
                    db.execute("UPDATE users SET cash=cash-:cost WHERE id=:id", cost=cost, id=session["user_id"]) # insert new money
                    # add transaction to transaction database
                    add_transaction = db.execute("INSERT INTO transactions (user_id, stock, quantity, price, date) VALUES (:user_id, :stock, :quantity, :price, :date)",
                        user_id=session["user_id"], stock=quote["symbol"], quantity=int(request.form.get("shares")), price=quote['price'], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                    # pull number of shares of symbol in portfolio
                    curr_portfolio = db.execute("SELECT quantity FROM portfolio WHERE stock=:stock", stock=quote["symbol"])

                    # add to portfolio database
                    # if symbol is new, add to portfolio
                    if not curr_portfolio:
                        db.execute("INSERT INTO portfolio (stock, quantity) VALUES (:stock, :quantity)",
                            stock=quote["symbol"], quantity=int(request.form.get("shares")))

                    # if symbol is already in portfolio, update quantity of shares and total
                    else:
                        db.execute("UPDATE portfolio SET quantity=quantity+:quantity WHERE stock=:stock",
                            quantity=int(request.form.get("shares")), stock=quote["symbol"]);

                    flash("Bought!")
                    return redirect("/")




@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    # pull all transactions belonging to user
    portfolio = db.execute("SELECT stock, quantity, price, date FROM transactions WHERE user_id=:id", id=session["user_id"])

    if not portfolio:
        return apology("sorry you have no transactions on record")

    return render_template("history.html", stocks=portfolio)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    if request.method == "GET": # renders default template if GET method
        return render_template('quote.html')

    elif request.method == "POST": # renders template for POST

        if not request.form.get("symbol"): # checks for a symbol, makes sure there is one
            return apology("please indecate a symbol")

        else:
            symbol = request.form.get("symbol") # lookups a quote
            quote = lookup(symbol)

        if not quote:
            return apology("symbol not found") # if there is no symbol found

        else:
            return render_template('quoted.html', name=quote["name"], price=quote["price"], symbol=symbol) # return a page



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""


    if request.method == "GET": # check for method
        return render_template("register.html")

    elif request.method == "POST": # check for another method

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username")) # find in database to see if username is taken

        if not request.form.get("username"): # check for blank username
            return apology("you cannot have a blank username")

        elif not request.form.get("password"): # check for blank password
            return apology("you cannot have a blank password")

        elif request.form.get("password") != request.form.get("password_confirm"): # make passwords match
            return apology("password and password confirmation must match")

        elif len(rows) == 1:
            return apology("This username is already taken") # error if username is taken


        else:
            hashed = generate_password_hash(request.form.get("password")) # hash password
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=hashed) # insert data
            return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure stock symbol and number of shares was submitted
        if (not request.form.get("stock")) or (not request.form.get("shares")):
            return apology("must provide stock symbol and number of shares")

        # ensure number of shares is valid
        if int(request.form.get("shares")) <= 0:
            return apology("must provide valid number of shares (integer)")

        available = db.execute("SELECT quantity FROM portfolio WHERE :stock=stock", stock=request.form.get("stock"))

        # check that number of shares being sold does not exceed quantity in portfolio
        if int(request.form.get("shares")) > available[0]['quantity']:
            return apology("You may not sell more shares than you currently hold")

        # pull quote from yahoo finance
        quote = lookup(request.form.get("stock"))

        # check is valid stock name provided
        if quote == None:
            return apology("Stock symbol not valid, please try again")

        # calculate cost of transaction
        cost = quote['price']

        # update cash amount in users database
        db.execute("UPDATE users SET cash=cash+:cost WHERE id=:id", cost=cost, id=session["user_id"]);

        # add transaction to transaction database
        add_transaction = db.execute("INSERT INTO transactions (user_id, stock, quantity, price, date) VALUES (:user_id, :stock, :quantity, :price, :date)",
            user_id=session["user_id"], stock=quote["symbol"], quantity=-int(request.form.get("shares")), price=quote['price'], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # update quantity of shares and total
        if available[0]['quantity'] == 1:
            db.execute("DELETE FROM portfolio WHERE stock=:stock",
                 stock=quote["symbol"]);
        else:
            db.execute("UPDATE portfolio SET quantity=quantity-:quantity WHERE stock=:stock",
                quantity=int(request.form.get("shares")), stock=quote["symbol"]);

        flash("Sold!")
        return redirect("/")

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        # pull all transactions belonging to user
        portfolio = db.execute("SELECT stock FROM portfolio")

        return render_template("sell.html", stocks=portfolio)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
