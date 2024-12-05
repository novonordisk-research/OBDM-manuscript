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
(count(?enr) as ?enriched)
(count(?enrichedCC) as ?enrichedCCs)
(count(?only_enriched) as ?enriched_only)
(count(?only_CC) as ?CC_only)
(count(?definedInLinked) as ?definedInLinkedModel)
{
  () teamwork:graphsUnderTeamControl (?model ?teamGraph)
  # keep only model types of interest
  FILTER(strstarts(str(?model), str(model:)))
  GRAPH ?teamGraph { ?teamGraph sem:tag ?tag }
  FILTER(?tag in ("domain"))
  
  GRAPH ?model {
    { # identify concepts defined in ?model
      ?concept skosxl:prefLabel/skosxl:literalForm ?label
      bind(true as ?enr)
    }
    UNION
    { # identify concepts having cc:enriched
      ?concept a cc:enriched
      bind(true as ?enrichedCC)
    }
    UNION
    { # identify concepts defined in ?model but *lacking* cc:enriched
      ?concept skosxl:prefLabel/skosxl:literalForm ?label
      FILTER NOT EXISTS { ?concept a cc:enriched }
      bind(?concept as ?only_enriched)
    }
    UNION
    { # identify concepts having cc:enriched but *not* defined in ?model
      ?concept a cc:enriched
      FILTER NOT EXISTS { ?concept skosxl:prefLabel/skosxl:literalForm ?label }
      bind(?concept as ?only_CC)
      OPTIONAL {
        # mark those that are defined in linked-in model
        GRAPH ?model { ?model owl:imports ?model2 }
        GRAPH ?model2 { ?concept skosxl:prefLabel/skosxl:literalForm ?_ }
        bind(true as ?definedInLinked)
      }
    }
  }
}
group by ?model
order by ?model
