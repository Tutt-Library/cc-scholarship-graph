__author__ = "Diane Westerfield"

import uuid
import click
import codecs
import re
import sys
import pdb
from sys import exit
import rdflib
from rdflib import RDFS
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

# tip: export citations from RefWorks. Direct export from Web of Science does not work.
BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
CITATION_EXTENSION = rdflib.Namespace("https://www.coloradocollege.edu/library/ns/citation/")
SCHEMA = rdflib.Namespace("http://schema.org/")

def author_lookup(people_graph,lookup_string):
# check the people graph for a match on name
    sparql="""SELECT ?person
              WHERE {{
              ?person rdf:type bf:Person .
              ?person rdfs:label ?label .
              FILTER (CONTAINS (?label,"{0}"))
              }}""".format(lookup_string)

    results = people_graph.query(sparql)

    for i in results:
        return i[0]

def alternate_author_lookup(people_graph,lookup_string):
# check the people graph for a match on alternateName
    sparql="""SELECT ?person
              WHERE {{
              ?person rdf:type bf:Person .
              ?person schema:alternateName ?AN .
              FILTER (CONTAINS (?AN,"{0}"))
              }}""".format(lookup_string)

    results = people_graph.query(sparql)

    for i in results:
        return i[0]

def doi_lookup(creative_works,lookup_string):
# check the creative works graph for a match on doi so that duplicate articles are not created

    sparql="""SELECT ?doi_iri
            WHERE {{
            ?doi_iri rdf:type schema:ScholarlyArticle .
            FILTER(CONTAINS (str(?doi_iri),"{0}"))
            }}""".format(lookup_string)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]
    
def journal_lookup(creative_works,lookup_string):
# check the creative works graph for a match on journal title so that duplicate journals are not created
    sparql="""SELECT ?journal_iri
	      WHERE {{
	      ?journal_iri rdf:type schema:Periodical .
	      ?journal_iri schema:name ?label .    
              FILTER (regex(?label,"^{0}$"))
              }}""".format(lookup_string)
    results = creative_works.query(sparql)

    for i in results:
        return i[0]


def volume_lookup(creative_works,lookup_string,journal_iri):
# check the creative works graph for a match on journal volume so that duplicates are not created
    sparql="""SELECT ?volume
              WHERE {{
              BIND(<{1}> as ?journal_iri)
	      BIND("{0}" as ?label)
              ?volume rdf:type schema:volumeNumber .
              ?volume schema:volumeNumber ?label .
              ?volume schema:partOf ?journal_iri .
              }}""".format(lookup_string,journal_iri)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]

def issue_lookup(creative_works,lookup_string,journal_iri):
# check the creative works graph for a match on journal issue that is part of journal volume, so that duplicate issues are not created
    sparql="""SELECT ?issue
              WHERE {{
              BIND(<{1}> as ?journal_iri)
	      BIND("{0}" as ?label)
              ?issue rdf:type schema:issueNumber .
              ?issue schema:issueNumber ?label .
              ?issue schema:partOf ?journal_iri .
              }}""".format(lookup_string,journal_iri)


    results = creative_works.query(sparql)

    for i in results:
        return i[0]

def volume_issue_lookup(creative_works,volume_iri,lookup_issue):
# check the creative works graph for a match on journal issue that is part of journal volume, so that duplicate issues are not created
    sparql="""SELECT ?issue
              WHERE {{
              BIND(<{1}> as ?volume_iri)
              BIND("{0}" as ?issue_label)
              ?issue rdf:type schema:issueNumber .
              ?issue schema:issueNumber ?label .
              ?issue schema:partOf ?volume_iri .
              }}""".format(lookup_issue,volume_iri)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]

def book_uri_lookup(creative_works,lookup_string):
# check the creative works graph for a match on doi so that duplicate articles are not created

    sparql="""SELECT ?book_uri
            WHERE {{
            ?book_uri rdf:type bf:Book .
            FILTER(CONTAINS (str(?book_uri),"{0}"))
            }}""".format(lookup_string)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]

