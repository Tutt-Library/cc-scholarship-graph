__author__ = "Diane Westerfield"

import rdflib
import bibtexparser
import uuid
import codecs

# Journal article workflow
# in Web of Science, set enhanced ID to Colorado College and select a year.
# Export the folder to BibTex format and copy file to working directory
# In Python: set up the people and creative works graphs
# open the BibTex file
# for each entry in the bibtex file:
# look for an author match. There can be multiple matches or none.
# if more than one author, have to add those authors
# if no author matched, may need human attention - or add the author automatically with a warning message?
# look for a journal match. If there is more than one journal returned, this is an error that needs human attention.
# if there is a journal match, look up volume.
# if no volume match, add the volume and refer to the journal.
# if no journal match, add the journal. still need to add the volume.
# if all matches (the article is already there) then don't add a duplicate

def author_lookup(people_graph,lookup_string):
# check the people graph for a match
    sparql="""SELECT ?person
              WHERE {{
              ?person rdf:type bf:Person .
              ?person rdfs:label ?label .
              FILTER(CONTAINS (?label,"{0}"))
              }}""".format(lookup_string)

    results = people_graph.query(sparql)

    for i in results:
        return i[0]

def doi_lookup(creative_works,lookup_string):
# check the creative works graph for a match on doi so that duplicate articles are not created

    sparql="""SELECT ?doi_iri
            WHERE {{
            ?doi_iri rdf:type schema:identifier
            ?doi_iri schema:name ?name
            FILTER (CONTAINS(?name,'''{0}'''))}}""".format(lookup_string)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]

def journal_lookup(creative_works,lookup_string):
# check the creative works graph for a match on journal title so that duplicate journals are not created
    sparql="""SELECT ?journal_iri
	      WHERE {{
	      ?journal_iri rdf:type schema:Periodical .
	      ?journal_iri schema:name ?name .
              FILTER (CONTAINS(?name,'''{0}'''))}}""".format(lookup_string)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]


def journal_volume_lookup(creative_works,lookup_string):
# check the creative works graph for a match on journal volume so that duplicates are not created
    sparql="""SELECT ?volume
              WHERE {{
              ?volume rdf:type bf:volume .
              ?volume rdfs:label ?label .
              FILTER(CONTAINS (?label,"{0}"))
              }}""".format(lookup_string)

    results = creative_works.query(sparql)

    for i in results:
        return i[0]
    
# function to return unique IRI using UUID
def unique_IRI(submitted_string):
    journal_url="{}{}".format(submitted_string,uuid.uuid1())
    return journal_url

class Citation(object):

    def __init__(self,raw_citation,creative_works):
        self.raw_citation=raw_citation
        self.creative_works=creative_works

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
        self.author_string=self.raw_citation["author"]

    def __CC_author__(self):
        
        # to do: account for multiple CC authors. Currently this will take the last match.
        # to do: what happens if there are no matches?
        
        for name in self.author_string.split(" and "):
            family_name=""
            given_name=""
            author_name_parsed=""

            # reverse last name, first name
            if "," in name:
                comma_pos=name.find(",")
                family_name = name[:comma_pos]
                given_name = name[comma_pos + 1:]
                name = given_name + " " + family_name

            # remove initials
            if "." in name:
                for part in name.split(" "):
                    if len(part) >= 3:
                        author_name_parsed = author_name_parsed + " "+ part
            else:
                author_name_parsed = name    

            author_name_parsed = author_name_parsed.strip()
    
            author_iri=author_lookup(people,author_name_parsed)
            
            if author_iri != None:
                self.CC_author=author_name_parsed
                self.author_iri=author_iri

    def __year__(self):
        if "year" in self.raw_citation.keys():
            self.year = self.raw_citation["year"]         
        else:
            self.year = "undefined"

    def __abstract__(self):
        if "abstract" in self.raw_citation.keys():
            self.abstract = self.raw_citation["abstract"]
        else:
            self.abstract = "undefined"

    def __citation_type__(self):
        self.citation_type=self.raw_citation["ENTRYTYPE"]
        
                                       
