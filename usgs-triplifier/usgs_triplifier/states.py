from typing import ClassVar


class States:
    """
    Two-letter codes and full names of the US states and territories,
    spelled as USGS writes them in the state_name column of its GNIS products.

    Legacy dumps and GeoNames give a feature's state as the code, while the
    current products give the full name. Feature-alias and gnis:state IRIs
    are built from the full name, so both directions of the lookup must use
    these exact spellings.
    """

    # Code -> name, spelled as in the STATE rows of
    # GovernmentUnits_National_Text
    NAMES: ClassVar[dict[str, str]] = {
        "AL": "Alabama",
        "AK": "Alaska",
        "AZ": "Arizona",
        "AR": "Arkansas",
        "CA": "California",
        "CO": "Colorado",
        "CT": "Connecticut",
        "DE": "Delaware",
        "DC": "District of Columbia",
        "FL": "Florida",
        "GA": "Georgia",
        "HI": "Hawaii",
        "ID": "Idaho",
        "IL": "Illinois",
        "IN": "Indiana",
        "IA": "Iowa",
        "KS": "Kansas",
        "KY": "Kentucky",
        "LA": "Louisiana",
        "ME": "Maine",
        "MD": "Maryland",
        "MA": "Massachusetts",
        "MI": "Michigan",
        "MN": "Minnesota",
        "MS": "Mississippi",
        "MO": "Missouri",
        "MT": "Montana",
        "NE": "Nebraska",
        "NV": "Nevada",
        "NH": "New Hampshire",
        "NJ": "New Jersey",
        "NM": "New Mexico",
        "NY": "New York",
        "NC": "North Carolina",
        "ND": "North Dakota",
        "OH": "Ohio",
        "OK": "Oklahoma",
        "OR": "Oregon",
        "PA": "Pennsylvania",
        "RI": "Rhode Island",
        "SC": "South Carolina",
        "SD": "South Dakota",
        "TN": "Tennessee",
        "TX": "Texas",
        "UT": "Utah",
        "VT": "Vermont",
        "VA": "Virginia",
        "WA": "Washington",
        "WV": "West Virginia",
        "WI": "Wisconsin",
        "WY": "Wyoming",
        "AS": "American Samoa",
        "GU": "Guam",
        "MP": "Commonwealth of the Northern Mariana Islands",
        "PR": "Puerto Rico",
        "UM": "U.S. Minor Outlying Islands",
        "VI": "United States Virgin Islands",
        "FM": "Federated States of Micronesia",
        "MH": "Marshall Islands",
        "PW": "Palau",
    }

    # Name -> code mapping
    CODES: ClassVar[dict[str, str]] = {name: code for code, name in NAMES.items()}

    @classmethod
    def name_for(cls, code: str) -> str | None:
        """
        Looks up the full name of a state or territory.

        :param code: Two-letter state code.
        :return: The name as USGS spells it or None for an unknown code.
        """
        return cls.NAMES.get(code)

    @classmethod
    def code_for(cls, name: str) -> str | None:
        """
        Looks up the two-letter code of a state or territory.

        :param name: Full name as USGS spells it, e.g. "United States Virgin Islands".
        :return: The two-letter code or None for an unknown name.
        """
        return cls.CODES.get(name)
