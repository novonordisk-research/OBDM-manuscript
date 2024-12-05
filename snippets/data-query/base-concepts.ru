PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX user: <urn:x-tb-users:>
PREFIX sempermissions: <http://www.smartlogic.com/2015/11/semaphore-permissions#>
PREFIX sem: <http://www.smartlogic.com/2014/08/semaphore-core#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
PREFIX model: <urn:x-evn-master:>
PREFIX role: <urn:x-tb-role:>
PREFIX teamwork: <http://topbraid.org/teamwork#>
PREFIX cc: <https://ontology.novonordisk.com/ConceptClass/>

SELECT
(replace(str(?model), str(model:), "") as ?modelID)
(count(?base) as ?concepts)

{
  () teamwork:graphsUnderTeamControl (?model ?teamGraph)
  # keep only model types of interest
  FILTER(strstarts(str(?model), str(model:)))
  GRAPH ?teamGraph { ?teamGraph sem:tag ?tag }
  FILTER(?tag in ("domain_base"))
  
  GRAPH ?model {
    { # identify concepts defined in ?model
      ?concept skosxl:prefLabel/skosxl:literalForm ?label
      bind(true as ?base)
    }
  }
}
group by ?model
order by ?model