class Article_Citation(Citation):
    def __init__(self,raw_citation,creative_works):
        self.raw_citation=raw_citation
        self.creative_works=creative_works

    def populate_special(self):
        self.__journal_title__()
        self.__doi__()
        self.__article__()
        self.__volume__()
        self.__issue__()

    def __journal_title__(self):
        # to do: check to make sure this isn't duplicated
        self.journal_title = self.raw_citation["journal"]
        self.journal_string = self.__unique_IRI__()
        self.journal_iri=rdflib.URIRef(self.journal_string)

        # add issn and/or eissn if present in raw citation
        if "issn" in self.raw_citation.keys():
            self.journal_issn=self.raw_citation["issn"]
        else:
            self.journal_issn="undefined"
        if "eissn" in self.raw_citation.keys():
            self.journal_eissn=self.raw_citation["eissn"]
        else:
            self.journal_eissn="undefined"

    def __article__(self):
        # information specific to the article itself
        self.article_title = self.raw_citation["title"]

        self.page_start = "undefined"
        self.page_end = "undefined"
        if "pages" in self.raw_citation.keys():
            pages=self.raw_citation["pages"]
            if "-" in pages:
                pages = pages.replace(" ","") # remove extraneous spaces
                hyphen=pages.find("-")
                self.page_start=pages[:hyphen]
                self.page_end=pages[hyphen+1:]
            else:
                self.page_start=pages
        print("I found start_page to be ",self.page_start, " and end_page to be ",self.page_end)
        
    def __doi__(self):
        # doi is the unique identifier for articles
        # to do: check for duplicate doi numbers
        if "doi" in self.raw_citation.keys():
            self.doi_string = "https://doi.org/" + self.raw_citation["doi"]
        else:
            self.doi_string=self.__unique_IRI__()
        self.doi_iri=rdflib.URIRef(self.doi_string)
        
    def __volume__(self):
        # to do: check for duplicate volumes of the journal title
        # a citation can have a volume number or none at all
        self.volume_number="undefined"
        if "volume" in self.raw_citation.keys():
            if self.raw_citation["volume"] != "" or self.raw_citation["volume"] != None:
                self.volume_number = self.raw_citation["volume"]
                self.volume_iri = self.__unique_IRI__()          
        
    def __issue__(self):
        # to do: check for duplicate issue numbers of the volume of the journal title, or the journal title itself
        # a journal can have no issue numbers, issue numbers as part of a volume, or issues without volume numbering
        self.issue_number="undefined"
        if "number" in self.raw_citation.keys():
            if (self.raw_citation["number"] !="") or (self.raw_citation["number"] != None):
                self.issue_number = self.raw_citation["number"]
                self.issue_iri = self.__unique_IRI__()
       
    def add_article(self):
        # Business logic for adding citations

        # add the journal title
        self.creative_works.add((self.journal_iri,rdflib.RDF.type,SCHEMA.Periodical))
        self.creative_works.add((self.journal_iri,SCHEMA.name,rdflib.Literal(self.journal_title,lang="en")))
        # add the issn and/or eissn if present
        if self.journal_issn != "undefined":
            self.creative_works.add((self.journal_iri,SCHEMA.issn,rdflib.Literal(self.journal_issn)))
        if self.journal_eissn != "undefined":
            self.creative_works.add((self.journal_iri,SCHEMA.eissn,rdflib.Literal(self.journal_eissn)))
        
        # add the article, using doi as unique identifier
        self.creative_works.add((self.doi_iri,rdflib.RDF.type,SCHEMA.ScholarlyArticle))
        self.creative_works.add((self.doi_iri,SCHEMA.name,rdflib.Literal(self.article_title,lang="en")))
        if self.page_start != "undefined":
            self.creative_works.add((self.doi_iri,SCHEMA.pageStart,rdflib.Literal(self.page_start)))
        if self.page_end != "undefined":
            self.creative_works.add((self.doi_iri,SCHEMA.pageEnd,rdflib.Literal(self.page_end)))
        # add doi link or other link here?

        # add the author
        self.creative_works.add((self.doi_iri,SCHEMA.author,self.author_iri))

        # add the publication year
        self.creative_works.add((self.doi_iri,SCHEMA.datePublished,rdflib.Literal(self.year)))

        # add the abstract
        self.creative_works.add((self.doi_iri,SCHEMA.about,rdflib.Literal(self.abstract)))
        
        # if there is no volume or issue number, add the article directly to the journal
        if (self.volume_number == "undefined") and (self.issue_number == "undefined"):
            self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.journal_iri))
        # if there is a volume but no issue number, add the volume to the journal and add the article to the volume
        elif (self.volume_number != "undefined") and (self.issue_number == "undefined"):
            self.creative_works.add((self.volume_iri,rdflib.RDF.type,SCHEMA.volumeNumber))
            self.creative_works.add((self.volume_iri,SCHEMA.partOf,self.journal_iri))
            self.creative_works.add((self.volume_iri,SCHEMA.name,rdflib.Literal(self.volume_number)))
            self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.volume_iri))
        # if there is no volume but there is an issue number, add the the issue to the journal and add the article to the issue
        elif (self.volume_number == "undefined") and (self.issue_number != "undefined"):
            self.creative_works.add((self.issue_iri,rdflib.RDF.type,SCHEMA.issueNumber))
            self.creative_works.add((self.issue_iri,SCHEMA.partOf,self.journal_iri))
            self.creative_works.add((self.issue_iri,SCHEMA.issueNumber,rdflib.Literal(self.issue_number)))
            self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.issue_iri))
        # presuming there is a volume and an issue, add the article to the issue, add the issue to the volume, add the volume to the journal
        else:
            self.creative_works.add((self.volume_iri,rdflib.RDF.type,SCHEMA.volumeNumber))
            self.creative_works.add((self.volume_iri,SCHEMA.partOf,self.journal_iri))
            self.creative_works.add((self.volume_iri,SCHEMA.name,rdflib.Literal(self.volume_number)))
            self.creative_works.add((self.issue_iri,SCHEMA.partOf,self.volume_iri))
            self.creative_works.add((self.issue_iri,rdflib.RDF.type,SCHEMA.issueNumber))
            self.creative_works.add((self.issue_iri,SCHEMA.issueNumber,rdflib.Literal(self.issue_number)))
            self.creative_works.add((self.doi_iri,SCHEMA.partOf,self.issue_iri))
                

