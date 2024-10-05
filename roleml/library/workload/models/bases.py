from typing import Any, Protocol, TypeVar, runtime_checkable


Parameters = TypeVar('Parameters')
Parameters_co = TypeVar('Parameters_co', covariant=True)
Parameters_contra = TypeVar('Parameters_contra', contravariant=True)

DataBlock_contra = TypeVar('DataBlock_contra', contravariant=True)  # point or batch

Gradients = TypeVar('Gradients')
Gradients_co = TypeVar('Gradients_co', covariant=True)
Gradients_contra = TypeVar('Gradients_contra', contravariant=True)

LR_contra = TypeVar('LR_contra', contravariant=True)

X_contra = TypeVar('X_contra', contravariant=True)
Y_co = TypeVar('Y_co', covariant=True)


@runtime_checkable
class ParametersReadable(Protocol[Parameters_co]):

    def get_params(self) -> Parameters_co: ...


@runtime_checkable
class ParametersWriteable(Protocol[Parameters_contra]):

    def set_params(self, params: Parameters_contra) -> None: ...


@runtime_checkable
class ParametersAccessible(ParametersReadable[Parameters_co], ParametersWriteable[Parameters_contra], Protocol):
    pass


@runtime_checkable
class Trainable(Protocol[DataBlock_contra]):

    def train(self, data: DataBlock_contra, **options) -> dict[str, Any]: ...


@runtime_checkable
class GradientsComputable(Protocol[DataBlock_contra, Gradients_co]):

    def compute_gradients(self, data: DataBlock_contra, **options) -> tuple[dict[str, Any], Gradients_co]: ...


@runtime_checkable
class GradientsApplicable(Protocol[Gradients_contra]):

    def apply_gradients(self, gradients: Gradients_contra) -> None: ...


@runtime_checkable
class GradientLRApplicable(Protocol[Gradients_contra, LR_contra]):

    def apply_gradients(self, gradients: Gradients_contra, lr: LR_contra) -> None: ...


@runtime_checkable
class Testable(Protocol[DataBlock_contra]):

    def test(self, data: DataBlock_contra) -> dict[str, Any]: ...


@runtime_checkable
class Predictable(Protocol[X_contra, Y_co]):

    def predict(self, x: X_contra) -> Y_co: ...


# Common combinations

@runtime_checkable
class TrainableModel(Trainable, ParametersAccessible, Protocol):
    pass


@runtime_checkable
class TestableModel(Testable, ParametersAccessible, Protocol):
    pass


@runtime_checkable
class GradientsOperableModel(
        GradientsComputable[DataBlock_contra, Gradients], GradientsApplicable[Gradients],
        ParametersAccessible, Protocol):
    pass
