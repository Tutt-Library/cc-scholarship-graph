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
    author_string = StringField("Full list of authors, individual authors separated by semi-colons",validators=[DataRequired()])
    datePublished = StringField("Year of publication", validators=[DataRequired()])
    abstract = TextAreaField("Abstract")
    citation_type = HiddenField("Citation type")
    iri = HiddenField()

class ArticleForm(CitationForm):
    journal_title = StringField("Journal title",validators=[DataRequired()])
    doi = StringField("DOI number if present")
    url = StringField("Link, if no DOI number and link is available")
    article_title = StringField("Article title", validators=[DataRequired()])
    month = StringField("Month of publication")
    volume_number = StringField("Journal volume")
    issue_number = StringField("Issue number")
    page_start = StringField("Start page of article")
    page_end = StringField("End page of particle")

class BookForm(CitationForm):
    book_title = StringField("Book title",validators=[DataRequired()])
    isbn = StringField("ISBN")
    provisionActivityStatement = StringField("Place of publication and publisher, for example New York, XYZ Publisher")
    editionStatement = StringField("Edition statement, for example Second, Third, Fourth, etc.")
    url = StringField("Link to book, if available")
    notes = StringField("Additional notes")


