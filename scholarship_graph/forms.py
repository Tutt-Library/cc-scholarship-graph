__author__ = "Jeremy Nelson"

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class SearchForm(FlaskForm):
    person = StringField('Person name')
    department = SelectField("Academic Department", choices=[('nil', 'None')])
    keywords = StringField('Keywords')

