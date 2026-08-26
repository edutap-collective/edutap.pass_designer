"""Descriptors are the only place a family differs from any other."""

import pytest

from edutap.pass_designer.platforms.google import families


def test_loyalty_is_registered() -> None:
    descriptor = families.get("loyalty")

    assert descriptor.family_id == "loyalty"
    assert descriptor.class_model.__name__ == "LoyaltyClass"
    assert descriptor.object_model.__name__ == "LoyaltyObject"


def test_loyalty_declares_what_google_requires_beyond_pydantic() -> None:
    descriptor = families.get("loyalty")

    assert "issuerName" in descriptor.required_on_create
    assert "programName" in descriptor.required_on_create
    assert "reviewStatus" in descriptor.required_on_create


def test_pydantic_alone_would_not_catch_those() -> None:
    descriptor = families.get("loyalty")
    pydantic_required = {
        name
        for name, field in descriptor.class_model.model_fields.items()
        if field.is_required()
    }

    assert "issuerName" not in pydantic_required


def test_an_unknown_family_is_refused_by_name() -> None:
    with pytest.raises(KeyError, match="nonesuch"):
        families.get("nonesuch")


def test_loyalty_head_fields_are_scoped_to_the_side_that_declares_them() -> None:
    descriptor = families.get("loyalty")
    by_key = {field.key: field for field in descriptor.head_fields}

    assert by_key["accountId"].scope == "object"
    assert by_key["accountName"].scope == "object"
    assert by_key["programName"].scope == "class"
    assert by_key["issuerName"].scope == "class"
