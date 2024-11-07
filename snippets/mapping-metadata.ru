# Adding relevant metadata into taxonomy

PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX dc:    <http://purl.org/dc/elements/1.1/>
PREFIX foaf:  <http://xmlns.com/foaf/0.1/>
PREFIX protege: <http://protege.stanford.edu/plugins/owl/protege#>
PREFIX terms: <http://purl.org/dc/terms/>

CONSTRUCT {
    ?conceptURI ?convertedMetadataType ?metadataValue_str .
}
WHERE {
    ?conceptURI a owl:Class ;
        rdfs:label ?tmp ;
        ?metadataType ?metadataValue .

    {
        ?conceptURI rdfs:subClassOf* <http://purl.obolibrary.org/obo/UBERON_0000000>
    }

    VALUES (?metadataType ?convertedMetadataType){
        (oboInOwl:hasDbXref oboInOwl:hasDbXref)
        (obo:IAO_0000115 skos:definition)
        (rdfs:comment rdfs:comment)
        (obo:IAO_0000232 skos:editorialNote)
    } .
    FILTER NOT EXISTS { ?conceptURI owl:deprecated true }
    FILTER(!isBlank(?metadataValue))
    FILTER (regex(str(?conceptURI), "/UBERON_" ))
    BIND(
        IF (
            isURI(?metadataValue) ,
            STR(?metadataValue) ,
            ?metadataValue
        ) AS ?metadataValue_str
    )
}