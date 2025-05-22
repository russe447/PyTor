# bencoding.py

"""
Module for encoding and decoding BitTorrent's bencode format.
This implementation is simplified and assumes valid bencoded input.
It will not handle all edge cases or malformed data gracefully.
"""

def decode_int(bencoded_bytes, start):
    """Decodes a bencoded integer."""
    end = bencoded_bytes.find(b'e', start)
    if end == -1:
        raise ValueError("Invalid bencoded integer format")
    val = int(bencoded_bytes[start+1:end].decode('utf-8'))
    return val, end + 1

def decode_string(bencoded_bytes, start):
    """Decodes a bencoded string."""
    colon_index = bencoded_bytes.find(b':', start)
    if colon_index == -1:
        raise ValueError("Invalid bencoded string format")
    length = int(bencoded_bytes[start:colon_index].decode('utf-8'))
    string_start = colon_index + 1
    string_end = string_start + length
    val = bencoded_bytes[string_start:string_end]
    return val, string_end

def decode_list(bencoded_bytes, start):
    """Decodes a bencoded list."""
    decoded_list = []
    current_pos = start + 1 # Skip 'l'
    while bencoded_bytes[current_pos:current_pos+1] != b'e':
        val, new_pos = decode_value(bencoded_bytes, current_pos)
        decoded_list.append(val)
        current_pos = new_pos
    return decoded_list, current_pos + 1 # Skip 'e'

def decode_dict(bencoded_bytes, start):
    """Decodes a bencoded dictionary."""
    decoded_dict = {}
    current_pos = start + 1 # Skip 'd'
    while bencoded_bytes[current_pos:current_pos+1] != b'e':
        key, key_end = decode_string(bencoded_bytes, current_pos)
        value, value_end = decode_value(bencoded_bytes, key_end)
        decoded_dict[key] = value
        current_pos = value_end
    return decoded_dict, current_pos + 1 # Skip 'e'

def decode_value(bencoded_bytes, start):
    """Determines the type of bencoded value and calls the appropriate decoder."""
    prefix = bencoded_bytes[start:start+1]
    if prefix == b'i':
        return decode_int(bencoded_bytes, start)
    elif prefix.isdigit():
        return decode_string(bencoded_bytes, start)
    elif prefix == b'l':
        return decode_list(bencoded_bytes, start)
    elif prefix == b'd':
        return decode_dict(bencoded_bytes, start)
    else:
        raise ValueError(f"Unknown bencoded type prefix: {prefix}")

def bdecode(bencoded_bytes):
    """Main function to decode bencoded bytes."""
    return decode_value(bencoded_bytes, 0)[0]

def bencode_value(value):
    """Encodes a Python value into bencoded bytes."""
    if isinstance(value, int):
        return b'i' + str(value).encode('utf-8') + b'e'
    elif isinstance(value, bytes):
        return str(len(value)).encode('utf-8') + b':' + value
    elif isinstance(value, str):
        encoded_str = value.encode('utf-8')
        return str(len(encoded_str)).encode('utf-8') + b':' + encoded_str
    elif isinstance(value, list):
        encoded_list = b'l'
        for item in value:
            encoded_list += bencode_value(item)
        return encoded_list + b'e'
    elif isinstance(value, dict):
        encoded_dict = b'd'
        # Keys must be sorted for consistent hashing in BitTorrent
        for key in sorted(value.keys()):
            encoded_dict += bencode_value(key) + bencode_value(value[key])
        return encoded_dict + b'e'
    else:
        raise TypeError(f"Unsupported type for bencoding: {type(value)}")

