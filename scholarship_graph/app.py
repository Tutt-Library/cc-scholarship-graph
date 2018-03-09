"""Flask web application for Colorado College Scholarship Database"""
__author__ = "Jeremy Nelson","Diane Westerfield"

import base64
import datetime
import os
import re
import xml.etree.ElementTree as etree
from collections import OrderedDict
import requests
import rdflib
import uuid

from flask import Flask, jsonify, render_template, redirect, request, session 
from flask import current_app, url_for
from flask_login import login_required, login_user, logout_user, current_user
from flask_login import LoginManager, UserMixin
from flask_ldap3_login import LDAP3LoginManager
from flask_ldap3_login import log as ldap_manager_log
from flask_ldap3_login.forms import LDAPLoginForm


from .forms import ProfileForm, SearchForm
from github import Github
from .sparql import add_qualified_generation, add_qualified_revision
from .sparql import CITATION, EMAIL_LOOKUP, ORG_INFO, ORG_LISTING, ORG_PEOPLE
from .sparql import PERSON_HISTORY, PERSON_INFO, PERSON_LABEL, PREFIX, PROFILE
from .sparql import RESEARCH_STMT, SUBJECTS, SUBJECTS_IRI
from rdfframework.configuration import RdfConfigManager



app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')
CONFIG_MANAGER = RdfConfigManager(app.config)
CONNECTION = CONFIG_MANAGER.conns
BF = CONFIG_MANAGER.nsm.bf
SCHEMA = CONFIG_MANAGER.nsm.schema

cc_github = Github(app.config.get("GITHUB_USER"),
                   app.config.get("GITHUB_PWD"))
tutt_github = cc_github.get_organization("Tutt-Library")
TIGER_REPO = tutt_github.get_repo("tiger-catalog")
SCHOLARSHIP_REPO = tutt_github.get_repo("cc-scholarship-graph")

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
    if hasattr(user, 'data'):
        return user.data.get("mail") in app.config.get("ADMINS")
    return False

@app.route("/academic-profile", methods=["POST", "GET"])
@login_required
def academic_profile():
    """Displays Personal Academic Profile and allows 
    authenticated users to edit their own profile"""
    if request.method.startswith("POST"):
        if request.form.get("iri") is None:
            msg = __add_profile__(request.form)
        else:
            msg = __update_profile__(request.form)
        return jsonify({"message": msg})
    email = current_user.data.get("mail")
    label = current_user.data.get("displayName")
    familyName = current_user.data.get("sn")
    givenName = current_user.data.get("givenName")
    fields = {"email": email, 
              "family_name": familyName, 
              "given_name": givenName}
    results = CONNECTION.datastore.query(
        PROFILE.format(familyName, givenName, email))
    if len(results) == 1:
        fields["iri"] = results[0].get("person").get("value")
        if "statement" in results[0]:
            fields["research_stmt"] = results[0].get('statement').get('value')
    profile_form = ProfileForm(**fields)
    subjects = CONNECTION.datastore.query(
        SUBJECTS.format(email))
    return render_template('academic-profile.html',
                           scholar=current_user, 
                           form=profile_form,
                           subjects=subjects)

