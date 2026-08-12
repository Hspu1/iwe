import sys

import orjson

from iwe.main import app


def dump() -> None:
    schema = app.openapi()
    data: bytes = orjson.dumps(schema)

    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    dump()
