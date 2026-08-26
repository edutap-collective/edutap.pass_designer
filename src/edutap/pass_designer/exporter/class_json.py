"""Translate a `Draft` into the family's Google Wallet class."""

from typing import Any

from edutap.wallet_google.models.datatypes.class_template_info import (
    BarcodeSectionDetail,
    CardBarcodeSectionDetails,
    CardRowOneItem,
    CardRowTemplateInfo,
    CardRowThreeItems,
    CardRowTwoItems,
    CardTemplateOverride,
    ClassTemplateInfo,
    DetailsItemInfo,
    DetailsTemplateOverride,
    FieldReference,
    FieldSelector,
    FirstRowOption,
    ListTemplateOverride,
    TemplateItem,
)
from edutap.wallet_google.models.datatypes.general import Image, ImageUri

from ..draft.models import (
    BarcodeSection,
    Cell,
    Draft,
    Line,
    ListView,
    Row,
    TransitOption,
)
from ..platforms.google.families import FamilyDescriptor
from ..platforms.google.families import get as get_family


def _selector(line: Line) -> FieldSelector:
    """Turn a fallback chain into the selector Google reads top-down."""
    return FieldSelector(
        fields=[
            FieldReference(
                fieldPath=reference.field_path, dateFormat=reference.date_format
            )
            for reference in line.fallback_chain
        ]
    )


def _item(cell: Cell) -> TemplateItem:
    return TemplateItem(
        firstValue=_selector(cell.first) if cell.first else None,
        secondValue=_selector(cell.second) if cell.second else None,
    )


def _row(row: Row) -> CardRowTemplateInfo:
    items = [_item(cell) for cell in row.cells]
    if len(items) == 1:
        return CardRowTemplateInfo(oneItem=CardRowOneItem(item=items[0]))
    if len(items) == 2:
        return CardRowTemplateInfo(
            twoItems=CardRowTwoItems(startItem=items[0], endItem=items[1])
        )
    return CardRowTemplateInfo(
        threeItems=CardRowThreeItems(
            startItem=items[0], middleItem=items[1], endItem=items[2]
        )
    )


def _list_override(view: ListView) -> ListTemplateOverride | None:
    if view.first_row is None and view.second_row is None:
        return None
    if isinstance(view.first_row, TransitOption):
        # Transit is not part of this plan. Silently dropping the value would be
        # exactly the failure this tool exists to prevent, so this raises instead
        # of producing a class with a missing first row option.
        message = "transit list options are not supported yet"
        raise NotImplementedError(message)
    first: FirstRowOption | None = None
    if view.first_row is not None:
        first = FirstRowOption(fieldOption=_selector(view.first_row))
    return ListTemplateOverride(
        firstRowOption=first,
        secondRowOption=_selector(view.second_row) if view.second_row else None,
    )


def _barcode_section(
    section: BarcodeSection | None,
) -> CardBarcodeSectionDetails | None:
    """Turn the three optional slots around the code into their details."""
    if section is None:
        return None

    def detail(line: Line | None) -> BarcodeSectionDetail | None:
        return BarcodeSectionDetail(fieldSelector=_selector(line)) if line else None

    details = CardBarcodeSectionDetails(
        firstTopDetail=detail(section.first_top),
        secondTopDetail=detail(section.second_top),
        firstBottomDetail=detail(section.first_bottom),
    )
    if all(
        value is None
        for value in (
            details.firstTopDetail,
            details.secondTopDetail,
            details.firstBottomDetail,
        )
    ):
        return None
    return details


def _template_info(draft: Draft) -> ClassTemplateInfo | None:
    card = (
        CardTemplateOverride(
            cardRowTemplateInfos=[_row(row) for row in draft.front_rows]
        )
        if draft.front_rows
        else None
    )
    details = (
        DetailsTemplateOverride(
            detailsItemInfos=[
                DetailsItemInfo(item=_item(cell)) for cell in draft.back_items
            ]
        )
        if draft.back_items
        else None
    )
    lists = _list_override(draft.list_view)
    barcode_section = _barcode_section(draft.barcode_section)
    if card is None and details is None and lists is None and barcode_section is None:
        return None
    return ClassTemplateInfo(
        cardBarcodeSectionDetails=barcode_section,
        cardTemplateOverride=card,
        detailsTemplateOverride=details,
        listTemplateOverride=lists,
    )


def _head_payload(descriptor: FamilyDescriptor, head: dict[str, str]) -> dict[str, Any]:
    """Copy the class-scoped head fields the family declares.

    Task 4 gave `HeadField` a `scope`: object-scoped fields such as
    `accountName` and `accountId` live on the pass *object*, not the class,
    and handing them to the class model would fail validation. A key
    `draft.head` carries that the descriptor does not declare at all is
    ignored outright — the descriptor is the single source of truth for what
    a family's head holds, so a stray key is more likely stale editor state
    than a value this exporter should preserve.

    `image_uri` fields need their string value wrapped as
    `Image(sourceUri=ImageUri(uri=...))`, since `Draft.head` is
    `dict[str, str]` but the wallet model expects a nested `Image`. An empty
    value is skipped rather than wrapped, because `ImageUri.uri` is a
    required, validated URL — an empty string would fail there, not signal
    "no image" the way it does for a plain text field.

    `localized_text` is rejected outright: it would need a `LocalizedString`,
    not a bare string, the same mismatch `image_uri` has. No current family
    declares one, so this raises instead of silently mis-mapping it, in the
    spirit of the transit ruling in `_list_override`.
    """
    fields_by_key = {field.key: field for field in descriptor.head_fields}
    payload: dict[str, Any] = {}
    for key, value in head.items():
        field = fields_by_key.get(key)
        if field is None or field.scope != "class":
            continue
        if field.kind == "image_uri":
            if value:
                payload[key] = Image(sourceUri=ImageUri(uri=value))
            continue
        if field.kind == "localized_text":
            message = "localized head fields are not supported yet"
            raise NotImplementedError(message)
        payload[key] = value
    return payload


def build_class(draft: Draft, class_id: str) -> dict[str, Any]:
    """Return the family's class as a plain dict, ready to be written out.

    The dict is produced by the upstream Pydantic model, so anything it
    contains has already passed that model's validation.
    """
    descriptor = get_family(draft.family)
    payload: dict[str, Any] = {"id": class_id, **_head_payload(descriptor, draft.head)}

    template_info = _template_info(draft)
    if template_info is not None:
        payload["classTemplateInfo"] = template_info

    if draft.redemption.smart_tap_enabled:
        payload["enableSmartTap"] = True
        payload["redemptionIssuers"] = draft.redemption.redemption_issuers

    wallet_class = descriptor.class_model(**payload)
    exported = wallet_class.model_dump(exclude_none=True, mode="json")

    # `exported` is a full model_dump, so it always carries a value for every
    # field with a non-None default (e.g. `reviewStatus`), whether or not this
    # function ever set it. Letting `exported` win unconditionally would
    # silently overwrite a preserved value with a default nobody chose. So
    # `exported` wins only for keys this function actually decided (`payload`);
    # for anything else, a preserved value in `draft.unmapped["class"]` wins,
    # defaults included.
    preserved = draft.unmapped.get("class", {})
    carried = {key: value for key, value in preserved.items() if key not in payload}
    return {**exported, **carried}
