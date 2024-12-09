# A program to translate public to NN URIs.
# dependency on mapping.py to handle SSSOM files

# Process:
# - load mapping file into NNURIs
# - load input file into a rdflib graph
# - replace public URIs with NN URIs
#   - criteria for which URIs are to be mapped:
#     1. URI exists in the mapping file
#     2. <URI> a skos:Concept and not in NN namespace
#   - add refs to public URIs
# - save both (updated) mapping file and the output file (now with NN URIs)

# Dependencies:
# pip install curies pip-system-certs

import curies, csv, io, yaml, logging, argparse
from mapping.mapping import NNURIs, Converter2, UnknownPrefix, NN_domain
from rdflib import Graph, RDF, RDFS, SKOS, URIRef, Literal, Namespace, OWL, XSD

# register some namespaces
oboInOwl = Namespace("http://www.geneontology.org/formats/oboInOwl#")
SKOSXL = Namespace("http://www.w3.org/2008/05/skos-xl#")
NNP = Namespace(NN_domain+"property/")

def build_curie_converter(input_file):
    """Build CURIE mappings from PREFIXes in `input_file`

    1. read from input .ttl file
    2. register nn:
"""
    with open(input_file) as file:
        prefixes = ""
        line = file.readline()
        while line.startswith("PREFIX") or line.startswith("@PREFIX"):
            prefixes += line
            line = file.readline()
    graph = Graph()
    graph.parse(io.StringIO(prefixes), format="ttl")
    converter = Converter2.from_rdflib(graph)
    converter.add_prefix("NN", NN_domain)
    return converter


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='''CLI tool for converting public URIs into NN URIs.

Replaces public URIs in the input_file with NN URIs (of both concepts and SKOS label objects)
and points to public URIs using NNP:sourced_from property.
''', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-d", "--domain", required=True, help="name of the domain model")
    parser.add_argument("-c", "--domain-code", required=True, help="numeric code of the domain model")
    parser.add_argument("-i", "--input-file", required=True, help="turtle file in which the public URIs will be replaced")
    parser.add_argument("-m", "--mapping-file", required=True, help="mapping file (in SSSOM format) to be used")
    parser.add_argument("-o", "--output-file", required=True, help="file to save the output to")
    parser.add_argument("--mapping-file2", help="alternative location to save the updated mapping file (in SSSOM format)")
    parser.add_argument("-p", "--from-public", action="store_true", help="download prefixes from public resources")
    parser.add_argument("--safe-load", action="store_true", help="[deprecated!] perform checks when loading mappings from sssom file (default behaviour)")
    parser.add_argument("--fast-load", action="store_true", help="do not perform checks when loading mappings from sssom file")
    parser.add_argument("--log", default="INFO", help="logging level (default: INFO")
    parser.add_argument("--dry", action="store_true", help="make no changes (do not save results to files)")

    args = parser.parse_args()

    numeric_level = getattr(logging, args.log)
    logging.basicConfig(
        level=numeric_level,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    try:
        nnuris = NNURIs.from_sssom_file(args.mapping_file, domain=args.domain, domain_code=args.domain_code, safe_load=not args.fast_load)
        logging.info("loaded mapping from {}".format(args.mapping_file))
        logging.info("mapping file contains {} prefixes, {} domain codes, and {} mappings".format(
            len(nnuris._curie_converter.prefix_map),
            len(nnuris._preamble["domain_codes"]),
            len(nnuris))
        )
    except FileNotFoundError:
        nnuris = NNURIs(domain=args.domain, domain_code=args.domain_code)
    g = Graph()
    logging.info("loading graph from {}...".format(args.input_file))
    g.parse(args.input_file)
    logging.info("loaded {} triples".format(len(g)))

    # get all subclasses of skos:Concept
    skos_concept_subclasses = [SKOS.Concept] + list(g.subjects(RDFS.subClassOf, SKOS.Concept))
    # get all public URIs to be replaced
    public_URIs = set()
    for cc in skos_concept_subclasses:
        public_URIs.update(s for s in g.subjects(RDF.type, cc))

    if args.from_public:
        # get missing prefixes from public sources
        nnuris.populate_prefixes(public_URIs, logging=logging)

    # filter out NN URIs
    public_URIs = sorted(puri for puri in public_URIs if nnuris.parse(str(puri))[0] != "NN")
    logging.info("extracted {} public URIs".format(len(public_URIs)))

    existing_maps = len(nnuris)
    # do NN URI minting in advance in order to control the order
    logging.info("obtaining NN URI for each public URI (minting it if needed)...")
    mapping = {puri:URIRef(nnuris.get_uri(str(puri))) for puri in public_URIs}
    logging.info("minted {} new NN URIs".format(len(nnuris) - existing_maps))
    # TODO: isolate newly-minted URIs

    logging.info("editing the graph...")

    # collect stats
    replaced_triples = 0
    added_triples = 0
    # store all skos:Labels (used for filtering later)
    label_objects = set(g.subjects(RDF.type, SKOSXL.Label))
    # go through all nodes from public_URIs
    for puri, nnuri in mapping.items():
        # get all triples where puri is subject
        for p, o in g.predicate_objects(puri):
            if isinstance(o, Literal):
                # leave Literals unchanged
                onn = o
            elif o in label_objects:
                # replace puri in a label URI
                onn = URIRef(str(o).replace(str(puri), str(nnuri)))
            else:
                # if o is a regular object, attempt to replace it into NN URI
                onn = mapping.get(o, o)
            g.remove((puri, p, o))
            g.add((nnuri, p, onn))
            replaced_triples += 1
            # if o is a skos:Label clean up other triples in which it participates
            if o in label_objects:
                for p1, o1 in g.predicate_objects(o):
                    # o1 can be puri, so we should map it to nnuri
                    o1nn = mapping.get(o1, o1)
                    g.remove((o, p1, o1))
                    g.add((onn, p1, o1nn))
                    replaced_triples += 1
        # get all triples where puri is object
        for s, p in g.subject_predicates(puri):
            # s can be puri, so we should map it to nnuri
            snn = mapping.get(s, s)
            g.remove((s, p, puri))
            g.add((snn, p, nnuri))
            replaced_triples += 1
        # add NNP:sourced_from to public URI
        g.add((nnuri, NNP.sourced_from, Literal(nnuris.compress(puri))))
        added_triples += 1
    logging.info("replaced {} and added {} triples".format(replaced_triples, added_triples))

    # save mapping file
    mf = args.mapping_file2 if args.mapping_file2 else args.mapping_file
    logging.info("saving updated mapping to file {}".format(mf))
    if not args.dry:
        nnuris.save_to_file(mf, logging=logging)
    # save input_file
    logging.info("saving graph to file {}".format(args.output_file))
    if not args.dry:
        g.serialize(destination=args.output_file, format="turtle")
    if args.dry:
        logging.info("NOTE: this is dry run, no file was saved to disk")
    logging.info("done")
