from enum import IntEnum
from io import BufferedReader
from os import PathLike
from pathlib import Path
from typing import IO, Generator
from itertools import count, chain
from tempfile import TemporaryFile

from binary_reader import BinaryReader, Whence
from keyvalues3 import MemoryBuffer, read_valve_keyvalue3
from vpk import VPK


__all__ = [
    "MapParser",
    "VPKFile", "ModelFile", "PhysicsFile"
]


class PhysicsFile:
    FILE_SUFFIX: str = "vphys_c"

    def __init__(self, source: str | PathLike | IO | bytes) -> None:
        if isinstance(source, BufferedReader):
            buffer = source.read()

        elif isinstance(source, bytes | bytearray):
            buffer = source

        elif isinstance(source, str | Path):
            model_path = Path(source)
            if not model_path.exists() or not model_path.is_file():
                raise FileNotFoundError(model_path)
            if not model_path.name.endswith(f".{self.FILE_SUFFIX}"):
                raise ValueError()

            with open(model_path, "rb") as model_file:
                buffer = model_file.read()

        else: raise ValueError()

        buffer_reader = MemoryBuffer(buffer)
        self.phys_data: dict = read_valve_keyvalue3(buffer_reader)


    def get_hulls(self) -> Generator[bytes, None, None]:
        for index in count(start=0, step=1):
            try: collision = self.phys_data["m_parts"][0]["m_rnShape"]["m_hulls"][index]["m_nCollisionAttributeIndex"]
            except Exception as err:
                collision = None

            if collision is None:
                break

            if collision != 0:
                continue

            hull: dict = self.phys_data["m_parts"][0]["m_rnShape"]["m_hulls"][index]["m_Hull"]
            vertices: bytes = hull.get("m_VertexPositions", None)
            faces: bytes = hull["m_Faces"]
            edges: bytes = hull["m_Edges"]
            # Edge(next, twin, origin, face)
            if vertices is None:
                vertices: bytes = hull.get("m_VertexPositions")

            saved_triangles = bytearray()
            for start_edge in faces:
                edge = edges[start_edge << 2]
                while edge != start_edge:
                    next_edge = edges[edge << 2]

                    saved_triangles.extend(chain(
                        vertices[(b := edges[(edge << 2) + 2] * 0xC): b + 0xC],
                        vertices[(b := edges[(start_edge << 2) + 2] * 0xC): b + 0xC],
                        vertices[(b := edges[(next_edge << 2) + 2] * 0xC): b + 0xC],
                    ))
                    edge = next_edge
            yield saved_triangles

    def get_meshes(self) -> Generator[bytes, None, None]:
        for index in count(start=0, step=1):
            try: collision = self.phys_data["m_parts"][0]["m_rnShape"]["m_meshes"][index]["m_nCollisionAttributeIndex"]
            except Exception as err:
                collision = None

            if collision is None:
                break

            if collision != 0:
                continue

            mesh: bytes = self.phys_data["m_parts"][0]["m_rnShape"]["m_meshes"][index]["m_Mesh"]
            triangles: bytes = mesh["m_Triangles"]
            vertices: bytes = mesh["m_Vertices"]

            saved_triangles = bytearray()
            for triangle in range((len(triangles) * 0x55555556) >> 34):
                triangle = (triangle << 2) + (triangle << 3)  # * 12

                saved_triangles.extend(chain(
                    vertices[(k := int.from_bytes(triangles[(b := triangle + 0x0): b + 0x4], "little") * 0xC): k + 0xC],
                    vertices[(k := int.from_bytes(triangles[(b := triangle + 0x4): b + 0x4], "little") * 0xC): k + 0xC],
                    vertices[(k := int.from_bytes(triangles[(b := triangle + 0x8): b + 0x4], "little") * 0xC): k + 0xC]
                ))
            yield saved_triangles

    def to_triangle_file(self, save_path: str | Path | None = None) -> bytes:
        data = bytearray()

        for triangles in chain(self.get_hulls(), self.get_meshes()):
            data.extend(triangles)

        if save_path is not None:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with save_path.open("wb") as file:
                file.write(data)
        return bytes(data)

    @property
    def tri(self) -> bytes:
        return self.to_triangle_file()

    def to_opt_file(self, save_path: str | Path | None = None) -> bytes:
        data = bytearray(0x08)

        chunk_counter = 0
        for triangles in chain(self.get_hulls(), self.get_meshes()):
            data.extend((len(triangles) // 36).to_bytes(8, "little"))
            data.extend(triangles)
            chunk_counter += 1

        data[:8] = chunk_counter.to_bytes(8, "little")

        if save_path is not None:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with save_path.open("wb") as file:
                file.write(data)
        return bytes(data)

    @property
    def opt(self) -> bytes:
        return self.to_opt_file()

class ModelFile:
    FILE_SUFFIX: str = "vmdl_c"

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

    def __init__(self, source: str | PathLike | IO | bytes) -> None:
        if isinstance(source, BufferedReader):
            buffer = source.read()

        elif isinstance(source, bytes | bytearray):
            buffer = source

        elif isinstance(source, str | Path):
            model_path = Path(source)
            if not model_path.exists() or not model_path.is_file():
                raise FileNotFoundError(model_path)
            if not model_path.name.endswith(f".{self.FILE_SUFFIX}"):
                raise ValueError()

            with open(model_path, "rb") as model_file:
                buffer = model_file.read()

        else: raise ValueError()

        self.reader = BinaryReader(buffer)

    def get_physics_file(self, save_path: str | Path | None = None) -> PhysicsFile:
        file_size      = self.reader.read_uint32()
        header_version = self.reader.read_uint16()
        version        = self.reader.read_uint16()

        block_offset = self.reader.read_uint32()
        block_count  = self.reader.read_uint32()
        self.reader.seek(block_offset - 0x8, Whence.CUR)

        for _ in range(block_count):
            block_type = self.reader.read_uint32()

            position = self.reader.pos()
            offset = position + self.reader.read_uint32()

            size = self.reader.read_uint32()
            if not size:
                continue

            if block_type == self.BlockType.PHYS:
                self.reader.seek(offset, Whence.BEGIN)

                phys_buffer = self.reader.read_bytes(size)
                if save_path is not None:
                    save_path = Path(save_path)
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    with save_path.open("wb") as file:
                        file.write(phys_buffer)
                return PhysicsFile(phys_buffer)

            self.reader.seek(position + 0x8, Whence.BEGIN)

        raise RuntimeError(f"Cant found Block: PHYS")

    @property
    def vphys_c(self) -> PhysicsFile:
        return self.get_physics_file()

class VPKFile:
    FILE_SUFFIX: str = "vpk"

    def __init__(self, source: str | PathLike | IO | bytes) -> None:
        if isinstance(source, BufferedReader):
            self._file = TemporaryFile("wb", suffix=f".{self.FILE_SUFFIX}")
            self._file.write(source.read())
            vpk_path = self._file.fileno()

        elif isinstance(source, bytes | bytearray):
            self._file = TemporaryFile("wb", suffix=f".{self.FILE_SUFFIX}")
            self._file.write(source)
            vpk_path = self._file.fileno()

        elif isinstance(source, str | Path):
            vpk_path = Path(source)
            if not vpk_path.exists() or not vpk_path.is_file():
                raise FileNotFoundError(vpk_path)
            if not vpk_path.name.endswith(f".{self.FILE_SUFFIX}"):
                raise ValueError()

        else: raise ValueError()

        self.vpk = VPK(vpk_path)

    # def __del__(self):
    #     self._file.close()


    def get_model_file(self, save_path: str | Path | None = None) -> ModelFile:
        model_path = [path for path, _ in self.vpk.items() if path.split("/")[-1] == "world_physics.vmdl_c"]
        if not len(model_path):
            raise FileNotFoundError("world_physics.vmdl_c Not Found.")

        model_file = self.vpk.get_file(model_path[0])
        model_buffer =model_file.read()

        if save_path is not None:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with save_path.open("wb") as file:
                file.write(model_buffer)
        return ModelFile(model_buffer)

    @property
    def vmdl_c(self) -> ModelFile:
        return self.get_model_file()





class MapParser:
    # @staticmethod
    # def vpk2mdl(path: str | PathLike) -> bytes:
    #     path = Path(path)
    #     map_name = path.name.split(".")[0]
    #
    #     if not path.exists() or not path.is_file():
    #         raise FileNotFoundError(path)
    #
    #     if not path.name.endswith(".vpk"):
    #         raise ValueError()
    #
    #     vpk = VPK(path)
    #     try:
    #         model = vpk.get_file(f"maps/{map_name}/world_physics.vmdl_c")
    #     except KeyError as err:
    #         raise ValueError(f"Can't dump .vmdl_c file from {path}") from err
    #
    #     return model.read()
    #
    # @staticmethod
    # def mdl2phys(path_or_stream_or_data: str | PathLike | IO | bytes) -> bytes:
    #     # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/Resource.cs
    #     # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/ResourceTypes/PhysAggregateData.cs
    #     # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/ResourceTypes/KeyValuesOrNTRO.cs
    #     # https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/ResourceTypes/BinaryKV3.cs
    #
    #     if isinstance(path_or_stream_or_data, BufferedIOBase):
    #         reader = BinaryReader(path_or_stream_or_data.read())
    #
    #     elif isinstance(path_or_stream_or_data, bytes):
    #         reader = BinaryReader(path_or_stream_or_data)
    #
    #     else:
    #         path = Path(path_or_stream_or_data)
    #         if not path.name.endswith(".vmdl_c"):
    #             raise ValueError()
    #
    #         with open(path, "rb") as model_file:
    #             reader = BinaryReader(model_file.read())
    #
    #     file_size = reader.read_uint32()
    #     header_version = reader.read_uint16()
    #     version = reader.read_uint16()
    #
    #     block_offset = reader.read_uint32()
    #     block_count = reader.read_uint32()
    #     reader.seek(block_offset - 0x8, Whence.CUR)
    #
    #     for i in range(block_count):
    #         block_type = reader.read_uint32()
    #
    #         position = reader.pos()
    #         offset = position + reader.read_uint32()
    #
    #         size = reader.read_uint32()
    #         if not size:
    #             continue
    #
    #         if block_type == ModelFile.BlockType.PHYS:
    #             reader.seek(offset, Whence.BEGIN)
    #             return reader.read_bytes(size)
    #
    #         reader.seek(position + 0x8, Whence.BEGIN)
    #
    #     raise RuntimeError(f"Cant found Block PHYS")
    #
    # @staticmethod
    # def phys2tri(path_or_stream_or_data: str | PathLike | IO | bytes) -> bytes:
    #     buffer = b""
    #     if isinstance(path_or_stream_or_data, BufferedIOBase):
    #         buffer = MemoryBuffer(path_or_stream_or_data.read())
    #
    #     elif isinstance(path_or_stream_or_data, bytes):
    #         buffer = MemoryBuffer(path_or_stream_or_data)
    #
    #     else:
    #         path = Path(path_or_stream_or_data)
    #         if not path.name.endswith(".vphys_c"):
    #             raise ValueError()
    #
    #         with open(path, "rb") as physics_file:
    #             buffer = MemoryBuffer(physics_file.read())
    #
    #     if not buffer:
    #         raise FileNotFoundError(path_or_stream_or_data)
    #
    #
    #     phys = read_valve_keyvalue3(buffer)
    #
    #     tris = bytearray()
    #     for index in count(start=0, step=1):
    #         # Hull
    #         try: collision_hull = phys["m_parts"][0]["m_rnShape"]["m_hulls"][index]["m_nCollisionAttributeIndex"]
    #         except Exception as err: collision_hull = None
    #
    #         if collision_hull == 0:
    #             hull    : dict  = phys["m_parts"][0]["m_rnShape"]["m_hulls"][index]["m_Hull"]
    #             vertices: bytes = hull.get("m_VertexPositions", None)
    #             faces   : bytes = hull["m_Faces"]
    #             edges   : bytes = hull["m_Edges"]
    #             # Edge(next, twin, origin, face)
    #             if vertices is None:
    #                 vertices: bytes = hull.get("m_VertexPositions")
    #
    #             for start_edge in faces:
    #                 edge = edges[start_edge << 2]
    #                 while edge != start_edge:
    #                     next_edge = edges[edge << 2]
    #
    #                     tris.extend(chain(
    #                         vertices[(b := edges[(edge       << 2) + 2] * 0xC): b + 0xC],
    #                         vertices[(b := edges[(start_edge << 2) + 2] * 0xC): b + 0xC],
    #                         vertices[(b := edges[(next_edge  << 2) + 2] * 0xC): b + 0xC],
    #                     ))
    #                     edge = next_edge
    #
    #         # Mesh
    #         try: collision_mesh = phys["m_parts"][0]["m_rnShape"]["m_meshes"][index]["m_nCollisionAttributeIndex"]
    #         except Exception as err: collision_mesh = None
    #
    #         if collision_mesh == 0:
    #             mesh     : bytes = phys["m_parts"][0]["m_rnShape"]["m_meshes"][index]["m_Mesh"]
    #             triangles: bytes = mesh["m_Triangles"]
    #             vertices : bytes = mesh["m_Vertices"]
    #
    #
    #             for triangle in range((len(triangles) * 0x55555556) >> 34):
    #                 triangle = (triangle << 2) + (triangle << 3)  # * 12
    #
    #                 tris.extend(chain(
    #                     vertices[
    #                         (k := ((bb := int.from_bytes(triangles[
    #                              (b := triangle + 0x0): b + 0x4
    #                          ] , "little")) << 2) + (bb << 3)): k + 0xC
    #                     ],
    #                     vertices[(k := int.from_bytes(triangles[(b := triangle + 0x4): b + 0x4], "little") * 0xC): k + 0xC],
    #                     vertices[(k := int.from_bytes(triangles[(b := triangle + 0x8): b + 0x4], "little") * 0xC): k + 0xC]
    #                 ))
    #
    #         if collision_hull is None and collision_mesh is None:
    #             break
    #     return tris
    #
    # @staticmethod
    # def phys2opt(path_or_stream_or_data: str | PathLike | IO | bytes) -> bytes:
    #     buffer = b""
    #     if isinstance(path_or_stream_or_data, BufferedIOBase):
    #         buffer = MemoryBuffer(path_or_stream_or_data.read())
    #
    #     elif isinstance(path_or_stream_or_data, bytes):
    #         buffer = MemoryBuffer(path_or_stream_or_data)
    #
    #     else:
    #         path = Path(path_or_stream_or_data)
    #         if not path.name.endswith(".vphys_c"):
    #             raise ValueError()
    #
    #         with open(path, "rb") as physics_file:
    #             buffer = MemoryBuffer(physics_file.read())
    #
    #     if not buffer:
    #         raise FileNotFoundError(path_or_stream_or_data)
    #
    #     phys = read_valve_keyvalue3(buffer)
    #
    #     meshes = list()
    #     for index in count(start=0, step=1):
    #         try:
    #             collision = phys["m_parts"][0]["m_rnShape"]["m_hulls"][index]["m_nCollisionAttributeIndex"]
    #         except Exception as err:
    #             collision = None
    #
    #         if collision is None:
    #             break
    #
    #         if collision != 0:
    #             continue
    #
    #         hull: dict = phys["m_parts"][0]["m_rnShape"]["m_hulls"][index]["m_Hull"]
    #         vertices: bytes = hull.get("m_VertexPositions", None)
    #         faces: bytes = hull["m_Faces"]
    #         edges: bytes = hull["m_Edges"]
    #         # Edge(next, twin, origin, face)
    #         if vertices is None:
    #             vertices: bytes = hull.get("m_VertexPositions")
    #
    #         a = bytearray(0x8)
    #         for start_edge in faces:
    #             edge = edges[start_edge << 2]
    #             while edge != start_edge:
    #                 next_edge = edges[edge << 2]
    #
    #                 a.extend(chain(
    #                     vertices[(b := edges[(edge << 2) + 2] * 0xC): b + 0xC],
    #                     vertices[(b := edges[(start_edge << 2) + 2] * 0xC): b + 0xC],
    #                     vertices[(b := edges[(next_edge << 2) + 2] * 0xC): b + 0xC],
    #                 ))
    #                 edge = next_edge
    #         a[0:8] = ((len(a) - 8) // 36).to_bytes(8, "little")
    #         meshes.append(a)
    #
    #     for index in count(start=0, step=1):
    #         try:
    #             collision = phys["m_parts"][0]["m_rnShape"]["m_meshes"][index]["m_nCollisionAttributeIndex"]
    #         except Exception as err:
    #             collision = None
    #
    #         if collision is None:
    #             break
    #
    #         if collision != 0:
    #             continue
    #
    #         mesh: bytes = phys["m_parts"][0]["m_rnShape"]["m_meshes"][index]["m_Mesh"]
    #         triangles: bytes = mesh["m_Triangles"]
    #         vertices: bytes = mesh["m_Vertices"]
    #
    #         a = bytearray(0x8)
    #         for triangle in range((len(triangles) * 0x55555556) >> 34):
    #             triangle = (triangle << 2) + (triangle << 3)  # * 12
    #
    #             a.extend(chain(
    #                 # vertices[(k := ((bb := int.from_bytes(triangles[(b := triangle + 0x0): b + 0x4], "little")) << 2) + (bb << 3)): k + 0xC],
    #                 # vertices[(k := ((bb := int.from_bytes(triangles[(b := triangle + 0x4): b + 0x4], "little")) << 2) + (bb << 3)): k + 0xC],
    #                 # vertices[(k := ((bb := int.from_bytes(triangles[(b := triangle + 0x8): b + 0x4], "little")) << 2) + (bb << 3)): k + 0xC],
    #                 vertices[(k := int.from_bytes(triangles[(b := triangle + 0x0): b + 0x4], "little") * 0xC): k + 0xC],
    #                 vertices[(k := int.from_bytes(triangles[(b := triangle + 0x4): b + 0x4], "little") * 0xC): k + 0xC],
    #                 vertices[(k := int.from_bytes(triangles[(b := triangle + 0x8): b + 0x4], "little") * 0xC): k + 0xC]
    #             ))
    #
    #         a[0:8] = ((len(a) - 8) // 36).to_bytes(8, "little")
    #         meshes.append(a)
    #
    #     meshes.insert(0, len(meshes).to_bytes(8, "little"))
    #     return b"".join(meshes)
    #
    # @classmethod
    # def vpk2phys(cls, path: str | PathLike) -> bytes:
    #     return cls.mdl2phys(cls.vpk2mdl(path))
    #
    # @classmethod
    # def vpk2tri(cls, path: str | PathLike) -> bytes:
    #     return cls.phys2tri(cls.mdl2phys(cls.vpk2mdl(path)))
    #
    # @classmethod
    # def mdl2tri(cls, path_or_stream_or_data: str | PathLike | IO | bytes) -> bytes:
    #     return cls.phys2tri(cls.mdl2phys(path_or_stream_or_data))
    #
    # @classmethod
    # def vpk2opt(cls, path: str | PathLike) -> bytes:
    #     return cls.phys2opt(cls.mdl2phys(cls.vpk2mdl(path)))
    #
    # @classmethod
    # def mdl2opt(cls, path_or_stream_or_data: str | PathLike | IO | bytes) -> bytes:
    #     return cls.phys2opt(cls.mdl2phys(path_or_stream_or_data))

    # VPK
    @staticmethod
    def vpk2mdl(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> ModelFile:
        return VPKFile(source).get_model_file(save_path)

    @staticmethod
    def vpk2phys(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> PhysicsFile:
        return VPKFile(source).vmdl_c.get_physics_file(save_path)

    @staticmethod
    def vpk2tri(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> bytes:
        return VPKFile(source).vmdl_c.vphys_c.to_triangle_file(save_path)

    @staticmethod
    def vpk2opt(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> bytes:
        return VPKFile(source).vmdl_c.vphys_c.to_opt_file(save_path)

    # model
    @staticmethod
    def mdl2phys(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> PhysicsFile:
        return ModelFile(source).get_physics_file(save_path)

    @staticmethod
    def mdl2tri(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> bytes:
        return ModelFile(source).vphys_c.to_triangle_file(save_path)

    @staticmethod
    def mdl2opt(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> bytes:
        return ModelFile(source).vphys_c.to_opt_file(save_path)

    # physics
    @staticmethod
    def phys2tri(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> bytes:
        return PhysicsFile(source).to_triangle_file(save_path)

    @staticmethod
    def phys2opt(source: str | PathLike | IO | bytes, save_path: str | Path | None = None) -> bytes:
        return PhysicsFile(source).to_opt_file(save_path)
