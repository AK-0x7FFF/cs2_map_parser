from dataclasses import dataclass
from pickle import dump, HIGHEST_PROTOCOL
from struct import unpack, pack
from typing import Iterable

from vphys_parser import VphysParser



@dataclass
class Vec3:
    x: float
    y: float
    z: float

@dataclass
class Triangle:
    p1: Vec3
    p2: Vec3
    p3: Vec3

@dataclass
class Edge:
    next: int
    twin: int
    origin: int
    face: int


class BytesHelper:
    @staticmethod
    def uint8(value: bytes) -> int:
        return unpack("B", value)[0]

    @staticmethod
    def int32(value: bytes) -> int:
        return unpack("i", value)[0]

    @staticmethod
    def float(value: bytes) -> float:
        return unpack("f", value)[0]

    @staticmethod
    def bytes_merge(bytes_str: bytes, size: int) -> list[bytes]:
        bytes_count = len(bytes_str) // size

        bytes_list = list()
        for index in range(bytes_count):
            index *= size
            bytes_list.append(bytes_str[index:index + size])

        return bytes_list


def write_pkl(file_name: str, triangles: Iterable[Triangle]) -> None:
    with open(f"{file_name}.pkl", "wb") as file:
        dump(triangles, file, protocol=HIGHEST_PROTOCOL)

def write_tri(file_name: str, triangles: Iterable[Triangle]) -> None:
    byte_raw = list()
    for triangle in triangles:
        for point in (triangle.p1, triangle.p2, triangle.p3):
            byte_raw.append(point.x)
            byte_raw.append(point.y)
            byte_raw.append(point.z)
    triangles_byte = " ".join([
        pack("f", i).hex(" ").upper()
        for i in byte_raw
    ])
    with open(f"{file_name}.tri", "w") as file:
        file.write(triangles_byte)

def write_bin(file_name: str, triangles: Iterable[Triangle]) -> None:
    byte_raw = list()
    for triangle in triangles:
        for point in (triangle.p1, triangle.p2, triangle.p3):
            byte_raw.append(point.x)
            byte_raw.append(point.y)
            byte_raw.append(point.z)
    triangles_byte = b"".join([
        pack("f", i)
        for i in byte_raw
    ])
    with open(f"{file_name}.bin", "wb") as file:
        file.write(triangles_byte)




