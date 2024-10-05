import inspect
import sys
from argparse import ArgumentParser
from threading import Event
from typing import Callable

from roleml.shared.interfaces import Runnable


class RuntimeCLI(Runnable):

    def __init__(self, title: str = ''):
        self._title = title
        self._should_stop = Event()
        self._root_parser = ArgumentParser()
        self._subparsers = self._root_parser.add_subparsers()

    def add_command(self, name: str, func: Callable, expand_arguments: bool = False):
        """ Add a command with the given handler.

        If ``expand_arguments`` is set to False (the default), the handler specified by ``func`` should accept a single
        argument which is a list of string containing all the command-line inputs (except the command name).

        If ``expand_arguments`` is set to True, the arguments defined in the handler specified by ``func`` will be used
        to construct the argument parser, and the type of an argument will be determined by its annotation (or ``str``
        if there is no annotation). Default values are also supported. Note that although positional arguments are to be
        provided positionally in the command string, all arguments including the positional arguments must support
        keyword specification (i.e. the slash argument ``/`` is not allowed), and cannot be named "_func" or
        "_expand_arguments".
        """
        parser = self._subparsers.add_parser(name)
        parser.set_defaults(_func=func, _expand_arguments=expand_arguments)
        if expand_arguments:
            signature = inspect.signature(func)
            for param_name, parameter in signature.parameters.items():
                param_type = parameter.annotation if parameter.annotation != parameter.empty else str
                if parameter.default == parameter.empty:
                    if parameter.kind == parameter.KEYWORD_ONLY:
                        parser.add_argument(f'--{param_name}', type=param_type, required=True)
                    else:
                        parser.add_argument(param_name, type=param_type)
                elif parameter.annotation == bool:
                    parser.add_argument(f'--{param_name}', action='store_const', const=not parameter.default)
                else:
                    parser.add_argument(f'--{param_name}', type=param_type, default=parameter.default)
        return parser

    def run(self):
        """ Expected to be run in a separate thread, just like other components with a run() function. """
        while not self._should_stop.is_set():
            try:
                command_str = input(f'{self._title}> ')
            except EOFError:    # if the commands are read from a file
                print('[info] EOF reached, CLI stopped')
                self.on_eof()
                break
            except Exception as e:  # such as UnicodeDecodeError
                print('[error]', repr(e), file=sys.stderr)
            else:
                if len(command_str) == 0 or command_str[0] == '#':
                    continue
                try:
                    self._parse_and_run_command(command_str)    # synchronous handler
                except Exception as e:
                    print('[error]', repr(e), file=sys.stderr)

    def stop(self):
        self._should_stop.set()

    def _parse_and_run_command(self, command: str):
        assert command
        tokens = command.split()
        try:
            args, unknown = self._root_parser.parse_known_args(tokens)
        except SystemExit:
            # don't exit on invalid command
            # exit_on_error is not used for the sake of compatibility
            pass
        else:
            if args._expand_arguments:      # noqa: not protected variable
                if unknown:
                    raise RuntimeError(f'Unexpected arguments {unknown}')
                func = args._func           # noqa: not protected variable
                delattr(args, '_expand_arguments')
                delattr(args, '_func')
                func(**args.__dict__)
            else:
                args._func(args, unknown)   # noqa: not protected variable

    def on_eof(self):
        pass
