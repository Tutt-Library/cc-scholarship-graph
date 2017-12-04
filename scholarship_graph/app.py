__author__ = "Jeremy Nelson"

from flask import Flask, render_template
from .forms import LoginForm, SearchForm

app = Flask(__name__)
app.config["SECRET_KEY"] = "1234"

@app.route("/login")
def cc_login():
    return "In login"

@app.route("/")
def home():
    return render_template("index.html", 
        login=LoginForm(),
        search_form=SearchForm())
