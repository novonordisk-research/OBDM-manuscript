# Adding logical axioms for exactMatch annotations

PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

INSERT {
    ?s a owl:Class ;
       owl:equivalentClass ?o .
}

WHERE {
    ?s skos:exactMatch ?o .
}