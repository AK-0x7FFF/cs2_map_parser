from enum import IntEnum
from typing import Union



class VphysBoundaryType(IntEnum):
    DICT_PREFIX         = 0x0
    DICT_SUFFIX         = 0x1
    LIST_PREFIX         = 0x2
    HEX_PREFIX          = 0x3
    LIST_AND_HEX_SUFFIX = 0x4


class VphysContainer:
    def __init__(self, parser: "VphysParser", boundary_start: int) -> None:
        self.parser = parser

        self.boundary_start = boundary_start
        self.boundary_end = self.get_boundary_end(boundary_start)


    def get_boundary_end(self, start_line: int) -> int | None:
        if start_line not in self.parser.object_boundaries.keys(): raise ValueError("start_line %i is legal." % start_line)

        if (end_line_from_cache := self.parser.object_boundaries_box_cache.get(start_line, None)) is not None:
            return end_line_from_cache

        prefix_type = self.parser.get_boundary_mark_type(start_line)
        suffix_type = {
            VphysBoundaryType.DICT_PREFIX: VphysBoundaryType.DICT_SUFFIX,
            VphysBoundaryType.LIST_PREFIX: VphysBoundaryType.LIST_AND_HEX_SUFFIX,
            VphysBoundaryType.HEX_PREFIX: VphysBoundaryType.LIST_AND_HEX_SUFFIX,
        }.get(prefix_type, None)
        if prefix_type is None or suffix_type is None: return None

        prefix_count, suffix_count = 1, 0

        # time cast is too big (28ms)
        # for line, boundary_type in {x: y for x, y in self.parser.object_boundaries.items() if x > start_line}.items():
        # time cast is too big (24ms)
        # for line, boundary_type in filter(lambda line_filtering: line_filtering[0] > start_line, self.parser.object_boundaries.items()):
        for line, boundary_type in (
                (line_filtering, boundary_type_filtering)
                for line_filtering, boundary_type_filtering in self.parser.object_boundaries.items()
                if line_filtering > start_line
        ):
            if boundary_type == prefix_type: prefix_count += 1
            if boundary_type == suffix_type: suffix_count += 1

            if prefix_type == VphysBoundaryType.LIST_PREFIX:
                if boundary_type == VphysBoundaryType.HEX_PREFIX: prefix_count += 1

            if prefix_count == suffix_count:
                self.parser.object_boundaries_box_cache.update({start_line: line})
                return line


class VphysList(VphysContainer):
    def __init__(self, parser: "VphysParser", boundary_start: int) -> None:
        super().__init__(parser, boundary_start)

    def __getitem__(self, index: int) -> Union[float, "VphysDict", "VphysList", "VphysHex", None]:
        if not isinstance(index, int): raise ValueError("keyword argument should be str.")
        return self.get_index(index)

    def get_index_value(self, target_line: int) -> Union[bool, float, "VphysDict", "VphysList", "VphysHex", None]:
        content = self.parser.get_line_content(target_line)

        match self.parser.get_boundary_mark_type(target_line):
            case VphysBoundaryType.DICT_PREFIX:
                return VphysDict(self.parser, target_line)
            case VphysBoundaryType.LIST_PREFIX:
                return VphysList(self.parser, target_line)
            case VphysBoundaryType.HEX_PREFIX:
                return VphysHex(self.parser, target_line)
            case None:
                content = content.replace(",", "").strip()

                if content.lower() in ("true", "false"):
                    return content.lower() == "true"
                elif "." in content:
                    return float(content)
                else:
                    return int(content)
        return None


    def get_index(self, target_index: int) -> Union[float, "VphysDict", None]:
        # line_index = self.boundary_start + 1
        # read_index = -1

        cached_list_boundary = self.parser.list_index_cache.get(self.boundary_start, {})
        if (cached_boundary := cached_list_boundary.get(target_index)) is not None:
            line_index =  cached_boundary[0]
            read_index = target_index - 1
        else:
            if cached_list_boundary.keys() and (max_index_in_cache := max(cached_list_boundary.keys())) < target_index:
                cached_boundary = cached_list_boundary[max_index_in_cache]

                line_index = cached_boundary[0]
                read_index = max_index_in_cache - 1
            else:
                line_index = self.boundary_start + 1
                read_index = -1

        while line_index < self.boundary_end:
            if self.parser.is_blank_line(line_index):
                line_index += 1
                continue

            var_type = self.parser.get_boundary_mark_type(line_index)
            read_index += 1

            if target_index == read_index:
                value = self.get_index_value(line_index)
                return value


            if var_type is None: line_index_next = line_index
            else:
                if var_type not in (VphysBoundaryType.DICT_PREFIX, VphysBoundaryType.LIST_PREFIX, VphysBoundaryType.HEX_PREFIX): return None
                line_index_next = boundary_end if (boundary_end := self.get_boundary_end(line_index)) is not None else line_index

            self.parser.list_index_cache.setdefault(self.boundary_start, {}).update({read_index: (line_index, line_index_next)})
            line_index = line_index_next + 1