class GitProfile(object):

    def __init__(self):
        self.cc_people_git = TIGER_REPO.get_file_contents(
            "/KnowledgeGraph/cc-people.ttl",
            ref="development")
        self.cc_people = rdflib.Graph()
        self.cc_people.parse(data=self.cc_people_git.decoded_content,
            format='turtle')
        now = datetime.datetime.utcnow()
        if now.month < 7:
            start_year = now.year - 1
            end_year = now.year
        else:
            start_year = now.year
            end_year = now.year + 1
        self.current_year_path = "/KnowledgeGraph/cc-{0}-{1}.ttl".format(
                start_year, end_year)
        self.current_year_git = TIGER_REPO.get_file_contents(
            self.current_year_path,
            ref="development")
        self.current_year = rdflib.Graph()
        self.current_year.parse(data=self.current_year_git.decoded_content,
            format='turtle')
        
        self.research_statements = rdflib.Graph()
        self.research_stmts_git = SCHOLARSHIP_REPO.get_file_contents(
            "/data/cc-research-statements.ttl")
        self.research_statements.parse(
            data=self.research_stmts_git.decoded_content,
            format='turtle')
        self.fast_subjects = rdflib.Graph()
        self.fast_subjects_git = SCHOLARSHIP_REPO.get_file_contents(
            "/data/cc-fast-subjects.ttl")
        self.fast_subjects.parse(
            data=self.fast_subjects_git.decoded_content,
            format='turtle')
    
    def update_all(self, person_label, action="Add"):
        TIGER_REPO.update_file("/KnowledgeGraph/cc-people.ttl",
            "{} {} to CC People".format(action, person_label),
            self.cc_people.serialize(format='turtle'),
            self.cc_people_git.sha,
            branch="development")
        TIGER_REPO.update_file(self.current_year_path,
            "{} person to Department for school year".format(action),
            self.current_year.serialize(format='turtle'),
            self.current_year_git.sha,
            branch="development")
        SCHOLARSHIP_REPO.update_file("/data/cc-research-statements.ttl",
            "{} Research Statement for {}".format(action, person_label),
            self.research_statements.serialize(format='turtle'),
            self.research_stmts_git.sha)
        SCHOLARSHIP_REPO.update_file("/data/cc-fast-subjects.ttl",
            "Fast subject added",
            self.fast_subjects.serialize(format='turtle'),
            self.fast_subjects_git.sha)



       
def __add_profile__(**kwargs):
    """Adds a profile stub to scholarship graph"""
    output = ''
    git_profile = GitProfile()
    generated_by = rdflib.URIRef(kwargs.get("generated_by"))
    person_uri = kwargs.get("uri")
    if person_uri is None:
        person_uri = "http://catalog.coloradocollege.edu/{}".format(
            uuid.uuid1())
    person_iri = rdflib.URIRef(person_uri)
    git_profile.cc_people.add(
        (person_iri, 
         rdflib.RDF.type, 
         BF.Person.rdflib))
    label = kwargs.get("label")
    if label is not None:
        git_profile.cc_people.add(
            (person_iri, 
             rdflib.RDFS.label, 
             rdflib.Literal(label, lang="en")))
    given_name = kwargs.get("given_name")
    if given_name is not None:
        git_profile.cc_people.add(
            (person_iri,
             SCHEMA.givenName.rdflib,
             rdflib.Literal(given_name, lang="en")))
    family_name = kwargs.get("family_name")
    if family_name is not None:
        git_profile.cc_people.add((person_iri,
            SCHEMA.familyName.rdflib,
            rdflib.Literal(family_name, lang="en")))
    if label is None:
        label = "{} {}".format(given_name, family_name)
        git_profile.cc_people.add((person_iri,
            rdflib.RDFS.label,
            rdflib.Literal(label, lang="en")))
    email = kwargs.get("email")
    if email is not None:
        self.cc_people.add((person_iri,
            SCHEMA.email.rdflib,
            rdflib.Literal(email)))
    add_qualified_generation(git_profile.cc_people, 
        person_iri, 
        generated_by)
    dept_year = kwargs.get("year-iri")
    if dept_year is not None:
        dept_year_iri = rdflib.URIRef(dept_year_iri)
        title = kwargs.get("title-iri")
        git_profile.current_year.add(
            (dept_year_iri, 
             rdflib.URIRef(title),
             person_iri))
    statement = kwargs.get("statement")
    if statement is not None:
        statement_iri = rdflib.URIRef("http://catalog.coloradocollege.edu/{}".format(
            uuid.uuid1()))
        git_profile.research_statements.add(
            (statement_iri,
             rdflib.RDF.type,
             SCHEMA.DigitalDocument.rdflib))
        git_profile.research_statements.add(
            (statement_iri,
             rdflib.RDFS.label,
             rdflib.Literal("Research Statement for {}".format(label),
                lang="en")))
        git_profile.research_statements.add(
            (statement_iri,
             SCHEMA.accountablePerson.rdflib,
             person_iri))
        git_profile.research_statements.add(
            (statement_iri,
             SCHEMA.description.rdflib,
             rdflib.Literal(statement, lang="en")))
        add_qualified_generation(git_profile.research_statements, 
            statement_iri, 
            generated_by)
    git_profile.save(label)
    return output

