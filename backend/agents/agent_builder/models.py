from pydantic import BaseModel, Field


class RequiredField(BaseModel):
    """Model for a required field"""

    name: str = Field(..., description="The name of the required field")
    description: str = Field(
        ..., description="A brief description of the required field"
    )
    type: str = Field(
        ..., description="The type of the required field, e.g., string, integer, etc."
    )
    required: bool = Field(..., description="Whether the field is required")


class BuilderResponse(BaseModel):
    """Response model for agent builder"""

    system_prompt: str = Field(..., description="The system prompt for the agent")
    tool_kits: list[str] = Field(
        ..., description="The tool kits required for the agent."
    )
    required_fields: list[RequiredField] = Field(
        ...,
        description="The crucial fields the agent needs from the user to run without human intervention.",
    )