def isbn_lookup(creative_works,lookup_string):
    # check creative works graph to see if isbn already exists
    sparql = """SELECT ?book
                WHERE {{
                ?book rdf:type bf:Book .
                ?isbn bf:isbn ?label .
                FILTER(CONTAINS (?label),"{0}")
                }}""".format(lookup_string)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]

def book_title_lookup(creative_works,lookup_string):
# check the creative works graph to see if book title already exists
    sparql="""SELECT ?book
              WHERE {{
              ?book rdf:type bf:Book .
              ?book bf:title ?label .
              FILTER (CONTAINS (?label,"{0}"))
              }}""".format(lookup_string)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]  

# function to return unique IRI using UUID
def unique_IRI(self):
        unique_IRI="http://catalog.coloradocollege.edu/{}".format(uuid.uuid1())
        return rdflib.URIRef(unique_IRI)


class Citation(object):

    def __init__(self, 
            raw_citation, 
            creative_works, 
            people, 
            is_interactive=True):
        self.raw_citation=raw_citation
        self.creative_works=creative_works
        self.people = people
        self.is_interactive=is_interactive

    def __unique_IRI__(self):
        unique_IRI="http://catalog.coloradocollege.edu/{}".format(uuid.uuid1())
        return rdflib.URIRef(unique_IRI)

    def populate(self):
        self.__author_string__()
        self.__CC_author__()
        self.__year__()
        self.__abstract__()
        self.__citation_type__()
        
    def __author_string__(self):
        self.author_string = self.raw_citation["author"]
        self.author_string = self.author_string.replace(" and ",", ")
        # add period to end of string
        if self.author_string[len(self.author_string)-1] != ".":
            self.author_string = self.author_string + "."

    def __CC_author__(self):
        
        # to do: account for multiple CC authors. Currently this will take the last match.
        # to do: what happens if there are no matches?
        self.cc_authors=[]
        default = " and "
        delimiters = [";", ","]
        delimiters.append(default)
        for row in delimiters:
            if row in self.raw_citation["author"]:
                default = row
                break 
        for name in self.raw_citation["author"].split(default):
            family_name=""
            given_name=""
            name_parsed=""
            author_name_parsed=""
            author_iri=""

            #to do: regex expression that covers all parsing
            #import pdb;pdb.set_trace()
            name = name.strip()
            if name.endswith("."):
                name = name[:-1]
            if "." in name:
                try:
                    # GivenName Initial FamilyName ex. Jane C. Doe
                    name_parsed = re.search(r"(\w+)\s\w?\.\s(\w+\-?\w+)",name).groups()
                except:
                    # Initial GivenName FamilyName ex. C. Jane Doe
                    if re.search(r"w?\.\s(\w+)\s(\w+\-?\w+)",name) != None:
                        name_parsed = re.search(r"w?\.\s(\w+)\s(\w+\-?\w+)",name).groups()
                    # Initial Initial FamilyName ex. J. C. Doe
                    elif re.search(r"(\w+\.)\s(\w+\.)\s(\w+)",name) != None:
                        name_parsed = re.search(r"(\w+\.)\s(\w+\.)\s(\w+)",name).groups()
                    # GivenName Initial Initial Family Name ex. Jane C. D. Doe
                    elif re.search(r"(\w+)\s\w?\.\s\w?\.\s(\w+\-?\w+)",name) !=None:
                        name_parsed = re.search(r"(\w+)\s\w?\.\s\w?\.\s(\w+\-?\w+)",name).groups()       
                    # Initial FamilyName ex. J. Doe
                    elif re.search(r"(\w+\.)\s(\w+)",name) != None:
                        name_parsed = re.search(r"(\w+\.)\s(\w+)",name).groups()
                else:
                    name_parsed = []
                    for word in name.split(" "):
                        word = word.strip()
                        if word != None or word != "":
                            name_parsed.append(word)

                    
            else: # GivenName [middle name] FamilyName ex. Jane Doe or Jane Carla Doe
                name_parsed = []
                for word in name.split(" "):
                    name_parsed.append(word)
            # print("The name is",name_parsed,"for ",self.raw_citation["title"])

            given_name = name_parsed[0]
            family_name = name_parsed[len(name_parsed)-1]
            author_name_parsed = given_name + " " + family_name            
            author_name_parsed = author_name_parsed.strip()


            if author_lookup(self.people, author_name_parsed) != None:
                author_iri=author_lookup(self.people, author_name_parsed)
                # print("Author",author_name_parsed,"found in author lookup")
                self.cc_authors.append(author_iri)
            elif alternate_author_lookup(self.people, author_name_parsed) != None:
                author_iri=alternate_author_lookup(self.people, author_name_parsed)
                # print("Author",author_name_parsed,"found in alternate author lookup")
                self.cc_authors.append(author_iri)
            #to do: code to search on family name plus initial first letter of givenname?
            else:
                # print("Author",author_name_parsed,"not found")
                pass
               
        # attempt to salvage a citation with no matched CC authors        
        if self.cc_authors == [] and self.is_interactive:
            print("The following citation is lacking one or more CC authors: ")
            print(self.raw_citation)
            user_submission=input("No CC author found, input one CC author, or multiple authors separated by semicolons >")
            if user_submission=="":
                print("ERROR NO CC AUTHOR",self.raw_citation)
                sys.exit(0)
            else:
                for person in user_submission.split(";"):
                    has_id = input("Does this person have an ORCID (o) or CCID (c) or no ID and needs one (n)?")
                    in_graph = input("Does this person already exist in the people graph? (y) or (n)")
                    if has_id == "o":
                        author_iri = input("ORCID >")
                    elif has_id == "c":
                        author_iri = input("CCID >")
                    elif has_id == "n":
                        author_iri = "http://catalog.coloradocollege.edu/{}".format(uuid.uuid1())
                        print("Author_iri assigned ",author_iri)
                    else:
                        print("NOT UNDERSTOOD, QUITTING")
                        sys.exit(0)
                    author_iri=rdflib.URIRef(author_iri)
                    self.cc_authors.append(author_iri)
                    if in_graph == "n":                                                
                        people.add((author_iri,rdflib.RDF.type, BF.Person))
                        people.add((author_iri,RDFS.label,rdflib.Literal(person,lang="en")))
                        given_name=input("What is the author's given (first) name?")
                        people.add((author_iri,SCHEMA.givenName,rdflib.Literal(given_name,lang="en")))
                        family_name=input("What is the author's family name?")
                        people.add((author_iri,SCHEMA.familyName,rdflib.Literal(family_name,lang="en")))
                        email=input("What is the person's email?")
                        people.add((author_iri,SCHEMA.email,rdflib.Literal(email)))
                        with open("C:/CCKnowledgeGraph/tiger-catalog/KnowledgeGraph/cc-people.ttl","wb+") as fo:
                            fo.write(people.serialize(format="turtle"))
                        print("YOU STILL NEED TO ADD THIS PERSON TO THE ACADEMIC YEAR GRAPH(s)")

        if self.cc_authors == []:
            if self.is_interactive:
                print("ERROR NO CC AUTHOR",self.raw_citation)
            sys.exit(0)

        #check cc_authors list for valid URIRef
        i = 0
        while i < len(self.cc_authors):      
            if type(self.cc_authors[i]) != rdflib.term.URIRef:
                self.cc_authors[i]=rdflib.URIRef(self.cc_authors[i])
            i = i + 1
        if self.is_interactive:
            print("CC Authors: ",self.cc_authors,"for ",self.raw_citation["title"])
        

    def __year__(self):
        if "year" in self.raw_citation.keys():
            self.year = self.raw_citation["year"]         
        else:
            self.year = ""

    def __abstract__(self):
        if "abstract" in self.raw_citation.keys():
            self.abstract = self.raw_citation["abstract"]
        else:
            self.abstract = ""

    def __citation_type__(self):
        self.citation_type=self.raw_citation["ENTRYTYPE"]

                                      
