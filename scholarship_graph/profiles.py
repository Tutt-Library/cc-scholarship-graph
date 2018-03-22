"""Profiles for Scholarship App"""
__author__ = "Jeremy Nelson"

import datetime
import hashlib
import uuid

import rdflib
from flask import current_app
from github import Github

from .sparql import EMAIL_LOOKUP, SUBJECTS_IRI
from .sparql import add_qualified_generation, add_qualified_revision 

#BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
#SCHEMA = rdflib.Namespace("http://schema.org/")

class GitProfile(object):

    def __init__(self, config):
        self.graph_hashes = {}
        cc_github = Github(config.get("GITHUB_USER"),
                           config.get("GITHUB_PWD"))
        self.triplestore_url = config.get("TRIPLESTORE_URL")
        self.tutt_github = cc_github.get_organization("Tutt-Library")
        self.tiger_repo = self.tutt_github.get_repo("tiger-catalog")
        self.scholarship_repo = self.tutt_github.get_repo("cc-scholarship-graph")
        self.cc_people_git = self.tiger_repo.get_file_contents(
            "/KnowledgeGraph/cc-people.ttl",
            ref="development")
        self.cc_people = rdflib.Graph()
        self.cc_people.parse(data=self.cc_people_git.decoded_content,
            format='turtle')
        self.graph_hashes["cc_people"] = hashlib.sha1(
            self.cc_people.serialize(format='n3')).hexdigest()
        now = datetime.datetime.utcnow()
        if now.month < 7:
            start_year = now.year - 1
            end_year = now.year
        else:
            start_year = now.year
            end_year = now.year + 1
        self.current_year_path = "/KnowledgeGraph/cc-{0}-{1}.ttl".format(
                start_year, end_year)
        self.current_year_git = self.tiger_repo.get_file_contents(
            self.current_year_path,
            ref="development")
        self.current_year = rdflib.Graph()
        self.current_year.parse(data=self.current_year_git.decoded_content,
            format='turtle')
        self.graph_hashes["current_year"] = hashlib.sha1(
            self.current_year.serialize(format='n3')).hexdigest()
        self.research_statements = rdflib.Graph()
        self.research_statements_git = self.scholarship_repo.get_file_contents(
            "/data/cc-research-statements.ttl")
        self.research_statements.parse(
            data=self.research_statements_git.decoded_content,
            format='turtle')
        self.graph_hashes["research_statements"] = hashlib.sha1(
            self.research_statements.serialize(format='n3')).hexdigest()

        self.fast_subjects = rdflib.Graph()
        self.fast_subjects_git = self.scholarship_repo.get_file_contents(
            "/data/cc-fast-subjects.ttl")
        self.fast_subjects.parse(
            data=self.fast_subjects_git.decoded_content,
            format='turtle')
        self.graph_hashes["fast_subjects"] = hashlib.sha1(
            self.fast_subjects.serialize(format='n3')).hexdigest()


    def __save_graph__(self, **kwargs):
        git_repo = kwargs.get("git_repo") 
        file_path = kwargs.get("file_path")
        graph_name = kwargs.get("graph_name")
        branch = kwargs.get("branch")
        message = kwargs.get("message", "Updating {}".format(graph_name))
        graph = getattr(self, graph_name)
        graph_sha1 = hashlib.sha1(graph.serialize(format='n3')).hexdigest()
        #click.echo("{}: org={}\ncurrent={} are equal? {}\n\n".format(
        #    graph_name,
        #    self.graph_hashes[graph_name],
        #    graph_sha1,
        #    graph_sha1 == self.graph_hashes[graph_name]))
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
            message="{} {} to CC People".format(action, person_label),
            branch="development")
        self.__save_graph__(
            git_repo=self.tiger_repo,
            file_path=self.current_year_path,
            graph_name="current_year",
            message="{} person to Department for school year".format(action),
            branch="development")
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
        if connection:
            self.__reload_triplestore__(connection)

    def __reload_triplestore__(self, connection):
        # Deletes existing triplestore if blazegraph
        if connection.datastore.type == "blazegraph":
            requests.delete(self.triplestore_url)
            # Reloads all of CC's base Knowledge Graph
            for row in self.tiger_repo.get_dir_contents("/KnowledgeGraph",
                ref="development"):
                raw_turtle = self.tiger_repo.get_file_contents(
                    row.path,
                    ref="development")
                requests.post(self.triplestore_url,
                    data=raw_turtle,
                    headers={"Content-Type": "text/turtle"})
            # Reloads Scholarship graphs
            for row in self.scholarship_repo.get_dir_content("/data"):
                raw_turtle = self.scholarship_REPO.get_file_contents(row.path)
                requests.post(triplestore_url,
                    data=raw_turtle,
                    headers={"Content-Type": "text/turtle"})
        else:
            import pdb; pdb.set_trace()

def add_profile(**kwargs):
    """Adds a profile stub to scholarship graph"""
    config = kwargs.get("config")
    output = ''
    git_profile = GitProfile(config)
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

def update_profile(**kwargs):
    """Updates existing triples based on form values"""
    config_manager = kwargs.get('config_manager')
    connection = config_manager.conns
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
                 rdflib.RDFS.label,
                 rdflib.Literal(fast_label, lang="en")))
    git_profile.update_all(person_iri, "Update", connection)
    return output
