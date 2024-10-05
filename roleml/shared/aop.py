import inspect
import logging
from functools import wraps
from types import FunctionType, MethodType
from typing import Any, Callable, Literal, NamedTuple, Protocol, runtime_checkable, Union

__all__ = ['set_logger', 'InvocationActivity', 'aspect', 'before', 'after', 'catch']


LOGGER = logging.getLogger()


def set_logger(logger: Union[str, logging.Logger]):
    global LOGGER
    LOGGER = logging.getLogger(logger) if isinstance(logger, str) else logger


class InvocationActivity(NamedTuple):
    method: FunctionType    # self.<method>
    invoker: Any            # corresponds to self, not available when method is a static method
    args: tuple
    kwargs: dict[str, Any]


BeforeAdviceType = Callable[[InvocationActivity], Any]
AfterAdviceType = Callable[[InvocationActivity, Any], Any]
CatchAdviceType = Callable[[InvocationActivity, Exception], Any]


@runtime_checkable
class AugmentedMethodType(Protocol):

    def __call__(self, *args, **kwargs): ...

    before_call_: list[BeforeAdviceType]
    after_call_: list[AfterAdviceType]
    on_exception_: list[CatchAdviceType]
    augmented_: bool     # whatever value is OK, but normally True


AdviceType = Literal['before', 'after', 'catch']


@runtime_checkable
class Advice(Protocol):

    def __call__(self, *args, **kwargs): ...    # see type annotation for before_call_, after_call_ and on_exception_

    advice_type_: AdviceType
    target_: Union[str, type, object]
    method_: str


# bound types
NO_BOUND = 0
BOUND_WHEN_INVOKE = 1
BOUND_ALREADY = 2


def augment_method(method: FunctionType, bound: int):
    before_call: list[BeforeAdviceType] = []
    after_call: list[AfterAdviceType] = []
    on_exception: list[CatchAdviceType] = []

    if bound == NO_BOUND:
        @wraps(method)
        def augmented_method(*args, **kwargs):
            if before_call or after_call or on_exception:
                activity = InvocationActivity(method, None, args, kwargs)
                _execute_before_advices(activity, before_call)
                try:
                    result = method(*args, **kwargs)
                except Exception as e:
                    _execute_catch_advices(activity, e, on_exception)
                    raise e
                else:
                    _execute_after_advices(activity, result, after_call)
                    return result
            else:
                return method(*args, **kwargs)
    elif bound == BOUND_WHEN_INVOKE:
        @wraps(method)
        def augmented_method(self_or_cls, *args, **kwargs):
            if before_call or after_call or on_exception:
                activity = InvocationActivity(method, self_or_cls, args, kwargs)
                _execute_before_advices(activity, before_call)
                try:
                    result = method(self_or_cls, *args, **kwargs)
                except Exception as e:
                    _execute_catch_advices(activity, e, on_exception)
                    raise e
                else:
                    _execute_after_advices(activity, result, after_call)
                    return result
            else:
                return method(self_or_cls, *args, **kwargs)
    elif bound == BOUND_ALREADY:
        @wraps(method)
        def augmented_method(self_or_cls, *args, **kwargs):
            if before_call or after_call or on_exception:
                activity = InvocationActivity(method, self_or_cls, args, kwargs)
                _execute_before_advices(activity, before_call)
                try:
                    result = method(*args, **kwargs)
                except Exception as e:
                    _execute_catch_advices(activity, e, on_exception)
                    raise e
                else:
                    _execute_after_advices(activity, result, after_call)
                    return result
            else:
                return method(*args, **kwargs)
    else:
        assert False

    augmented_method.before_call_ = before_call
    augmented_method.after_call_ = after_call
    augmented_method.on_exception_ = on_exception
    augmented_method.augmented_ = True
    return augmented_method


def _execute_before_advices(activity: InvocationActivity, advices: list[BeforeAdviceType]):
    for func in advices:
        try:
            func(activity)
        except Exception:   # noqa: using Logger.exception()
            LOGGER.exception(f'failure in before advice of {activity.method.__name__}')


def _execute_catch_advices(activity: InvocationActivity, e: Exception, advices: list[CatchAdviceType]):
    for func in advices:
        try:
            func(activity, e)
        except Exception:   # noqa: using Logger.exception()
            LOGGER.exception(f'failure in catch advice {func.__name__} of {activity.method.__name__}')


def _execute_after_advices(activity: InvocationActivity, result: Any, advices: list[AfterAdviceType]):
    for func in advices:
        try:
            func(activity, result)
        except Exception:   # noqa: using Logger.exception()
            LOGGER.exception(f'failure in after advice {func.__name__} of {activity.method.__name__}')


