# Classes for handling SSSOM file

# Dependencies:
# pip install curies pip-system-certs validators

import curies, csv, yaml, validators
from collections import UserDict
from itertools import chain


NN_domain = "https://ontology.novonordisk.com/"

class UnknownPrefix(KeyError):
    """An error raised when URI or CURIE cannot be understood (prefix is unknown)."""

    def __init__(self, key, *args):
        super().__init__(*args)
        self.key = key

    def __str__(self):
        return "Missing prefix for '{}'".format(self.key)

class RecordExists(KeyError):
    """An error raised when record already exists in Mapping."""

    def __init__(self, key, *args):
        super().__init__(*args)
        self.key = key

    def __str__(self):
        return "Record for key '{}' already exists.".format(self.key)

class InvalidURI(ValueError):
    """An error raised when an invalid URI is encoutered."""

    def __init__(self, key, *args):
        super().__init__(*args)
        self.key = key

    def __str__(self):
        return "'{}' is not a valid URI.".format(self.key)

class InvalidLine(Exception):
    """An error raised when a line in SSSOM file cannot be read."""

    def __init__(self, line, line_nr=None, *args):
        super().__init__(*args)
        self.line = line
        self.line_nr = "" if line_nr==None else str(line_nr)

    def __str__(self):
        return "Line {}'{}' in SSSOM file could not be read.".format(self.line_nr + ": " if self.line_nr else self.line_nr, self.line)

class Converter2(curies.Converter):
    """Overrides .compress and .expand methods to fail if there are unknown prefixes."""

    def compress(self, uri, mode="safe"):
        """Compresses provided URI.

        Modes of operation:
        "safe"  - Exception is raised if prefix is missing
        "fast"  - returns CURIE if prefix exists, else returns the input
        """
        if mode=="fast":
            if not uri: return ""
            try:
                curi = super().compress(uri)
                return curi if curi else uri
            except ValueError:
                return uri
        elif mode=="safe":
            input_type = self.validate(uri)
            if input_type=="curie":
                return uri
            if input_type=="uri":
                return super().compress(uri)

    def expand(self, curie, mode="safe"):
        """Expands provided CURIE.

        Modes of operation:
        "safe"  - Exception is raised if prefix is missing
        "fast"  - returns URI if prefix exists, else returns the input
        """
        if mode=="fast":
            if not curie: return ""
            try:
                uri = super().expand(curie)
                return uri if uri else curie
            except (ValueError, AttributeError):
                return curie
        elif mode=="safe":
            input_type = self.validate(curie)
            if input_type=="uri":
                return curie
            if input_type=="curie":
                return super().expand(curie)

    def parse(self, value):
        """A natural join of parse_curie and parse_uri (with added failing in case of unknown prefixes)."""
        input_type = self.validate(value)
        if input_type=="curie":
            return super().parse_curie(value)
        if input_type=="uri":
            return self.parse_uri(value)

    def validate(self, value):
        """Checks whether `value` can be understood using prefixes known to the object.

        Can return:
        - `uri`
        - `curie`
        If neither, raises UnknownPrefix error
        """
        if self.parse_uri(value)[0] in self.prefix_map:
            if not validators.url(value):
                raise InvalidURI(value)
            return "uri"
        try:
            if self.parse_curie(value)[0] in self.prefix_map:
                return "curie"
        except ValueError:
            pass
        raise UnknownPrefix(value)

    def standardize(self, curie):
        """Standardizes CURIE by passing it through expand and compress (cf curies.Converter.standardize_curies)."""
        return self.compress(self.expand(curie))

    @classmethod
    def get_converters(cls, sources=["obo", "go", "monarch", "bioregistry"]):
        """Fetches converters from the given locations and returns a joined converter.

        Uses existing get_<source>_converter class methods from curies module.
        In case of conflicting records, sources earlier in the list take precedence.
        """
        return cls(
            list(chain(*map(
                lambda source: getattr(curies, "get_"+source+"_converter")().records,
                sources[::-1]
            ))),
            strict=False
        )


