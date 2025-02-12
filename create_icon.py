from PIL import Image
import os
from pathlib import Path

def create_icons():
    try:
        # Načítame zdrojový obrázok
        img = Image.open('icon.png')
        print(f"Načítaný zdrojový obrázok: {img.size}")
        
        # Veľkosti ikon potrebné pre Windows
        sizes = [(16,16), (24,24), (32,32), (48,48), (256,256)]
        
        # Vytvoríme priečinok pre ikony ak neexistuje
        output_dir = Path(os.path.expanduser("~/Documents/VideoScheduler/resources/icons"))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Pripravíme všetky veľkosti pre ICO súbor
        icons = []
        for size in sizes:
            # Vytvoríme kópiu v správnej veľkosti
            resized_img = img.resize(size, Image.Resampling.LANCZOS)
            icons.append(resized_img)
            print(f"Pripravená veľkosť: {size}")
        
        # Uložíme ako jeden ICO súbor so všetkými veľkosťami
        ico_path = output_dir / 'icon.ico'
        icons[0].save(ico_path, 
                     format='ICO',
                     sizes=[(i.width, i.height) for i in icons],
                     append_images=icons[1:])
        
        print(f"\nICO súbor bol úspešne vytvorený v: {ico_path}")
        print("Obsahuje tieto veľkosti:", sizes)
        
    except FileNotFoundError:
        print("Chyba: Súbor icon.png nebol nájdený!")
        print("Prosím, umiestnite icon.png do rovnakého priečinka ako tento script.")
    except Exception as e:
        print("Chyba pri vytváraní ikony:", str(e))

if __name__ == "__main__":
    create_icons()