def find_and_augment_method(target, method_name: str) -> AugmentedMethodType:
    if isinstance(target, type):
        attr = getattr(target, method_name)
        if hasattr(attr, 'augmented_'):
            return attr
        raw = target.__dict__[method_name]
        if type(raw) is staticmethod:   # raw is a descriptor
            augmented_method = augment_method(attr, NO_BOUND)
            setattr(target, method_name, staticmethod(augmented_method))
            return augmented_method
        elif type(raw) is classmethod:  # raw is a descriptor
            augmented_method = augment_method(attr, BOUND_ALREADY)
            setattr(target, method_name, classmethod(augmented_method))
            return augmented_method
        else:
            augmented_method = augment_method(attr, BOUND_WHEN_INVOKE)
            setattr(target, method_name, augmented_method)
            return augmented_method
    else:
        parent = target.__class__.__dict__[method_name]     # not parent class
        if type(parent) in (staticmethod, classmethod):
            raise TypeError('when the target is an object instance rather than a class, '
                            'the target method cannot be a static or class method')
        if not hasattr(parent, 'augmented_'):
            parent = augment_method(parent, BOUND_WHEN_INVOKE)
            setattr(target.__class__, method_name, parent)
        bound_method = getattr(target, method_name)
        augmented_method = augment_method(bound_method, BOUND_ALREADY)
        setattr(target, method_name, MethodType(augmented_method, target))
        return augmented_method


def weave_in(augmented_method: AugmentedMethodType, advice: Advice):
    weave_in_impl(augmented_method, advice.advice_type_, advice)


def weave_in_impl(augmented_method: AugmentedMethodType,
                  advice_type: AdviceType, func: Union[BeforeAdviceType, AfterAdviceType, CatchAdviceType]):
    if advice_type == 'before':
        augmented_method.before_call_.insert(0, func)
    elif advice_type == 'after':
        augmented_method.after_call_.append(func)
    elif advice_type == 'catch':
        augmented_method.on_exception_.append(func)
    else:
        assert False


class MethodAdviceWrapper:      # for directly applying a bound method

    def __init__(self, func, advice_type: str, target, method):
        self.advice_type_ = advice_type
        self.target_ = target
        self.method_ = method   # method of the target (class or instance)
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


def before(*, target: Union[str, type, object], method: str):
    """ Mark a function as a before advice, which is expected to be "woven into" the target method and executed first
    when invoking the target method.

    The arguments to call the advice will be ``(InvocationActivity, )`` and the user is responsible for ensuring the
    correctness of the signature. Incorrect number of arguments will only be reported at runtime. The return value of
    the advice will be ignored.

    When marking a class or static method, this decorator should be used under the ``@classmethod`` or ``@staticmethod``
    decorator, such as:

    >>> class A:
    >>>     @classmethod
    >>>     @before(target=Bar, method='echo')
    >>>     def advice(cls, activity: InvocationActivity):
    >>>         print('this is an advice')

    Args:
        target (str | type | object): the target class or object containing the target method. If the target is an
            object, then the advice will only be applied to that object as a customized instance method. If specified as
            a str, the advice must be a regular method (not a standalone function nor a class or static method) and this
            str will be used as the attribute name to search for the target object in an instance of the class to which
            the method belongs.
        method (str): the name of the target method.
    """
    def wrap_function(m):
        if inspect.ismethod(m):     # for directly applying a bound method
            return MethodAdviceWrapper(m, 'before', target, method)
        else:
            m.advice_type_ = 'before'
            m.target_ = target
            m.method_ = method      # method of the target (class or instance)
            return m
    return wrap_function


def after(*, target: Union[str, type, object], method: str):
    """ Mark a function as an after advice, which is expected to be "woven into" the target method and executed after
    invoking the target method.

    The arguments to call the advice will be ``(InvocationActivity, object)`` where ``object`` is the return value of
    the target method. The user is responsible for ensuring the correctness of the signature. Incorrect number of
    arguments will only be reported at runtime. The return value of the advice will be ignored.

    When marking a class or static method, this decorator should be used under the ``@classmethod`` or ``@staticmethod``
    decorator, such as:

    >>> class B:
    >>>     @classmethod
    >>>     @after(target=Bar, method='echo')
    >>>     def advice(cls, activity: InvocationActivity, result):
    >>>         print('this is an advice')

    Args:
        target (str | type | object): the target class or object containing the target method. If the target is an
            object, then the advice will only be applied to that object as a customized instance method. If specified as
            a str, the advice must be a regular method (not a standalone function nor a class or static method) and this
            str will be used as the attribute name to search for the target object in an instance of the class to which
            the method belongs.
        method (str): the name of the target method.
    """
    def wrap_function(m):
        if inspect.ismethod(m):     # for directly applying a bound method
            return MethodAdviceWrapper(m, 'after', target, method)
        else:
            m.advice_type_ = 'after'
            m.target_ = target
            m.method_ = method      # method of the target (class or instance)
            return m
    return wrap_function


