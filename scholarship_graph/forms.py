__author__ = "Jeremy Nelson"

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class SearchForm(FlaskForm):
    person = StringField('Person name')
    department = SelectField("Academic Department", choices=[('nil', 'None')])
    keywords = StringField('Keywords')

class ProfileForm(FlaskForm):
    family_name = StringField("Family (last) name")
    given_name = StringField("Given (first) name")
    orchid = StringField("ORCID")
    research_stmt = TextAreaField("Research Statement")