class VphysDict(VphysContainer):
    def __init__(self, parser: "VphysParser", boundary_start: int) -> None:
        super().__init__(parser, boundary_start)

    def __getitem__(self, keyword: str) -> Union[int, float, "VphysDict", "VphysList", "VphysHex", None]:
        if not isinstance(keyword, str): raise ValueError("keyword argument should be str.")
        return self.get_var(keyword)

    def get_var_name(self, target_line: int) -> str | None:
        target_content_split = self.parser.get_line_content(target_line).split(" = ")

        if len(target_content_split) != 2: return None
        return target_content_split[0]

    def get_var_value(self, target_line: int) -> Union[int, float, "VphysDict", "VphysList", "VphysHex", None]:
        target_content_split = self.parser.get_line_content(target_line).split(" = ")
        if len(target_content_split) != 2: return None
        content_var = target_content_split[1]


        if content_var != "":
            if content_var.lower() in ("true", "false"):
                return content_var.lower() == "true"
            elif "." in content_var:
                return float(content_var)
            else:
                return int(content_var)
        else:
            target_line += 1

            match self.parser.get_boundary_mark_type(target_line):
                case VphysBoundaryType.DICT_PREFIX:
                    return VphysDict(self.parser, target_line)
                case VphysBoundaryType.LIST_PREFIX:
                    return VphysList(self.parser, target_line)
                case VphysBoundaryType.HEX_PREFIX:
                    return VphysHex(self.parser, target_line)
            return None

    def get_var(self, target_var_name: str) -> Union[int, float, "VphysDict", VphysList, "VphysHex", None]:
        line_index = self.boundary_start + 1
        while line_index < self.boundary_end:
            if self.parser.is_blank_line(line_index):
                line_index += 1
                continue

            var_name = self.get_var_name(line_index)
            if var_name is not None and var_name == target_var_name:
                return self.get_var_value(line_index)

            # 4 more readable
            # line_index = line_index_next + 1 if (line_index_next := self.get_boundary_end(line_index)) is not None else line_index + 1
            line_index = self.get_boundary_end(line_index) + 1 if self.parser.get_boundary_mark_type(line_index) is not None else line_index + 1
        return None


class VphysHex(VphysContainer):
    def __init__(self, parser: "VphysParser", boundary_start: int) -> None:
        super().__init__(parser, boundary_start)

    def get_str(self) -> str | None:
        return " ".join(self.parser.get_line_content(line) for line in range(self.boundary_start + 1, self.boundary_end)).strip()

    def get_bytes(self) -> bytes:
        return bytes.fromhex(self.get_str())


class VphysParser:
    def __init__(self, content: str) -> None:
        self.content = content.replace("\t", "").splitlines()
        self.object_boundaries = self.object_boundaries_build(self.content)

        self.object_boundaries_box_cache: dict[int, int] = dict()
        self.list_index_cache: dict[int, dict[int, tuple[int, int]]] = dict()

        self.main_dict = VphysDict(self, tuple(self.object_boundaries.keys())[0])


    @classmethod
    def from_file_name(cls, file_name: str) -> "VphysParser":
        with open(file_name, "r") as vphys_file:
            vphys_content = vphys_file.read()
            return VphysParser(vphys_content)


    def get_line_content(self, target_line: int) -> str:
        return self.content[target_line].lstrip()


    def get_boundary_mark_type(self, target_line: int) -> VphysBoundaryType | None:
        content = self.get_line_content(target_line).replace(",", "")
        return {
            "{": VphysBoundaryType.DICT_PREFIX,
            "}": VphysBoundaryType.DICT_SUFFIX,
            "#[": VphysBoundaryType.HEX_PREFIX,
            "[": VphysBoundaryType.LIST_PREFIX,
            "]": VphysBoundaryType.LIST_AND_HEX_SUFFIX,
        }.get(content, None)


    def is_blank_line(self, target_line: int) -> bool:
        return self.get_line_content(target_line) == ""


    def object_boundaries_build(self, content: list) -> dict[int, int]:
        object_boundaries = dict()
        for line, line_content in enumerate(content):
            if "<!" in line_content: continue

            boundary_type = self.get_boundary_mark_type(line)
            if boundary_type is None: continue

            object_boundaries.update({line: boundary_type})
        boundaries = list(object_boundaries.values())
        if (
            boundaries.count(VphysBoundaryType.DICT_PREFIX) != boundaries.count(VphysBoundaryType.DICT_SUFFIX) or
            (boundaries.count(VphysBoundaryType.LIST_PREFIX) + boundaries.count(VphysBoundaryType.HEX_PREFIX)) != boundaries.count(VphysBoundaryType.LIST_AND_HEX_SUFFIX)
        ): raise ValueError("Missing closed sign.")

        return object_boundaries


    def search(self, *args: int | str) -> int | float | bytes | None:
        target_object = self.main_dict
        for keyword in args:
            if isinstance(keyword, str):
                if isinstance(target_object, VphysDict): target_object = target_object.get_var(keyword)
                if isinstance(target_object, VphysHex): target_object = target_object.get_bytes()
                if target_object is None: return None
            elif isinstance(keyword, int):
                target_object = target_object.get_index(keyword)
            else: raise ValueError("Keyword %s does not exist." % keyword)

        return target_object
