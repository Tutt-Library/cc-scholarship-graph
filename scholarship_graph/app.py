"""Flask web application for Colorado College Scholarship Database"""
__author__ = "Jeremy Nelson","Diane Westerfield"


import datetime
import hashlib
import os
import re
import xml.etree.ElementTree as etree
from collections import OrderedDict
import click
import requests
import rdflib
import sys
import traceback
import uuid
import utilities


import email.mime.text as email_text
import mimetypes

from types import SimpleNamespace
from flask import Flask, jsonify, render_template, redirect, request, session 
from flask import abort, current_app, url_for, flash
from flask_login import login_required, login_user, logout_user, current_user
from flask_login import LoginManager, UserMixin
from flask_ldap3_login import LDAP3LoginManager
from flask_ldap3_login import log as ldap_manager_log
from flask_ldap3_login.forms import LDAPLoginForm

from jinja2 import contextfilter

from .forms import ProfileForm, SearchForm, ArticleForm, BookForm
from github import Github
from .sparql import add_qualified_generation, add_qualified_revision
from .sparql import CITATION, BOOK_CITATION,EMAIL_LOOKUP, ORG_INFO, ORG_LISTING, ORG_PEOPLE
from .sparql import PERSON_HISTORY, PERSON_INFO, PERSON_LABEL, PREFIX, PROFILE
from .sparql import RESEARCH_STMT, SUBJECTS, SUBJECTS_IRI
from .sparql import COUNT_ARTICLES, COUNT_BOOKS, COUNT_JOURNALS, COUNT_ORGS, COUNT_PEOPLE
from .sparql import COUNT_BOOK_AUTHORS, WORK_INFO
from .profiles import add_creative_work, add_profile, update_profile
from rdfframework.configuration import RdfConfigManager



app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')
CONFIG_MANAGER = RdfConfigManager(app.config, 
    verify=False, 
    delay_check=True)
CONNECTION = CONFIG_MANAGER.conns
BF = CONFIG_MANAGER.nsm.bf
SCHEMA = CONFIG_MANAGER.nsm.schema

login_manager = LoginManager(app)
ldap_manager = LDAP3LoginManager(app)

PROJECT_BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
USERS = OrderedDict()

class Scholar(UserMixin):

    def __init__(self, dn, username, data):
        self.dn = dn
        self.username = username
        self.data = data

    def __repr__(self):
        return self.dn

    def get_id(self):
        return self.dn

# LDAP decorators
@ldap_manager.save_user
def save_user(dn, username, data, memberships):
    user = Scholar(dn, username, data)
    USERS[dn] = user
    return user

@login_manager.user_loader
def user_loader(user_id):
    if user_id in USERS:
        return USERS[user_id]
    return None

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html", scholar=current_user), 404

def __send_email__(info):
    sender = app.config.get('EMAIL')['user']
    recipients = info.get('recipients') 
    subject = info.get('subject')
    text = info.get('text')
    message = """From: <{0}>
To: <{1}>
Subject: {2}


{3}""".format(
        sender,
        ",".join(recipients),
        subject,
        text)
    message = email_text.MIMEText(message, _charset="UTF-8")
    #try:
    server = smtplib.SMTP(app.config.get('EMAIL')['host'],
                              app.config.get('EMAIL')['port'])

    server.ehlo()
    if app.config.get('EMAIL')['tls']:
        server.starttls()
    server.ehlo()
    server.login(sender,
                 app.config.get("EMAIL")["password"])
    server.sendmail(sender, recipients, message.as_string())
    server.close()
    #except:
    #    print("Error trying to send email")
    #    return False
    return True

@app.errorhandler(500)
def server_error(e):
    click.echo("SERVER ERROR: {}".format(e))
    body = "Current user: {0}\nURL:{1}\nError:\n{2}".format(
        current_user,
        request.url,
        str(e))
    if app.config.get("DEBUG"):
        click.echo(body)
    else:
        __send_email__({"recipients": app.config.get("ADMINS"),
                        "subject": "CC Scholarship 500 Error",
                        "text": body})
        
    return render_template("500.html", scholar=current_user), 500 
    

