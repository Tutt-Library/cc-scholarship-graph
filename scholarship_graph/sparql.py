__author__ = "Jeremy Nelson"

PREFIX = """PREFIX bf: <http://id.loc.gov/ontologies/bibframe/>
PREFIX cc_fac: <https://www.coloradocollege.edu/ns/faculty/>
PREFIX cc_info: <https://www.coloradocollege.edu/ns/info/>  
PREFIX etd: <http://catalog.coloradocollege.edu/ns/etd#> 
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
PREFIX schema: <http://schema.org/>"""

ORG_INFO = PREFIX + """
SELECT ?label ?year ?year_label
WHERE {{
    ?org rdfs:label ?label .
    ?year schema:organizer ?org ;
          rdfs:label ?year_label .
    BIND(<{0}> as ?org)
}}"""

ORG_LISTING = PREFIX + """

SELECT ?iri ?label
WHERE {
    ?iri rdfs:label ?label ;
         rdf:type ?type .
    FILTER(?type=schema:CollegeDepartment||?type=schema:Library)
} ORDER BY ?label"""

ORG_PEOPLE = PREFIX + """
SELECT ?event ?person ?name ?rank ?statement
WHERE {{
    ?event schema:organizer ?dept ;
           ?rank_iri ?person .
    ?rank_iri rdfs:label ?rank .
    ?person rdf:type bf:Person ;
            schema:familyName ?family ;
            rdfs:label ?name .
    OPTIONAL {{ ?stmt_iri schema:accountablePerson ?person ;
                          schema:description ?statement . }}
    BIND(<{0}> as ?dept)
}} ORDER BY ?family"""

PERSON_HISTORY = PREFIX + """

SELECT ?org ?event ?year_label ?rank
WHERE {{
    ?event ?rank_iri ?person ;
           schema:organizer ?org ;
           rdfs:label ?year_label .
    ?rank_iri rdfs:label ?rank .
    BIND(<{0}> AS ?person)
}}"""

PERSON_INFO = PREFIX + """

SELECT ?family ?given ?email
WHERE {{
    ?person schema:familyName ?family ;
            schema:givenName ?given ;
            schema:email ?email .
    BIND(<{0}> AS ?person)
}}"""


RESEARCH_STMT = PREFIX + """
SELECT ?statement
WHERE {{
    ?stmt_iri schema:accountablePerson ?person ;
              schema:description ?statement .
    BIND(<{0}> AS ?person)
}}"""