class DomainCodes(UserDict):
    """Dict containing domain codes.

    Implements assumptions:
    - domain is a string without blanks
    - domain_code is int between 00 and 99 (incl.)
    - domain_codes are unique
    """
    def __init__(self, domain_codes=None):
        """Initializes DomainCodes object. If provided, loads from domain_codes."""
        super().__init__()
        self._reverse_map = {}
        if domain_codes:
            for domain, domain_code in domain_codes.items():
                self.__setitem__(domain, domain_code)

    @classmethod
    def _format_domain_code(cls, domain_code):
        # Casts domain_code into {:02}
        return "{:02}".format(int(domain_code))

    def __setitem__(self, domain, domain_code):
        """Inserts new entry."""
        # format domain_code
        domain_code = self._format_domain_code(domain_code)
        # if the pair exists, do nothing
        if (domain, domain_code) in self.items():
            return
        # check validity of values
        assert isinstance(domain, str), "Domain should be a string"
        assert len(domain.split()) == 1 and len(domain) == len(domain.strip()), "Domain cannot contain whitespaces"
        assert 0 <= int(domain_code) < 100, "Domain code {} is out of bounds: 0 <= domain_code < 100".format(domain_code)
        # check if domain and domain_code already exist
        assert domain not in self, "Domain {} is already registered with domain code {}".format(domain, self[domain])
        assert domain_code not in self._reverse_map, "Domain code {} is already registered for domain {}".format(domain_code, self._reverse_map[domain_code])
        # if all checks pass, insert new value
        super().__setitem__(domain, domain_code)
        self._reverse_map[domain_code] = domain

    def get_domain(self, domain_code):
        # Returns domain for provided domain_code
        domain_code = self._format_domain_code(domain_code)
        try:
            return self._reverse_map[domain_code]
        except KeyError:
            raise KeyError("Domain code {} is not registered".format(domain_code))

    def get_code(self, domain):
        # Returns domain_code for provided domain
        return self.__getitem__(domain)

    def __getitem__(self, domain):
        try:
            return super().__getitem__(domain)
        except KeyError:
            raise KeyError("Domain {} is not registered".format(domain))