class Article_Citation(Citation):
    def __init__(self,
            raw_citation, 
            creative_works, 
            people,
            is_interactive=True):
        super(Article_Citation, self).__init__(
            raw_citation,
            creative_works,
            people,
            is_interactive)

    def populate_article(self):
        self.__journal_title__()
        self.__doi__()
        self.__url__()
        self.__article__()
        self.__month__()
        self.__volume__()
        self.__issue__()

    def __journal_title__(self):
        self.journal_title = self.raw_citation["journal"]
        # check for duplicates
        journal_str = journal_lookup(self.creative_works,self.journal_title)
        if journal_str != None:
            self.journal_string=journal_str
        else:
            self.journal_string = self.__unique_IRI__()
        self.journal_iri=rdflib.URIRef(self.journal_string)

        # add issn if present in raw citation; currently noted as isbn in bibtex format
        if "isbn" in self.raw_citation.keys():
            self.journal_issn=self.raw_citation["isbn"]
        else:
            self.journal_issn=""
        #if "eissn" in self.raw_citation.keys():
        #    self.journal_eissn=self.raw_citation["eissn"]
        #else:
        #    self.journal_eissn=""

    def __article__(self):
        # information specific to the article itself
        self.article_title = self.raw_citation["title"]

        self.page_start = ""
        self.page_end = ""
        if "pages" in self.raw_citation.keys():
            pages = self.raw_citation["pages"]
            if "-" in pages:
                pages = pages.replace(" ","") # remove extraneous spaces
                pages = pages.replace("--","-") # turn double hyphens into single hypens
                hyphen = pages.find("-")
                self.page_start = pages[:hyphen]
                self.page_end = pages[hyphen+1:]
            else:
                self.page_start=pages
    
    def __url__(self):
        # If there is a real doi, turn it into a doi link. If there is no doi, look for exported link from RefWorks.
        # Please note some citations have a doi field entry which isn't a real doi but a base link.
        self.url = ""
        if "doi" in self.raw_citation.keys() and len(self.raw_citation["doi"]) > 0:
            if self.raw_citation["doi"].startswith("http") == False:
                self.url="https://doi.org/" + self.raw_citation["doi"]
        elif "link" in self.raw_citation.keys():
            #if self.raw_citation["link"].startswith("http"):
            self.url = self.raw_citation["link"]

    def __month__(self):
        
        if "month" in self.raw_citation.keys():
            self.month=self.raw_citation["month"]
        else:
            self.month=""
       
    def __doi__(self):
        # doi is the unique identifier for articles
        if "doi" in self.raw_citation.keys() and len(self.raw_citation["doi"]) > 0:
            self.doi_string = self.raw_citation["doi"]
            self.doi_string = "https://doi.org/" + self.doi_string
            self.doi_iri=rdflib.URIRef(self.doi_string)
        else:
            self.doi_iri=self.__unique_IRI__()
        if doi_lookup(self.creative_works, self.doi_iri) != None: 
            if self.is_interactive:
                print("ERROR DUPLICATE DOI FOUND",self.raw_citation["doi"])
            sys.exit(0)


    def __volume__(self):
        # a citation can have a volume number or none at all
        self.volume_number=""
        if "volume" in self.raw_citation.keys():
            if (self.raw_citation["volume"] != None):
                self.volume_number = self.raw_citation["volume"]
                if self.raw_citation["volume"] != "" or self.raw_citation["volume"] != None:
                    #check for duplicates else assign new iri for volume
                    if volume_lookup(self.creative_works, self.volume_number,self.journal_iri):
                        self.volume_iri = volume_lookup(self.creative_works,self.volume_number,self.journal_iri)
                    else:    
                        self.volume_iri = self.__unique_IRI__()     
        
    def __issue__(self):
        # a journal can have no issue numbers, issue numbers as part of a volume, or issues without volume numbering
        # logic of avoiding duplicates has to sit in add_article()
        self.issue_number=""
        if "number" in self.raw_citation.keys():
            if (self.raw_citation["number"] !="") or (self.raw_citation["number"] != None):
                self.issue_number = self.raw_citation["number"]
                self.issue_iri = self.__unique_IRI__()
  
    def add_article(self):
        # Business logic for adding citations
        # print(self.raw_citation)
        # add the journal title
        if doi_lookup(self.creative_works, self.doi_iri):
            if self.is_interactive:
                print("Article exists!")
            sys.exit(0)
        
        self.creative_works.add((self.journal_iri,rdflib.RDF.type,SCHEMA.Periodical))
        self.creative_works.add((self.journal_iri,SCHEMA.name,rdflib.Literal(self.journal_title,lang="en")))
        # add the issn and/or eissn if present
        if self.journal_issn != "":
            self.creative_works.add((self.journal_iri,SCHEMA.issn,rdflib.Literal(self.journal_issn)))
        #if self.journal_eissn != "":
        #    self.creative_works.add((self.journal_iri,SCHEMA.eissn,rdflib.Literal(self.journal_eissn)))
        
        # add the article, using doi as unique identifier
        self.creative_works.add((self.doi_iri,rdflib.RDF.type,SCHEMA.ScholarlyArticle))
        self.creative_works.add((self.doi_iri,SCHEMA.name,rdflib.Literal(self.article_title,lang="en")))
        if self.page_start != "":
            self.creative_works.add((self.doi_iri,SCHEMA.pageStart,rdflib.Literal(self.page_start)))
        if self.page_end != "":
            self.creative_works.add((self.doi_iri,SCHEMA.pageEnd,rdflib.Literal(self.page_end)))
        
        # add url
        self.creative_works.add((self.doi_iri, SCHEMA.url, rdflib.URIRef(self.url)))

        # add the author
        for author in self.cc_authors:
            self.creative_works.add((self.doi_iri,SCHEMA.author,author))

        # add the author string
        self.creative_works.add((self.doi_iri,
                                 CITATION_EXTENSION.authorString,
                                 rdflib.Literal(self.author_string)))

        # add the publication year
        self.creative_works.add((self.doi_iri,SCHEMA.datePublished,rdflib.Literal(self.year)))

        # add the month.
        self.creative_works.add((self.doi_iri,CITATION_EXTENSION.month,rdflib.Literal(self.month)))

        # add the abstract
        self.creative_works.add((self.doi_iri,SCHEMA.about,rdflib.Literal(self.abstract)))

        # add the citation type
        self.creative_works.add((self.doi_iri,CITATION_EXTENSION.citationType,rdflib.Literal(self.citation_type)))
        
        # if there is no volume or issue number, add the article directly to the journal
        if (self.volume_number == "") and (self.issue_number == ""):
            self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.journal_iri))
            
        # if there is a volume but no issue number, and the volume is not prexisting, add the volume to the journal and add the article to the volume
        # else just add the article to the preexisting volume
        elif (self.volume_number != "") and (self.issue_number == ""):
            if volume_lookup(creative_works,self.volume_number,self.journal_iri) != None:
                self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.volume_iri))
            else:
                self.creative_works.add((self.volume_iri,rdflib.RDF.type,SCHEMA.volumeNumber))
                self.creative_works.add((self.volume_iri,SCHEMA.partOf,self.journal_iri))
                self.creative_works.add((self.volume_iri,SCHEMA.volumeNumber,rdflib.Literal(self.volume_number)))
                self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.volume_iri))

        # if there is no volume but there is an issue number, add the the issue to the journal and add the article to the issue
        elif (self.volume_number == "") and (self.issue_number != ""):
            #check for dups
            if issue_lookup(self.creative_works,self.issue_number,self.journal_iri) != None:
                self.issue_iri=issue_lookup(self.creative_works,self.issue_number,self.journal_iri)
                self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.issue_iri))
            else:
                self.creative_works.add((self.issue_iri,rdflib.RDF.type,SCHEMA.issueNumber))
                self.creative_works.add((self.issue_iri,SCHEMA.partOf,self.journal_iri))
                self.creative_works.add((self.issue_iri,SCHEMA.issueNumber,rdflib.Literal(self.issue_number)))
                self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.issue_iri))
            
        # presuming there is a volume and an issue, add the article to the issue, add the issue to the volume, add the volume to the journal
        # check for dups
        else:
            volume_check_iri=volume_lookup(creative_works,self.volume_number,self.journal_iri)
            if volume_issue_lookup(creative_works,volume_check_iri,self.issue_number) != None:
                issue_check_iri=volume_issue_lookup(creative_works,volume_check_iri,self.issue_number)
                self.creative_works.add((self.doi_iri,SCHEMA.partOf,issue_check_iri))
            else:
                self.creative_works.add((self.volume_iri,rdflib.RDF.type,SCHEMA.volumeNumber))
                self.creative_works.add((self.volume_iri,SCHEMA.partOf,self.journal_iri))
                self.creative_works.add((self.volume_iri,SCHEMA.volumeNumber,rdflib.Literal(self.volume_number)))
                self.creative_works.add((self.issue_iri,SCHEMA.partOf,self.volume_iri))
                self.creative_works.add((self.issue_iri,rdflib.RDF.type,SCHEMA.issueNumber))
                self.creative_works.add((self.issue_iri,SCHEMA.issueNumber,rdflib.Literal(self.issue_number)))
                self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.issue_iri))
                

