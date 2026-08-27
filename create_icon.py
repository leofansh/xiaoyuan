"""Create a simple tray icon for Xiaoyuan"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """Create a 64x64 icon with cat face"""
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle (green theme #96BB85)
    draw.ellipse([2, 2, 62, 62], fill=(150, 187, 133, 255))
    
    # Cat ears
    draw.polygon([(16, 8), (24, 20), (8, 20)], fill=(100, 140, 80, 255))
    draw.polygon([(48, 8), (56, 20), (40, 20)], fill=(100, 140, 80, 255))
    
    # Eyes
    draw.ellipse([20, 26, 28, 34], fill=(255, 255, 255, 255))
    draw.ellipse([36, 26, 44, 34], fill=(255, 255, 255, 255))
    draw.ellipse([22, 28, 26, 32], fill=(50, 50, 50, 255))
    draw.ellipse([38, 28, 42, 32], fill=(50, 50, 50, 255))
    
    # Nose
    draw.polygon([(30, 36), (34, 36), (32, 38)], fill=(255, 150, 150, 255))
    
    # Mouth
    draw.arc([24, 36, 40, 48], 0, 180, fill=(100, 100, 100, 255), width=2)
    
    # Whiskers
    draw.line([(10, 34), (22, 36)], fill=(100, 100, 100, 255), width=1)
    draw.line([(10, 38), (22, 38)], fill=(100, 100, 100, 255), width=1)
    draw.line([(42, 36), (54, 34)], fill=(100, 100, 100, 255), width=1)
    draw.line([(42, 38), (54, 38)], fill=(100, 100, 100, 255), width=1)
    
    return img

if __name__ == "__main__":
    icon = create_icon()
    output_path = os.path.join(os.path.dirname(__file__), "assets", "tray_icon.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    icon.save(output_path)
    print(f"Icon saved to {output_path}")