class Mapping(UserDict):
    """A dict containing URI mappings with extra features:

    - reads mapping from SSSOM file
      - stores them as CURIEs, based on included mapping
      - raises error if there's a missing CURIE mapping
    - uses CURIEs to:
      - translate any key thrown at it,
      - return value as CURIE by default (with __getitem__)
      - separate get_uri function returns mapped value as URI
    - save mapping into SSSOM file
    """

    # all columns, properly ordered
    # TODO: consider putting labels after mapping_justification (as it is done in SSSOM file example)
    _SSSOM_columns = [
        'subject_id',
        'subject_label',
        'subject_category',
        'predicate_id',
        'predicate_label',
        'predicate_modifier',
        'object_id',
        'object_label',
        'object_category',
        'mapping_justification',
        'author_id',
        'author_label',
        'reviewer_id',
        'reviewer_label',
        'creator_id',
        'creator_label',
        'license',
        'subject_type',
        'subject_source',
        'subject_source_version',
        'object_type',
        'object_source',
        'object_source_version',
        'mapping_provider',
        'mapping_source',
        'mapping_cardinality',
        'mapping_tool',
        'mapping_tool_version',
        'mapping_date',
        'confidence',
        'curation_rule',
        'curation_rule_text',
        'subject_match_field',
        'object_match_field',
        'match_string',
        'subject_preprocessing',
        'object_preprocessing',
        'semantic_similarity_score',
        'semantic_similarity_measure',
        'see_also',
        'other',
        'comment'
    ]

    def __init__(self, curie_converter=None, mapping=None, preamble=None,
        defaults={"predicate_id":"skos:exactMatch", "mapping_justification":"semapv:LexicalMatching"},
        safe_load=True,
        **kwargs):
        """Initialize the Mapping object.

        :curie_converter: object of type curie.Converter
        :mapping: iterable that returns a tuple of mapped values on __next__
        :preamble: dict representing preamble of the SSSOM file
        :defaults: default values for columns: predicate_id, mapping_justification
        :safe_load: perform checks on values if True
        """
        super().__init__(**kwargs)
        self._defaults = defaults
        self._curie_converter = Converter2([]) if curie_converter is None else curie_converter
        self.add_prefix = self._curie_converter.add_prefix
        self.format_curie = self._curie_converter.format_curie
        self.expand = self._curie_converter.expand
        self.compress = self._curie_converter.compress
        self.parse = self._curie_converter.parse
        self.standardize = self._curie_converter.standardize
        if preamble is not None:
            # populate self._curie_converter.prefix_map first
            try:
                for prefix, uri in preamble["curie_map"].items():
                    if prefix not in self._curie_converter.prefix_map:
                        self.add_prefix(prefix, uri)
            except KeyError:
                pass
            self._preamble = preamble
        else:
            self._preamble = {}
        self._preamble["curie_map"] = self._curie_converter.prefix_map
        if mapping:
            set_val = self.set if safe_load else self._fast_set
            for k,v in mapping:
                set_val(k, v)

    @classmethod
    def from_sssom_file(cls, sssom_file, safe_load=True, **kwargs):
        """Parses the SSSOM mapping file and returns a Mapping object.

        CURIE mappings need to be present in the SSSOM file, otherwise loading will fail.
        """
        def extract_rows(f, header, line_nr=0):
            """Iterator over rows in the body of SSSOM file. Also extracts values.

            Raises informative exception (InvalidLine) in case of an invalid row.
            """
            try:
                subj_i = header.index("subject_id")
                key_ind = [(key, index) for index, key in enumerate(header) if key != "subject_id"]
            except ValueError:
                return []
            try:
                for vals in csv.reader(f, delimiter="\t"):
                    line_nr += 1
                    yield (vals[subj_i], {key: vals[i] for key, i in key_ind})
            except IndexError:
                raise InvalidLine("\t".join(vals), line_nr)

        with open(sssom_file) as f:
            # read preamble
            preamble = ""
            line = f.readline()
            line_nr = 1
            while line.startswith("#"):
                preamble += line[1:].rstrip() + "\n"
                line = f.readline()
                line_nr += 1
            # parse preamble into preamble
            preamble = yaml.safe_load(preamble)
            preamble = preamble if preamble else {"curie_map": {}}
            # load `curie_map` from preamble into Converter2
            curie_converter = Converter2.from_prefix_map(preamble["curie_map"])
            # extract rows from SSSOM file
            header = list(csv.reader((line,), delimiter='\t'))[0]
            uri_map = extract_rows(f, header, line_nr)
            # return initialized Mapping object
            return Mapping(
                curie_converter=curie_converter,
                mapping=uri_map,
                preamble=preamble,
                safe_load=safe_load,
                **kwargs
            )

    def populate_prefixes(self, uri_list,
        sources=["obo", "go", "monarch", "bioregistry"],
        public_converter=None,
        logging=None):
        # Adds prefixes needed for uri_list by fetching them from public sources.
        if logging:
            logging.info("loading prefixes from public sources...")
            new_prefixes = []
        public_converter = public_converter if public_converter else Converter2.get_converters()
        if logging:
            logging.info("loaded {} prefixes".format(len(public_converter.prefix_map)))
        for uri in uri_list:
            try:
                # in case of multiple prefixes, we rely on parse_* functions from curies.Converter
                # to return the one that shortens CURIE the most
                prefix, id = public_converter.parse(uri)
            except UnknownPrefix:
                # we are only interested in collecting prefixes that are present in public_converter
                continue
            # construct uri part of the mapping
            uri_prefix = uri.replace(id, "")
            if prefix not in self._curie_converter.prefix_map:
                self.add_prefix(prefix, uri_prefix)
                if logging:
                    new_prefixes.append((prefix, uri_prefix))
        if logging:
            logging.info("added {} prefixes".format(len(new_prefixes)))
            if len(new_prefixes):
                logging.debug("added prefixes:\n{}".format("".join("  {:>10}: {}\n".format(*p) for p in new_prefixes)))

    def set(self, key, item):
        # Setter that supports setting additional metadata for the subject_id:object_id pair.
        ekey = self.expand(key)
        if type(item) is dict:
            assert "object_id" in item, "provided dict has to have 'object_id'"
            # do not store metadata if it is the same as in defaults
            value = {k:v for k,v in item.items() if not self._defaults.get(k) == v}
            if item["object_id"] != "":
                # expand object_id unless it is an empty string
                value.update({"object_id": self.expand(item["object_id"])})
        else:
            value = {"object_id" : self.expand(item)}
        if ekey in self.data:
            if value == self.data[ekey]:
                # do nothing if inserted data already exists
                return
            raise RecordExists(ekey)
        self.data[ekey] = value

    def _fast_set(self, key, item):
        """Like set, but it performs no checks."""
        if type(item) is dict:
            # do not store metadata if it is the same as in defaults
            value = {k:self.expand(v, "fast") for k,v in item.items() if not self._defaults.get(k) == v}
        else:
            value = {"object_id" : self.expand(item, "fast")}
        self.data[self.expand(key, "fast")] = value

    def get_values(self, key, *args):
        """Getter that returns requested values (metadata) for key.

        Returns values in a tuple in the order they were requested.
        Values are looked for in the following order:
        - in dict behind 'key',
        - in self._defaults dict
        If not found in neither, None is returned.
        """
        ekey = self.expand(key, "fast")
        return tuple(self.compress(self.data[ekey].get(md, self._defaults.get(md)), "fast") for md in args)

    def __setitem__(self, key, item):
        # Expands both `key` nad `item` into URIs and fails if key already exists.
        ekey = self.expand(key)
        if ekey in self.data:
            raise RecordExists(ekey)
        self.data[ekey] = {"object_id": self.expand(item)}

    def __getitem__(self, key):
        # Returns the compressed mapped-to value, if exists
        return self.compress(super().__getitem__(self.expand(key))["object_id"], "fast")

    def __contains__(self, key):
        # A wrapper around built-in __contains__ that compresses `key` into CURIE
        try:
            return super().__contains__(self.expand(key))
        except UnknownPrefix:
            return False

    def __iter__(self):
        # A wrapper around built-in __iter__ that compresses keys into CURIEs
        for k in super().__iter__():
            yield self.compress(k, "fast")

    def get_uri(self, key):
        # read from the mapping and return the result as URI
        return self.expand(self.__getitem__(key))

    def get_uri2(self, key):
        """Read from the mapping and return the result as URI.
        If unsuccessful, make the best effort to provide something.

        This function does its best to return the requested URI by:
        - returning expanded value for key if present in mapping,
        - if the mapping is not present, return expanded key,
          (this includes the case where prefix is missing for the value of object_id)
        - if expanding key also fails (prefix is missing for key), return unmodified key.
        """
        # TODO: consider merging this with get_uri by adding a 'default' parameter there
        try:
            return self.expand(self.__getitem__(key))
        except UnknownPrefix as ex:
            # in case UnknownPrefix is raised by value, compress key
            if ex.key != key:
                key = self.expand(key)
            # else, UnknownPrefix is raised by key, return it verbatim
            return key
        except KeyError:
            return self.expand(key)

    def save_to_file(self, file_name, logging=None):
        """Saves the mapping to a SSSOM file.

        All metadata values present for each key (subject_id) are saved,
        if they are present in the list of permitted SSSOM columns.
        Values for columns present in self._defaults are used when not present in individual key's entry.
        """
        with open(file_name, "w") as f:
            # save preamble
            f.writelines(["#"+line+"\n" for line in yaml.dump(self._preamble).split("\n")[:-1]])
            # collect all columns from metadata in individual mappings and default values
            all_columns = set(chain(*(v.keys() for v in self.data.values())))
            all_columns.update(set(self._defaults.keys()))
            # add first column
            all_columns.add("subject_id")
            # retain only columns that are valid in SSSOM file
            columns = [c for c in self._SSSOM_columns if c in all_columns]
            if logging:
                logging.info("columns that will be saved: {}".format(", ".join(columns)))
                remaining_columns = [c for c in all_columns if c not in columns]
                if remaining_columns:
                    logging.info("columns that WILL NOT be saved (they are not valid SSSOM slots): {}".format(", ".join(remaining_columns)))
            # save URI mapping
            f.write("\t".join(columns) + "\n")
            for subject_id in sorted(self.__iter__()):
                row = (subject_id,) + self.get_values(subject_id, *columns[1:])
                if logging:
                    logging.debug("saving row: {}".format(row))
                f.write("{}\n".format("\t".join(row)))