@app.template_filter("get_history")
def person_history(person_iri):
    ul = etree.Element("ul")
    results = CONNECTION.datastore.query(PERSON_HISTORY.format(person_iri))
    for row in results:
        li = etree.SubElement(ul, "li")
        li.text = "{} ".format(row.get("rank").get("value"))
        org_link = etree.SubElement(li, "a")
        org_link.attrib["href"] = "{}#{}".format(url_for("org_browsing", 
            uri=row.get("org").get('value')),
            row.get("event").get('value'))
        org_link.text = row.get("year_label").get("value")
    return etree.tostring(ul).decode()
    
@app.template_filter("get_iri")
def extract_iri(row):
    if "article" in row:
        return row.get("article").get("value")
    elif "book" in row:
        return row.get("book").get('value')
    elif "person" in row:
        return row.get("person").get("value")
    return ''

@app.template_filter("get_stat")
@contextfilter
def generate_statistic(context, type_of):
    type_of = type_of.lower()
    if type_of.startswith("articles"):
        result = CONNECTION.datastore.query(COUNT_ARTICLES)
    elif type_of.startswith("authors"):
        result = CONNECTION.datastore.query(COUNT_BOOK_AUTHORS)
    elif type_of.startswith("book"):
        result = CONNECTION.datastore.query(COUNT_BOOKS)
    elif type_of.startswith("journal"):
        result = CONNECTION.datastore.query(COUNT_JOURNALS)
    elif type_of.startswith("org"):
        result = CONNECTION.datastore.query(COUNT_ORGS)
    elif type_of.startswith("users"):
        result = CONNECTION.datastore.query(COUNT_PEOPLE)
    else:
        result = None
    if result:
        return "{:,}".format(int(result[0].get("count").get("value")))

@app.template_filter("get_statement")
def research_statement(person_iri):
    sparql = RESEARCH_STMT.format(person_iri)
    results = CONNECTION.datastore.query(sparql)
    for row in results:
        return row.get("statement").get("value")
    return ''

@app.template_filter("is_admin")
def is_administrator(user):
    if hasattr(user, 'data'):
        return user.data.get("mail") in app.config.get("ADMINS")
    return False

@app.route("/academic-profile", methods=["POST", "GET"])
@login_required
def academic_profile():
    """Displays Personal Academic Profile and allows 
    authenticated users to edit their own profile"""
    fields = dict()
    if request.method.startswith("POST"):
        if len(request.form.get("iri")) < 1:
            msg = add_profile(
                form=request.form,
                config=app.config,
                config_manager=CONFIG_MANAGER,
                current_user=current_user)
        else:
            msg = "None"
            msg = update_profile(
                form=request.form, 
                config=app.config,
                config_manager=CONFIG_MANAGER,
                current_user=current_user)
        return jsonify({"message": msg})
    # Editing a profile as an admin
    elif "person" in request.args:
        person_iri = request.args.get("person")
        person_results = CONNECTION.datastore.query(
            PERSON_INFO.format(person_iri))
        fields["iri"] = person_iri
        for row in person_results:
            fields["email"] = row.get('email').get('value')
            fields["given_name"] = row.get("given").get("value")
            fields["family_name"] = row.get("family").get("value")
            fields["display_label"] = row.get("label").get("value")
    # Editing own profile
    else: 
        fields["email"] = current_user.data.get("mail")
        fields["family_name"] = current_user.data.get("sn")
        fields["given_name"] = current_user.data.get("givenName")
        fields["display_label"] = current_user.data.get("displayName")
    results = CONNECTION.datastore.query(
        PROFILE.format(fields.get("family_name"), 
            fields.get("given_name"), 
            fields.get("email")))
    if len(results) == 1:
        fields["iri"] = results[0].get("person").get("value")
        if "statement" in results[0]:
            fields["research_stmt"] = results[0].get('statement').get('value')
    profile_form = ProfileForm(**fields)
    citations = []
    if "iri" in fields:
        citation_sparql = CITATION.format(fields["iri"])
        citations_result = CONNECTION.datastore.query(citation_sparql)
        for row in citations_result:
            row['icon'] = 'fas fa-file-alt'
            citations.append(row)
        book_sparql = BOOK_CITATION.format(fields["iri"])
        book_result = CONNECTION.datastore.query(book_sparql)
        for row in book_result:
            row['icon'] = 'fas fa-book'
            citations.append(row)
    subjects = CONNECTION.datastore.query(
        SUBJECTS.format(fields.get("email")))
    
