# cattrs-api

A serialization/deserialization (serde) library for Starlette built on top of
cattrs. Starlette is the underlying ASGI framework that powers the very popular
library FastAPI. FastAPI provides a nice layer of serde on top of Starlette
using Pydantic. cattrs-api is the same idea, but with cattrs instead of
Pydantic.


## Usage

Using `cattrs_api.body_wrap` or `cattrs_api.query_wrap` as decorators on a
standard Starlette endpoint, you gain access to automatic serialization of
incoming query parameters or the request body into a user defined type. You
must specify both the converter in the decorator, and the custom type in the
function signature as the only parameter other than the request. The parameters
_must_ be typed.

```python
converter = cattrs.Converter()

@body_wrap(converter)
def post_hello(request: Request, foo: Foo) -> PlainTextResponse:
    return PlainTextResponse(f"POST Foo: {foo}")

@query_wrap(converter)
def get_hello(request: Request, foo: Foo) -> PlainTextResponse:
    return PlainTextResponse(f"GET Foo: {foo}")
```

## Why cattrs instead of Pydantic?

Personal choice, mostly. Pydantic is great if you are starting from scratch and
have only "modern" datasources (e.g., JSON). I have found Pydantic to be
inflexible if you interact with data that you either don't own or is old enough
to be built using different technologies.

cattrs is unopinionated and largely allows you to separate the serde of a
library/application from the actual business logic. Separation allows for a
data model to only care about its shape and business use-cases, and to not care
about how it gets serialized to and from some data store.


## Example

```python
from dataclasses import dataclass

from cattrs import Converter
from cattrs.cols import is_sequence
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from cattrs_api import body_wrap, query_wrap, list_factory

# Register a custom hook into the converter handle comma-delimited lists.
converter = Converter()
converter.register_structure_hook_factory(is_sequence, list_factory)


# Some endpoint-specific or business logic dataclass
@dataclass
class Parameters:
    names: list[str]
    id: int


# query_wrap parses the query parameters to structure the user class
@query_wrap(converter)
async def get_params(request: Request, params: Parameters) -> HTMLResponse:
    return PlainTextResponse(f"Params: {params}")

# body_wrap parses the body parameters to structure the user class. The body
# must be JSON formatted.
@body_wrap(converter)
async def post_params(request: Request, params: Parameters) -> HTMLResponse:
    return PlainTextResponse(f"Params: {params}")

routes = [
    Route("/params", params, methods=["GET"]),
    Route("/params", post_params, methods=["POST"]),
]

app = Starlette(routes=routes)
```

```bash
➜  cattrs-api git:(main) ✗ uvicorn example:app &> /dev/null &
➜  cattrs-api git:(main) ✗ export SERVER_PID=$!
[1] 123456
➜  cattrs-api git:(main) ✗ curl -X GET localhost:8000/params?names=steve,bob&id=2
Params: Parameters(names=['steve', 'bob'], id=2)%
➜  cattrs-api git:(main) ✗ curl -X POST --json '{"names":["steve","bob"],"id":2}' localhost:8000/params
Params: Parameters(names=['steve', 'bob'], id=2)%
➜  cattrs-api git:(main) ✗ kill $SERVER_PID
```
