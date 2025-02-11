from PIL import Image
import os

def create_icons():
    try:
        # Otvoríme zdrojový obrázok
        img = Image.open('icon.png')
        
        # Definujeme veľkosti
        sizes = [16, 24, 32, 48, 256]
        
        # Vytvoríme priečinok ak neexistuje
        os.makedirs('resources/icons', exist_ok=True)
        
        # Pre každú veľkosť vytvoríme samostatnú ikonu
        for size in sizes:
            # Konvertujeme na RGBA ak nie je
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize s vysokou kvalitou
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Uložíme ako ico
            icon_path = f'resources/icons/icon{size}.ico'
            resized.save(icon_path, format='ICO')
            print(f"Vytvorená ikona {size}x{size}: {icon_path}")
        
        # Vytvoríme aj kombinovanú ikonu so všetkými veľkosťami
        icons = []
        for size in sizes:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            icons.append(resized)
        
        # Uložíme kombinovanú ikonu
        icons[0].save('resources/icons/icon.ico',
                     format='ICO',
                     sizes=[(size, size) for size in sizes],
                     append_images=icons[1:])
        print("Vytvorená kombinovaná ikona so všetkými veľkosťami")
            
    except Exception as e:
        print(f"Chyba pri vytváraní ikon: {str(e)}")

if __name__ == "__main__":
    create_icons()
