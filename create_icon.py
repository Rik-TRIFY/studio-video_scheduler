from PIL import Image
import os

def create_ico():
    try:
        img = Image.open('icon.png')
        
        # Vytvoríme všetky potrebné veľkosti
        sizes = [(16,16), (32,32), (48,48), (256,256)]
        icons = []
        
        for size in sizes:
            # Konvertujeme na RGBA ak nie je
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize s vysokou kvalitou
            resized = img.resize(size, Image.Resampling.LANCZOS)
            icons.append(resized)
        
        # Uložíme ako ico
        icons[0].save('icon.ico',
                     format='ICO',
                     sizes=sizes,
                     append_images=icons[1:],
                     optimize=True)
        
        print("Ikona bola úspešne vytvorená!")
        
    except Exception as e:
        print(f"Chyba pri vytváraní ikony: {str(e)}")

if __name__ == "__main__":
    create_ico()