class Book_Citation(Citation):
    def __init__(self, 
            raw_citation,
            creative_works,
            people,
            is_interactive=True):
        super(Book_Citation, self).__init__(
            raw_citation,
            creative_works,
            people,
            is_interactive)
        
    def populate_book(self):
        self.__title__()
        self.__publisher_provision__()
        self.__edition__()
        self.__editor__()
        self.__isbn__()
        self.__note__()
        self.__abstract__()
        self.__call__()
        self.__url__()

    def __title__(self):
        self.title=self.raw_citation["title"]

    def __citation_type__(self):
        # have to overwrite for book chapters so that the parent book is still a book
        self.citation_type = "book"

    def __publisher_provision__(self):
        if "publisher" in self.raw_citation.keys():
            self.publisher = self.raw_citation["publisher"]
        else:
            self.publisher = "[Publisher not identified]"
        if "address" in self.raw_citation.keys():
            self.publisher_address = self.raw_citation["address"]
        else:
            self.publisher_address = "[Place of publication not identified]"
        self.publisher_provision = ""
        self.publisher_provision = self.publisher_address + " : " + self.publisher + ", " + self.year 

    def __edition__(self):
        if "edition" in self.raw_citation.keys():
            self.edition = self.raw_citation["edition"]
        else:
            self.edition = ""

    def __editor__(self):
        # need to figure out how to differentiate between editors and authors
        editor=""
        # "editor" can refer to one or several editors
        if "editor" in self.raw_citation.keys():
            self.editor = self.raw_citation["editor"]
            self.editor = self.editor.replace(" and ","; ")

    def __isbn__(self):
        # may need code in here to isolate single ISBN, as there may be multiple in bib records exported to RefWorks
        # also the issue of inconsistent punctuation
        if "isbn" in self.raw_citation.keys():
            self.isbn = self.raw_citation["isbn"]
        else:
            self.isbn = ""

    def __note__(self):
        if "note" in self.raw_citation.keys():
            self.note = self.raw_citation["note"]
        else:
            self.note = ""

    def __call__(self):
        if "call" in self.raw_citation.keys():
            self.call = self.raw_citation["call"]
        else:
            self.call = ""

    def __url__(self):
        if "link" in self.raw_citation.keys():
            if self.raw_citation["link"].startswith("http"):
                self.url = self.raw_citation["link"]
        elif "url" in self.raw_citation.keys():
            if self.raw_citation["link"].startswith("http"):
                self.url = self.raw_citation["url"]
        else:
            self.url = ""

    def add_book(self):

        #bib number as unique ID?
        if "bib" in self.raw_citation.keys():
            self.bib=self.raw_citation["bib"]
            self.bib = "https://tiger.coloradocollege.edu/record=" + self.bib[0:8] + "~s5"
        else:
            self.bib=self.__unique_IRI__()

        self.bib_uri=rdflib.URIRef(self.bib)

        # check for duplicates
        

        #add isbn
        if "isbn" in self.raw_citation.keys():
            self.isbn=self.raw_citation["isbn"]
        else:
            self.isbn = ""
        self.creative_works.add((self.bib_uri,rdflib.RDF.type, BF.Book))

        self.creative_works.add((self.bib_uri, BF.isbn,rdflib.Literal(self.isbn)))


        #add author - use author instead of agent to be consistent with articles
        for author in self.cc_authors:
            self.creative_works.add((self.bib_uri,SCHEMA.author,author))

        
    
        #add title
        self.creative_works.add((self.bib_uri, BF.title,rdflib.Literal(self.title,lang="en")))
        
        #add provision_publisher (provision activity statement in bf, equivalent to 264 field)
        self.creative_works.add((self.bib_uri,
                                 BF.provisionActivityStatement,
                                 rdflib.Literal(
                                    self.publisher_provision,lang="en")))

        #add year (in case it is needed separately)
        self.creative_works.add((self.bib_uri,SCHEMA.publicationDate,rdflib.Literal(self.year)))
                 
        #add edition if present
        self.creative_works.add((self.bib_uri, BF.editionStatement,rdflib.Literal(self.edition,lang="en")))
               
        #add abstract (summary) if present
        if self.abstract != "":
            self.creative_works.add((self.bib_uri, BF.Summary,rdflib.Literal(self.abstract,lang="en")))

        # add note if present
        if self.note != "":
            self.creative_works.add((self.bib_uri, 
                BF.Note,rdflib.Literal(self.note,lang="en")))

        # add the citation type
        self.creative_works.add((self.bib_uri,CITATION_EXTENSION.citationType,rdflib.Literal(self.citation_type,lang="en")))

        # add call # if present
        if self.call != "":
            self.creative_works.add((self.bib_uri,CITATION_EXTENSION.callNumber,rdflib.Literal(self.call)))

        # add url if present (a few books are not in Tiger)
        if self.url != "":
            self.creative_works.add((self.bib_uri,SCHEMA.url,rdflib.Literal(self.url)))
            
