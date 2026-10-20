from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class FormatOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Literal["hust", "report"] = "hust"
    mode: Literal["strict", "layout"] = "strict"
    heading_levels: dict[str, int] = Field(default_factory=dict, max_length=1000)
    preserved_candidates: list[str] = Field(default_factory=list, max_length=1000)
    locked_blocks: list[str] = Field(default_factory=list, max_length=5000)
    preserve_cover: bool = True
    preserve_references: bool = False
    preserve_appendices: bool = False
    cover: Literal["keep", "academic", "minimal"] = "keep"
    cover_end: str | None = None
    layout_decisions: dict[str, Literal["body", "center", "right_block", "keep"]] = (
        Field(default_factory=dict, max_length=1000)
    )
    caption_links: dict[str, str] = Field(default_factory=dict, max_length=500)
    table_headers: list[str] = Field(default_factory=list, max_length=500)
    toc: Literal["keep", "insert", "replace"] = "keep"
    page_numbers: Literal["keep", "arabic", "academic"] = "keep"
    hide_first_page_number: bool = True
    normalize_tables: bool = True
    normalize_images: bool = True
    enlarge_images: bool = True
    object_lists: bool = False
    caption_fields: bool = False
    convert_manual_lists: bool = False
    style_code: bool = True
    signature_position: Literal["keep", "end_of_body"] = "keep"
