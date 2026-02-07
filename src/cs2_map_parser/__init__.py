from enum import IntEnum
from io import BufferedIOBase
from os import PathLike
from pathlib import Path
from typing import IO

from binary_reader import BinaryReader, Whence
from keyvalues3 import MemoryBuffer, read_valve_keyvalue3
from vpk import VPK


__all__ = [
    "MapParser"
]

class BlockType(IntEnum):
    # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/Enums/BlockType.cs
    RERL = ord('R') | (ord('E') << 8) | (ord('R') << 16) | (ord('L') << 24)
    REDI = ord('R') | (ord('E') << 8) | (ord('D') << 16) | (ord('I') << 24)
    RED2 = ord('R') | (ord('E') << 8) | (ord('D') << 16) | (ord('2') << 24)
    NTRO = ord('N') | (ord('T') << 8) | (ord('R') << 16) | (ord('O') << 24)
    DATA = ord('D') | (ord('A') << 8) | (ord('T') << 16) | (ord('A') << 24)
    VBIB = ord('V') | (ord('B') << 8) | (ord('I') << 16) | (ord('B') << 24)
    VXVS = ord('V') | (ord('X') << 8) | (ord('V') << 16) | (ord('S') << 24)
    SNAP = ord('S') | (ord('N') << 8) | (ord('A') << 16) | (ord('P') << 24)
    CTRL = ord('C') | (ord('T') << 8) | (ord('R') << 16) | (ord('L') << 24)
    MDAT = ord('M') | (ord('D') << 8) | (ord('A') << 16) | (ord('T') << 24)
    MRPH = ord('M') | (ord('R') << 8) | (ord('P') << 16) | (ord('H') << 24)
    MBUF = ord('M') | (ord('B') << 8) | (ord('U') << 16) | (ord('F') << 24)
    ANIM = ord('A') | (ord('N') << 8) | (ord('I') << 16) | (ord('M') << 24)
    ASEQ = ord('A') | (ord('S') << 8) | (ord('E') << 16) | (ord('Q') << 24)
    AGRP = ord('A') | (ord('G') << 8) | (ord('R') << 16) | (ord('P') << 24)
    PHYS = ord('P') | (ord('H') << 8) | (ord('Y') << 16) | (ord('S') << 24)
    INSG = ord('I') | (ord('N') << 8) | (ord('S') << 16) | (ord('G') << 24)
    SrMa = ord('S') | (ord('r') << 8) | (ord('M') << 16) | (ord('a') << 24)
    LaCo = ord('L') | (ord('a') << 8) | (ord('C') << 16) | (ord('o') << 24)
    STAT = ord('S') | (ord('T') << 8) | (ord('A') << 16) | (ord('T') << 24)
    SPRV = ord('S') | (ord('P') << 8) | (ord('R') << 16) | (ord('V') << 24)
    FLCI = ord('F') | (ord('L') << 8) | (ord('C') << 16) | (ord('I') << 24)
    DSTF = ord('D') | (ord('S') << 8) | (ord('T') << 16) | (ord('F') << 24)
    TBUF = ord('T') | (ord('B') << 8) | (ord('U') << 16) | (ord('F') << 24)
    MVTX = ord('M') | (ord('V') << 8) | (ord('T') << 16) | (ord('X') << 24)
    MIDX = ord('M') | (ord('I') << 8) | (ord('D') << 16) | (ord('X') << 24)
    MADJ = ord('M') | (ord('A') << 8) | (ord('D') << 16) | (ord('J') << 24)



