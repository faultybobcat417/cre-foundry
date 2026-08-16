from cre_foundry.normalization import normalize_address, normalize_name


def test_normalize_name_strips_legal_suffix():
    assert normalize_name("Northstar Logistics Inc.") == "northstar logistics"


def test_normalize_address_standardizes_suffix():
    assert normalize_address("8100 Dixie Road") == normalize_address("8100 Dixie Rd")
