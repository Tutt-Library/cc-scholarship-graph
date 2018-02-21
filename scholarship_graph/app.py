"""Flask web application for Colorado College Scholarship Database"""
__author__ = "Jeremy Nelson","Diane Westerfield"

import datetime
import re
import xml.etree.ElementTree as etree
from collections import OrderedDict
import requests

from flask import Flask, render_template, redirect, request, session, url_for
from flask_login import login_required, login_user, logout_user, current_user
from flask_login import LoginManager, UserMixin
from flask_ldap3_login import LDAP3LoginManager
from flask_ldap3_login import log as ldap_manager_log
from flask_ldap3_login.forms import LDAPLoginForm


from .forms import ProfileForm, SearchForm
from .sparql import ORG_INFO, ORG_LISTING, ORG_PEOPLE, PERSON_HISTORY
from .sparql import PERSON_INFO, PREFIX, RESEARCH_STMT, CITATION
from rdfframework.configuration import RdfConfigManager

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')
CONFIG_MANAGER = RdfConfigManager(app.config)
CONNECTION = CONFIG_MANAGER.conns

login_manager = LoginManager(app)
ldap_manager = LDAP3LoginManager(app)



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
    

@app.template_filter("get_statement")
def research_statement(person_iri):
    sparql = RESEARCH_STMT.format(person_iri)
    results = CONNECTION.datastore.query(sparql)
    for row in results:
        return row.get("statement").get("value")
    return ''

@app.template_filter("is_admin")
def is_administrator(user):
    if hasattr(user, 'mail'):
        print(user.mail, user.mail in app.config.ADMINS)
        if user.mail in app.config.ADMINS:
            return True
    return False

@app.route("/academic-profile", methods=["POST", "GET"])
@login_required
def academic_profile():
    """Displays Personal Academic Profile and allows 
    authenticated users to edit their own profile"""
    email = current_user.data.get("mail")
    label = current_user.data.get("displayName")
    familyName = current_user.data.get("sn")
    givenName = current_user.data.get("givenName")
    
    profile_form = ProfileForm(email=email, 
        family_name=familyName, 
        given_name=givenName)
    
    return render_template('academic-profile.html',
                           scholar=current_user, 
                           form=profile_form)
    

    
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
        info=org_info)    


@app.route("/person")
def person_view():
    person_iri = request.args.get("iri")
    person_info = {"url": person_iri,"citations":[]}
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
    return render_template("person.html",
        user=current_user,
        info=person_info)

@app.route("/results")
def search_results():
    query = session.get("query", {})
    results = __people_search__(query['person'])
    results.extend(__keyword_search__(query['keywords']))
    return render_template("search-results.html",
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
    output = []
    if len(keywords) < 1:
        return output
    sparql = PREFIX
    sparql += """
SELECT ?person ?label ?statement
WHERE {
    ?person rdf:type bf:Person ;
            schema:familyName ?family;
            rdfs:label ?label .
    ?research_statement schema:accountablePerson ?person ;
            schema:description ?statement ."""
    for token in keywords:
        for row in token.split(","):
            if len(row) < 1: continue
            sparql += """\nFILTER(CONTAINS(?statement, "{0}"))""".format(row)
    sparql += "} ORDER BY ?person"""
    result = requests.post(app.config.get("TRIPLESTORE_URL"),
        data={"query": sparql,
              "format": "json"})
    bindings = result.json().get('results').get('bindings')
    for row in bindings:
        output.append({"iri": row.get("person").get("value"),
                       "name": row.get("label").get("value"),
                       "statement": row.get("statement").get("value")})
    return output
         

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
            sparql += """\nFILTER(CONTAINS(?label, "{0}"))""".format(token)
    sparql += "} ORDER BY ?family"
    results = CONNECTION.datastore.query(sparql)
    for row in results:
        output.append({"iri": row.get("person").get("value"),
                       "name": row.get("label").get("value")})
    return output


@app.route("/login", methods=['POST'])
def cc_login():
    """Login Method """
    form = LDAPLoginForm()
    validation = form.validate_on_submit()
    if validation:
        login_user(form.user)
        return redirect(url_for('academic_profile'))
    else:
        return redirect(url_for('home'))

@app.route('/logout', methods=['POST'])
def cc_logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/")
def home():
    search_form = SearchForm()
    results = CONNECTION.datastore.query(ORG_LISTING)
    for row in results:
        search_form.department.choices.append(
            (row.get('iri').get('value'),
             row.get('label').get('value')))
    return render_template("index.html", 
        login=LDAPLoginForm(),
        search_form=search_form,
        scholar=current_user)
