"""Per-kind conversion shared by the class and object head exporters.

Both `class_json._head_payload` and `object_json._head_payload` walk
`draft.head` and, for each declared field in the scope they each care about,
convert the field's string value the same way. What differs between the two
is only *which* scope they keep (`"class"` vs `"object"`) — that filtering
stays local to each function, since sharing it would need a flag argument to
pick the scope, and forcing that flag would buy nothing but a fatter call
signature. What is genuinely identical is what happens once a field is known
to belong to the scope being built, and that is what lives here.
"""

from edutap.wallet_google.models.datatypes.general import Image, ImageUri

from ..platforms.google.families import HeadField


def convert_head_value(field: HeadField, value: str) -> Image | str | None:
    """Convert one head value per `field.kind`.

    Returns `None` to signal "skip this field" — currently only an empty
    `image_uri`, since `ImageUri.uri` is a required, validated URL and an
    empty string would fail there rather than mean "no image" the way it does
    for a plain text field.

    Raises `NotImplementedError` for `localized_text`: it would need a
    `LocalizedString`, not a bare string, the same mismatch `image_uri` has.
    No current family declares one, so this raises instead of silently
    mis-mapping it, in the spirit of the transit ruling in `class_json`.
    """
    if field.kind == "image_uri":
        return Image(sourceUri=ImageUri(uri=value)) if value else None
    if field.kind == "localized_text":
        message = "localized head fields are not supported yet"
        raise NotImplementedError(message)
    return value