#    current_user = SimpleNamespace()
#    current_user.data = SimpleNamespace()
#    current_user.data.email = "testemail@email.com"
#    current_user.data.displayName = "Test User"
    return render_template('academic-profile.html',
                           scholar=current_user, 
                           form=profile_form,
                           citations=citations,
                           new_article_form = ArticleForm(),
                           book_form = BookForm(),
                           subjects=subjects)

       

@app.route("/fast")
def fast_suggest():
    term = request.args.get('q')
    start = request.args.get("start", 0)
    oclc_fast_base = "http://fast.oclc.org/searchfast/fastsuggest"
    url = "{}?query={}&wt=json&fl=suggestall&queryReturn=suggestall,id".format(
        oclc_fast_base,
        term)
    if int(start) > 0:
        url += "&start={}".format(start)
    fast_result = requests.get(url)
    return jsonify(fast_result.json().get("response").get('docs'))
    
    
@app.route("/org")
def org_browsing():
    org_iri = request.args.get("uri")
    org_info = {"people":dict(),
                "url": org_iri, 
                "years": dict()}
    now = datetime.datetime.utcnow()
    org_sparql =  ORG_INFO.format(org_iri, 
        now.isoformat())
    results = CONNECTION.datastore.query(org_sparql)
    for row in results:
        if not "name" in org_info:
            org_info["name"] = row.get("label").get("value")
        year_iri = row.get("year").get("value")
        org_info["years"][year_iri] = {"label": row.get("year_label"),
                                       "people": []}
    event_uri = list(org_info["years"].keys())[0]
    org_people_sparql = ORG_PEOPLE.format(event_uri)
    people_results = CONNECTION.datastore.query(org_people_sparql)
    for row in people_results:
        person_iri = row.get("person").get("value")
        org_info["years"][event_uri]["people"].append(person_iri)
        org_info["people"][person_iri] = {
            "name": row.get("name").get("value"),
            "rank": row.get("rank").get("value"),
            "statement": ""
        }
        if "statement" in row:
            org_info["people"][person_iri]["statement"] = \
                row.get('statement').get('value')
    # Dedup and Sort
    for event in org_info["years"]:
        org_info["years"][event]["people"] = list(
            set(org_info["years"][event]["people"]))
    org_info["years"][event]["people"].sort(
        key=lambda x: org_info["people"][x]["name"])
    return render_template("organization.html",
        scholar=current_user, 
        info=org_info)    


@app.route("/person")
def person_view():
    person_iri = request.args.get("iri")
    person_info = {"url": person_iri,
                   "citations":[],
                   "book_citations": []}
    sparql = PERSON_INFO.format(person_iri)
    results = CONNECTION.datastore.query(sparql)
    for row in results:
        email = row.get('email').get('value')
        if "email" in person_info:
            person_info["email"].append(email)
            continue
        person_info["givenName"] = row.get("given").get("value")
        person_info["familyName"] = row.get("family").get("value")
        person_info["email"] = [email,]
        
    citation_sparql = CITATION.format(person_iri)
    citations_result = CONNECTION.datastore.query(citation_sparql)
    for row in citations_result:
        person_info["citations"].append(row)

    book_citations_sparql = BOOK_CITATION.format(person_iri)
    book_citations_result = CONNECTION.datastore.query(book_citations_sparql)
    for row in book_citations_result:
        person_info["book_citations"].append(row)
    
    subjects = CONNECTION.datastore.query(
        SUBJECTS.format(email))
    if len(subjects) > 0:
        person_info["subjects"] = subjects
    return render_template("person.html",
        scholar=current_user,
        info=person_info)

