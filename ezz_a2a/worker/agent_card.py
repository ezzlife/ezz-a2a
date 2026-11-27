from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.types import HTTPAuthSecurityScheme, SecurityRequirement, SecurityScheme

from ezz_a2a.settings import LOCAL_HOST

SECURITY_SCHEME_NAME = "localToken"


def build_agent_card(port: int) -> AgentCard:
    """Describe the worker: who it is, its one skill and how to authenticate."""
    return AgentCard(
        name="Claude review worker", description="Context review without tools.",
        version="0.1.0", default_input_modes=["text/plain"],
        default_output_modes=["text/plain"], capabilities=AgentCapabilities(),
        security_schemes={SECURITY_SCHEME_NAME: SecurityScheme(
            http_auth_security_scheme=HTTPAuthSecurityScheme(scheme="bearer"),
        )},
        security_requirements=[SecurityRequirement(
            schemes={SECURITY_SCHEME_NAME: {"list": []}},
        )],
        supported_interfaces=[AgentInterface(
            protocol_binding="JSONRPC", url=f"http://{LOCAL_HOST}:{port}/",
            protocol_version="1.0",
        )],
        skills=[AgentSkill(id="review", name="Review supplied context",
                           description="Findings and limits; does not modify files.",
                           tags=["review"])],
    )
