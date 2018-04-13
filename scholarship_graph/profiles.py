"""Profiles for Scholarship App"""
__author__ = "Jeremy Nelson"

import base64
import datetime
import hashlib
import os
import pprint
import subprocess
import uuid

import click
import rdflib
import requests
from bs4 import BeautifulSoup
from flask import current_app
from github import Github, GithubException

import utilities
from .sparql import EMAIL_LOOKUP, SUBJECTS_IRI
from .sparql import add_qualified_generation, add_qualified_revision 

class GitProfile(object):

    def __init__(self, config):
        self.graph_hashes = {}
        cc_github = Github(config.get("GITHUB_USER"),
                           config.get("GITHUB_PWD"))
        self.triplestore_url = config.get("TRIPLESTORE_URL")
        self.tutt_github = cc_github.get_organization("Tutt-Library")
        # Start retrieving and parsing latest RDF for current academic year
        # and CC people
        now = datetime.datetime.utcnow()
        if now.month < 7:
            start_year = now.year - 1
            end_year = now.year
        else:
            start_year = now.year
            end_year = now.year + 1
        self.current_year_path = "/KnowledgeGraph/cc-{0}-{1}.ttl".format(
                start_year, end_year)
        self.current_year = rdflib.Graph()
        self.cc_people = rdflib.Graph()
        self.tiger_repo = self.tutt_github.get_repo("tiger-catalog")
        for content in self.tiger_repo.get_dir_contents("/KnowledgeGraph/"):
            raw_turtle = self.__get_content__("tiger_repo",
                                              content)
            if content.name.startswith(self.current_year_path.split("/")[-1]):
                self.current_year_git = content
                self.current_year.parse(data=raw_turtle,
                    format='turtle')
            if content.name.startswith("cc-people"):
                self.cc_people_git = content
                self.cc_people.parse(data=raw_turtle,
                    format='turtle')
        self.graph_hashes["cc_people"] = hashlib.sha1(
            self.cc_people.serialize(format='n3')).hexdigest()
        self.graph_hashes["current_year"] = hashlib.sha1(
            self.current_year.serialize(format='n3')).hexdigest()
        # Start retrieving and parsing latest RDF for creative works, 
        # research statements, and FAST subjects
        self.creative_works = rdflib.Graph()
        self.research_statements = rdflib.Graph()
        self.fast_subjects = rdflib.Graph()
        self.scholarship_repo = self.tutt_github.get_repo("cc-scholarship-graph")
        for content in self.scholarship_repo.get_dir_contents("/data/"):
            raw_turtle = self.__get_content__("scholarship_repo",
                                              content)
            if content.name.startswith("cc-research-statements"):
                self.research_statements_git = content
                self.research_statements.parse(
                    data=raw_turtle,
                    format='turtle')
            if content.name.startswith("cc-fast-subjects"):
                self.fast_subjects_git = content
                self.fast_subjects.parse(
                    data=raw_turtle,
                    format='turtle')
            if content.name.startswith("creative-works"):
                self.creative_works_git = content
                self.creative_works.parse(
                    data=raw_turtle,
                    format='turtle')
        self.graph_hashes["creative_works"] = hashlib.sha1(
            self.creative_works.serialize(format='n3')).hexdigest()
        self.graph_hashes["research_statements"] = hashlib.sha1(
            self.research_statements.serialize(format='n3')).hexdigest()
        self.graph_hashes["fast_subjects"] = hashlib.sha1(
            self.fast_subjects.serialize(format='n3')).hexdigest()

    def __get_content__(self, repo_name, content):
        raw_turtle = None
        try:
            raw_turtle = content.decoded_content
        except GithubException:
            repo = getattr(self, repo_name)
            blob = repo.get_git_blob(content.sha)
            raw_turtle = base64.b64decode(blob.content)
        return raw_turtle

    def __save_graph__(self, **kwargs):
        git_repo = kwargs.get("git_repo") 
        file_path = kwargs.get("file_path")
        graph_name = kwargs.get("graph_name")
        branch = kwargs.get("branch")
        message = kwargs.get("message", "Updating {}".format(graph_name))
        graph = getattr(self, graph_name)
        graph_sha1 = hashlib.sha1(graph.serialize(format='n3')).hexdigest()
        if graph_sha1 == self.graph_hashes[graph_name]:
            return
        git_graph = getattr(self, "{}_git".format(graph_name))
        if branch:
            git_repo.update_file(file_path,
                message,
                graph.serialize(format='turtle'),
                git_graph.sha,
                branch=branch)
        else:
            git_repo.update_file(file_path,
                message,
                graph.serialize(format='turtle'),
                git_graph.sha)
                
    
    def update_all(self, person_label, action="Add", connection=None):
        self.__save_graph__(
            git_repo=self.tiger_repo,
            file_path="/KnowledgeGraph/cc-people.ttl",
            graph_name="cc_people",
            message="{} {} to CC People".format(action, person_label))
        self.__save_graph__(
            git_repo=self.tiger_repo,
            file_path=self.current_year_path,
            graph_name="current_year",
            message="{} person to Department for school year".format(action))
        self.__save_graph__(
            git_repo=self.scholarship_repo,
            file_path="/data/cc-research-statements.ttl",
            graph_name="research_statements",
            message="{} Research Statement for {}".format(
                action, person_label))
        self.__save_graph__(
            git_repo=self.scholarship_repo,
            file_path ="/data/cc-fast-subjects.ttl",
            graph_name="fast_subjects",
            message="Fast subject added")
        self.__save_graph__(
            git_repo=self.scholarship_repo,
            file_path ="/data/creative-works.ttl",
            graph_name="creative_works",
            message="Creative Works added")
        if connection:
            self.__reload_triplestore__(connection)

    def __reload_triplestore__(self, config_mgr):
        data_upload = []
        for row in config_mgr.get("CONNECTIONS"):
            if row.get("name").startswith("datastore"):
                for directory_row in row.get("data_upload"):
                    data_upload.append(directory_row[1])
        # Pull in the latest changes in each repository
        for directory in data_upload:
            os.chdir(directory)
            result = subprocess.run(['git', 'pull', 'origin', 'master'])
            click.echo(result.returncode, result.stdout)
        config_mgr.conns.datastore.mgr.reset()

