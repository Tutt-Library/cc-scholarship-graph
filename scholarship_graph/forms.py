__author__ = "Jeremy Nelson"

from flask_wtf import FlaskForm
from wtforms import HiddenField, PasswordField, SelectField, StringField 
from wtforms import TextAreaField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class SearchForm(FlaskForm):
    person = StringField('Person name')
    department = SelectField("Academic Department", choices=[('nil', 'None')])
    keywords = StringField('Keywords')

class ProfileForm(FlaskForm):
    display_label = HiddenField()
    email = StringField("Email")
    family_name = StringField("Family (last) name")
    given_name = StringField("Given (first) name")
    iri = HiddenField()
    research_stmt = TextAreaField("Research Statement")
