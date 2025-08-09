import base64
import struct
import base58
programm = "G3KpTd7rY3YNAAAAUG9wY29ybiBTbmFpbAUAAABTTkFJTFAAAABodHRwczovL2lwZnMuaW8vaXBmcy9iYWZrcmVpZDYyNDJwcGxza3Jmbm5zb2dpbzVhd2F5emVtaHBvZTZwbXJqamozdmJhZmRqYXZ0YWJoZVelRUGvs6pWutdQPCw2y6VbdgZNC/57S2bfUfPj26I/VlBlpIw8XuDSBGvoYpjMjmjbmmHzyIZEMnY2nu5o5a0QtxqcQVlbA4kjBhcaYAJJy/OYNY6DdPf34nsgcRFUohC3GpxBWVsDiSMGFxpgAknL85g1joN09/fieyBxEVSi7tKWaAAAAAAAENhH488DAACsI/wGAAAAAHjF+1HRAgAAgMakfo0DAA==" 
def parse_create_instruction(program_data: str) -> dict:
    """Парсит данные инструкции Create из Pump.fun"""
    try:
        decoded_data = base64.b64decode(program_data)
        offset = 0
        
        # Парсим discriminator (первые 8 байт)
        discriminator = decoded_data[offset:offset + 8].hex()
        offset += 8
        
        # Парсим имя токена
        name_len = struct.unpack_from('<I', decoded_data, offset)[0]
        offset += 4
        name = decoded_data[offset:offset + name_len].decode('utf-8').rstrip('\x00')
        offset += name_len
        
        # Парсим символ токена
        symbol_len = struct.unpack_from('<I', decoded_data, offset)[0]
        offset += 4
        symbol = decoded_data[offset:offset + symbol_len].decode('utf-8').rstrip('\x00')
        offset += symbol_len
        
        # Парсим URI токена
        uri_len = struct.unpack_from('<I', decoded_data, offset)[0]
        offset += 4
        uri = decoded_data[offset:offset + uri_len].decode('utf-8').rstrip('\x00')
        offset += uri_len
        
        # Парсим mint account (32 байта)
        mint_bytes = decoded_data[offset:offset + 32]
        mint = base58.b58encode(mint_bytes).decode('utf-8')
        offset += 32
        
        # Пропускаем 32 байта (похоже на bonding curve)
        bonding_curve_bytes = decoded_data[offset:offset + 32]
        offset += 32
        
        # Пропускаем еще 32 байта
        associated_bonding_curve_bytes = decoded_data[offset:offset + 32]
        offset += 32
        
        # Парсим user account (32 байта)
        user_bytes = decoded_data[offset:offset + 32]
        user = base58.b58encode(user_bytes).decode('utf-8')
        offset += 32
        
        # Остальные данные (если есть)
        remaining_data = decoded_data[offset:]
        
        parsed_data = {
            "source": "bonk",
            "mint": mint,
            "user": user,
            "name": name,
            "symbol": symbol,
            "uri": uri,
        }
        
        return parsed_data
    except:
        return None

print(parse_create_instruction(programm))