class Book_Citation(Citation):
    def __init__(self,raw_citation,creative_works):
        self.raw_citation=raw_citation
        self.creative_works=creative_works

class Book_Chapter_Citation(Book_Citation):
    def __init__(self,raw_citation,creative_works):
        self.raw_citation=raw_citation
        self.creative_works=creative_works

            
def load_citations():
    # Take the bibparse data and load it into the creative_works knowledge graph
    with open('C:/CCKnowledgeGraph/Temp/BibTexLoad.txt') as bibtex_file:
        bibtex_str = bibtex_file.read()
        bib_database = bibtexparser.loads(bibtex_str)

    # remove carriage returns and lower-cap the key values
    i = 0
    while i < len(bib_database.entries):
        for key in bib_database.entries[i].keys():
            bib_database.entries[i][key]=bib_database.entries[i][key].replace("\n", " ")
            key = key.lower()
        i = i + 1
            
    for row in bib_database.entries:
        if row["ENTRYTYPE"]=="article":
            citation=Article_Citation(row,creative_works)
            citation.populate()
            citation.populate_special()
            citation.add_article()
            print("Article successfully added")


    with open("C:/CCKnowledgeGraph/cc-scholarship-graph/data/creative-works.ttl", "wb+") as fo:
        fo.write(creative_works.serialize(format="turtle"))
        print("CC Scholarship Graph written")
   

#######################################START################################
# initialize graphs and schemas/namespaces

people=rdflib.Graph()
people.parse("C:/CCKnowledgeGraph/tiger-catalog/KnowledgeGraph/cc-people.ttl",format="turtle")
creative_works=rdflib.Graph()
creative_works.parse("C:/CCKnowledgeGraph/cc-scholarship-graph/data/creative-works.ttl",format="turtle")
SCHEMA = rdflib.Namespace("http://schema.org/")
creative_works.namespace_manager.bind("schema",SCHEMA)
BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")

# load bibtex data, parse it, and attempt to add citations to the creative_works graph
load_citations()
