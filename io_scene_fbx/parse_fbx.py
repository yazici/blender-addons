# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Script copyright (C) 2006-2012, assimp team
# Script copyright (C) 2013 Blender Foundation

__all__ = (
    "parse",
    "data_types",
    "FBXElem",
    )

from struct import unpack
import array
import zlib

# at the end of each nested block, there is a NUL record to indicate
# that the sub-scope exists (i.e. to distinguish between P: and P : {})
# this NUL record is 13 bytes long.
_BLOCK_SENTINEL_LENGTH = 13
_BLOCK_SENTINEL_DATA = (b'\0' * _BLOCK_SENTINEL_LENGTH)
_IS_BIG_ENDIAN = (__import__("sys").byteorder != 'little')
from collections import namedtuple
FBXElem = namedtuple("FBXElem", ("id", "props", "props_type", "elems"))
del namedtuple


def read_uint(read):
    return unpack(b'<I', read(4))[0]


def read_ubyte(read):
    return unpack(b'B', read(1))[0]


def read_string_ubyte(read):
    size = read_ubyte(read)
    data = read(size)
    return data


def unpack_array(read, array_type, array_stride, array_byteswap):
    length = read_uint(read)
    encoding = read_uint(read)
    comp_len = read_uint(read)

    data = read(comp_len)

    if encoding == 0:
        pass
    elif encoding == 1:
        data = zlib.decompress(data)

    assert(length * array_stride == len(data))

    data_array = array.array(array_type, data)
    if array_byteswap and _IS_BIG_ENDIAN:
        data_array.byteswap()
    return data_array


read_data_dict = {
    b'Y'[0]: lambda read, size: unpack(b'<h', read(2))[0],  # 16 bit int
    b'C'[0]: lambda read, size: unpack(b'?', read(1))[0],   # 1 bit bool (yes/no)
    b'I'[0]: lambda read, size: unpack(b'<i', read(4))[0],  # 32 bit int
    b'F'[0]: lambda read, size: unpack(b'<f', read(4))[0],  # 32 bit float
    b'D'[0]: lambda read, size: unpack(b'<d', read(8))[0],  # 64 bit float
    b'L'[0]: lambda read, size: unpack(b'<q', read(8))[0],  # 64 bit int
    b'R'[0]: lambda read, size: read(read_uint(read)),      # binary data
    b'S'[0]: lambda read, size: read(read_uint(read)),      # string data
    b'f'[0]: lambda read, size: unpack_array(read, 'f', 4, False),  # array (float)
    b'i'[0]: lambda read, size: unpack_array(read, 'i', 4, True),   # array (int)
    b'd'[0]: lambda read, size: unpack_array(read, 'd', 8, False),  # array (double)
    b'l'[0]: lambda read, size: unpack_array(read, 'q', 8, True),   # array (long)
    b'b'[0]: lambda read, size: read(size),  # unknown
    }


def read_elem(read, tell, use_namedtuple):
    # [0] the offset at which this block ends
    # [1] the number of properties in the scope
    # [2] the length of the property list
    end_offset = read_uint(read)
    if end_offset == 0:
        return None

    prop_count = read_uint(read)
    prop_length = read_uint(read)

    elem_id = read_string_ubyte(read)        # elem name of the scope/key
    elem_props_type = bytearray(prop_count)  # elem property types
    elem_props_data = [None] * prop_count    # elem properties (if any)
    elem_subtree = []                        # elem children (if any)

    for i in range(prop_count):
        data_type = read(1)[0]
        elem_props_data[i] = read_data_dict[data_type](read, prop_length)
        elem_props_type[i] = data_type

    if tell() < end_offset:
        while tell() < (end_offset - _BLOCK_SENTINEL_LENGTH):
            elem_subtree.append(read_elem(read, tell, use_namedtuple))

        if read(_BLOCK_SENTINEL_LENGTH) != _BLOCK_SENTINEL_DATA:
            raise IOError("failed to read nested block sentinel, "
                          "expected all bytes to be 0")

    if tell() != end_offset:
        raise IOError("scope length not reached, something is wrong")

    args = (elem_id, elem_props_data, elem_props_type, elem_subtree)
    return FBXElem(*args) if use_namedtuple else args


def parse(fn, use_namedtuple=True):
    # import time
    # t = time.time()

    root_elems = []

    with open(fn, 'rb') as f:
        read = f.read
        tell = f.tell

        HEAD_MAGIC = b'Kaydara FBX Binary\x20\x20\x00\x1a\x00'
        if read(len(HEAD_MAGIC)) != HEAD_MAGIC:
            raise IOError("Invalid header")

        fbx_version = read_uint(read)

        while True:
            elem = read_elem(read, tell, use_namedtuple)
            if elem is None:
                break
            root_elems.append(elem)

    # print("done in %.4f sec" % (time.time() - t))

    args = (b'', [], bytearray(0), root_elems)
    return FBXElem(*args) if use_namedtuple else args, fbx_version

# Inline module, only for external use
# pyfbx.data_types
data_types = type(array)("data_types")
data_types.__dict__.update(
dict(
INT16 = b'Y'[0],
BOOL = b'C'[0],
INT32 = b'I'[0],
FLOAT32 = b'F'[0],
FLOAT64 = b'D'[0],
INT64 = b'L'[0],
BYTES = b'R'[0],
STRING = b'S'[0],
FLOAT32_ARRAY = b'f'[0],
INT32_ARRAY = b'i'[0],
FLOAT64_ARRAY = b'd'[0],
INT64_ARRAY = b'l'[0],
))