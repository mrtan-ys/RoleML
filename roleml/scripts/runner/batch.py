from multiprocessing import Process
from typing import Any, Iterable, Optional
import warnings

from roleml.core.builders.actor import BaseActorBuilder
from roleml.scripts.runner.single import run_actor, run_actor_with_profiling


def batch_initiate(actor_options: Iterable[dict[str, Any]], common_options: Optional[dict[str, Any]] = None, *, 
                   actor_builder_cls: Optional[type[BaseActorBuilder]] = None, start: bool = True):
    if common_options is None:
        common_options = {}
    actor_processes = []
    for actor_option in actor_options:
        config = {**actor_option, **common_options}
        process_name = f'python-roleml-{actor_option["name"]}' if 'name' in actor_option else None
        process = Process(name=process_name, target=run_actor, args=(actor_builder_cls, ), kwargs=config)
        actor_processes.append(process)
        if start:
            process.start()
    return actor_processes


def batch_initiate_with_profiling(
        actor_options: Iterable[dict[str, Any]], common_options: Optional[dict[str, Any]] = None, *,
        actor_builder_cls: Optional[type[BaseActorBuilder]] = None,
        save_path: str = '.', profiling_entries: int = 1000000, start: bool = True):
    if common_options is None:
        common_options = {}
    actor_processes = []
    for actor_option in actor_options:
        config = {**actor_option, **common_options}
        process_name = f'python-roleml-{actor_option["name"]}' if 'name' in actor_option else None
        process = Process(
            name=process_name, target=run_actor_with_profiling,
            args=(actor_builder_cls, save_path, profiling_entries), kwargs=config)
        actor_processes.append(process)
        if start:
            process.start()
    return actor_processes


def run_actors_from_cli(
        *,
        builder_cls: Optional[type[BaseActorBuilder]] = None,
        default_workdir: Optional[str] = None,
        default_profiling_save_path: str = 'profiling', default_profiling_entries: int = 1000000):
    """ Default script to start and run a batch of actors. """
    import argparse
    import time
    from threading import Event

    from roleml.shared.yml import ObjectFromYAML

    parser = argparse.ArgumentParser()
    parser.add_argument('profiles', type=ObjectFromYAML)
    parser.add_argument('-c', '--common-config', type=ObjectFromYAML)
    parser.add_argument('-w', '--workdir', default=default_workdir)
    parser.add_argument('-s', '--src')
    parser.add_argument('-p', '--profiling', action='store_true')
    parser.add_argument('-ps', '--profiling-save-path', type=str, default=default_profiling_save_path, dest='save_path')
    parser.add_argument('-pe', '--profiling-entries', type=int, default=default_profiling_entries, dest='entries')
    parser.add_argument('--containerize', action='store_true')
    args = parser.parse_args()

    profiles = args.profiles['profiles']
    common_config = args.common_config or {}
    if args.workdir:
        common_config['workdir'] = args.workdir
    if args.src:
        common_config['src'] = args.src

    if args.containerize:
        from roleml.extensions.containerization.builders.actor import NodeControllerBuilder
        if builder_cls:
            warnings.warn('Ignoring the provided builder_cls as containerization mode is enabled.')
        builder_cls = NodeControllerBuilder

    if args.profiling:
        processes = batch_initiate_with_profiling(
            profiles, common_config,
            actor_builder_cls=builder_cls, start=True, save_path=args.save_path, profiling_entries=args.entries)
        time.sleep(3)
        print('======== Profiling enabled ========')
        print('If you wish to keep the results at the specified path, please rename the output folder when the '
              'profiling is done; otherwise the results will be overwritten by the next run.')
        print('Use Ctrl+C to exit before the number of entries has reached.')
    else:
        processes = batch_initiate(profiles, common_config, actor_builder_cls=builder_cls, start=True)

    try:
        Event().wait()
    except KeyboardInterrupt:
        # we don't need to manually terminate the children
        # because when pressing Ctrl+C, the SIGINT signal will be sent to the children as well
        print('Process(es) terminated due to KeyboardInterrupt')


if __name__ == '__main__':
    run_actors_from_cli()
