"""Additive v2 inventory preserves fine publisher distinctions and coarse aliases."""
from .protocol import FINE_TO_COARSE

ONTOLOGY_V2 = "address-benchmark.us-roles/v2"
US_COARSE = {
    **dict.fromkeys(("AddressNumber", "AddressNumberPrefix", "AddressNumberSuffix"), "house_number"),
    **dict.fromkeys(("StreetName", "StreetNamePreDirectional", "StreetNamePostDirectional", "StreetNamePreType", "StreetNamePostType", "StreetNamePreModifier", "StreetNamePostModifier"), "road"),
    **dict.fromkeys(("OccupancyType", "OccupancyIdentifier"), "unit"),
    **dict.fromkeys(("SubaddressType", "SubaddressIdentifier"), "subaddress"),
    **dict.fromkeys(("FloorType", "FloorIdentifier"), "level"),
    **dict.fromkeys(("USPSBoxType", "USPSBoxID", "USPSBoxGroupType", "USPSBoxGroupID"), "po_box"),
    "PlaceName": "city", "StateName": "state", "ZipCode": "postcode", "ZipPlus4": "postcode",
    "CountryName": "country", "BuildingName": "building", "LandmarkName": "building", "Recipient": "recipient",
    "NotAddress": "not_address", "CornerOf": "corner_of", "IntersectionSeparator": "intersection_separator",
    "CityDistrict": "city_district", "Suburb": "suburb", "StateDistrict": "state_district", "Category": "category", "Near": "near",
}
US_FINE = {native: "us:" + native for native in US_COARSE}
COARSE_ALIASES = {"house": "building", "postal_delivery": "po_box"}
NEUTRAL_ROLES = set(US_COARSE.values()) | {"road", "house_number", "unit", "level", "name", "country_region", "island", "world_region", "entrance", "staircase"}
GEO_NATIVE = dict(HOUSENUM="AddressNumber", PREDIRECTIONAL="StreetNamePreDirectional", STREET="StreetName",
                  ROADTYPE="StreetNamePostType", POSTDIRECTIONAL="StreetNamePostDirectional", CITY="PlaceName", STATE="StateName", POSTAL="ZipCode")


def register():
    FINE_TO_COARSE.update({US_FINE[native]: coarse for native, coarse in US_COARSE.items()})
    FINE_TO_COARSE.update({role: role for role in NEUTRAL_ROLES})


register()
