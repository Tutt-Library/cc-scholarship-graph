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
	ORDER BY DESC(?article)"""

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

SELECT ?org ?event ?year_label ?rank
WHERE {{
    ?event ?rank_iri ?person ;
           schema:organizer ?org ;
           rdfs:label ?year_label .
    ?rank_iri rdfs:label ?rank .
    FILTER(<{0}> = ?person)
}}"""

PERSON_INFO = PREFIX + """

SELECT ?family ?given ?email
WHERE {{
    ?person schema:familyName ?family ;
            schema:givenName ?given ;
            schema:email ?email .
    FILTER (<{0}> = ?person)
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