class MapParser:
    @staticmethod
    def vpk2mdl(path: str | PathLike) -> bytes:
        path = Path(path)
        map_name = path.name.split(".")[0]

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(path)

        if not path.name.endswith(".vpk"):
            raise ValueError()

        vpk = VPK(path)
        try:
            model = vpk.get_file(f"maps/{map_name}/world_physics.vmdl_c")
        except KeyError as err:
            raise ValueError(f"Can't dump .vmdl_c file from {path}") from err

        return model.read()

    @staticmethod
    def mdl2phys(path_or_stream_or_data: str | PathLike | IO | bytes) -> bytes:
        # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/Resource.cs
        # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/ResourceTypes/PhysAggregateData.cs
        # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/ResourceTypes/KeyValuesOrNTRO.cs
        # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/ResourceTypes/BinaryKV3.cs

        if isinstance(path_or_stream_or_data, BufferedIOBase):
            reader = BinaryReader(path_or_stream_or_data.read())

        elif isinstance(path_or_stream_or_data, bytes):
            reader = BinaryReader(path_or_stream_or_data)

        else:
            path = Path(path_or_stream_or_data)
            if not path.name.endswith(".vmdl_c"):
                raise ValueError()

            with open(path, "rb") as model_file:
                reader = BinaryReader(model_file.read())

        file_size = reader.read_uint32()
        header_version = reader.read_uint16()
        version = reader.read_uint16()

        block_offset = reader.read_uint32()
        block_count = reader.read_uint32()
        reader.seek(block_offset - 0x8, Whence.CUR)

        for i in range(block_count):
            block_type = reader.read_uint32()

            position = reader.pos()
            offset = position + reader.read_uint32()

            size = reader.read_uint32()
            if not size:
                continue

            if block_type == BlockType.PHYS:
                reader.seek(offset, Whence.BEGIN)
                return reader.read_bytes(size)

            reader.seek(position + 0x8, Whence.BEGIN)

        raise RuntimeError(f"Cant found Block PHYS")

    @staticmethod
    def phys2tri(path_or_stream_or_data: str | PathLike | IO | bytes) -> bytes:
        buffer = b""
        if isinstance(path_or_stream_or_data, BufferedIOBase):
            buffer = MemoryBuffer(path_or_stream_or_data.read())

        elif isinstance(path_or_stream_or_data, bytes):
            buffer = MemoryBuffer(path_or_stream_or_data)

        else:
            path = Path(path_or_stream_or_data)
            if not path.name.endswith(".vphys_c"):
                raise ValueError()

            with open(path, "rb") as physics_file:
                buffer = MemoryBuffer(physics_file.read())

        if not buffer:
            raise FileNotFoundError(path_or_stream_or_data)

        phys = read_valve_keyvalue3(buffer)

        tris = []
        for index in range(1 << 31):
            try: collision = phys["m_parts"][0]["m_rnShape"]["m_hulls"][index]["m_nCollisionAttributeIndex"]
            except Exception as err: collision = None

            if collision is None:
                break

            if collision != 0:
                continue

            hull    : dict  = phys["m_parts"][0]["m_rnShape"]["m_hulls"][index]["m_Hull"]
            vertices: bytes = hull.get("m_VertexPositions", None)
            faces   : bytes = hull["m_Faces"]
            edges   : bytes = hull["m_Edges"]
            # Edge(next, twin, origin, face)
            if vertices is None:
                vertices: bytes = hull.get("m_VertexPositions")

            for start_edge in faces:
                edge = edges[start_edge << 2]
                while edge != start_edge:
                    next_edge = edges[edge << 2]

                    tris.extend((
                        vertices[(b := edges[(edge       << 2) + 2] * 0xC): b + 0xC],
                        vertices[(b := edges[(start_edge << 2) + 2] * 0xC): b + 0xC],
                        vertices[(b := edges[(next_edge  << 2) + 2] * 0xC): b + 0xC],
                    ))
                    edge = next_edge


        for index in range(1 << 31):
            try: collision = phys["m_parts"][0]["m_rnShape"]["m_meshes"][index]["m_nCollisionAttributeIndex"]
            except Exception as err: collision = None

            if collision is None:
                break

            if collision != 0:
                continue

            mesh     : bytes = phys["m_parts"][0]["m_rnShape"]["m_meshes"][index]["m_Mesh"]
            triangles: bytes = mesh["m_Triangles"]
            vertices : bytes = mesh["m_Vertices"]


            for triangle in range((len(triangles) * 0x55555556) >> 34):
                triangle = (triangle << 2) + (triangle << 3)  # * 12

                tris.extend((
                    vertices[
                        (k := ((bb := int.from_bytes(triangles[
                             (b := triangle + 0x0): b + 0x4
                         ] , "little")) << 2) + (bb << 3)): k + 0xC
                    ],
                    vertices[(k := int.from_bytes(triangles[(b := triangle + 0x4): b + 0x4], "little") * 0xC): k + 0xC],
                    vertices[(k := int.from_bytes(triangles[(b := triangle + 0x8): b + 0x4], "little") * 0xC): k + 0xC]
                ))

        return b"".join(tris)

    @classmethod
    def vpk2tri(cls, path: str | PathLike) -> bytes:
        return cls.phys2tri(cls.mdl2phys(cls.vpk2mdl(path)))

    @classmethod
    def vpk2phys(cls, path: str | PathLike) -> bytes:
        return cls.mdl2phys(cls.vpk2mdl(path))

    @classmethod
    def mdl2tri(cls, path_or_stream_or_data: str | PathLike | IO | bytes) -> bytes:
        return  cls.phys2tri(cls.mdl2phys(path_or_stream_or_data))





if __name__ == '__main__':
    # open("mirage.vphys_c", "wb").write(vphys)
    # kv3.read(open("de_mirage.vmdl_c", "rb"))

    # vphys_data = get_block()
    # vphys = kv3.read_valve_keyvalue3(MemoryBuffer(vphys_data))
    # print(vphys)
    from time import perf_counter

    t = perf_counter()
    parser = MapParser
    b = parser.phys2tri(parser.mdl2phys(parser.vpk2mdl("de_mirage.vpk")))

    with open("../../de_mirage.tri", "wb") as tri_file:
        tri_file.write(b)