def main() -> None:
    parser = VphysParser.from_file_name("parse_example.vphys")
    saved_triangles = list()

    index = 0
    while True:
        collision = parser.search("m_parts", 0, "m_rnShape", "m_hulls", index, "m_nCollisionAttributeIndex")
        if collision is None: break
        if collision != 0:
            index += 1
            continue

        vertices_raw = parser.search("m_parts", 0, "m_rnShape", "m_hulls", index, "m_Hull", "m_Vertices")
        faces_raw = parser.search("m_parts", 0, "m_rnShape", "m_hulls", index, "m_Hull", "m_Faces")
        edges_raw = parser.search("m_parts", 0, "m_rnShape", "m_hulls", index, "m_Hull", "m_Edges")

        # vertices = list()
        vertices_merged = BytesHelper.bytes_merge(vertices_raw, 4)
        # for i in range(len(vertices_merged) // 3):
        #     i *= 3
        #     vertices.append(Vec3(
        #         BytesHelper.float(vertices_merged[i]),
        #         BytesHelper.float(vertices_merged[i + 1]),
        #         BytesHelper.float(vertices_merged[i + 2])
        #     ))
        vertices = [
            Vec3(
                BytesHelper.float(vertices_merged[(ii := i * 3)]),
                BytesHelper.float(vertices_merged[ii + 1]),
                BytesHelper.float(vertices_merged[ii + 2])
            )
            for i in range(len(vertices_merged) // 3)
        ]

        faces = (
            BytesHelper.uint8(byte)
            for byte in BytesHelper.bytes_merge(faces_raw, 1)
        )

        # edges = list()
        edges_merged = BytesHelper.bytes_merge(edges_raw, 1)
        # for i in range(len(edges_merged) // 4):
        #     i *= 4
        #     edges.append(Edge(
        #         BytesHelper.uint8(edges_merged[i]),
        #         BytesHelper.uint8(edges_merged[i + 1]),
        #         BytesHelper.uint8(edges_merged[i + 2]),
        #         BytesHelper.uint8(edges_merged[i + 3])
        #     ))
        edges = [
            Edge(
                BytesHelper.uint8(edges_merged[(ii := i * 4)]),
                BytesHelper.uint8(edges_merged[ii + 1]),
                BytesHelper.uint8(edges_merged[ii + 2]),
                BytesHelper.uint8(edges_merged[ii + 3]),
            )
            for i in range(len(edges_merged) // 4)
        ]

        for start_edge in faces:
            edge = edges[start_edge].next
            while edge != start_edge:
                next_edge = edges[edge].next

                saved_triangles.append(Triangle(
                    vertices[edges[start_edge].origin],
                    vertices[edges[edge].origin],
                    vertices[edges[next_edge].origin],
                ))

                edge = next_edge
        index += 1

    index = 0
    while True:
        collision = parser.search("m_parts", 0, "m_rnShape", "m_meshes", index, "m_nCollisionAttributeIndex")
        if collision is None: break
        if collision != 0:
            index += 1
            continue

        triangles_raw = parser.search("m_parts", 0, "m_rnShape", "m_meshes", index, "m_Mesh", "m_Triangles")
        vertices_raw = parser.search("m_parts", 0, "m_rnShape", "m_meshes", index, "m_Mesh", "m_Vertices")

        # vertices = list()
        vertices_merged = BytesHelper.bytes_merge(vertices_raw, 4)
        # for i in range(len(vertices_merged) // 3):
        #     i *= 3
        #     vertices.append(Vec3(
        #         BytesHelper.float(vertices_merged[i]),
        #         BytesHelper.float(vertices_merged[i + 1]),
        #         BytesHelper.float(vertices_merged[i + 2])
        #     ))
        vertices = [
            Vec3(
                BytesHelper.float(vertices_merged[(ii := i * 3)]),
                BytesHelper.float(vertices_merged[ii + 1]),
                BytesHelper.float(vertices_merged[ii + 2])
            )
            for i in range(len(vertices_merged) // 3)
        ]

        triangles_merged = [
            BytesHelper.int32(byte)
            for byte in BytesHelper.bytes_merge(triangles_raw, 4)
        ]
        # for i in range(len(triangles_merged) // 3):
        #     i *= 3
        #     saved_triangles.append(Triangle(
        #         vertices[triangles_merged[i]],
        #         vertices[triangles_merged[i + 1]],
        #         vertices[triangles_merged[i + 2]],
        #     ))
        saved_triangles.extend((
            Triangle(
                vertices[triangles_merged[(ii := i * 3)]],
                vertices[triangles_merged[ii + 1]],
                vertices[triangles_merged[ii + 2]],
            )
            for i in range(len(triangles_merged) // 3)
        ))
        index += 1



    write_pkl("output", saved_triangles)
    write_tri("output", saved_triangles)
    write_bin("output", saved_triangles)




# def test() -> None:
#     from time import perf_counter
#
#     class TimeCounter:
#         def __init__(self, prefix: str, is_print: bool = False) -> None:
#             self.prefix = prefix
#             self.is_print = is_print
#
#         def __enter__(self) -> None: self.start_time = perf_counter()
#
#         def __exit__(self, _, __, ___) -> None:
#             if self.is_print:
#                 print("%s: %.8f ms" % (self.prefix, (perf_counter() - self.start_time) * 1000))
#
#     with open("parse_example.vphys", "r") as vphys_file:
#         vphys_content = vphys_file.read()
#
#         with TimeCounter("VphysParser __init__"):
#             parser = VphysParser(vphys_content)
#
#         parser.search("m_parts", 0, "m_rnShape", "m_hulls", 0, "m_Hull", "m_Vertices")
#
#
#         parser.search("m_parts", 0, "m_rnShape", "m_hulls", 999, "m_Hull", "m_Vertices")
#         with TimeCounter("VphysParser search 1000", True):
#             parser.search("m_parts", 0, "m_rnShape", "m_hulls", 1000, "m_Hull", "m_Vertices")
#
#         with TimeCounter("VphysParser search 1", True):
#             parser.search("m_parts", 0, "m_rnShape", "m_hulls", 1, "m_Hull", "m_Vertices")


if __name__ == '__main__':
    main()