def __generate_citation_html__(citation):
    soup = BeautifulSoup("", 'lxml')
    div = soup.new_tag("div", **{"class": "row citation"})
    col_1 = soup.new_tag("div", **{"class": "col-8"})
    if hasattr(citation, "article_title"):
        name = citation.article_title
    elif hasattr(citation, "title"):
        name = citation.title
    if hasattr(citation, "url"):
        work_link = soup.new_tag("a", href=citation.url)
        work_link.string = name
        col_1.append(work_link)
    else:
        span = soup.new_tag("span")
        span.string = name
        col_1.append(span)
    if hasattr(citation, "journal_title"):
        em = soup.new_tag("em")
        em.string = citation.journal_title
        col_1.append(em)
    if hasattr(citation, "year"):
        span = soup.new_tag("span")
        span.string = "({0})".format(citation.year)
        col_1.append(span)
    if hasattr(citation, "volume_number") and len(citation.volume_number) > 0:
        span = soup.new_tag("span")
        span.string = "v. {}".format(citation.volume_number)
        col_1.append(span)
    if hasattr(citation, "issue_number") and len(citation.issue_number) > 0:
        span = soup.new_tag("span")
        span.string = " no. {}".format(citation.issue_number)
        col_1.append(span)
    if hasattr(citation, "page_start") and len(citation.page_start) > 0:
        span = soup.new_tag("span")
        span.string = "p. {}".format(citation.page_start)
        col_1.append(span)
    if hasattr(citation, "page_end") and len(citation.page_end) > 0:
        span = soup.new_tag("span")
        if hasattr(citation, "page_start"): 
            page_string = "- {}."
        else:
            page_string = "{}."
        span.string = page_string.format(citation.page_end)
        col_1.append(span)
    div.append(col_1)
    col_2 = soup.new_tag("div", **{"class": "col-4"})
    if hasattr(citation, "doi_iri"):
        edit_click = "editCitation('{}');".format(citation.doi_iri)
        delete_click = "deleteCitation('{}');".format(
            citation.doi_iri)
    elif hasattr(citation, "bib_uri"):
        edit_click = "editCitation('{}');".format(citation.bib_iri)
        delete_click = "deleteCitation('{}');".format(
            citation.doi_iri)
    edit_a = soup.new_tag("a", **{"class": "btn btn-warning",
                                 "onclick": edit_click,
                                 "type=": "input"})
    edit_a.append(soup.new_tag("i", **{"class": "fas fa-edit"}))
    col_2.append(edit_a)
    delete_a = soup.new_tag("a", **{"class": "btn btn-danger",
                                   "onclick": delete_click,
                                   "type=": "input"})
    delete_a.append(soup.new_tag("i", **{"class": "fas fa-trash-alt"}))
    col_2.append(delete_a)
    div.append(col_2)
    return div.prettify()
 
                                       
        
