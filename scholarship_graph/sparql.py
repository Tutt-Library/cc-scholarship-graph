__author__ = "Jeremy Nelson"

import datetime
import rdflib

PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")

def add_qualified_revision(graph, target_entity, revisedBy, label=None):
    """Takes a rdflib Graph, target entity IRI, revisedBy IRI, and an 
    optional label and generates a revision"""
    qualified_revision = rdflib.BNode()
    graph.add((target_entity, PROV.qualifiedRevision, qualified_revision))
    graph.add((qualified_revision, rdflib.RDF.type, PROV.Revision))
    graph.add((qualified_revision, PROV.atTime,
               rdflib.Literal(datetime.datetime.utcnow().isoformat(),
                              datatype=rdflib.XSD.dateTime)))
    graph.add((qualified_revision, PROV.wasGeneratedBy, revisedBy))
    if not label is None:
        graph.add((qualified_revision,
                   PROV.label,
                   label))

def add_qualified_generation(graph, entity_iri, generatedBy):
    """Takes a rdflib Grpah, target entity iri, and generatedBy iri and 
    creates a generation event"""
    gen_bnode = rdflib.BNode()
    graph.add((entity_iri, PROV.qualifiedGeneration, gen_bnode))
    graph.add((gen_bnode, rdflib.RDF.type, PROV.Generation))
    graph.add((gen_bnode, 
               PROV.atTime, 
               rdflib.Literal(datetime.datetime.utcnow().isoformat(), 
                              datatype=rdflib.XSD.dateTime)))
    graph.add((gen_bnode, PROV.wasGeneratedBy, generatedBy))


PREFIX = """PREFIX bf: <http://id.loc.gov/ontologies/bibframe/>
PREFIX cc_fac: <https://www.coloradocollege.edu/ns/faculty/>
PREFIX cc_info: <https://www.coloradocollege.edu/ns/info/> 
PREFIX cc_staff: <https://www.coloradocollege.edu/ns/staff/>  
PREFIX cite: <https://www.coloradocollege.edu/library/ns/citation/>
PREFIX etd: <http://catalog.coloradocollege.edu/ns/etd#> 
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
PREFIX schema: <http://schema.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"""

CITATION = PREFIX + """
SELECT DISTINCT ?article ?name ?datePublished ?journal_title ?volume_number ?issue_number ?page_start ?page_end ?url
WHERE {{
	?article rdf:type schema:ScholarlyArticle ;
                 schema:name ?name ;
	         schema:author ?author .
	OPTIONAL {{?article schema:url ?url.}}
	OPTIONAL {{?article schema:datePublished ?datePublished.}}
	OPTIONAL {{?article schema:partOf ?issue .
				?issue schema:issueNumber ?issue_number .}}
	OPTIONAL {{?article schema:partOf ?volume .
				?volume schema:volumeNumber ?volume_number .
				?volume schema:partOf ?journal .
				?journal schema:name ?journal_title .}}
	OPTIONAL {{?article schema:partOf ?journal .
				?journal schema:name ?journal_title .}}
        OPTIONAL {{ ?article schema:partOf ?issue .
                    ?issue schema:partOf ?journal .
                    ?journal schema:name ?journal_title .}}
	OPTIONAL {{?article schema:partOf ?issue .
				?issue schema:partOf ?volume .
				?issue schema:issueNumber ?issue_number .
				?volume schema:partOf ?journal .
				?volume schema:volumeNumber ?volume_number .
				?journal schema:name ?journal_title .}}
	OPTIONAL {{?article schema:pageStart ?page_start .}}
	OPTIONAL {{?article schema:pageEnd ?page_end .}}
	FILTER(<{0}> = ?author)

	}}
	ORDER BY DESC(?publicationDate)"""


BOOK_CITATION = PREFIX + """
SELECT DISTINCT ?book ?author ?title ?isbn ?publicationDate ?provisionActivityStatement ?editionStatement ?summary ?note ?url
WHERE {{
	?book rdf:type bf:Book ;
                 bf:title ?title ;
	         schema:author ?author .
	FILTER(<{0}> = ?author)
	OPTIONAL {{?book bf:isbn ?isbn.}}
	OPTIONAL {{?book schema:publicationDate ?publicationDate.}}
	OPTIONAL {{?book bf:provisionActivityStatement ?provisionActivityStatement.}}
	OPTIONAL {{?book bf:editionStatement ?editionStatement.}}
	OPTIONAL {{?book bf:summary ?summary.}}
	OPTIONAL {{?book bf:note ?note.}}
	OPTIONAL {{?book schema:url ?url.}}
	}}
	ORDER BY DESC(?publicationDate)"""

