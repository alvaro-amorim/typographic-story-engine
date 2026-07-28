import argparse
import json
import os
from engine.models import SemanticObject
from engine.image_analysis import get_valid_coordinates
from engine.glyph_distribution import distribute_glyphs
from engine.svg_renderer import render_to_svg
from engine.semantic_validation import validate_scene
from engine.png_exporter import export_to_png

def main():
    # 1. Configuração da Interface de Linha de Comando (CLI)
    parser = argparse.ArgumentParser(description="Typographic Story Engine - Renderizador CLI")
    parser.add_argument("--id", type=str, default="obj_01", help="ID único do objeto (ex: cat_01)")
    parser.add_argument("--word", type=str, required=True, help="Palavra que formará o objeto (ex: CAT)")
    parser.add_argument("--mask", type=str, required=True, help="Caminho para o arquivo PNG de máscara")
    parser.add_argument("--count", type=int, default=12000, help="Quantidade de letras a serem distribuídas")
    
    args = parser.parse_args()

    print(f"Iniciando Typographic Story Engine: Renderizando '{args.word}'...")
    
    if not os.path.exists(args.mask):
        print(f"Erro: O arquivo de máscara '{args.mask}' não foi encontrado.")
        return

    # 2. Configuração Dinâmica do Objeto
    # (Para a CLI, estamos usando uma paleta neutra base, mas isso poderá ser parametrizado no futuro)
    target_object = SemanticObject(
        id=args.id,
        word=args.word.upper(),
        mask_path=args.mask,
        glyph_count=args.count, 
        font_size_range=(8, 28),
        palette=["#2C303A", "#4F5D75", "#BFC0C0", "#EAE2B7"]
    )
    
    # 3. Análise e Distribuição
    print(f"[{target_object.id}] Analisando máscara '{target_object.mask_path}'...")
    valid_pixels, img_width, img_height = get_valid_coordinates(target_object.mask_path)
    scene_glyphs = distribute_glyphs(
        object_id=target_object.id,
        valid_coords=valid_pixels,
        allowed_chars=target_object.allowed_characters,
        glyph_count=target_object.glyph_count,
        font_size_range=target_object.font_size_range,
        palette=target_object.palette,
        seed=817392
    )
    
    # Nomes dinâmicos para os arquivos gerados
    svg_file = f"{target_object.id}_scene.svg"
    json_file = f"{target_object.id}_scene.json"
    report_file = f"{target_object.id}_validation.json"
    png_file = f"{target_object.id}_preview.png"

    # 4. Renderização SVG
    print(f"Renderizando vetor ({svg_file})...")
    svg_output = render_to_svg(scene_glyphs, width=img_width, height=img_height)
    with open(svg_file, "w", encoding="utf-8") as f:
        f.write(svg_output)
        
    # 5. Dados JSON
    print(f"Exportando dados ({json_file})...")
    scene_data = [g.model_dump() for g in scene_glyphs]
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(scene_data, f, indent=2)
        
    # 6. Validação Estrita
    print("Executando o Validador Semântico...")
    report = validate_scene(scene_glyphs, target_object.allowed_characters, svg_output)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    if report["is_valid"]:
        print("  -> Validação APROVADA: Arquitetura 100% tipográfica e semântica.")
    else:
        print("  -> Validação REPROVADA: Regras estritas violadas.")

    # 7. Exportação PNG (Agora com PyMuPDF garantido)
    print(f"Rasterizando prévia ({png_file})...")
    export_to_png(svg_output, png_file)
    print("  -> Prévia PNG gerada com sucesso.")
        
    print(f"\nSUCESSO! O objeto '{args.word}' foi gerado em todos os formatos.")

if __name__ == "__main__":
    main()