def add_creative_work(**kwargs):
    """Calls utilities to populate and save to datastore"""
    config = kwargs.get("config")
    git_profile = GitProfile(config)
    current_user = kwargs.get("current_user")
    config_manager = kwargs.get('config_manager')
    connection = config_manager.conns
    generated_by = kwargs.get("generated_by")
    raw_citation = kwargs.get("citation")
    work_type = kwargs.get("work_type", "article")
    BF = config_manager.nsm.bf
    SCHEMA = config_manager.nsm.schema
    sparql = EMAIL_LOOKUP.format(
            current_user.data.get('mail').lower())
    email_results = connection.datastore.query(sparql)
    if len(email_results) > 0:
        generated_by = rdflib.URIRef(
            email_results[0].get("person").get('value'))

    if work_type.startswith("article"):
        citation = utilities.Article_Citation(raw_citation,
            git_profile.creative_works,
            git_profile.cc_people,
            False)
        citation.populate()
        citation.populate_article()
        citation.add_article()
    elif work_type.startswith("book"):
        citation = utilities.Book_Citation(raw_citation,
            git_profile.creative_works,
            git_profile.cc_people,
            False)
        citation.poulate()
        citation.populate_book()
        citation.add_book()
    if generated_by:
        if hasattr(citation, "bib_iri") :
            work_iri = citation.bib_iri
        elif hasattr(citation, "doi_iri"):
            work_iri = citation.doi_iri
        add_qualified_generation(git_profile.creative_works, 
            work_iri, 
            generated_by)
    
    #! with open("D:/2018/tmp/creative_works.ttl", "wb+") as fo:
    #!    fo.write(git_profile.creative_works.serialize(format='turtle'))
    git_profile.__save_graph__(
        git_repo=git_profile.scholarship_repo,
        file_path="/data/creative-works.ttl",
        graph_name="creative_works")
    git_profile.__reload_triplestore__(connection)
    return {"message": "Added {} to Scholarship".format(work_type),
            "status": True,
            "html":  __generate_citation_html__(citation),
            "iri": work_iri}
          

    


def add_profile(**kwargs):
    """Adds a profile stub to scholarship graph"""
    config = kwargs.get("config")
    git_profile = GitProfile(config)
    current_user = kwargs.get("current_user")
    config_manager = kwargs.get('config_manager')
    connection = config_manager.conns
    BF = config_manager.nsm.bf
    SCHEMA = config_manager.nsm.schema
    results = connection.datastore.query(
        EMAIL_LOOKUP.format(
            current_user.data.get('mail').lower()))
    if len(results) > 0:
        generated_by = rdflib.URIRef(results[0].get("person").get('value'))
    else:
        generated_by = None
    form = kwargs.get("form")
    if form.get("orcid"):
        person_uri = form.get("orcid")
    else:
        person_uri = "http://catalog.coloradocollege.edu/{}".format(
            uuid.uuid1())
    person_iri = rdflib.URIRef(person_uri)
    if generated_by is None:
        generated_by = person_iri
    git_profile.cc_people.add(
        (person_iri, 
         rdflib.RDF.type, 
         BF.Person.rdflib))
    
    given_name = form.get("given_name")
    if given_name is not None:
        git_profile.cc_people.add(
            (person_iri,
             SCHEMA.givenName.rdflib,
             rdflib.Literal(given_name, lang="en")))
    family_name = form.get("family_name")
    if family_name is not None:
        git_profile.cc_people.add((person_iri,
            SCHEMA.familyName.rdflib,
            rdflib.Literal(family_name, lang="en")))
    label = "{} {}".format(given_name, family_name)
    git_profile.cc_people.add((person_iri,
        rdflib.RDFS.label,
        rdflib.Literal(label, lang="en")))
    email = form.get("email")
    git_profile.cc_people.add((person_iri,
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
    statement = kwargs.get("statement", form.get("research_stmt"))
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
    git_profile.update_all(person_iri, "Add", config_manager)
    #with open("D:/2018/tmp/cc-people.ttl", "wb+") as fo:
    #
    #    fo.write(git_profile.cc_people.serialize(format='turtle'))

    return "Added {} as {} to Colorado College's Scholarship Graph".format(
        label,
        person_iri)

def update_profile(**kwargs):
    """Updates existing triples based on form values"""
    config_manager = kwargs.get('config_manager')
    connection = config_manager.conns
    BF = config_manager.nsm.bf
    SCHEMA = config_manager.nsm.schema
    
    form = kwargs.get('form')
    current_user = kwargs.get("current_user")
    git_profile = GitProfile(config_manager) 
    output = ''
    person_iri = rdflib.URIRef(form.get("iri"))
    results = connection.datastore.query(
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
    subjects = connection.datastore.query(
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
                 rdflib.RDF.type,
                 BF.Topic.rdflib)) 
            git_profile.fast_subjects.add(
                (iri_subject, 
                 rdflib.RDFS.label,
                 rdflib.Literal(fast_label, lang="en")))
    git_profile.update_all(person_iri, "Update", config_manager)
    return output


