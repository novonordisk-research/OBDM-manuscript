# Converting subclass and related object properties to broader/narrower relationships

PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>

CONSTRUCT {
    ?concept skos:broader ?superclass .
}
WHERE {
	?concept a owl:Class ;
        rdfs:subClassOf
        |(owl:equivalentClass/owl:intersectionOf/rdf:rest*/rdf:first)
        |^(owl:equivalentClass/owl:unionOf/rdf:rest*/rdf:first)
        ?superclass .
    {
        ?concept rdfs:subClassOf* <http://purl.obolibrary.org/obo/UBERON_0000000>
    }
    FILTER EXISTS { ?concept rdfs:label ?_ }
    FILTER EXISTS { ?superclass rdfs:label ?_ }
    FILTER NOT EXISTS { ?concept owl:deprecated true }
    FILTER (regex(str(?concept), "/UBERON_" ))
    FILTER (regex(str(?superclass), "/UBERON_" ))
}