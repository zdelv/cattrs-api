from functools import wraps
import inspect
from typing import Callable, Any, Concatenate, Coroutine, Mapping, get_args
from cattrs import Converter
import json

from cattrs.dispatch import StructureHook
from starlette.requests import Request


def list_factory[T](typ: type[list[T]], converter: Converter) -> StructureHook:
    inner = get_args(typ)
    if len(inner) > 1:
        raise ValueError("List cannot have more than one subscript")
    elif not inner:
        raise ValueError("List must have a subscript")
    cls = inner[0]

    print(f"Created func for {typ}")

    def struct_list(value: Any, _) -> list[T]:
        if isinstance(value, str):
            listed = value.split(",")
            return [converter.structure(v.strip(), cls) for v in listed]
        elif isinstance(value, list):
            # If we get a list, just pass through unchanged
            return [converter.structure(v, cls) for v in value]
        else:
            raise ValueError(f"Unknown value type given. Type: {type(value)}")

    return struct_list


type InnerFunc = Callable[[Request], Mapping[str, Any]]
type AsyncInnerFunc = Callable[[Request], Coroutine[Any, Any, Mapping[str, Any]]]
type Endpoint[T] = Callable[[Request], Coroutine[Any, Any, T]]
type UserEndpoint[T] = Callable[Concatenate[Request, ...], Coroutine[Any, Any, T]]
type RequestWrapper[T] = Callable[[UserEndpoint[T]], Endpoint[T]]


def parse_wrap(
    converter: Converter,
    inner_func: InnerFunc | AsyncInnerFunc,
) -> Callable[[UserEndpoint], Endpoint]:
    """Higher-order function for extracting a custom parameter from a
    user-defined endpoint and structuring it into its type using a cattrs
    converter. Provide a converter to be used during runtime conversion and a
    inner_func callable that takes in a Request object and returns some Mapping
    that can be serialized into the type. inner_func can be async (e.g., "async
    def" or returns a coroutine).

    Prefer to use the user-facing functions like query_wrap and body_wrap,
    which come with a pre-baked inner_func for extracting the query params or
    body and using it to serialize into the custom object."""

    def wr[T](func: UserEndpoint[T]) -> Endpoint[T]:
        sig = inspect.signature(func)
        custom = [
            (idx, p)
            for idx, p in enumerate(sig.parameters.values())
            if p.annotation != Request
        ]
        if len(custom) > 1:
            raise ValueError("Only one custom parameter allowed")
        elif custom:
            _, p = custom[0]

            @wraps(func)
            async def wr_func(request: Request) -> T:
                if inspect.iscoroutinefunction(inner_func):
                    inner = await inner_func(request)
                else:
                    inner = inner_func(request)
                if not inner:
                    raise ValueError("Failed to extract inner from request")
                structed = converter.structure(inner, p.annotation)
                return await func(request, structed)

        else:

            @wraps(func)
            async def wr_func(request: Request) -> T:
                return await func(request)  # type: ignore

        return wr_func

    return wr


def query_wrap[T](
    converter: Converter,
) -> RequestWrapper[T]:
    """Decorator for serializing the query parameters from a request into a
    custom user-defined type. A Request object must be the first parameter and
    the second parameter can be any cattrs-serializable type.

    Usage:
    >>> from cattrs import Converter
    >>> from dataclasses import dataclass
    >>> from starlette.requests import Request
    >>> from starlette.responses import PlainTextResponse
    >>> @dataclass
    ... class Foo:
    ...     x: int
    ...
    >>> converter = Converter()
    >>> @query_wrap(converter)
    ... def my_func(request: Request, foo: Foo) -> PlainTextResponse:
    ...     return PlainTextResponse(f"Foo: {foo}")"""
    return parse_wrap(converter, lambda req: req.query_params)


async def get_body(req: Request) -> dict[str, Any]:
    return json.loads(await req.body())


def body_wrap[T](
    converter: Converter,
) -> RequestWrapper[T]:
    """Decorator for serializing the body from a request into a custom
    user-defined type. The body *must* be a JSON object. A Request object must
    be the first parameter and the second parameter can be any
    cattrs-serializable type.

    Usage:
    >>> from cattrs import Converter
    >>> from dataclasses import dataclass
    >>> from starlette.requests import Request
    >>> from starlette.responses import PlainTextResponse
    >>> @dataclass
    ... class Foo:
    ...     x: int
    ...
    >>> converter = Converter()
    >>> @body_wrap(converter)
    ... def my_func(request: Request, foo: Foo) -> PlainTextResponse:
    ...     return PlainTextResponse(f"Foo: {foo}")"""
    return parse_wrap(converter, get_body)
