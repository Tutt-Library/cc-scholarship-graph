__author__ = "Diane Westerfield"

import rdflib
import bibtexparser

def author_lookup(people_graph,lookup_string):

    sparql="""SELECT ?person
              WHERE {{
              ?person rdf:type bf:Person .
              ?person rdfs:label ?label .
              FILTER(CONTAINS (?label,"{0}"))
              }}""".format(lookup_string)

    results = people_graph.query(sparql)

    for i in results:
        return i[0]
    
