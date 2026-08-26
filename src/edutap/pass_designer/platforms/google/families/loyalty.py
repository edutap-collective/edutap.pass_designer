"""The Loyalty family — the library card case.

`required_on_create` is copied from Google's REST reference, not derived from
the model: the model requires only `id`, while the API also insists on
`issuerName`, `programName` and `reviewStatus`.
See https://developers.google.com/wallet/retail/loyalty-cards/rest/v1/loyaltyclass

`accountName` and `accountId` are scoped to the pass object: they live on
`LoyaltyObject`, not on `LoyaltyClass`, even though every other head field
here is a class attribute. Every other head field keeps the default
`scope="class"`.
"""

from edutap.wallet_google.models.passes.retail import LoyaltyClass, LoyaltyObject

from . import FamilyDescriptor, HeadField, register

DESCRIPTOR = register(
    FamilyDescriptor(
        family_id="loyalty",
        label="Loyalty card",
        class_model=LoyaltyClass,
        object_model=LoyaltyObject,
        head_fields=[
            HeadField(
                key="issuerName", label="Issuer name", kind="text", required=True
            ),
            HeadField(
                key="programName", label="Program name", kind="text", required=True
            ),
            HeadField(key="programLogo", label="Program logo", kind="image_uri"),
            HeadField(key="wideProgramLogo", label="Wide logo", kind="image_uri"),
            HeadField(key="heroImage", label="Hero image", kind="image_uri"),
            HeadField(key="hexBackgroundColor", label="Background", kind="colour"),
            HeadField(key="accountNameLabel", label="Account name label", kind="text"),
            HeadField(key="accountIdLabel", label="Account ID label", kind="text"),
            HeadField(
                key="accountName", label="Account name", kind="text", scope="object"
            ),
            HeadField(key="accountId", label="Account ID", kind="text", scope="object"),
        ],
        required_on_create=frozenset({"issuerName", "programName", "reviewStatus"}),
    )
)
