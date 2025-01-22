"""Module responsible for parsing config file."""

import logging
from shutil import copyfile
from typing import Any, Callable, Dict, Optional, List
import ruamel.yaml
import re
from bpy import types

logger = logging.getLogger(__name__)

# Name of the configuration file
# This is the name that is used for the template
# and when copying the template to a local config.
BLENDCFG_FILENAME = "blendcfg.yaml"


class Field:
    """Represents schema of a configuration field."""

    def __init__(
        self,
        field_type: str,
        conv: Optional[Callable[[Any], Any]] = None,
        optional: bool = False,
    ) -> None:
        """Create a configuration field.

        Args:
        ----
            field_type: String name of the type of the field. One of: "color",
                "background", "bool", "number", "color_preset", "transition".
            conv: Converter function to use. When set, the value of the field from
                config YAML is passed to this function. Value returned from
                the function is still checked against the field's specified type.
            optional: Specify if the field can be omitted from the blendcfg. Optional
                fields are set to None in the configuration if they are not
                present.

        """
        self.type = field_type
        self.conv = conv
        self.optional = optional


def parse_data_block_strings(arg: str) -> list[str] | str:
    """Parse data-block string and split into separate values by any separator."""
    pattern = r"^(Collection|Object)([^\w\s])(.+)$"
    if match := re.match(pattern, arg):
        return [match.group(1), match.group(3)]
    return arg


def parse_focal_ratio_strings(arg: str) -> float | str:
    """Parse focal ratio string into float."""
    pattern = r"^[1f]\/\d+$"
    if match := re.match(pattern, arg):
        return eval(match.group(0).replace("f", "1"))
    return arg


def parse_strings(arg: str) -> list[str]:
    """Parse string and split into separate values by comma separator."""
    return arg.replace(",", "").split()


def get_image_formats() -> List[str]:
    """Get list of valid Blender image format extensions."""
    formats_dict = types.ImageFormatSettings.bl_rna.properties["file_format"].enum_items  # type: ignore
    return [item.identifier for item in formats_dict if "Output image" in item.description]


def to_float(arg: str) -> str | float:
    try:
        return float(arg)
    except (ValueError, TypeError):
        return arg


# Schema for YAML config file
CONFIGURATION_SCHEMA = {
    "SETTINGS": {
        "PRJ_EXTENSION": Field("string"),
        "FAB_DIR": Field("string"),
        "RENDER_DIR": Field("string"),
        "ANIMATION_DIR": Field("string"),
        "IMAGE_FORMAT": Field("image_format"),
        "VIDEO_FORMAT": Field("video_format"),
        "THUMBNAILS": Field("bool"),
        "KEEP_FRAMES": Field("bool"),
        "SAVE_SCENE": Field("bool"),
    },
    "RENDERER": {
        "SAMPLES": Field("int"),
        "FPS": Field("int"),
        "IMAGE_WIDTH": Field("int"),
        "IMAGE_HEIGHT": Field("int"),
        "VIDEO_WIDTH": Field("int"),
        "VIDEO_HEIGHT": Field("int"),
        "THUMBNAIL_WIDTH": Field("int"),
        "THUMBNAIL_HEIGHT": Field("int"),
    },
    "SCENE": {
        "LIGHTS_COLOR": Field("color"),
        "LIGHTS_INTENSITY": Field("float", conv=to_float),
        "HDRI_INTENSITY": Field("float", conv=to_float),
        "DEPTH_OF_FIELD": Field("bool"),
        "FOCAL_RATIO": Field("focal_ratio", conv=parse_focal_ratio_strings),
        "ZOOM_OUT": Field("float", conv=to_float),
        "LED_ON": Field("bool"),
        "ADJUST_POS": Field("bool"),
        "ORTHO_CAM": Field("bool"),
        "RENDERED_OBJECT": Field("data_block", optional=True, conv=parse_data_block_strings),
    },
    "BACKGROUNDS": {"LIST": Field("list[str]")},
    "CAMERAS": {
        "TOP": Field("bool"),
        "ISO": Field("bool"),
        "FRONT": Field("bool"),
        "LEFT": Field("bool"),
        "RIGHT": Field("bool"),
        "PHOTO1": Field("bool"),
        "PHOTO2": Field("bool"),
        "CUSTOM": Field("bool"),
    },
    "POSITIONS": {
        "TOP": Field("bool"),
        "BOTTOM": Field("bool"),
        "REAR": Field("bool"),
    },
}