class NNURIs(Mapping):
    """An extension of Mapping specific for mappings between public and NN URIs.

    Features:
    - if mapping is missing, it will be generated at request time
    - setting a duplicate `key` (with `[..]`) raises a `RecordExists` exception
    """
    def __init__(self, domain=None, domain_code=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain_codes = DomainCodes(self._preamble.get("domain_codes"))
        # at least one has to be given
        assert domain != None or domain_code != None
        # go through the options
        if domain and not domain_code:
            self._domain_code = self.domain_codes.get_code(domain)
        if not domain and domain_code:
            assert domain_code in self.domain_codes._reverse_map, "domain_code '{}' is not registered in the mapping file".format(domain_code)
            self._domain_code = domain_code
        if domain and domain_code:
            self.domain_codes[domain] = domain_code
            self._domain_code = self.domain_codes[domain]
        self._preamble["domain_codes"] = self.domain_codes.data
        # add NN prefix
        if "NN" not in self._curie_converter.prefix_map:
            self.add_prefix("NN", NN_domain)
        self._NNURIs = set(nnuri["object_id"] for nnuri in self.data.values())
        self._nextNNID = 1
        self._maxID = 900000

    @property
    def domain_code(self):
        return self._domain_code

    @property
    def domain(self):
        return self.domain_codes.get_domain(self._domain_code)

    @classmethod
    def from_sssom_file(cls, sssom_file, domain=None, domain_code=None, **kwargs):
        mapping = super().from_sssom_file(sssom_file, **kwargs)
        return cls(
            domain=domain,
            domain_code=domain_code,
            curie_converter=mapping._curie_converter,
            mapping=mapping.data.items(),
            preamble=mapping._preamble,
            **kwargs
        )

    @property
    def nextNNID(self):
        # returns first available NNID (to be used when minting NN URIs)
        while self._format_NNURI(self._nextNNID) in self._NNURIs:
            nextNNID = self._nextNNID + 1
            assert nextNNID < self._maxID
            self._nextNNID = nextNNID
        return "{:06}".format(self._nextNNID)

    def _format_NNURI(self, NNID):
        return NN_domain + "{}{:06}".format(self.domain_code, int(NNID))

    def __setitem__(self, key, item):
        # Extends __setitem__ from Mapping by adding item to ._NNURIs
        super().__setitem__(key, item)
        self._NNURIs.add(self.expand(item))

    def get(self, key):
        # Gets the item for `key`. Creates one if missing.
        try:
            return self.__getitem__(key)
        except KeyError:
            self.__setitem__(key, self._format_NNURI(self.nextNNID))
            return self.__getitem__(key)

    def get_uri(self, key):
        # Gets NN URI for a given public uri. Create one if missing.
        return self.expand(self.get(key))


if __name__ == "__main__":
    pass
