import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from typing import List, Tuple

def get_valid_coordinates(mask_path: str) -> Tuple[List[Tuple[int, int, float]], int, int]:
    """
    Lê a imagem, calcula a distância para a borda (Edge Detection) e retorna:
    1. Lista de tuplas (x, y, normalized_distance).
    2. A largura original da imagem.
    3. A altura original da imagem.
    """
    img = Image.open(mask_path).convert("L")
    width, height = img.size
    
    # Converte para array numpy. Pixels escuros (< 128) são o nosso objeto (True).
    data = np.array(img)
    binary_mask = data < 128
    
    # Calcula a distância exata de cada pixel escuro até o pixel claro (borda) mais próximo
    distance_map = distance_transform_edt(binary_mask)
    
    # Normaliza as distâncias para um valor entre 0.0 (borda) e 1.0 (centro máximo)
    max_dist = distance_map.max()
    if max_dist > 0:
        normalized_distance_map = distance_map / max_dist
    else:
        normalized_distance_map = distance_map
        
    # Pega as coordenadas onde a máscara é válida
    y_coords, x_coords = np.where(binary_mask)
    
    # Cria a lista unindo x, y e a distância normalizada daquele pixel específico
    valid_coords_with_dist = [
        (int(x), int(y), float(normalized_distance_map[y, x])) 
        for x, y in zip(x_coords, y_coords)
    ]
    
    return valid_coords_with_dist, width, height