@app.route("/results")
def search_results():
    query = session.get("query", {})
    results = __people_search__(query['person'])
    results.extend(__keyword_search__(query['keywords']))
    return render_template("search-results.html",
        scholar=current_user, 
        query=query,
        people=results)

@app.route("/search", methods=["POST"])
def search_triplestore():
    search_form = SearchForm()
    query = {"person": [], 
             "keywords": []}
    for token in re.split(r"(\w+)", " ".join(search_form.person.raw_data)):
        if len(token) < 1: continue
        query['person'].append(token)
    for token in [kw.strip() for kw in search_form.keywords.raw_data]:
        if len(token) < 1: continue
        query['keywords'].append(token)
    session['query'] = query
    return redirect(url_for("search_results"))

def __keyword_search__(keywords):
    output = dict()
    if len(keywords) < 1:
        return output
    subject_sparql = PREFIX
    subject_sparql += """
SELECT ?person ?subject ?label ?statement
WHERE {
    ?subject rdf:type bf:Topic;  
             rdfs:label ?label .
    ?statement_iri schema:about ?subject ;
                   schema:accountablePerson ?person ;
                   schema:description ?statement .        
    """  
    people_sparql = PREFIX 
    people_sparql += """
SELECT ?person ?statement
WHERE {
    ?person rdf:type bf:Person .
    ?research_statement schema:accountablePerson ?person ;
            schema:description ?statement ."""
    for token in keywords:
        for row in token.split(","):
            if len(row) < 1: continue
            people_sparql += """\nFILTER(CONTAINS(lcase(str(?statement)), "{0}"))""".format(
                row.lower())
            subject_sparql += """\nFILTER(CONTAINS(lcase(str(?label)), "{0}"))""".format(
                row.lower())
    subject_sparql += "} ORDER BY ?person"
    people_sparql += "} ORDER BY ?person"
    subject_result = CONNECTION.datastore.query(subject_sparql)
    for row in subject_result:
        person_iri = row.get("person").get("value")
        if person_iri in output:
            output[person_iri]["subjects"].append(
                {"iri": row.get("subject").get("value"),
                 "label": row.get("label").get("value")})
            output["weight"] += 1
        else:
            output[person_iri] = {"subjects": [
                {"iri": row.get("subject").get("value"),
                 "label": row.get("label").get("value")},],
                "iri": person_iri,
                "statement": row.get("statement").get("value"),
                "weight": 1}
    people_result = CONNECTION.datastore.query(people_sparql)
    for row in people_result:
        person_iri = row.get("person").get("value")
        if person_iri in output:
            output[person_iri]["weight"] += 1
        else:
            output[person_iri] = {
                "iri": person_iri,
                "statement": row.get("statement").get("value"),
                "weight": 1}
    for key in output.keys():
        name_result = CONNECTION.datastore.query(
            PERSON_LABEL.format(key))
        output[key]["name"] = name_result[0].get("label").get("value")
    return sorted(output.values(), key=lambda x: x['weight'])
         