def is_color(arg: str | None) -> bool:
    """Check if given string represents hex color."""
    hex_chars = "0123456789ABCDEF"
    if arg is None:
        return False
    return len(arg) == 6 and all([c in hex_chars for c in arg])


def is_color_preset(arg: str | list[str] | None) -> bool:
    """Check if given string represents preset color."""
    if arg is None:
        return False
    presets = ["White", "Black", "Blue", "Red", "Green"]  # allowed color keywords
    if isinstance(arg, list):
        arg = arg[0]
    if arg in presets:
        return True
    if is_color(arg):
        return True
    return False


def is_focal_ratio(arg: str | list[str] | None) -> bool:
    """Check if given string represents focal ratio fraction or allowed keyword."""
    if arg is None:
        return False
    presets = ["auto"]  # allowed keywords
    if arg in presets:
        return True
    if type(arg) == float:
        return True
    return False


def is_data_block(arg: str | list[str] | None) -> bool:
    """Check if given string represents Blender data-block (Collection or Object)."""
    if arg is None:
        return False
    return len(arg) == 2


def is_image_format(arg: str | None) -> bool:
    """Check if given string is valid Blender image output format."""
    if arg is None:
        return False
    if arg in get_image_formats():
        return True
    return False


def is_video_format(arg: str | None) -> bool:
    """Check if given string is a supported video output format."""
    if arg is None:
        return False
    if arg in ["AVI", "MP4", "MPEG", "WEBM", "GIF"]:
        return True
    return False


def check_throw_error(cfg: Dict[str, Any], args: list[str], schema: Field) -> None:
    """Validate the given configuration entry.

    Args:
    ----
        cfg: entire deserialized YAML config file
        args: a list of names leading to the configuration entry that
              needs to be checked, for example: ["SETTINGS", "DPI"].
              Currently, there must be exactly two names present in the list!
        schema: schema for the field

    """
    missing_config = False
    val = None
    if cfg is None:
        missing_config = True

    if len(args) < 2:
        logger.error(f"[{args[0]}][{args[1]}] not found in {BLENDCFG_FILENAME}")
        raise RuntimeError("Configuration invalid")

    try:
        val = cfg.get(args[0], None)
        if val is None:
            raise Exception
        val = val.get(args[1], None)
    except Exception:
        missing_config = True

    if not schema.optional and (val is None or missing_config):
        logger.error(f"[{args[0]}][{args[1]}] not found in {BLENDCFG_FILENAME}")
        raise RuntimeError("Configuration invalid")

    # Short-circuit when the field is not required
    if val is None and schema.optional:
        cfg[args[0]][args[1]] = None
        return

    if schema.conv is not None:
        try:
            val = schema.conv(val)
            cfg[args[0]][args[1]] = val
        except Exception as e:
            logger.error(
                "Converting value [%s][%s] (= %s) failed: %e",
                args[0],
                args[1],
                val,
                str(e),
            )
            raise RuntimeError("Configuration invalid") from e

    not_schema_type_err = f"{val} is not a {schema.type}"
    color_type_err = f"{val} is not a color, should be hex color value"
    data_block_type_err = f"{val} is not a valid <type>/<name> string defining Blender data-block"
    image_file_format_err = f"{val} is not a valid Blender image output format, must be one of {get_image_formats()}"
    video_file_format_err = (
        f"{val} is not a supported video output format, must be one of {['AVI', 'MP4', 'MPEG', 'WEBM', 'GIF']}"
    )
    focal_ratio_err = f"{val} is not a valid focal ratio, must be a fraction like '1/4' or 'f/4', float or 'auto'"

    match schema.type:
        case "color":
            assert is_color(val), color_type_err
        case "bool":
            assert isinstance(val, bool), not_schema_type_err
        case "int":
            assert isinstance(val, int), not_schema_type_err
        case "float":
            assert isinstance(val, (int, float)), not_schema_type_err
        case "color_preset":
            assert is_color_preset(val), color_type_err + " or presets"
        case "focal_ratio":
            assert is_focal_ratio(val), focal_ratio_err
        case "tuple":
            assert isinstance(val, tuple), not_schema_type_err
        case "string":
            assert isinstance(val, str), not_schema_type_err
        case "data_block":
            assert is_data_block(val), data_block_type_err
        case "list[str]":
            assert isinstance(val, list), not_schema_type_err
            assert all(isinstance(x, str) for x in val), not_schema_type_err
        case "image_format":
            assert isinstance(val, list), not_schema_type_err
            assert all(is_image_format(x) for x in val), image_file_format_err
        case "video_format":
            assert isinstance(val, list), not_schema_type_err
            assert all(is_video_format(x) for x in val), video_file_format_err
        case _:
            raise RuntimeError(f"[{args[0]}][{args[1]}] is not a {schema.type}")


