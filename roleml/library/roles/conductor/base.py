import time
from pathlib import Path
from typing import Iterator, Optional, cast as c

from roleml.core.context import ActorProfile, RoleInstanceID, parse_instances
from roleml.core.role.base import Role
from roleml.library.roles.conductor.helpers import match_actors, detect_templates, apply_templates
from roleml.library.roles.conductor.types import RunSpec, RunSpecTemplate, validate_run_spec
from roleml.shared.cli import RuntimeCLI
from roleml.shared.collections.segmentation import SegmentedList
from roleml.shared.interfaces import Runnable
from roleml.shared.yml import load_yaml, save_yaml

__all__ = ['Conductor']


class Conductor(Role, Runnable):

    def __init__(self, name: str = 'RoleML'):
        super().__init__()
        self.cli = RuntimeCLI(name)
        self.cli.add_command('configure', self.configure, expand_arguments=True)
        self.cli.on_eof = self.on_eof

    def run(self):
        time.sleep(0.5)
        self.ctx.relationships.add_to_relationship('manager', self.id)
        self.cli.run()

    def stop(self):
        self.cli.stop()

    # noinspection PyMethodMayBeStatic
    def on_eof(self):
        print('[info] the actor will now terminate, please wait')
        import signal
        signal.raise_signal(signal.SIGINT)

    def configure(self, config_file: str, path: Optional[str] = None):
        """ Configure actors in preparation for a DML run. All actors must be started first.

        Basically this function does the following things, according to the specification given (or converted from
        template if necessary):

        1. sends connection information to all the actors (physical topology).
        2. sends role assignments to all the actors (including role class, options, fillings, etc.), and wait for the
           actors to finish initialization.
        3. sends relationship information to all the actors (active logical topology), and wait for the actors to finish
           setup.
        """
        raw_spec = load_yaml(config_file)
        if not isinstance(raw_spec, dict):
            raise ValueError('Config or config template is not a dict')

        if raw_spec.get('fixed') is True:
            spec = c(RunSpec, raw_spec)
            save = False
        else:
            spec = self._generate_run_configuration(c(RunSpecTemplate, raw_spec))
            save = True

        validate_run_spec(spec)     # will raise error if not valid

        connections = spec.get('connections', dict())
        role_assignments = spec.get('roles', dict())
        relationships = spec.get('relationships', dict())
        relationship_links = spec.get('relationship_links', dict())
        deployment_order = spec.get('deployment_order', list())
        non_deployed_actors: set[str] = set()

        for actor_spec in spec['profiles']:
            self.ctx.contacts.add_contact(ActorProfile(**actor_spec))   # keys: name, address
            non_deployed_actors.add(actor_spec['name'])

        # final validation of config
        for actor_name in deployment_order:
            if actor_name not in non_deployed_actors:
                raise ValueError(f'invalid deployment target: {actor_name}')

        if save:
            if path is None:
                save_path = Path(config_file).parent
            else:
                save_path = Path(path)
            save_path.mkdir(parents=True, exist_ok=True)
            save_filename = save_path / f'run-{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(time.time()))}.yaml'
            save_yaml(save_filename, spec)
            self.logger.info(f'successfully saved actual configurations for this run to {save_filename}')

        def iterate_over_actors():
            yield self.ctx.profile.name
            for _actor_name in deployment_order:
                yield _actor_name
                non_deployed_actors.remove(_actor_name)
            for _actor_name in non_deployed_actors:
                yield _actor_name

        for actor_name in iterate_over_actors():
            native_role = RoleInstanceID(actor_name, 'actor')
            # 1. physical connection information (contacts)
            if targets := connections.get(actor_name):
                send_profiles = {target: self.ctx.contacts.get_actor_profile(target).address for target in targets}
                self.call(native_role, 'update-contacts', {'contacts': send_profiles})
                self.logger.info(f'{actor_name}: deployed contacts')

            # 2. relationships and links
            if actor_relationships := relationships.get(actor_name):
                for relationship_name, instance_strings in actor_relationships.items():
                    if instance_strings:
                        instances = parse_instances(instance_strings, relationship_name)
                        self.call(native_role, 'update-relationship',
                                  {'relationship_name': relationship_name, 'op': 'add', 'instances': instances})
                self.logger.info(f'{actor_name}: deployed relationships')
            if actor_relationship_links := relationship_links.get(actor_name):
                for from_name, to_name in actor_relationship_links.items():
                    self.call(native_role, 'add-relationship-link',
                              {'from_relationship_name': from_name, 'to_relationship_name': to_name})
                self.logger.info(f'{actor_name}: deployed relationship links')

            # 3. roles
            if actor_assignments := role_assignments.get(actor_name):
                for instance_name, role_spec in actor_assignments.items():
                    self.call_task(native_role, 'assign-role', {'name': instance_name, 'spec': role_spec}).result()
                self.logger.info(f'{actor_name}: deployed roles')

        self.logger.info('deploy completed')

    BATCH_ACTORS = (0, 1)
    BATCH_AND_SEPARATE_ACTORS = (0, 2)
    ALL_ACTORS = (0, 3)

    def _generate_run_configuration(self, template: RunSpecTemplate) -> RunSpec:
        # actors
        all_actors: SegmentedList[str] = SegmentedList(3)
        batch_actors = all_actors[0]
        separate_actors = all_actors[1]
        individual_actors = all_actors[2]
        for item in template.get('profiles', []):
            batch_actors.append(item['name'])
        for item in template.get('profiles_separate', []):
            separate_actors.append(item['name'])
        for item in template.get('profiles_individual', []):
            individual_actors.append(item['name'])
        batch_actors.append(self.profile.name)      # this is temporary

        profiles = template.get('profiles', [])
        profiles.extend(template.get('profiles_separate', []))
        profiles.extend(template.get('profiles_individual', []))

        spec: RunSpec = {'profiles': profiles, 'fixed': True}

        # roles
        actual_roles = {}
        for actor_name_pattern, roles in template.get('roles', {}).items():
            template_paths: dict[tuple, Iterator] = {}    # path => producer
            # traverse through the conf dict to find templates
            detect_templates(roles, template_paths, ())
            # find all matches and apply templates
            matched_actors = match_actors(all_actors.iter(range=Conductor.BATCH_ACTORS), pattern=actor_name_pattern)
            for actor_name in matched_actors:
                actor_roles = apply_templates(roles, template_paths)
                actual_roles.setdefault(actor_name, {}).update(actor_roles)
        spec['roles'] = actual_roles

        # connections
        connections: dict[str, set[str]] = dict()
        for rule in template.get('connection_rules', []):
            pattern = str(rule).split(' ')
            pattern_from, pattern_to = pattern[0].strip(), pattern[1].strip()
            if matched_from := match_actors(all_actors.iter(range=Conductor.BATCH_AND_SEPARATE_ACTORS), pattern_from):
                matched_to = match_actors(all_actors.iter(), pattern_to)
                for actor_name in matched_from:
                    connections.setdefault(actor_name, set()).update(matched_to)
        for from_actor, to_actor in template.get('connections', {}).items():
            connections.setdefault(from_actor, set()).update(list(to_actor))
        spec['connections'] = {from_actor: list(to_actors) for from_actor, to_actors in connections.items()}
        del connections

        # relationships
        relationships: dict[str, dict[str, list[str]]] = template.get('relationships', {})
        for pattern_from, rules in template.get('relationship_rules', {}).items():
            if matched_from := match_actors(all_actors.iter(range=Conductor.BATCH_AND_SEPARATE_ACTORS), pattern_from):
                for r_name, rule in rules.items():
                    split = rule.rsplit('/', maxsplit=2)
                    instance_name = split[1] if len(split) == 2 else r_name
                    matched_to = match_actors(all_actors.iter(), pattern=split[0])
                    for actor_name in matched_from:
                        current = relationships.setdefault(actor_name, {}).setdefault(r_name, [])
                        current.extend(f'{actor}/{instance_name}' for actor in matched_to)
        spec['relationships'] = relationships

        # relationship links
        actual_relationship_links: dict[str, dict[str, str]] = {}
        for pattern, links in template.get('relationship_links', {}).items():
            matched_actors = match_actors(all_actors.iter(range=Conductor.BATCH_AND_SEPARATE_ACTORS), pattern=pattern)
            for actor_name in matched_actors:
                actual_relationship_links[actor_name] = links
        spec['relationship_links'] = actual_relationship_links

        # deployment order
        deployment_order: list[str] = []
        for pattern in template.get('deployment_order', []):
            matched_actors = match_actors(all_actors.iter(), pattern)
            deployment_order.extend(matched_actors)
        spec['deployment_order'] = deployment_order

        return spec
