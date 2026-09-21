#!/usr/bin/env python3
"""Create sample images for testing the Case Management UI."""

from PIL import Image, ImageDraw, ImageFont
import uuid
import os

def create_sample_image(text, size=(400, 300), color='white', text_color='black'):
    """Create a simple sample image with text."""
    img = Image.new('RGB', size, color=color)
    draw = ImageDraw.Draw(img)

    # Try to use a font, fallback to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        font = ImageFont.load_default()

    # Calculate text position (center)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)

    draw.text(position, text, font=font, fill=text_color)
    return img

def create_sample_verification_images():
    """Create sample images for testing."""

    # Create images directory
    images_dir = "/home/bharti/PramaanAI/images"
    os.makedirs(images_dir, exist_ok=True)

    # Generate a sample verification ID (you can change this to match an actual case)
    verification_id = "12345678-1234-5678-9abc-123456789abc"

    # Create document front image
    doc_front = create_sample_image("SAMPLE DOCUMENT\nFRONT", color='lightblue')
    doc_front.save(f"{images_dir}/{verification_id}.jpg", "JPEG")

    # Create document back image
    doc_back = create_sample_image("SAMPLE DOCUMENT\nBACK", color='lightgreen')
    doc_back.save(f"{images_dir}/{verification_id}_back.jpg", "JPEG")

    # Create selfie image
    selfie = create_sample_image("SAMPLE SELFIE\nLIVE PHOTO", color='lightcoral')
    selfie.save(f"{images_dir}/{verification_id}_selfie.jpg", "JPEG")

    print(f"Created sample images for verification ID: {verification_id}")
    print(f"Images saved in: {images_dir}")
    print("\nTo test:")
    print(f"1. Find a case with verification ID: {verification_id}")
    print("2. Or update the verification_id variable to match an existing case")
    print("3. View the case in the dashboard to see the images")

if __name__ == "__main__":
    create_sample_verification_images()