def validate_module_config(schema: dict[str, Field], conf: dict[str, Any], module_name: str) -> bool:
    """Validate the module config against a given schema.

    Returns
    -------
        True: module configuration is valid
        False: module configuration is invalid

    """
    valid = True

    for name, field in schema.items():
        try:
            check_throw_error(conf, [module_name, name], field)
        except Exception as e:
            logger.error("Field %s invalid: %s", name, str(e))
            valid = False

    return valid


def validate_setting_dependencies(cfg: Any) -> None:
    """Validate if certain YAML config file settings have their required dependencies."""
    _ = cfg
    pass
    # Left empty on purpose
    # If required, this can be expanded to include additional validation
    # for blencfg.yaml configuration entries, for example: a setting depends
    # on a different setting to be enabled.


def open_blendcfg(path: str, config_preset: str, pcbt_path: str) -> Dict[str, Any]:
    """Open configuration file from the specified path."""
    project_cfg = path + "/" + BLENDCFG_FILENAME

    yaml = ruamel.yaml.YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(project_cfg) as prj_file:
        project_cfg = yaml.load(prj_file)

    if not isinstance(project_cfg, dict):
        raise RuntimeError(f"Invalid config loaded.")

    if not config_preset:
        if "default" not in project_cfg:
            raise RuntimeError(f"Default config is not defined in {BLENDCFG_FILENAME}.")
        config = project_cfg["default"]
    else:
        if config_preset not in project_cfg:
            raise RuntimeError(f"Unknown blendcfg preset: {config_preset}")
        config = update_yamls(project_cfg["default"], project_cfg[config_preset])

    return check_and_parse_blendcfg(config)


def copy_blendcfg(file_path: str, pcbt_path: str) -> None:
    """Copy blendcfg to project's directory."""
    logger.warning(f"Copying default config from template.")
    copyfile(pcbt_path + "/templates/" + BLENDCFG_FILENAME, file_path + BLENDCFG_FILENAME)


def merge_blendcfg(file_path: str, pcbt_path: str, overwrite: bool = False) -> None:
    """
    Merge template blendcfg with local one in project's directory and save changes to file.
    When overwrite is enabled, values set in local config will be replaced with the ones in template.
    When overwrite is disabled, settings that are missing in the local config will be added from template
    (serves as a fallback in situations when required config keys are missing to prevent crashes).
    """
    prompt = " (overwriting local values)" if overwrite else ""
    logger.warning(f"Merging default config from template with local one found{prompt}.")
    project_cfg_path = file_path + "/" + BLENDCFG_FILENAME
    template_cfg_path = pcbt_path + "/templates/" + BLENDCFG_FILENAME

    yaml = ruamel.yaml.YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(project_cfg_path) as prj_file, open(template_cfg_path) as temp_file:
        project_cfg = yaml.load(prj_file)
        template_cfg = yaml.load(temp_file)

    if overwrite:
        cfg = update_yamls(project_cfg, template_cfg)

    else:
        cfg = update_yamls(template_cfg, project_cfg)

    merged_cfg = project_cfg = file_path + "/" + BLENDCFG_FILENAME
    with open(merged_cfg, "w") as file:
        yaml.dump(cfg, file)


def update_yamls(
    source: Dict[str, Any],
    target: Dict[str, Any],
) -> Dict[str, Any]:
    """Recursively overwrite target values with source values. Adds missing keys found in source."""
    for key, value in source.items():
        if key in target:
            if isinstance(value, dict) and isinstance(target[key], dict):
                update_yamls(value, target[key])
        else:
            target[key] = value
    return target


def check_and_parse_blendcfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and parse the YAML loaded from a file."""
    valid = True

    for module in cfg:
        if module not in CONFIGURATION_SCHEMA:
            continue

        # Check config for module
        if not validate_module_config(CONFIGURATION_SCHEMA[module], cfg, module):
            valid = False

    if not valid:
        raise RuntimeError(f"Configuration in {BLENDCFG_FILENAME} invalid")

    validate_setting_dependencies(cfg)

    return cfg
