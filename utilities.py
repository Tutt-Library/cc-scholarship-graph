__author__ = "Diane Westerfield"

import rdflib
import bibtexparser
import uuid

# Journal article workflow
# in Web of Science, set enhanced ID to Colorado College and select a year.
# Export all to RefWorks, put in a folder
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

def journal_lookup(creative_works,lookup_string):
# check the creative works graph for a match on journal title so that duplicates are not created
    sparql="""SELECT ?name
              WHERE {{
              ?name rdf:type bf:name .
              ?name rdfs:label ?label .
              FILTER(CONTAINS (?label,"{0}"))
              }}""".format(lookup_string)

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

def load_citations():
# Take the bibparse data and load it into the creative_works knowledge graph
    with open('C:/CCKnowledgeGraph/Temp/BibTexTest.txt') as bibtex_file:
        bibtex_str = bibtex_file.read()
        bib_database = bibtexparser.loads(bibtex_str)
    for citation in bib_database.entries:
        journal_title = citation["journal"]
        journal_iri = unique_IRI("http://catalog.coloradocollege.edu/")
        author_string = citation["author"]
        author_iri=""
        print(author_string)
        for name in author_string.split(" and "):
            if " " in name:
                author_name_parsed=""
                for part in name.split(" "):
                    if len(part) >= 3:
                        author_name_parsed = author_name_parsed + " "+ part
            else:
                author_name_parsed = name
            author_name_parsed = author_name_parsed.lstrip()
            author_name_parsed = author_name_parsed.rstrip()
            if str(author_lookup(people,author_name_parsed)) != "None":
                author_iri = author_iri + str(author_lookup(people,author_name_parsed))


        doi_string = "https://doi.org/" + citation["doi"]
        article_iri=rdflib.URIRef(doi_string)
        
        
        if "volume" in citation:
            volume_number = citation["volume"]
            volume_iri = unique_IRI("http://catalog.coloradocollege.edu/")
        else:
            volume_number = ""
        if "number" in citation:
            issue_number = citation["number"]
        else:
            issue_number = ""

        # add article, with doi as unique identifier
        # WIP: look to make sure the article is not yet in graph
        # if article is there, other steps don't need to be taken
        # more than one CC author can be associated with an article
        creative_works.add((article_iri,rdflib.RDF.type,SCHEMA.ScholarlyArticle))
        
        # add journal, make journal iri
        # WIP: look to make sure the journal title is not yet in graph
        # if journal is there, use that identifier
        journal_iri=rdflib.URIRef(journal_iri)
        creative_works.add((journal_iri,rdflib.RDF.type,SCHEMA.Periodical))
        creative_works.add((journal_iri,SCHEMA.name,rdflib.Literal(journal_title,lang="en")))
            
        # add volume number, if in the citation
        # WIP: look to make sure the volume associated with this journal is not yet in graph
        volume_iri=rdflib.URIRef(volume_iri)
        if volume_number != "" :
            creative_works.add((volume_iri,rdflib.RDF.type,SCHEMA.PublicationVolume))
            creative_works.add((volume_iri,SCHEMA.volumeNumber,rdflib.Literal(volume_number)))
            creative_works.add((volume_iri,SCHEMA.partOf,journal_iri))

        # add issue number, if in citation
        # WIP: look to make sure the issue number associated with this journal is not yet in graph
        if issue_number != "":
            issue_iri=unique_IRI("http://catalog.coloradocollege.edu/")
            issue_iri=rdflib.URIRef(issue_iri)
 
        if issue_number != "" :
            creative_works.add((issue_iri,rdflib.RDF.type,SCHEMA.PublicationIssue))
            creative_works.add((volume_iri,SCHEMA.issueNumber,rdflib.Literal(issue_number)))
            if volume_number != "":
                creative_works.add((issue_iri,SCHEMA.partOf,volume_iri))
            else:
                creative_works.add((issue_iri,SCHEMA.partOf,journal_iri))

        if volume_number != "" and issue_number != "":
            creative_works.add((article_iri,SCHEMA.partOf,issue_iri))
        elif volume_number != "" and issue_number == "":
            creative_works.add((article_iri,SCHEMA.partOf,volume_iri))
        elif volume_number == "" and issue_number != "":
            creative_works.add((article_iri,SCHEMA.partOf,issue_iri))
        else:
            creative_works.add((article_iri,SCHEMA.partOf,journal_iri))
        print(journal_iri,journal_title,author_iri,volume_number,issue_number)

        creative_works.add((article_iri,SCHEMA.author,author_iri))


    with open("C:/CCKnowledgeGraph/cc-scholarship-graph/data/creative-works.ttl", "wb+") as fo:
        fo.write(creative_works.serialize(format="turtle"))
	
#######################################START########################
people=rdflib.Graph()
people.parse("C:/CCKnowledgeGraph/tiger-catalog/KnowledgeGraph/cc-people.ttl",format="turtle")
creative_works=rdflib.Graph()
# creative_works.parse("C:/CCKnowledgeGraph/cc-scholarship-graph/data/creative-works.ttl",format="turtle")
SCHEMA = rdflib.Namespace("http://www.schema.org/")
BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")

load_citations()
