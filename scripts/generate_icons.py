#!/usr/bin/env python3
"""
Generate app icons for all platforms from a single source image.

This script generates:
- macOS .icns file with rounded corners (Apple HIG standard)
- Windows .ico file with square edges
- Linux PNGs at various sizes with square edges

Usage:
    python scripts/generate_icons.py [--source PATH] [--output-dir PATH]

The source image should be at least 1024x1024 pixels for best quality.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


# Icon sizes for each platform
MACOS_SIZES = [
    (16, 1),    # 16x16
    (16, 2),    # 16x16@2x (32x32)
    (32, 1),    # 32x32
    (32, 2),    # 32x32@2x (64x64)
    (48, 1),    # 48x48 (non-standard but included in some icns)
    (128, 1),   # 128x128
    (128, 2),   # 128x128@2x (256x256)
    (256, 1),   # 256x256
    (256, 2),   # 256x256@2x (512x512)
    (512, 1),   # 512x512
    (512, 2),   # 512x512@2x (1024x1024)
]

WINDOWS_SIZES = [16, 32, 48, 64, 128, 256]

LINUX_SIZES = [16, 32, 48, 64, 128, 256, 512]


def create_rounded_mask(size: int, radius_percent: float = 0.22) -> Image.Image:
    """
    Create a rounded rectangle mask for macOS-style icons.

    Apple's macOS icons use approximately 22% corner radius relative to icon size.

    Args:
        size: The size of the mask in pixels
        radius_percent: Corner radius as percentage of size (default 22%)

    Returns:
        RGBA image with rounded rectangle alpha mask
    """
    radius = int(size * radius_percent)

    # Create a high-res mask for better anti-aliasing
    scale = 4
    large_size = size * scale
    large_radius = radius * scale

    # Create mask at higher resolution
    mask = Image.new('L', (large_size, large_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        [(0, 0), (large_size - 1, large_size - 1)],
        radius=large_radius,
        fill=255
    )

    # Downscale with antialiasing
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)

    return mask


def resize_image(source: Image.Image, size: int) -> Image.Image:
    """
    Resize image with high-quality LANCZOS resampling.

    Args:
        source: Source image (should be RGBA)
        size: Target size (square)

    Returns:
        Resized RGBA image
    """
    return source.resize((size, size), Image.Resampling.LANCZOS)


def apply_rounded_corners(image: Image.Image, radius_percent: float = 0.22) -> Image.Image:
    """
    Apply rounded corners to an image.

    Args:
        image: Source RGBA image
        radius_percent: Corner radius as percentage of size

    Returns:
        Image with rounded corners (transparent outside)
    """
    size = image.width
    mask = create_rounded_mask(size, radius_percent)

    # Ensure image has alpha channel
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    # Apply mask to alpha channel
    result = image.copy()
    # Composite the mask with existing alpha
    r, g, b, a = result.split()
    # Multiply existing alpha with mask
    a = Image.composite(a, Image.new('L', (size, size), 0), mask)
    result = Image.merge('RGBA', (r, g, b, a))

    return result


def generate_macos_iconset(source: Image.Image, output_dir: Path) -> Path:
    """
    Generate macOS .iconset directory with all required sizes.

    Args:
        source: Source image (at least 1024x1024)
        output_dir: Directory to create iconset in

    Returns:
        Path to the created .iconset directory
    """
    iconset_dir = output_dir / 'AppIcon.iconset'
    iconset_dir.mkdir(parents=True, exist_ok=True)

    for base_size, scale in MACOS_SIZES:
        actual_size = base_size * scale

        # Resize
        resized = resize_image(source, actual_size)

        # Apply rounded corners
        rounded = apply_rounded_corners(resized)

        # Generate filename
        if scale == 1:
            filename = f'icon_{base_size}x{base_size}.png'
        else:
            filename = f'icon_{base_size}x{base_size}@{scale}x.png'

        # Save
        output_path = iconset_dir / filename
        rounded.save(output_path, 'PNG', optimize=True)
        print(f'  Created {filename} ({actual_size}x{actual_size})')

    return iconset_dir


def generate_macos_icns(source: Image.Image, output_path: Path) -> None:
    """
    Generate macOS .icns file.

    Args:
        source: Source image (at least 1024x1024)
        output_path: Path for output .icns file
    """
    print('Generating macOS .icns...')

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Generate iconset
        iconset_dir = generate_macos_iconset(source, tmpdir_path)

        # Convert to icns using iconutil (macOS only)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                ['iconutil', '-c', 'icns', str(iconset_dir), '-o', str(output_path)],
                check=True,
                capture_output=True,
                text=True
            )
            print(f'  Created {output_path}')
        except FileNotFoundError:
            print('  Warning: iconutil not found (requires macOS)')
            print('  Copying iconset directory instead...')
            # On non-macOS, just save the iconset
            import shutil
            dest_iconset = output_path.parent / 'AppIcon.iconset'
            if dest_iconset.exists():
                shutil.rmtree(dest_iconset)
            shutil.copytree(iconset_dir, dest_iconset)
            print(f'  Created {dest_iconset}')
        except subprocess.CalledProcessError as e:
            print(f'  Error running iconutil: {e.stderr}')
            raise


def generate_windows_ico(source: Image.Image, output_path: Path) -> None:
    """
    Generate Windows .ico file with multiple sizes.

    Args:
        source: Source image (at least 256x256)
        output_path: Path for output .ico file
    """
    print('Generating Windows .ico...')

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate all sizes (largest first for better compatibility)
    images = []
    for size in sorted(WINDOWS_SIZES, reverse=True):
        resized = resize_image(source, size)
        # Ensure RGBA for ICO format
        if resized.mode != 'RGBA':
            resized = resized.convert('RGBA')
        images.append(resized)
        print(f'  Added {size}x{size}')

    # Save as ICO - use the largest image as base and append others
    # Pillow requires sizes to match the actual images being saved
    images[0].save(
        output_path,
        format='ICO',
        append_images=images[1:],
        sizes=[(img.width, img.height) for img in images]
    )
    print(f'  Created {output_path}')


def generate_linux_pngs(source: Image.Image, output_dir: Path, name_prefix: str = 'mhkit-dolfyn') -> None:
    """
    Generate Linux PNG icons at various sizes.

    Args:
        source: Source image
        output_dir: Directory to save PNGs
        name_prefix: Prefix for icon filenames
    """
    print('Generating Linux PNGs...')

    output_dir.mkdir(parents=True, exist_ok=True)

    for size in LINUX_SIZES:
        resized = resize_image(source, size)

        # Ensure RGBA
        if resized.mode != 'RGBA':
            resized = resized.convert('RGBA')

        filename = f'{name_prefix}-{size}x{size}.png'
        output_path = output_dir / filename
        resized.save(output_path, 'PNG', optimize=True)
        print(f'  Created {filename}')


def main():
    parser = argparse.ArgumentParser(
        description='Generate app icons for all platforms from a source image'
    )
    parser.add_argument(
        '--source',
        type=Path,
        default=Path('assets/app_icon/ios/AppIcon~ios-marketing.png'),
        help='Path to source image (default: assets/app_icon/ios/AppIcon~ios-marketing.png)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('assets/app_icon'),
        help='Base output directory (default: assets/app_icon)'
    )
    parser.add_argument(
        '--platform',
        choices=['all', 'macos', 'windows', 'linux'],
        default='all',
        help='Which platform icons to generate (default: all)'
    )

    args = parser.parse_args()

    # Load source image
    if not args.source.exists():
        print(f'Error: Source image not found: {args.source}')
        sys.exit(1)

    print(f'Loading source image: {args.source}')
    source = Image.open(args.source)

    # Convert to RGBA if needed
    if source.mode != 'RGBA':
        source = source.convert('RGBA')

    print(f'Source size: {source.width}x{source.height}')

    if source.width < 1024 or source.height < 1024:
        print('Warning: Source image is smaller than 1024x1024, quality may be reduced')

    # Generate icons
    if args.platform in ('all', 'macos'):
        generate_macos_icns(source, args.output_dir / 'macos' / 'AppIcon.icns')

    if args.platform in ('all', 'windows'):
        generate_windows_ico(source, args.output_dir / 'windows' / 'AppIcon.ico')

    if args.platform in ('all', 'linux'):
        generate_linux_pngs(source, args.output_dir / 'linux')

    print('\nDone!')


if __name__ == '__main__':
    main()