class Book_Chapter_Citation(Book_Citation):
    def __init__(self,
            raw_citation,
            creative_works,
            people,
            is_interactive=True):
        super(Book_Chapter_Citation, self).__init__(
            raw_citation,
            creative_works,
            people,
            is_interactive)

    def populate_book_chapter(self):
        self.__book_chapter_title__()
        self.__pages__()

    def __book_chapter_title__(self):
        self.book_chapter_title=""
        if "book_chapter_title" in self.raw_citation.keys():
            self.book_chapter_title = self.raw_citation["book_chapter_title"]

    def __pages__(self):
        self.pageStart=""
        self.pageEnd=""
        if "pages" in self.raw_citation.keys():
            pages = self.raw_citation["pages"]
            if "-" in pages:
                pages = pages.replace(" ","") # remove extraneous spaces
                pages = pages.replace("--","-") # turn double hyphens into single hypens
                hyphen = pages.find("-")
                self.page_start = pages[:hyphen]
                self.page_end = pages[hyphen+1:]
            else:
                self.page_start=pages    

    def add_book_chapter(self):

        self.book_chapter_uri = ""
        
        # if book does not yet exist, add new book, otherwise add chapter to pre-existing book
        # look for bib record derived uri first, then isbn, then title [and date to exclude different editions]
        #if "bib" in self.raw_citation.keys():
        #    self.bib=self.raw_citation["bib"]
        #    self.bib = "https://tiger.coloradocollege.edu/record=" + self.bib[0:8] + "~s5"
        #    if book_uri_lookup(creative_works,self.bib) == None:
        #        if isbn_lookup(self.isbn) == None:
        #            if book_title_lookup(self.title) == None:
        #                print("Book not found, need to add book")
        #                citation.add_book()

        # look for duplicate book chapter

        #add book chapter as uri
        if self.book_chapter_uri == "":
            self.book_chapter_uri = self.__unique_IRI__()
        self.creative_works.add((self.book_chapter_uri,rdflib.RDF.type,SCHEMA.Chapter))

        #add book chapter is part of book
        self.creative_works.add((self.book_chapter_uri,SCHEMA.PartOf,self.bib_uri))
    
        #add book chapter title
        self.creative_works.add((self.book_chapter_uri,SCHEMA.name,rdflib.Literal(self.book_chapter_title,"en")))

        #add chapter pages
        if self.page_start != "":
            self.creative_works.add((self.book_chapter_uri,SCHEMA.pageStart,rdflib.Literal(self.page_start)))
        if self.page_end != "":
            self.creative_works.add((self.book_chapter_uri,SCHEMA.pageEnd,rdflib.Literal(self.page_end)))

        print("Hey I'm in add_book_chapter and it's ",self.book_chapter_title)
        
            
