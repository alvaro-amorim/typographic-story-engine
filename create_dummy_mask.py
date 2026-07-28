from PIL import Image, ImageDraw

def create_mask():
    # Cria uma imagem de 400x400 com fundo branco (255)
    img = Image.new('L', (400, 400), color=255)
    draw = ImageDraw.Draw(img)
    
    # Desenha um círculo preto (0) no centro para simular nosso "objeto"
    draw.ellipse((50, 50, 350, 350), fill=0)
    
    # Salva na raiz do projeto
    img.save('cat_mask.png')
    print("Máscara de teste 'cat_mask.png' gerada com sucesso!")

if __name__ == "__main__":
    create_mask()