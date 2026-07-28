import fitz  # PyMuPDF
import tempfile
import os

def export_to_png(svg_content: str, output_path: str):
    """
    Rasteriza a obra vetorial para um formato leve de pré-visualização (Solução Nativa Windows via PyMuPDF).
    """
    # 1. Salva o SVG em um arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix=".svg", mode="w", encoding="utf-8") as temp_svg:
        temp_svg.write(svg_content)
        temp_path = temp_svg.name

    try:
        # 2. Abre o documento, renderiza a página em pixels e salva
        doc = fitz.open(temp_path)
        page = doc.load_page(0)
        
        # dpi=150 garante uma boa resolução para a prévia
        pix = page.get_pixmap(dpi=150) 
        pix.save(output_path)
        doc.close()
    finally:
        # 3. Limpeza de memória
        if os.path.exists(temp_path):
            os.remove(temp_path)