def load_citations(bibtext_filepath, creative_works_path):
    # Take the bibparse data and load it into the creative_works knowledge graph
    with open(bibtext_filepath) as bibtex_file:
        bibtex_str = bibtex_file.read()
        bib_database = bibtexparser.loads(bibtex_str)
        
    # remove carriage returns and lower-cap the key values
    i = 0
    while i < len(bib_database.entries):
        for key in bib_database.entries[i].keys():
            bib_database.entries[i][key]=bib_database.entries[i][key].replace("\n", " ")
            key = key.lower()
        i = i + 1

    # populate the citations and count them
    i = 0
    print("Working, please wait ...")
    for row in bib_database.entries:
        if row["ENTRYTYPE"]=="article":
            citation=Article_Citation(row, creative_works, people)
            citation.populate()
            citation.populate_article()
            citation.add_article()
            i = i  + 1
            print(i)
        elif row["ENTRYTYPE"]=="book":
            citation=Book_Citation(row, creative_works, people)
            citation.populate()
            citation.populate_book()
            citation.add_book()
            i = i + 1
        elif row["ENTRYTYPE"]=="inbook":
            citation=Book_Chapter_Citation(row, creative_works, people)
            citation.populate()
            citation.populate_book()
            citation.populate_book_chapter()
            citation.add_book()
            citation.add_book_chapter()
            i = i + 1

    # save the graph to disk
    with open(creative_works_path, "wb+") as fo:
        fo.write(creative_works.serialize(format="turtle"))
        print("CC Scholarship Graph written for ",i,"articles.")
   

@click.command()
@click.option("--people_path", 
    help="Full file path to tiger-catalog/KnowledgGraph/cc-people.ttl")
@click.option("--creative_works_path", 
    help="Full file path to cc-scholarship-graph/data/creative-works.ttl")
@click.option("--bibtext_path",
    default=None,
    help="Full file path to bibtext text file")
def main(people_path, creative_works_path, bibtext_path):
    initialize(people_path, creative_works_path, bibtext_path)

#######################################START################################
# initialize graphs and schemas/namespaces
def initialize(people_path, creative_works_path, bibtext_path):
    global people, creative_works, SCHEMA, BF, CITATION_EXTENSION
    people=rdflib.Graph()
    people.parse(people_path, format="turtle")
    creative_works=rdflib.Graph()
    creative_works.parse(creative_works_path, format="turtle")
    creative_works.namespace_manager.bind("schema",SCHEMA)
    creative_works.namespace_manager.bind("bf", BF)
    creative_works.namespace_manager.bind("cite",CITATION_EXTENSION)

    # load bibtex data, parse it, and attempt to add citations to the creative_works graph
    if bibtext_path:
        load_citations(bibtext_path, creative_works_path)

if __name__ == '__main__':
    main()
