"""The editor's intermediate model.

Google nests a card row six levels deep. Editing that directly is unpleasant
and error-prone, so the editor works on this flat model and translates only at
the edges — see `exporter` and `importer`.
"""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class FieldRef(BaseModel):
    """One reference in a fallback chain."""

    kind: Literal["text", "image"]
    module_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    date_format: str | None = None

    @property
    def field_path(self) -> str:
        """Return the `fieldPath` Google expects for this reference."""
        collection = "textModulesData" if self.kind == "text" else "imageModulesData"
        return f"object.{collection}['{self.module_id}']"


class Line(BaseModel):
    """A displayed value.

    `fallback_chain` is a list of things to *try*, not a list of things to
    show: Google displays the first reference that points at a non-empty
    field. This is how one template serves several kinds of person.
    """

    fallback_chain: Annotated[list[FieldRef], Field(min_length=1)]


class Cell(BaseModel):
    """One column of a front row, or one entry of the back list.

    When both values are set Google renders them as a single element with a
    slash between them, and it refuses a second value without a first.
    """

    first: Line | None = None
    second: Line | None = None

    @model_validator(mode="after")
    def _second_requires_first(self) -> Self:
        if self.second is not None and self.first is None:
            message = "second value requires a first value"
            raise ValueError(message)
        return self


class Row(BaseModel):
    """A front row: one, two or three cells."""

    cells: Annotated[list[Cell], Field(min_length=1, max_length=3)]


class TransitOption(BaseModel):
    """The Transit-only alternative to a field reference in the list view."""

    option: str


class ListView(BaseModel):
    """The two rows of the Wallet overview entry.

    `thirdRowOption` is deprecated upstream and is not modelled here.
    """

    first_row: Line | TransitOption | None = None
    second_row: Line | None = None


class BarcodeSection(BaseModel):
    """Text above and below the code area on the front of the card.

    Google offers three slots; two above the code and one below it.
    """

    first_top: Line | None = None
    second_top: Line | None = None
    first_bottom: Line | None = None


class TextModuleDraft(BaseModel):
    """One text module, either a constant or bound to a provider field."""

    module_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    header: str | None = Field(default=None, max_length=35)
    value: str = ""
    bound: bool = False


class ImageModuleDraft(BaseModel):
    """One image module. `uri` is exported; local previews never are."""

    module_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    uri: str = ""
    bound: bool = False


class LinkModuleDraft(BaseModel):
    """One entry of the link block on the back of the pass."""

    uri: str
    description: str | None = None


class RedemptionSettings(BaseModel):
    """How the pass is redeemed: over NFC, visually, or both."""

    smart_tap_enabled: bool = False
    redemption_issuers: list[str] = []
    redemption_value: str | None = None
    barcode_type: str | None = None
    barcode_value: str | None = None


class Draft(BaseModel):
    """A complete pass design, independent of Google's structures."""

    family: str
    head: dict[str, str] = {}
    front_rows: list[Row] = []
    barcode_section: BarcodeSection | None = None
    back_items: list[Cell] = []
    list_view: ListView = ListView()
    text_modules: list[TextModuleDraft] = []
    image_modules: list[ImageModuleDraft] = []
    link_modules: list[LinkModuleDraft] = []
    redemption: RedemptionSettings = RedemptionSettings()
    unmapped: dict[str, Any] = {}
