from dataclasses import dataclass
from io import BytesIO, BufferedReader
from os import PathLike
from pathlib import Path
from struct import unpack
from typing import IO


@dataclass
class Vec3:
    x: float
    y: float
    z: float


@dataclass
class Triangle:
    a: Vec3
    b: Vec3
    c: Vec3



def _source2stream(source: str | PathLike | IO | bytes) -> BytesIO:
    if isinstance(source, BufferedReader):
        stream = source

    elif isinstance(source, bytes | bytearray):
        stream = BytesIO(source)

    elif isinstance(source, str | Path):
        model_path = Path(source)
        if not model_path.exists() or not model_path.is_file():
            raise FileNotFoundError(model_path)

        stream = open(model_path, "rb")
    else:
        raise ValueError()

    if not hasattr(stream, "readinto"):
        raise RuntimeError(f"Can't read {source}")

    return stream


def read_opt_file(source: str | PathLike | IO | bytes) -> list[list[Triangle]]:
    with _source2stream(source) as stream:
        chunk_count = unpack("<Q", stream.read(0x8))[0]
        if not chunk_count:
            raise RuntimeError()

        triangles = [[]] * chunk_count
        for index in range(chunk_count):
            triangle_count = unpack("<Q", stream.read(0x8))[0]
            if not triangle_count:
                raise RuntimeError()

            for _ in range(triangle_count):
                buffer = stream.read(0x24)

                triangles[index].append(
                    Triangle(
                        Vec3(*unpack("<fff", buffer[00: 12])),
                        Vec3(*unpack("<fff", buffer[12: 24])),
                        Vec3(*unpack("<fff", buffer[24: 36]))
                    )
                )
    return triangles



def read_triangle_file(source: str | PathLike | IO | bytes) -> list[Triangle]:
    triangles = []
    with _source2stream(source) as stream:
        buffer = memoryview(bytearray(0x24))
        while buf_size := stream.readinto(buffer):
            if buf_size < 0x24:
                raise RuntimeError()

            triangles.append(
                Triangle(
                    Vec3(*unpack("<fff", buffer[00: 12])),
                    Vec3(*unpack("<fff", buffer[12: 24])),
                    Vec3(*unpack("<fff", buffer[24: 36]))
                )
            )

    return triangles








