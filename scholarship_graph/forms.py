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

class CitationForm(FlaskForm):
    author_string = StringField("Full list of authors")
    CC_author = StringField("CC Author(s)",validators=[DataRequired()])
    year = StringField("Year of publication", validators=[DataRequired()])
    abstract = TextAreaField("Abstract")
    citation_type = SelectField("Citation type", choices=[('Article','Article'),('Book','Book')])

class ArticleForm(CitationForm):
    journal_title = StringField("Journal title",validators=[DataRequired()])
    doi = StringField("DOI number if present")
    #self.__url__()
    #self.__article__()
    #self.__month__()
    #self.__volume__()
    #self.__issue__()