def __update_profile__(form):
    """Updates existing triples based on form values"""
    git_profile = GitProfile()
    output = ''
    person_iri = rdflib.URIRef(form.get("iri"))
    results = CONNECTION.datastore.query(
        EMAIL_LOOKUP.format(
            current_user.data.get('mail').lower()))
    if len(results) > 0:
        generated_by = rdflib.URIRef(results[0].get("person").get('value'))
    else:
        generated_by = person_iri
    statement_iri = git_profile.research_statements.value(
        predicate=SCHEMA.accountablePerson.rdflib,
        object=person_iri)
    if statement_iri is None:
        statement_iri = rdflib.URIRef(
            "http://catalog.coloradocollege.edu/{}".format(uuid.uuid1()))
        git_profile.research_statements.add(
            (statement_iri, 
             rdflib.RDF.type, 
             SCHEMA.DigitalDocument.rdflib))
        git_profile.research_statements.add(
            (statement_iri, 
             SCHEMA.accountablePerson.rdflib, 
             person_iri))
        git_profile.research_statements.add(
            (statement_iri, 
             rdflib.RDFS.label, 
             rdflib.Literal("Research Statement for {} {}".format(
                form.get('given_name'),
                form.get('family_name')), lang="en")))
        add_qualified_generation(
            git_profile.research_statements, 
            statement_iri, 
            generated_by)
    else:
        add_qualified_revision(git_profile.research_statements, 
            statement_iri, 
            generated_by)    
    statement = form.get("research_stmt")
    existing_stmt = git_profile.research_statements.value(
        subject=statement_iri,
        predicate=SCHEMA.description.rdflib)
    if existing_stmt and str(existing_stmt) != statement:
        git_profile.research_statements.remove(
            (statement_iri, 
             SCHEMA.description.rdflib, 
             existing_stmt))
    git_profile.research_statements.add(
        (statement_iri, 
         SCHEMA.description.rdflib, 
         rdflib.Literal(statement, lang="en")))
    form_subjects = form.getlist("subjects")
    new_subjects = {} 
    for row in form_subjects:
        fast_id, fast_label = row.split("==")
        if fast_id.startswith("http"):
            fast_uri = fast_id
        else:
            fast_uri = "http://id.worldcat.org/fast/{}".format(fast_id[3:])
        new_subjects[fast_uri] = fast_label
    subjects = CONNECTION.datastore.query(
        SUBJECTS_IRI.format(person_iri))
    # Remove any existing subjects that aren't current
    for row in subjects:
        existing_subject = row.get("subject").get("value")
        if not existing_subject in new_subjects:
            git_profile.research_statements.remove(
                (statement_iri,
                 SCHEMA.about.rdflib,
                 rdflib.URIRef(existing_subject)))
    for fast_subject, fast_label  in new_subjects.items():
        iri_subject = rdflib.URIRef(fast_subject)
        git_profile.research_statements.add(
            (statement_iri,
             SCHEMA.about.rdflib,
             iri_subject))
        existing_label = git_profile.fast_subjects.value(
            subject=iri_subject,
            predicate=rdflib.RDFS.label)
        if existing_label is None:
            git_profile.fast_subjects.add(
                (iri_subject, 
                 rdflib.RDFS.label,
                 rdflib.Literal(fast_label, lang="en")))
    git_profile.update_all(person_iri, "Update")
    return output

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

    subjects = CONNECTION.datastore.query(
        SUBJECTS.format(email))
    if len(subjects) > 0:
        person_info["subjects"] = subjects
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
            sparql += """\nFILTER(CONTAINS(lcase(str(?statement)), "{0}"))""".format(
                row.lower())
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
    info = {"subject": subject_iri}
      
    return render_template("subject.html",
        subject=info)

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

@app.template_filter("article_link_filter")
def article_link(citation):
	url = str(citation["url"]["value"])
	if url.startswith("http"):
		link = "<a href='" + url + "' target='_blank'>" + citation["name"]["value"]+"</a>"
	else:
		link = citation["name"]["value"]
	return(link)

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