def get_salt(mac_address):
    mac_parts = mac_address.split(':')

    # Convert hex strings to integers and reverse the order
    salt_array = [int(part, 16) for part in mac_parts]
    salt_array.reverse()

    return bytearray(salt_array)
