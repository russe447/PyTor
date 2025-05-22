# torrent_parser.py

import hashlib
from bencoding import bdecode, bencode_value # Import bencoding functions

def parse_torrent_file(torrent_filepath):
    """
    Parses a .torrent file to extract essential information.
    Returns the decoded torrent data, announce URL, and info hash.
    """
    print(f"\n--- Parsing Torrent File: {torrent_filepath} ---")
    with open(torrent_filepath, 'rb') as f:
        torrent_data_bytes = f.read()

    decoded_torrent = bdecode(torrent_data_bytes)

    # Extract announce URL
    announce_url = decoded_torrent[b'announce'].decode('utf-8')
    print(f"Announce URL: {announce_url}")

    # Calculate info hash
    info_dict = decoded_torrent[b'info']
    # Re-bencode the info dictionary to get its raw bytes for hashing
    info_bencoded_bytes = bencode_value(info_dict)
    info_hash = hashlib.sha1(info_bencoded_bytes).digest()
    print(f"Info Hash (hex): {info_hash.hex()}")

    # Extract file name and size for display
    if b'name' in info_dict:
        torrent_name = info_dict[b'name'].decode('utf-8')
        print(f"Torrent Name: {torrent_name}")
    
    total_length = 0
    if b'files' in info_dict: # Multi-file torrent
        for file_info in info_dict[b'files']:
            total_length += file_info[b'length']
    else: # Single-file torrent
        total_length = info_dict[b'length']
    print(f"Total Size: {total_length} bytes")

    return decoded_torrent, announce_url, info_hash

