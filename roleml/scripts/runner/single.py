from typing import Optional
import warnings
from typing_extensions import Unpack

from roleml.core.actor.base import BaseActor
from roleml.core.builders.actor import ActorBootstrapSpec, BaseActorBuilder


def run_actor(_builder_cls: Optional[type[BaseActorBuilder]] = None, **config: Unpack[ActorBootstrapSpec]):
    if not _builder_cls:
        from roleml.core.actor.default.bootstrap import ActorBuilder
        _builder_cls = ActorBuilder
    builder = _builder_cls()
    builder.load_config(config)
    actor = builder.build()
    run_actor_gracefully(actor)


def run_actor_with_profiling(_builder_cls: Optional[type[BaseActorBuilder]] = None,
                             _save_path: str = '.', _tracer_entries: int = 1000000,
                             **config: Unpack[ActorBootstrapSpec]):
    from pathlib import Path
    try:
        from viztracer import VizTracer     # type: ignore
    except ModuleNotFoundError as e:
        e.msg = 'Failed to import viztracer, which is required for profiling. Please install it in your environment.'
        raise e

    name = config['name']
    save_path = (Path(_save_path) / f'profiler-{name}.json').absolute()
    # save_path.parent.mkdir(parents=True, exist_ok=True)

    with VizTracer(output_file=str(save_path), tracer_entries=_tracer_entries):
        run_actor(_builder_cls, **config)


def run_actor_gracefully(actor: BaseActor):
    """ Should only be called in the main thread. """
    import signal
    # convert SIGTERM to SIGINT so that actor.stop() can be executed
    signal.signal(signal.SIGTERM, lambda signum, frame: signal.raise_signal(signal.SIGINT))

    try:
        actor.run()
    finally:
        actor.stop()
        raise SystemExit


def run_actor_from_cli(
        default_config_file: str = 'start.yaml', *, builder_cls: Optional[type[BaseActorBuilder]] = None):
    """ Default script to start and run a single actor. """
    import argparse
    from roleml.shared.yml import ObjectFromYAML

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config', type=ObjectFromYAML, help='actor configuration file', default=default_config_file)
    parser.add_argument('-w', '--workdir', dest='workdir')
    parser.add_argument('-s', '--src', dest='src')
    parser.add_argument('-p', '--profiling', action='store_true')
    parser.add_argument('-ps', '--profiling-save-path', type=str, default='profiling', dest='save_path')
    parser.add_argument('-pe', '--profiling-entries', type=int, default=1000000, dest='tracer_entries')
    parser.add_argument('--containerize', action='store_true')
    args = parser.parse_args()

    if not isinstance(args.config, dict):
        raise TypeError(f'Config must be a dict, got {type(args.config)}')
    if args.workdir:
        args.config['workdir'] = args.workdir
    if args.src:
        args.config['src'] = args.src

    if args.containerize:
        from roleml.extensions.containerization.builders.actor import NodeControllerBuilder
        if builder_cls:
            warnings.warn('Ignoring the provided builder_cls as containerization mode is enabled.')
        builder_cls = NodeControllerBuilder

    if args.profiling:
        print('======== About profiling ========')
        print('If you wish to keep the results at the specified path, please rename the output folder when the '
              'profiling is done; otherwise the results will be overwritten by the next run.')
        print('Use Ctrl+C to exit before the number of entries has reached.')
        run_actor_with_profiling(builder_cls, args.save_path, args.tracer_entries, **args.config)
    else:
        run_actor(builder_cls, **args.config)


if __name__ == '__main__':
    run_actor_from_cli()
