from typing_extensions import TypedDict, Required

from schema import Schema, Optional, Or

from roleml.core.builders.role import RoleSpec
from roleml.core.context import ActorProfileSpec

__all__ = ['RunSpec', 'RunSpecTemplate', 'validate_run_spec']


class RunSpec(TypedDict, total=False):

    profiles: Required[list[ActorProfileSpec]]
    """ all nodes in the experiment, which is the combination of batch, separate and individual nodes
    (see `RunSpecTemplate`) """

    roles: dict[str, dict[str, RoleSpec]]
    """ role information that should be deployed by the Conductor """

    connections: dict[str, list[str]]
    """ contact information that should be deployed by the Conductor """

    relationships: dict[str, dict[str, list[str]]]
    """ relationship information that should be deployed by the Conductor """

    relationship_links: dict[str, dict[str, str]]
    """ relationship link (alias) information that should be deployed by the Conductor """

    # TODO consider support for handshakes and handwaves

    deployment_order: list[str]
    """ order of node deployment, each item is a node name """

    fixed: Required[bool]
    """ should be True to indicate that this is not a template """


class RunSpecTemplate(TypedDict, total=False):

    profiles: list[ActorProfileSpec]
    """ batch nodes (directly managed by the Conductor) """

    profiles_separate: list[ActorProfileSpec]
    """ separate nodes (deploy roles on themselves; accept connections and relationships from Conductor) """

    profiles_individual: list[ActorProfileSpec]
    """ individual nodes (deploy roles and configure on themselves; accept nothing from the Conductor) """

    roles: dict[str, dict[str, RoleSpec]]
    """ only applies to batch nodes """

    connections: dict[str, list[str]]
    """ includes all nodes, but only applies to batch & separate nodes """

    relationships: dict[str, dict[str, list[str]]]
    """ includes all nodes, but only applies to batch & separate nodes """

    relationship_links: dict[str, dict[str, str]]
    """ only applies to batch & separate nodes """

    connection_rules: list[str]
    """ includes all nodes, but only applies to batch & separate nodes """

    relationship_rules: dict[str, dict[str, str]]
    """ includes all nodes, but only applies to batch & separate nodes """

    deployment_order: list[str]
    """ order of node deployment, each item is a template that will be used to match all nodes """


# TODO in the future, consider developing a tool that converts a TypedDict into a schema


RUN_SPEC_SCHEMA = Schema({
    Optional('profiles', default=list): [
        {'name': str, 'address': str}
    ],
    # Optional('profiles_separate', default=list): [{'name': str, 'address': str}],
    # Optional('profiles_individual', default=list): [{'name': str, 'address': str}],
    Optional('roles', default=dict): {
        Optional(str): {  # actor name
            str: {  # role instance name
                'class': Or(type, str),
                Optional('options'): {str: object},
                Optional('impl'): {str: object},
            }
        }
    },
    Optional('connections', default=dict): {
        Optional(str): [str]  # from actor name => to actor names (directional)
    },
    Optional('relationships', default=dict): {
        Optional(str): {  # actor name
            str: [str]  # relationship name => list of role instances (or patterns)
        }
    },
    Optional('relationship_links', default=dict): {
        Optional(str): {  # actor name
            str: str    # from relationship name => to relationship name
        }
    },
    Optional('deployment_order'): [Optional(str)],    # actor names
    Optional('fixed', default=True): bool,
})


def validate_run_spec(spec: RunSpec):
    return RUN_SPEC_SCHEMA.validate(spec)