def catch(*, target: Union[str, type, object], method: str):
    """ Mark a function as a catch advice, which is expected to be "woven into" the target method and executed when
    invoking the target method has caused an exception.

    The arguments to call the advice will be ``(InvocationActivity, e)`` where ``e`` is the exception to a call to the
    target method. The user is responsible for ensuring the correctness of the signature. Incorrect number of arguments
    will only be reported at runtime. The return value of the advice will be ignored.

    When marking a class or static method, this decorator should be used under the ``@classmethod`` or ``@staticmethod``
    decorator, such as:

    >>> class C:
    >>>     @classmethod
    >>>     @catch(target=Bar, method='echo')
    >>>     def advice(cls, activity: InvocationActivity, e):
    >>>         print('this is an advice')

    Args:
        target (str | type | object): the target class or object containing the target method. If the target is an
            object, then the advice will only be applied to that object as a customized instance method. If specified as
            a str, the advice must be a regular method (not a standalone function nor a class or static method) and this
            str will be used as the attribute name to search for the target object in an instance of the class to which
            the method belongs.
        method (str): the name of the target method.
    """
    def wrap_function(m):
        if inspect.ismethod(m):     # for directly applying a bound method
            return MethodAdviceWrapper(m, 'catch', target, method)
        else:
            m.advice_type_ = 'catch'
            m.target_ = target
            m.method_ = method      # method of the target (class or instance)
            return m
    return wrap_function


def aspect(cls_or_func):
    """ Mark a class or a standalone function as an aspect. """
    if isinstance(cls_or_func, type):   # is a class
        cls = cls_or_func
        cls._instance_advices_ = []
        for name, value in cls.__dict__.items():
            if type(value) in (staticmethod, classmethod):  # value is just a descriptor
                attr = getattr(cls, name)
                if hasattr(attr, 'advice_type_'):
                    target = attr.target_
                    method = attr.method_
                    if isinstance(target, str):
                        raise TypeError('target of advice as a static or class method '
                                        'can only be the actual class or object')
                    augmented_method = find_and_augment_method(target, method)
                    weave_in(augmented_method, attr)
            else:
                if hasattr(value, 'advice_type_'):
                    cls._instance_advices_.append(name)

        original_init = cls.__init__

        def __init__(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            for name_ in self._instance_advices_:
                advice_ = getattr(self, name_)
                target_ = getattr(self, advice_.target_) if isinstance(advice_.target_, str) else advice_.target_
                weave_in(find_and_augment_method(target_, advice_.method_), advice_)

        cls.__init__ = __init__
        return cls

    else:   # is a function
        advice = cls_or_func
        if not hasattr(advice, 'advice_type_'):
            raise TypeError('the function the @aspect decorator applies to must have @before or @after decorated')
        if isinstance(advice.target_, str):
            raise TypeError('target of advice as standalone function can only be the actual class or object')
        augmented_method = find_and_augment_method(advice.target_, advice.method_)
        weave_in(augmented_method, advice)
        return advice


if __name__ == '__main__':
    # a simple test
    class Bar:
        def echo(self):
            print(f'echo {self}')

        def broken_echo(self):
            raise RuntimeError("don't worry; if you see this exception in console, it is normal")

    bar1 = Bar()

    @aspect
    class Foo:

        def __init__(self):
            self.bar = Bar()

        @before(target='bar', method='echo')
        def advice1(self, activity: InvocationActivity):
            print("before advice as bound instance method to bound instance method", activity.invoker)

        @before(target=Bar, method='echo')
        def advice2(self, activity):
            print("before advice as bound instance method to class instance method")

        @classmethod
        @before(target=Bar, method='echo')
        def advice3(cls, activity):
            print("before advice as class method to class instance method")

        @staticmethod
        @before(target=Bar, method='echo')
        def advice4(activity):
            print("before advice as static method to class instance method")

        @staticmethod
        @before(target=bar1, method='echo')
        def advice5(activity: InvocationActivity):
            print("before advice as static method to bound instance method", activity.invoker)

    @aspect
    @before(target=Bar, method='echo')
    def advice6(activity):
        print("before advice as ordinary function to class instance method")

    @aspect
    @catch(target=Bar, method='broken_echo')
    def advice7(activity, e):
        print(f'catch advice as ordinary function to class instance method, caught {type(e)}')

    Foo().bar.echo()
    bar1.echo()
    bar1.broken_echo()
