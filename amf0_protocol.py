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
object_end_marker = 0x09
strict_array_marker = 0x0A
date_marker = 0x0B
long_string_marker = 0x0C
unsupported_marker = 0x0D
xml_document_marker = 0x0F
typed_object_marker = 0x10


class AMF0:
    def __init__(self, *args, **kwargs):
        self.obj = []
        pass

    def parse(self, msg: bytes):
        print(msg)
        # TODO
        while len(msg) > 0:
            res, msg = self.parse_types(msg)
            self.obj.append(res)
            print(res)
        return self.obj

    def compile(self):
        # TODO
        pass

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
            while msg[idx:idx+3] != bytes.fromhex('000009'):
                idx += 1
            obj = msg[1:idx]
            msg = msg[idx:]

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
            pass  # TODO
        elif type == strict_array_marker:
            pass  # TODO
        elif type == date_marker:
            return datetime.fromtimestamp(float.fromhex(msg[1:9].hex())), msg[10:]
        elif type == long_string_marker:
            mlen = int.from_bytes(msg[1:5], 'big')
            return msg[5:5 + mlen], msg[5 + mlen:]
        elif type == xml_document_marker:
            mlen = int.from_bytes(msg[1:5], 'big')
            xml = msg[5:5 + mlen]
            pass  # TODO
        elif type == typed_object_marker:
            pass  # TODO
