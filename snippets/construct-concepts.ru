# Converting owl:Class into skos:Concept

PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
PREFIX obo:  <http://purl.obolibrary.org/obo/>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
PREFIX model: <https://ontology.novonordisk.com/model/>

CONSTRUCT {
    ?conceptURI a skos:Concept, model:ANATOMY .
    ?conceptURI skosxl:prefLabel ?labelURI .
    ?labelURI a skosxl:Label .
    ?labelURI skosxl:literalForm ?label .
}
WHERE {
    ?conceptURI a owl:Class ;
        rdfs:label ?label .
    {
        ?conceptURI rdfs:subClassOf* <http://purl.obolibrary.org/obo/UBERON_0000000>
    }
    FILTER (regex(str(?conceptURI), "/UBERON_" ))
    FILTER NOT EXISTS { ?conceptURI owl:deprecated true }
    BIND (URI(CONCAT(str(?conceptURI), "_prefLabel")) AS ?labelURI) .
}
