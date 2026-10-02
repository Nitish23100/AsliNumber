"""Shared model plumbing used by every domain model in this package.

All five domain models (`Tenant`, `User`, `Membership`, `Session`, plus any
future ones) represent MongoDB documents and therefore share the same `_id`
convention: a `bson.ObjectId`, exposed to Pydantic as `id` via the `_id`
alias. `PyObjectId` is the one place that teaches Pydantic v2 how to
validate and serialize a raw `ObjectId` (as a string on the JSON side, as an
`ObjectId` instance on the Python side), so every model in this phase uses
the same convention consistently instead of each file inventing its own.
"""

from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler
from pydantic_core import core_schema


class _ObjectIdPydanticAnnotation:
    """Pydantic v2 core-schema glue for `bson.ObjectId`.

    - Python input: accepts an existing `ObjectId` or a valid 24-char hex
      string and converts it to `ObjectId`.
    - JSON input/output: represented as a plain string, since MongoDB's
      `ObjectId` isn't JSON-native and the API layer deals in strings.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate_from_str(value: str) -> ObjectId:
            if not ObjectId.is_valid(value):
                raise ValueError(f"{value!r} is not a valid ObjectId")
            return ObjectId(value)

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    from_str_schema,
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )


PyObjectId = Annotated[ObjectId, _ObjectIdPydanticAnnotation]
"""An `ObjectId` field type usable directly in Pydantic v2 models.

Accepts an `ObjectId` or a valid hex string on input; serializes to a plain
string (e.g. for JSON responses).
"""


class MongoBaseModel(BaseModel):
    """Base class for documents stored in MongoDB.

    Exposes Mongo's `_id` field as `id` on the Python side (via
    `populate_by_name`, so both `id=` and `_id=` work as constructor
    kwargs), and allows `ObjectId` as an arbitrary type for any field that
    isn't going through `PyObjectId`'s annotation path.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
