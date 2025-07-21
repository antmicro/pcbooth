"""Schema for gerber2blend configuration file"""

from marshmallow import fields  # type: ignore
from marshmallow import fields, ValidationError, Schema, EXCLUDE  # type: ignore
import re
from typing import Any, List, Set
from bpy import types


class BaseSchema(Schema):
    """
    A base schema for configuration definitions.
    This schema ensures that:
    - unknown fields are ignored during deserialization and not included in the parsed config
    - the schema is used only for loading (all fields are marked as `load_only`)
    - all fields are required, enforcing strict input validation
    """

    class Meta:
        unknown = EXCLUDE

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        for field in self.declared_fields.values():
            field.load_only = True
            field.required = True


class Color(fields.Field):
    """Custom Marshmallow field for validating color as a hex value."""

    HEX_PATTERN = r"^#?([0-9A-Fa-f]{6})$"

    def _deserialize(self, value: str, attr: Any, data: Any, **kwargs: Any) -> str:
        if isinstance(value, str):
            if match := re.match(self.HEX_PATTERN, value):
                return match.group(0)

        raise ValidationError(f"Not a valid color format (expected RGB hex value like AABBCC)")


class FileFormat(fields.Field):
    """Custom Marshmallow field for validating file formats belonging to predefined set."""

    def __init__(self, formats: Set[str] = set(), *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.formats = formats

    def _deserialize(self, value: str, attr: Any, data: Any, **kwargs: Any) -> str:
        if isinstance(value, str):
            if value in self.formats:
                return value

        raise ValidationError(f"'{value}' is not a valid file format (accepted formats: {', '.join(self.formats)})")


class FocalRatio(fields.Field):
    """Custom Marshmallow field for validating focal ratio strings."""

    FR_PATTERN = r"^[1f]\/\d+$"

    def _deserialize(self, value: str, attr: Any, data: Any, **kwargs: Any) -> float | str:
        if isinstance(value, str):
            if value == "auto":
                return value
            if match := re.match(self.FR_PATTERN, value):
                return eval(match.group(0).replace("f", "1"))

        if isinstance(value, float):
            return value

        raise ValidationError(f"Not a valid focal ratio (can be 'auto', float or fraction like '1/4' or 'f/4')")


class DataBlock(fields.Field):
    """Custom Marshmallow field for validating if string represents Blender data-block (Collection or Object)"""

    DB_PATTERN = r"^(Collection|Object)([^\w\s])(.+)$"

    def _deserialize(self, value: str, attr: Any, data: Any, **kwargs: Any) -> List[str]:
        if isinstance(value, str):
            if match := re.match(self.DB_PATTERN, value):
                return [match.group(1), match.group(3)]

        raise ValidationError(f"Not a valid <type>/<name> string defining Blender data-block")


def get_schema_field(schema_class: type[BaseSchema], field_name: str) -> fields.Field:
    """Get declared schema field by name."""
    try:
        schema_field = schema_class._declared_fields[field_name]
        return schema_field
    except KeyError:
        raise RuntimeError(f"Schema field '{field_name}' could not be found in {schema_class.__name__}")


def get_image_formats() -> Set[str]:
    """Get list of valid Blender image format extensions."""
    formats_dict = types.ImageFormatSettings.bl_rna.properties["file_format"].enum_items  # type: ignore
    return {item.identifier for item in formats_dict if "Output image" in item.description}


class SettingsSchema(BaseSchema):
    PRJ_EXTENSION = fields.String()
    FAB_DIR = fields.String()
    RENDER_DIR = fields.String()
    ANIMATION_DIR = fields.String()
    IMAGE_FORMAT = fields.List(FileFormat(get_image_formats()))
    VIDEO_FORMAT = fields.List(FileFormat({"AVI", "MP4", "MPEG", "WEBM", "GIF"}))
    THUMBNAILS = fields.Bool()
    KEEP_FRAMES = fields.Bool()
    SAVE_SCENE = fields.Bool()


class RendererSchema(BaseSchema):
    SAMPLES = fields.Integer()
    FPS = fields.Integer()
    IMAGE_WIDTH = fields.Integer()
    IMAGE_HEIGHT = fields.Integer()
    VIDEO_WIDTH = fields.Integer()
    VIDEO_HEIGHT = fields.Integer()
    THUMBNAIL_WIDTH = fields.Integer()
    THUMBNAIL_HEIGHT = fields.Integer()


class SceneSchema(BaseSchema):
    LIGHTS_COLOR = Color()
    LIGHTS_INTENSITY = fields.Number()  # type: ignore
    HDRI_INTENSITY = fields.Number()  # type: ignore
    DEPTH_OF_FIELD = fields.Bool()
    FOCAL_RATIO = FocalRatio()
    FOCAL_LENGTH = fields.Number()  # type: ignore
    ZOOM_OUT = fields.Number()  # type: ignore
    LED_ON = fields.Bool()
    ADJUST_POS = fields.Bool()
    ORTHO_CAM = fields.Bool()
    RENDERED_OBJECT = DataBlock(allow_none=True)


class BackgroundsSchema(BaseSchema):
    LIST = fields.List(fields.String(), allow_none=True)


class CamerasSchema(BaseSchema):
    TOP = fields.Bool()
    ISO = fields.Bool()
    FRONT = fields.Bool()
    LEFT = fields.Bool()
    RIGHT = fields.Bool()
    PHOTO1 = fields.Bool()
    PHOTO2 = fields.Bool()
    CUSTOM = fields.Bool()


class PositionsSchema(BaseSchema):
    TOP = fields.Bool()
    BOTTOM = fields.Bool()
    REAR = fields.Bool()


class ConfigurationSchema(BaseSchema):
    """Parent schema for configuration file"""

    SETTINGS = fields.Nested(SettingsSchema)
    RENDERER = fields.Nested(RendererSchema)
    SCENE = fields.Nested(SceneSchema)
    BACKGROUNDS = fields.Nested(BackgroundsSchema)
    CAMERAS = fields.Nested(CamerasSchema)
    POSITIONS = fields.Nested(PositionsSchema)
    OUTPUTS = fields.List(fields.Dict(), allow_none=True)