def __people_search__(people):
    output = []
    if len(people) < 1:
        return output
    sparql = PREFIX
    sparql += """
SELECT ?person ?label
WHERE {
    ?person rdf:type bf:Person;
           schema:familyName ?family;
           rdfs:label ?label . """
    if people == ["*"]:
        sparql += "} "
    else:
        for token in people:
            sparql += """\nFILTER(CONTAINS(lcase(str(?label)), "{0}"))""".format(
                token.lower())
    sparql += "} ORDER BY ?family"
    results = CONNECTION.datastore.query(sparql)
    for row in results:
        output.append({"iri": row.get("person").get("value"),
                       "name": row.get("label").get("value")})
    return output

@app.route("/subject")
def subject_view():
    subject_iri = request.args.get("iri")
    info = {"subject": subject_iri, 
            "assignments": []}
    subject_prefix = PREFIX + """
SELECT ?label
WHERE {{
    BIND(<{0}> as ?subject)""".format(subject_iri)
    subject_sparql = subject_prefix + """
    ?subject rdfs:label ?label . }"""
    info["label"] = CONNECTION.datastore.query(subject_sparql)[0].get("label").get("value")
    person_sparql = PREFIX + """
SELECT ?person 
WHERE {{
    BIND(<{0}> as ?subject)
    ?stmt schema:about ?subject ;
          schema:accountablePerson ?person .}}""".format(subject_iri)
    for row in CONNECTION.datastore.query(person_sparql):
        person_iri = row.get("person").get("value")
        person_info = {"iri": person_iri}
        person_info.update(CONNECTION.datastore.query(
            PERSON_INFO.format(person_iri))[0])
        
        info["assignments"].append(person_info)
    return render_template("subject.html",
        scholar=current_user,
        subject=info)

@app.route("/login", methods=['GET', 'POST'])
def cc_login():
    """Login Method """
    form = LDAPLoginForm()
    if request.method.startswith("GET"):
        return render_template("login.html", 
            login=form, 
            scholar=current_user,
        )
    validation = form.validate_on_submit()
    if validation:
        login_user(form.user)
        return redirect(url_for('academic_profile'))
    else:
        flash("Invalid username or password")
        return render_template("login.html", 
            login=form,
            scholar=current_user)



@app.route('/logout', methods=['POST', 'GET'])
def cc_logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/work", methods=['POST'])
@login_required
def add_work():
    citation_type = request.form['citation_type']
    if citation_type.startswith("article"):
        work_form = ArticleForm(request.form)
    elif citation_type.startswith("book"):
        work_form = BookForm(request.form)
    if work_form.validate():
        try:
            raw_citation = {"ENTRYTYPE": citation_type,
                             "author": work_form.author_string.data,
                             "year": work_form.datePublished.data}
            if citation_type.startswith("article"):
                raw_citation["journal"]=work_form.journal_title.data
                raw_citation["title"]=work_form.article_title.data
                if work_form.page_start.data !=None:
                    raw_citation["page_start"]=work_form.page_start.data
                if work_form.page_end.data !=None:
                    raw_citation["page_end"]=work_form.page_end.data
                if work_form.month.data != None:
                    raw_citation["month"]=work_form.month.data
                if work_form.volume_number.data != None:
                    raw_citation["volume_number"]=work_form.volume_number.data
                if work_form.issue_number.data != None:
                    raw_citation["number"]=work_form.issue_number.data
                if work_form.doi.data != None:
                    raw_citation["doi"]=work_form.doi.data
                if work_form.url.data != None:
                    raw_citation["link"]=work_form.url.data
            elif citation_type.startswith("book-chapter"):
                pass
            elif citation_type.startswith("book"):
                raw_citation["title"] = work_form.book_title.data
            else:
                abort(500)
            if work_form.abstract.data != None:
                raw_citation["abstract"]=work_form.abstract.data
            output = add_creative_work(
                config=app.config,
                citation=raw_citation,
                config_manager=CONFIG_MANAGER,
                current_user=current_user,
                work_type=citation_type)
        except:
            click.echo("Error {}".format(
                traceback.print_tb(sys.exc_info()[-1])))
            output = {
                "message": """Work from journal {} not added, 
Error:\n{}""".format(
                    work_form.journal_title.data,
                    sys.exc_info()[0]),
                "status": False }
    else:
        output = {"message": "Invalid fields",
                  "status": False,
                  "errors": work_form.errors}
    return jsonify(output)