BOOK_CHAPTER_CITATION = PREFIX + """
SELECT DISTINCT ?book ?author ?editor ?title ?book_chapter_title ?isbn ?publicationDate ?provisionActivityStatement ?editionStatement ?summary ?note ?url ?page_start ?page_end
WHERE {{
	?book_chapter rdf:type schema:Chapter ;
                 schema:name ?book_chapter_title ;
				 schema:partOf ?book ;
	         schema:author ?author .
	?book bf:title ?title .
	FILTER(<{0}> = ?author)
	OPTIONAL {{?book bf:isbn ?isbn.}}
	OPTIONAL {{?book schema:editor ?editor.}}
	OPTIONAL {{?book schema:publicationDate ?publicationDate.}}
	OPTIONAL {{?book bf:provisionActivityStatement ?provisionActivityStatement.}}
	OPTIONAL {{?book bf:editionStatement ?editionStatement.}}
	OPTIONAL {{?book bf:summary ?summary.}}
	OPTIONAL {{?book bf:note ?note.}}
	OPTIONAL {{?book schema:url ?url.}}
	OPTIONAL {{?book_chapter schema:pageStart ?page_start .}}
	OPTIONAL {{?book_chapter schema:pageEnd ?page_end .}}
	}}
	ORDER BY DESC(?publicationDate)"""
	
COUNT_ARTICLES = PREFIX + """
SELECT (COUNT(?article) as ?count)
WHERE {
    ?article rdf:type schema:ScholarlyArticle .
}
"""

COUNT_BOOK_AUTHORS = PREFIX + """
SELECT (COUNT(?author) as ?count)
WHERE {
   ?book rdf:type bf:Book ;
         schema:author ?author .
}"""

COUNT_BOOKS = PREFIX + """
SELECT (COUNT(?book) as ?count)
WHERE {
    ?book rdf:type bf:Book .
}"""

COUNT_JOURNALS = PREFIX + """
SELECT (COUNT(?journal) as ?count)
WHERE {
    ?journal rdf:type schema:Periodical .
}"""

COUNT_ORGS = PREFIX + """
SELECT (COUNT(?org) as ?count)
WHERE {
    ?org rdf:type ?type .
    FILTER(?type=schema:CollegeDepartment||?type=schema:Library)
}"""

COUNT_PEOPLE = PREFIX + """
SELECT (COUNT(?person) as ?count)
WHERE {
    ?person rdf:type bf:Person .
}"""

COUNT_CHAPTERS = PREFIX + """
SELECT (COUNT (?chapter) as ?count)
WHERE {
	?chapter rdf:type schema:Chapter .}
}"""

EMAIL_LOOKUP = PREFIX + """SELECT ?person 
WHERE {{ ?person schema:email ?email .
       FILTER(CONTAINS(?email, "{0}")) 
}}"""
 

ORG_INFO = PREFIX + """
SELECT DISTINCT ?label ?year ?year_label
WHERE {{
    
    ?org rdfs:label ?label .
    ?year schema:organizer ?org ;
          rdfs:label ?year_label ;
          schema:superEvent ?academic_year .
    ?academic_year schema:startDate ?start ;
                   schema:endDate ?end . 
    FILTER(?start < "{1}"^^xsd:dateTime)
    FILTER(?end >= "{1}"^^xsd:dateTime) 
    FILTER(?org = <{0}>)
}}"""

ORG_LISTING = PREFIX + """

SELECT ?iri ?label
WHERE {
    ?iri rdfs:label ?label ;
         rdf:type ?type .
    FILTER(?type=schema:CollegeDepartment||?type=schema:Library)
} ORDER BY ?label"""

OLD_ORG_PEOPLE = PREFIX + """
SELECT ?event ?person ?name ?rank ?statement
WHERE {{
    ?event schema:organizer ?dept ;
           schema:superEvent ?academic_year ;
           ?rank_iri ?person .
    ?academic_year schema:startDate ?start ;
                   schema:endDate ?end .
    ?rank_iri rdfs:label ?rank .
    ?person rdf:type bf:Person ;
            schema:familyName ?family ;
            rdfs:label ?name .
    OPTIONAL {{ ?stmt_iri schema:accountablePerson ?person ;
                          schema:description ?statement . }}
    FILTER(<{0}> = ?dept)
    FILTER(?start < "{1}"^^xsd:dateTime)
    FILTER(?end >= "{1}"^^xsd:dateTime) 
}} ORDER BY ?family"""

ORG_PEOPLE = PREFIX + """
SELECT ?person ?name ?rank ?statement
WHERE {{
    BIND(<{0}> as ?event)
    ?event ?rank_iri ?person .
    ?rank_iri rdfs:label ?rank .
    ?person rdf:type bf:Person ;
             schema:familyName ?family ;
             rdfs:label ?name .
    OPTIONAL {{ ?stmt_iri schema:accountablePerson ?person ;
                          schema:description ?statement . }}
      
}} ORDER BY ?family"""

