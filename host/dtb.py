"""Minimal FDT v17 editor: preserve every property except three USB settings."""
import struct

PHY = '/syscon@ff2c0000/usb2-phy@100/otg-port'
CHANGES = {('/usb@ff300000', 'dr_mode'): b'peripheral\0',
           (PHY, 'status'): b'okay\0', (PHY, 'rockchip,vbus-always-on'): b''}


def parse(data):
    if len(data) < 40:
        raise ValueError('Truncated DTB')
    h = list(struct.unpack_from('>10I', data))
    magic, total, start, strings, reserve, version, compatible, cpu, slen, tlen = h
    if not (magic == 0xd00dfeed and version == 17 and compatible <= 17 and
            total == len(data) and 40 <= reserve < start < strings and
            start + tlen <= strings and strings + slen <= total):
        raise ValueError('Unsupported or malformed DTB layout; no changes made')
    table = data[strings:strings+slen]
    at, stack, tokens, props, nodes = start, [], [], {}, set()
    while at < start + tlen:
        begin = at
        kind = struct.unpack_from('>I', data, at)[0]; at += 4
        key = None
        if kind == 1:
            end = data.index(b'\0', at, start+tlen)
            stack.append(data[at:end].decode('ascii'))
            at = (end+4) & ~3
            path = '/'.join(stack) or '/'
            if path in nodes:
                raise ValueError('Duplicate DTB node')
            nodes.add(path)
        elif kind == 2:
            path = '/'.join(stack) or '/'
            stack.pop()
        elif kind == 3:
            length, offset = struct.unpack_from('>II', data, at); at += 8
            if offset >= len(table) or at + length > start+tlen:
                raise ValueError('Invalid DTB property bounds')
            name = table[offset:table.index(b'\0', offset)].decode('ascii')
            path = '/'.join(stack) or '/'
            key = (path, name)
            if key in props:
                raise ValueError('Duplicate DTB property')
            props[key] = data[at:at+length]
            at = (at+length+3) & ~3
        elif kind == 4:
            path = '/'.join(stack) or '/'
        elif kind == 9:
            if stack:
                raise ValueError('Unbalanced DTB nodes')
            tokens.append((kind, '/', None, data[begin:at]))
            if any(data[at:start+tlen]):
                raise ValueError('Unexpected DTB trailer')
            return h, table, tokens, props, nodes
        else:
            raise ValueError('Unknown DTB token')
        tokens.append((kind, path, key, data[begin:at]))
    raise ValueError('Missing DTB END token')


def patch(data):
    h, strings, tokens, before, nodes = parse(data)
    if b'rockchip,rk3326\0' not in before.get(('/', 'compatible'), b''):
        raise ValueError('Expected an RK3326 device tree')
    if not all(path in nodes for path, name in CHANGES):
        raise ValueError('Expected USB controller/PHY nodes are absent')
    if before.get(('/usb@ff300000', 'dr_mode')) not in (b'otg\0', b'peripheral\0'):
        raise ValueError('Unexpected controller role; inspect manually')
    if before.get((PHY, 'status')) not in (b'disabled\0', b'okay\0'):
        raise ValueError('Unexpected OTG PHY status; inspect manually')
    changed = {k for k, v in CHANGES.items() if before.get(k) != v}
    if not changed:
        return data, []
    table = bytearray(strings)

    def prop(name, value):
        needle = name.encode('ascii') + b'\0'
        off = bytes(table).find(needle)
        if off < 0:
            off = len(table); table.extend(needle)
        return struct.pack('>III', 3, len(value), off) + value + b'\0' * (-len(value) % 4)

    body = bytearray()
    for kind, path, key, raw in tokens:
        if kind == 2:
            for k, value in CHANGES.items():
                if k[0] == path and k not in before:
                    body.extend(prop(k[1], value))
        body.extend(prop(key[1], CHANGES[key]) if kind == 3 and key in CHANGES else raw)
    prefix = bytearray(data[:h[2]])
    tail = data[h[3]+h[8]:]
    h[3], h[8], h[9] = h[2]+len(body), len(table), len(body)
    h[1] = len(prefix)+len(body)+len(table)+len(tail)
    struct.pack_into('>10I', prefix, 0, *h)
    result = bytes(prefix+body+table+tail)
    after = parse(result)
    expected = dict(before); expected.update(CHANGES)
    if after[3] != expected or after[4] != nodes or result[40:h[2]] != data[40:h[2]]:
        raise ValueError('DTB preservation verification failed')
    return result, sorted(path+':'+name for path, name in changed)
