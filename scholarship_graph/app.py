__author__ = "Jeremy Nelson"

import xml.etree.ElementTree as etree
import re
import requests

from flask import Flask, render_template, redirect, request, session, url_for
from .forms import LoginForm, SearchForm
from .sparql import ORG_INFO, ORG_LISTING, ORG_PEOPLE, PERSON_HISTORY
from .sparql import PERSON_INFO, PREFIX, RESEARCH_STMT

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')

@app.template_filter("get_history")
def person_history(person_iri):
    ul = etree.Element("ul")
    result = requests.post(app.config.get("TRIPLESTORE_URL"),
        data={"query": PERSON_HISTORY.format(person_iri),
              "format": "json"})
    bindings = result.json().get("results").get("bindings")
    for row in bindings:
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
    result = requests.post(app.config.get("TRIPLESTORE_URL"),
        data={"query": sparql,
              "format": "json"})
    bindings = result.json().get("results").get("bindings")
    for row in bindings:
        return row.get("statement").get("value")
    return ''
    
@app.route("/org")
def org_browsing():
    org_iri = request.args.get("uri")
    org_info = {"people":dict(),
                "url": org_iri, 
                "years": dict()} 
    result = requests.post(app.config.get("TRIPLESTORE_URL"),
        data={"query": ORG_INFO.format(org_iri),
              "format": "json"})
    bindings = result.json().get("results").get("bindings")
    for row in bindings:
        if not "name" in org_info:
            org_info["name"] = row.get("label").get("value")
        year_iri = row.get("year").get("value")
        org_info["years"][year_iri] = {"label": row.get("year_label"),
                                       "people": []}
    result = requests.post(app.config.get("TRIPLESTORE_URL"),
        data={"query": ORG_PEOPLE.format(org_iri),
              "format": "json"})
    bindings = result.json().get("results").get("bindings")
    for row in bindings:
        person_iri = row.get("person").get("value")
        event = row.get("event").get("value")
        org_info["years"][event]["people"].append(person_iri)
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
    person_info = {"url": person_iri}
    result = requests.post(app.config.get("TRIPLESTORE_URL"),
        data={"query": PERSON_INFO.format(person_iri),
              "format": "json"})
    bindings = result.json().get("results").get("bindings")
    for row in bindings:
        email = row.get('email').get('value')
        if "email" in person_info:
            person_info["email"].append(email)
            continue
        person_info["givenName"] = row.get("given").get("value")
        person_info["familyName"] = row.get("family").get("value")
        person_info["email"] = [email,]
    return render_template("person.html",
        info=person_info)

@app.route("/results")
def search_results():
    people = session.get("people", [])
    query = session.get("query", [])
    return render_template("search-results.html",
        query=query,
        people=people)

@app.route("/search", methods=["POST"])
def search_triplestore():
    search_form = SearchForm()
    session['query'] = []
    results = __people_search__(search_form.person.raw_data)
    session['people'] = results
    return redirect("/results")

def __people_search__(raw_people):
    people = []
    sparql = PREFIX
    sparql += """
SELECT ?person ?label
WHERE {
    ?person rdf:type bf:Person;
           schema:familyName ?family;
           rdfs:label ?label . """
    for token in re.split(r"(\w+)", " ".join(raw_people)):
        if len(token) < 1: continue
        session["query"].append(token)
        sparql += """\nFILTER(CONTAINS(?label, "{0}"))""".format(token)
    sparql += "} ORDER BY ?family"
    result = requests.post(app.config.get("TRIPLESTORE_URL"),
        data={"query": sparql,
              "format": "json"})
    bindings = result.json().get("results").get("bindings")
    for row in bindings:
        people.append({"iri": row.get("person").get("value"),
                       "name": row.get("label").get("value")})
    return people

@app.route("/login")
def cc_login():
    return "In login"

@app.route("/")
def home():
    search_form = SearchForm()
    result = requests.post(app.config.get("TRIPLESTORE_URL"),
        data={"query": ORG_LISTING,
              "format": "json"})
    bindings = result.json().get('results').get('bindings')
    for row in bindings:
        search_form.department.choices.append(
            (row.get('iri').get('value'),
             row.get('label').get('value')))
    return render_template("index.html", 
        login=LoginForm(),
        search_form=search_form)
