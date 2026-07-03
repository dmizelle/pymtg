"""Base model for all pymtg data models.

This module provides the base model class that all other models in the pymtg
library inherit from, ensuring consistent behavior and functionality.
"""

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict


class PyMTGBaseModel(PydanticBaseModel):
    """Base model for all pymtg data models.

    This class serves as the base for all data models in the pymtg library,
    providing consistent configuration and behavior across all models.

    All models in pymtg inherit from this class to ensure:
    - Consistent serialization/deserialization
    - Proper handling of extra fields
    - Type coercion where appropriate
    - Compatibility with Pydantic v2 features

    Attributes:
        model_config: Pydantic configuration dict with settings for all models.
    """

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )
