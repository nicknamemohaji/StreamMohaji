from datetime import datetime
import struct

# amf0 type constants
number_marker = 0x00
boolean_marker = 0x01
string_marker = 0x02
object_marker = 0x03
null_marker = 0x05
undefined_marker = 0x06
reference_marker = 0x07
ecma_array_marker = 0x08
object_end_marker = bytes.fromhex('000009')    # utf8_empty + 0x09
strict_array_marker = 0x0A
date_marker = 0x0B
long_string_marker = 0x0C
unsupported_marker = 0x0D
xml_document_marker = 0x0F
typed_object_marker = 0x10


class AMF0:
    def __init__(self, *args, **kwargs):
        self.obj = []
        self.__dict__.update(kwargs)

        if len(args) == 1:
            self.parse(args[0])
        return

    def parse(self, msg: bytes):
        while len(msg) > 0:
            res, msg = self.parse_types(msg)
            self.obj.append(res)
        return self.obj

    def compile(self):
        res = bytes()
        for data in self.obj:
            res += self.compile_amf0(data)
        return res

    def compile_amf0(self, data):
        # TODO implement amf0 fully
        res = bytes()
        if isinstance(data, str):
            if len(data) > 0xffff:
                res += bytes.fromhex(f'{long_string_marker}') + struct.pack('>Q', len(data)) + data.encode()
            else:
                res += bytes.fromhex(f'{string_marker}') + struct.pack('>I', len(data)) + data.encode()
        elif isinstance(data, float):
            res += bytes.fromhex(f'{number_marker}') + struct.pack('>d', data)
        elif isinstance(data, dict):
            res += self.compile_obj(data)
        elif isinstance(data, bool):
            res += bytes.fromhex(f'{boolean_marker}') + struct.pack('>?', data)
        else:
            raise NotImplementedError(f"type {type(data)} is not implemented...")
        return res

    def compile_obj(self, obj: dict):
        # TODO support amf0 fully
        res = bytes.fromhex(f'{object_marker}')
        for key in obj.keys():
            res += struct.pack('>I', len(key)) + key.compile()
            res += self.compile_amf0(obj[key])
        res += object_end_marker
        return res

    def parse_types(self, msg: bytes):
        type = msg[0]
        if type == number_marker:
            return struct.unpack('>d', msg[1:9])[0], msg[9:]
        elif type == boolean_marker:
            return (False if msg[1] == 0 else True), msg[2:]
        elif type == string_marker:
            mlen = int.from_bytes(msg[1:3], 'big')
            return msg[3: 3 + mlen], msg[3 + mlen:]
        elif type == object_marker:
            # first, calculate where the object end is...
            idx = 1
            while msg[idx:idx+3] != object_end_marker:
                idx += 1
            obj = msg[1:idx]
            msg = msg[idx+3:]

            # object notation is *(`keylen`:u16, `key`:string, `value_type`:marker, `value`: Any.. )
            obj_res = {}
            while len(obj) > 0:
                keylen = int.from_bytes(obj[0:2], 'big')
                key = obj[2:2+keylen]
                value, obj = self.parse_types(obj[2+keylen:])
                obj_res[key] = value

            return obj, msg

        elif type in (null_marker, undefined_marker):
            return None, msg[1:]
        elif type == reference_marker:
            pass  # TODO implement amf0 fully
        elif type == strict_array_marker:
            pass  # TODO implement amf0 fully
        elif type == date_marker:
            return datetime.fromtimestamp(float.fromhex(msg[1:9].hex())), msg[10:]
        elif type == long_string_marker:
            mlen = int.from_bytes(msg[1:5], 'big')
            return msg[5:5 + mlen], msg[5 + mlen:]
        elif type == xml_document_marker:
            mlen = int.from_bytes(msg[1:5], 'big')
            xml = msg[5:5 + mlen]
            pass  # TODO implement amf0 fully
        elif type == typed_object_marker:
            pass  # TODO implement amf0 fully