@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit_work():
    if request.method.startswith("GET"):
        uri = request.args.get("iri")
        results = CONNECTION.datastore.query(WORK_INFO.format(uri))
        click.echo("Results are {}\nSPARQ=\n{}".format(results, WORK_INFO.format(uri)))
        if not results or len(results) < 0:
            abort(404)
        if results[0].get("type").get("value").endswith("ScholarlyArticle"):
            article_form = ArticleForm()
            for key, value in results[0].items():
                if key.startswith("type"):
                    continue
                if key.startswith('name'):
                    article_form.article_title.data = value.get("value")
                elif hasattr(article_form, key):
                    field = getattr(article_form, key)
                    field.data = value.get('value')
            dialog_id = uri.split("/")[-1]
        return jsonify({"html": render_template("add-article-dlg.html",
                                    new_article_form=article_form,
                                    dialog_id=dialog_id),
                        "dialog-id": dialog_id})

@app.route("/")
def home():
    search_form = SearchForm()
    if len(search_form.department.choices) < 2:
        results = CONNECTION.datastore.query(ORG_LISTING)
        for row in results:
            search_form.department.choices.append(
                (row.get('iri').get('value'),
                 row.get('label').get('value')))
    return render_template("index.html", 
        login=LDAPLoginForm(),
        search_form=search_form,
        scholar=current_user)

@app.template_filter("article_link_filter")
def article_link(citation):
	url = str(citation["url"]["value"])
	if url.startswith("http"):
		link = "<a href='" + url + "' target='_blank'>" + citation["name"]["value"]+"</a>"
	else:
		link = citation["name"]["value"]
	return(link)

@app.template_filter("volume_issue_filter")
def volume_issue(citation):
	volume_issue_string = ""
	volume_number = ""
	issue_number = ""
	if "volume_number" in citation.keys():
		volume_number = str(citation["volume_number"]["value"])
	if "issue_number" in citation.keys():
		issue_number = str(citation["issue_number"]["value"])
		
	if volume_number != "":
		volume_issue_string = "v." + volume_number
		if issue_number != "":
			volume_issue_string = volume_issue_string + " no." + issue_number
	if volume_number == "" and issue_number != "":
		volume_issue_string = "no." + issue_number
	
	return(volume_issue_string)
	
@app.template_filter("page_number_filter")
def page_number(citation):
	page_string = ""
	page_start = ""
	page_end = ""
	if "page_start" in citation.keys():
		page_start = str(citation["page_start"]["value"])
	if "page_end" in citation.keys():
		page_end = str(citation["page_end"]["value"])
	if page_start != "":
		page_string = "p." + page_start
	if page_end != "":
		page_string = page_string + "-" + page_end
	if page_string != "":
		page_string = page_string + "."
	return(page_string)

@app.template_filter("book_title_filter")
def book_title(book_citation):
    title_string=""
    title = book_citation["title"]["value"] 
    uri = str(book_citation["book"]["value"])
    if uri.startswith("https://tiger.coloradocollege.edu/"):
        title_string = "<a href='" + uri + "', target='_blank'>" + title + "</a>"
    #elif book_citation["url"]["value"] != None and book_citation["url"]["value"] != "":
    #    title_string = "<a href='" + book_citation["url"]["value"] + ",target= 'blank'>" + title + "</a>"
    else:
        title_string = title
    return(title_string)

@app.template_filter("book_edition_filter")
def book_edition(book_citation):
    edition_string=""
    if "editionStatement" in book_citation.keys():
        if book_citation["editionStatement"]["value"] != "":
            ed = book_citation["editionStatement"]["value"]
            edition_string = ed + " ed. "
    return(edition_string)
