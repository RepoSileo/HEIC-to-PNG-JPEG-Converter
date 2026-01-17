import sys
import time
import json
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from colorama import init, Fore, Style, Back
import humanize

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

init(autoreset=True)

HEIF_AVAILABLE = False
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
except Exception as e:
    print(f"{Fore.RED}HEIF support unavailable: {e}{Style.RESET_ALL}")
    HEIF_AVAILABLE = False

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

def load_config():
    default = {"output_format": "png", "jpeg_quality": 95}
    if CONFIG_PATH.exists():
        try:
            return {**default, **json.loads(CONFIG_PATH.read_text('utf-8'))}
        except:
            pass
    return default

def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), 'utf-8')
    except:
        pass

def print_header():
    print(f"\n{Back.BLUE}{Fore.WHITE} By RepoSileo {Style.RESET_ALL}")
    print(f"\n{Back.BLUE}{Fore.WHITE} HEIC to PNG/JPEG Converter {Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")

def sanitize_image(img):
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        if img.mode == "RGBA":
            bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img

def choose_format():
    cfg = load_config()
    while True:
        print(f"{Fore.YELLOW}Select output format:{Style.RESET_ALL}")
        print("1. JPEG ")
        print("2. PNG ")
        print("Q. Quit\n")
        choice = input(f"{Fore.CYAN}→ Enter 1, 2, or Q: {Style.RESET_ALL}").strip().lower()
        if choice == 'q':
            return None
        elif choice == '1':
            q_input = input(f"{Fore.CYAN}→ JPEG quality (1–100, Enter = {cfg['jpeg_quality']}): {Style.RESET_ALL}").strip()
            try:
                q = int(q_input) if q_input else cfg['jpeg_quality']
                q = max(1, min(100, q))
            except:
                q = cfg['jpeg_quality']
            cfg.update({"output_format": "jpeg", "jpeg_quality": q})
            break
        elif choice == '2':
            cfg["output_format"] = "png"
            break
        else:
            print(f"{Fore.RED}Invalid input. Try again.{Style.RESET_ALL}\n")
    save_config(cfg)
    return cfg

def print_summary(stats, output_format, jpeg_quality=None):
    print(f"\n{Back.GREEN}{Fore.BLACK} Conversion Complete {Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
    total_orig = sum(s['original_size'] for s in stats)
    total_conv = sum(s['converted_size'] for s in stats)

    print(f"\n{Fore.GREEN}Files converted: {len(stats)}{Style.RESET_ALL}")
    if output_format == "jpeg":
        print(f"{Fore.BLUE}Format: JPEG (quality {jpeg_quality}%)")
    else:
        print(f"{Fore.BLUE}Format: PNG")

    print(f"{Fore.YELLOW}Size summary:{Style.RESET_ALL}")
    print(f"   Original: {Fore.CYAN}{humanize.naturalsize(total_orig)}{Style.RESET_ALL}")
    print(f"   Converted: {Fore.CYAN}{humanize.naturalsize(total_conv)}{Style.RESET_ALL}")

    delta = total_conv - total_orig
    sign = "↑" if delta > 0 else "↓"
    print(f"   Change: {sign} {Fore.MAGENTA}{humanize.naturalsize(abs(delta))}{Style.RESET_ALL}")

    if stats:
        top3 = sorted(stats, key=lambda x: x['converted_size'], reverse=True)[:3]
        print(f"\n{Fore.YELLOW}Top 3 largest outputs:{Style.RESET_ALL}")
        for s in top3:
            ratio = s['converted_size'] / s['original_size'] if s['original_size'] else 1
            print(f"   • {s['filename']}: {humanize.naturalsize(s['original_size'])} → "
                  f"{humanize.naturalsize(s['converted_size'])} ({ratio:.2f}x)")

def convert_files(config):
    script_dir = Path(__file__).resolve().parent
    input_dir = script_dir / "input"
    output_dir = script_dir / "output"
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    files = [f for f in input_dir.iterdir() if f.is_file() and f.suffix.lower() in ('.heic', '.heif')]
    if not files:
        print(f"{Fore.RED}No .heic/.heif files in 'input' folder.{Style.RESET_ALL}")
        input("\nPress Enter to return...")
        return []

    fmt = config["output_format"]
    quality = config.get("jpeg_quality", 95)
    ext = ".jpg" if fmt == "jpeg" else ".png"

    print(f"\n{Fore.GREEN}Found {len(files)} file(s). Converting to {fmt.upper()}...{Style.RESET_ALL}")

    stats = []
    pbar = tqdm(files, desc="Converting", unit="file",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                ncols=80, dynamic_ncols=True)

    for fp in pbar:
        try:
            orig_size = fp.stat().st_size
            with Image.open(fp) as img:
                img.load()
                img = sanitize_image(img)
                out_path = output_dir / (fp.stem + ext)
                if fmt == "jpeg":
                    img.save(out_path, "JPEG", quality=quality, optimize=True)
                else:
                    img.save(out_path, "PNG", optimize=False, compress_level=1)
            stats.append({
                'filename': fp.name,
                'original_size': orig_size,
                'converted_size': out_path.stat().st_size,
            })
            pbar.set_description(f" {fp.stem[:25]}{ext}")
        except Exception as e:
            tqdm.write(f"\n{Fore.RED}Error {fp.name}: {e}{Style.RESET_ALL}")

    return stats

def main():
    while True:
        print_header()
        config = choose_format()
        if config is None:
            print(f"\n{Fore.YELLOW}Exiting.{Style.RESET_ALL}")
            break
        stats = convert_files(config)
        if stats:
            print_summary(stats, config["output_format"], config.get("jpeg_quality"))
        print(f"\n{Fore.CYAN}Ready for next conversion.{Style.RESET_ALL}")
        input(f"\n{Back.BLUE}{Fore.WHITE} Press Enter to restart... {Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted.{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Error: {e}{Style.RESET_ALL}")