PERSON_HISTORY = PREFIX + """

SELECT ?org ?event ?year_label ?rank ?end
WHERE {{
    ?event ?rank_iri ?person ;
           schema:organizer ?org ;
           rdfs:label ?year_label ;
           schema:superEvent ?year_event .
    ?year_event schema:endDate ?end ;
                schema:startDate ?start .
    ?rank_iri rdfs:label ?rank .
    FILTER(<{0}> = ?person)
    FILTER (?start < "{1}"^^xsd:dateTime)
    FILTER (?end > "{1}"^^xsd:dateTime)
}} ORDER BY ?end"""

PERSON_INFO = PREFIX + """

SELECT ?family ?given ?email ?label
WHERE {{
    BIND(<{0}> as ?person)
    ?person schema:familyName ?family ;
            schema:givenName ?given ;
            schema:email ?email ;
            rdfs:label ?label .
}}"""

PERSON_LABEL = PREFIX + """

SELECT ?label
WHERE {{
    ?person rdfs:label ?label .
    FILTER(<{0}> = ?person)
}}"""

PROFILE = PREFIX + """
SELECT ?person ?statement
WHERE {{
    ?person rdf:type bf:Person .
    ?person schema:familyName ?family .
    ?person schema:givenName ?given .
    FILTER(CONTAINS(?family, "{0}"))
    FILTER(CONTAINS(?given, "{1}"))
    OPTIONAL {{ ?person schema:email "{2}" . }}
    OPTIONAL {{ ?stmt_iri schema:accountablePerson ?person ;
                           schema:description ?statement . }}
}}"""

RESEARCH_STMT = PREFIX + """
SELECT ?statement
WHERE {{
    ?stmt_iri schema:accountablePerson ?person ;
              schema:description ?statement .
    FILTER (<{0}> = ?person)
}}"""

RESEARCH_STMT_IRI = PREFIX + """
SELECT ?iri
WHERE {{
    ?iri schema:accountablePerson ?person ;
         schema:description ?statement .
    FILTER (<{0}> = ?person)
}}"""


SUBJECTS = PREFIX + """
SELECT ?subject ?label
WHERE {{
    ?person schema:email ?email .
    ?statement schema:accountablePerson ?person .
    ?statement schema:about ?subject .
    ?subject rdfs:label ?label .
    FILTER (CONTAINS(?email, "{0}"))
}}""" 

SUBJECTS_IRI = PREFIX + """
SELECT ?subject
WHERE {{
    ?statement schema:accountablePerson ?person ;
        schema:about ?subject .
    FILTER (?person = <{0}>)
}}"""

WORK_INFO = PREFIX + """
SELECT * 
WHERE {{
    BIND(<{0}> as ?work)
    ?work a ?type ;
    OPTIONAL {{?work schema:name ?name . }}
    OPTIONAL {{?work bf:title ?title . }}
    OPTIONAL {{?work schema:about ?abstract . }} 
    OPTIONAL {{?work schema:url ?url.}}
    OPTIONAL {{?work schema:datePublished ?datePublished.}}
    OPTIONAL {{?work schema:partOf ?issue .
				?issue schema:issueNumber ?issue_number .}}
    OPTIONAL {{?work schema:partOf ?volume .
				?volume schema:volumeNumber ?volume_number .
				?volume schema:partOf ?journal .
				?journal schema:name ?journal_title .}}
    OPTIONAL {{?work schema:partOf ?journal .
				?journal schema:name ?journal_title .}}
    OPTIONAL {{?work schema:partOf ?issue .
				?issue schema:partOf ?volume .
				?issue schema:issueNumber ?issue_number .
				?volume schema:partOf ?journal .
				?volume schema:volumeNumber ?volume_number .
				?journal schema:name ?journal_title .}}
    OPTIONAL {{ ?work schema:partOf ?issue .
                ?issue schema:partOf ?journal .
                ?journal schema:name ?journal_title .}}
    OPTIONAL {{ ?work cite:authorString ?author_string . }}
    OPTIONAL {{ ?work schema:author ?author .
                ?author rdfs:label ?author_string . }}
    OPTIONAL {{?work schema:pageStart ?page_start .}}
    OPTIONAL {{?work schema:pageEnd ?page_end .}}
    OPTIONAL {{?work bf:provisionActivityStatement ?provisionActivityStatement . }}
    OPTIONAL {{?work bf:editionStatement ?editionStatement . }}
    OPTIONAL {{?work bf:isbn ?isbn . }}
    OPTIONAL {{?work schema:publicationDate ?datePublished .}}
    OPTIONAL {{?work bf:Note ?notes .}}
}}""" 
