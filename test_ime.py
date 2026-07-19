import sys
import re
import random
import subprocess
import time
import requests

# Try to import pyautogui, flag if not installed
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# API Configuration
API_URL = "https://9router1.blackcatofficial.qzz.io/v1"
API_KEY = "sk-5ecc2c9f74870499-e0jma6-5e255271"
DEFAULT_MODEL = "mimo-code-free-auto-switcher"

# Full decomposition map of Vietnamese accented characters to (base, modifier, tone)
CHAR_MAP = {
    # Lowercase
    'á': ('a', '', 'sắc'), 'à': ('a', '', 'huyền'), 'ả': ('a', '', 'hỏi'), 'ã': ('a', '', 'ngã'), 'ạ': ('a', '', 'nặng'),
    'ă': ('a', 'breve', ''), 'ắ': ('a', 'breve', 'sắc'), 'ằ': ('a', 'breve', 'huyền'), 'ẳ': ('a', 'breve', 'hỏi'), 'ẵ': ('a', 'breve', 'ngã'), 'ặ': ('a', 'breve', 'nặng'),
    'â': ('a', 'hat', ''), 'ấ': ('a', 'hat', 'sắc'), 'ầ': ('a', 'hat', 'huyền'), 'ẩ': ('a', 'hat', 'hỏi'), 'ẫ': ('a', 'hat', 'ngã'), 'ậ': ('a', 'hat', 'nặng'),
    'é': ('e', '', 'sắc'), 'è': ('e', '', 'huyền'), 'ẻ': ('e', '', 'hỏi'), 'ẽ': ('e', '', 'ngã'), 'ẹ': ('e', '', 'nặng'),
    'ê': ('e', 'hat', ''), 'ế': ('e', 'hat', 'sắc'), 'ề': ('e', 'hat', 'huyền'), 'ể': ('e', 'hat', 'hỏi'), 'ễ': ('e', 'hat', 'ngã'), 'ệ': ('e', 'hat', 'nặng'),
    'í': ('i', '', 'sắc'), 'ì': ('i', '', 'huyền'), 'ỉ': ('i', '', 'hỏi'), 'ĩ': ('i', '', 'ngã'), 'ị': ('i', '', 'nặng'),
    'ó': ('o', '', 'sắc'), 'ò': ('o', '', 'huyền'), 'ỏ': ('o', '', 'hỏi'), 'õ': ('o', '', 'ngã'), 'ọ': ('o', '', 'nặng'),
    'ô': ('o', 'hat', ''), 'ố': ('o', 'hat', 'sắc'), 'ồ': ('o', 'hat', 'huyền'), 'ổ': ('o', 'hat', 'hỏi'), 'ỗ': ('o', 'hat', 'ngã'), 'ộ': ('o', 'hat', 'nặng'),
    'ơ': ('o', 'horn', ''), 'ớ': ('o', 'horn', 'sắc'), 'ờ': ('o', 'horn', 'huyền'), 'ở': ('o', 'horn', 'hỏi'), 'ỡ': ('o', 'horn', 'ngã'), 'ợ': ('o', 'horn', 'nặng'),
    'ú': ('u', '', 'sắc'), 'ù': ('u', '', 'huyền'), 'ủ': ('u', '', 'ngã'), 'ụ': ('u', '', 'nặng'),
    'ư': ('u', 'horn', ''), 'ứ': ('u', 'horn', 'sắc'), 'ừ': ('u', 'horn', 'huyền'), 'ử': ('u', 'horn', 'hỏi'), 'ữ': ('u', 'horn', 'ngã'), 'ự': ('u', 'horn', 'nặng'),
    'ý': ('y', '', 'sắc'), 'ỳ': ('y', '', 'huyền'), 'ỷ': ('y', '', 'hỏi'), 'ỹ': ('y', '', 'ngã'), 'ỵ': ('y', '', 'nặng'),
    'đ': ('d', 'đ', ''),
    # Uppercase
    'Á': ('A', '', 'sắc'), 'À': ('A', '', 'huyền'), 'Ả': ('A', '', 'hỏi'), 'Ã': ('A', '', 'ngã'), 'Ạ': ('A', '', 'nặng'),
    'Ă': ('A', 'breve', ''), 'Ắ': ('A', 'breve', 'sắc'), 'Ằ': ('A', 'breve', 'huyền'), 'Ẳ': ('A', 'breve', 'hỏi'), 'Ẵ': ('A', 'breve', 'ngã'), 'Ặ': ('A', 'breve', 'nặng'),
    'Â': ('A', 'hat', ''), 'Ấ': ('A', 'hat', 'sắc'), 'Ầ': ('A', 'hat', 'huyền'), 'Ẩ': ('A', 'hat', 'hỏi'), 'Ẫ': ('A', 'hat', 'ngã'), 'Ậ': ('A', 'hat', 'nặng'),
    'É': ('E', '', 'sắc'), 'È': ('E', '', 'huyền'), 'Ẻ': ('E', '', 'hỏi'), 'Ẽ': ('E', '', 'ngã'), 'Ẹ': ('E', '', 'nặng'),
    'Ê': ('E', 'hat', ''), 'Ế': ('E', 'hat', 'sắc'), 'Ề': ('E', 'hat', 'huyền'), 'Ể': ('E', 'hat', 'hỏi'), 'Ễ': ('E', 'hat', 'ngã'), 'Ệ': ('E', 'hat', 'nặng'),
    'Í': ('I', '', 'sắc'), 'Ì': ('I', '', 'huyền'), 'Ỉ': ('I', '', 'hỏi'), 'Ĩ': ('I', '', 'ngã'), 'Ị': ('I', '', 'nặng'),
    'Ó': ('O', '', 'sắc'), 'Ò': ('O', '', 'huyền'), 'Ỏ': ('O', '', 'hỏi'), 'Õ': ('O', '', 'ngã'), 'Ọ': ('O', '', 'nặng'),
    'Ô': ('O', 'hat', ''), 'Ố': ('O', 'hat', 'sắc'), 'Ồ': ('O', 'hat', 'huyền'), 'Ổ': ('O', 'hat', 'hỏi'), 'Ỗ': ('O', 'hat', 'ngã'), 'Ộ': ('O', 'hat', 'nặng'),
    'Ơ': ('O', 'horn', ''), 'Ớ': ('O', 'horn', 'sắc'), 'Ờ': ('O', 'horn', 'huyền'), 'Ở': ('O', 'horn', 'hỏi'), 'Ỡ': ('O', 'horn', 'ngã'), 'Ợ': ('O', 'horn', 'nặng'),
    'Ú': ('U', '', 'sắc'), 'Ù': ('U', '', 'huyền'), 'Ủ': ('U', '', 'ngã'), 'Ụ': ('U', '', 'nặng'),
    'Ư': ('U', 'horn', ''), 'Ứ': ('U', 'horn', 'sắc'), 'Ừ': ('U', 'horn', 'huyền'), 'Ử': ('U', 'horn', 'hỏi'), 'Ữ': ('U', 'horn', 'ngã'), 'Ự': ('U', 'horn', 'nặng'),
    'Ý': ('Y', '', 'sắc'), 'Ỳ': ('Y', '', 'huyền'), 'Ỷ': ('Y', '', 'hỏi'), 'Ỹ': ('Y', '', 'ngã'), 'Ỵ': ('Y', '', 'nặng'),
    'Đ': ('D', 'đ', ''),
}

# Mapping of tones for each mode
TONE_MAP = {
    'Telex': {'sắc': 's', 'huyền': 'f', 'hỏi': 'r', 'ngã': 'x', 'nặng': 'j'},
    'VNI': {'sắc': '1', 'huyền': '2', 'hỏi': '3', 'ngã': '4', 'nặng': '5'},
    'VIQR': {'sắc': "'", 'huyền': '`', 'hỏi': '?', 'ngã': '~', 'nặng': '.'},
    'Microslop VI Layout': {'sắc': '8', 'huyền': '5', 'hỏi': '6', 'ngã': '7', 'nặng': '9'},
    'Simple Telex': {'sắc': "'", 'huyền': '`', 'hỏi': '?', 'ngã': '~', 'nặng': '.'},
    'Simple Telex 2': {'sắc': "'", 'huyền': '`', 'hỏi': '?', 'ngã': '~', 'nặng': '.'},
    'Telex + VNI': {'sắc': '1', 'huyền': '2', 'hỏi': '3', 'ngã': '4', 'nặng': '5'},
}

def copy_to_clipboard(text):
    """Cross-platform clipboard copying without external packages."""
    try:
        if sys.platform == 'win32':
            subprocess.run(['clip'], input=text.encode('utf-16'), check=True)
        elif sys.platform == 'darwin':
            subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
        else:
            subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)
        return True
    except Exception:
        return False

def get_random_vietnamese_paragraph():
    """Fetches a custom paragraph from the specified API with local fail-safes."""
    print("\n[~] Connecting to the LLM API to generate a paragraph...")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        "Hãy viết một đoạn văn tiếng Việt ngắn (khoảng 3-4 câu, khoảng 50-70 từ) "
        "về cuộc sống thường ngày, công nghệ hoặc thiên nhiên. Đoạn văn cần có "
        "đầy đủ các dấu thanh tiếng Việt (sắc, huyền, hỏi, ngã, nặng) và các nguyên âm đặc biệt "
        "(â, ă, ê, ô, ơ, ư, đ) để thử nghiệm bộ gõ tiếng Việt IME. Chỉ trả về đúng đoạn văn đó, "
        "không thêm bất kỳ lời dẫn giải nào."
    )
    
    data = {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(f"{API_URL}/chat/completions", headers=headers, json=data, timeout=8)
        response.raise_for_status()
        result = response.json()
        paragraph = result["choices"][0]["message"]["content"].strip()
        print("[+] Generation successful.")
        return paragraph
    except Exception as e:
        print(f"[-] API call failed or timed out: {e}")
        print("[!] Using local fallback paragraph instead to avoid blocking tests...")
        fallback_paragraphs = [
            "Hôm nay trời rất đẹp, nắng ấm áp lan tỏa khắp nẻo đường của thành phố Đà Nẵng. "
            "Tôi thích ngồi ở một quán cà phê vỉa hè để ngắm dòng người qua lại, nhâm nhi tách cà phê sữa đá đậm đà. "
            "Cuộc sống trôi qua thật bình yên và nhẹ nhàng, mang lại cảm giác dễ chịu sau những ngày làm việc vất vả.",
            
            "Công nghệ thông tin đang ngày càng phát triển mạnh mẽ và thay đổi cuộc sống của chúng ta từng giờ. "
            "Các lập trình viên luôn nỗ lực không ngừng để tạo ra những sản phẩm phần mềm chất lượng cao, phục vụ cộng đồng. "
            "Việc tối ưu hóa công cụ gõ tiếng Việt là bước đi quan trọng giúp nâng cao trải nghiệm người dùng trong nước.",
            
            "Rừng vàng biển bạc là những món quà tuyệt vời mà thiên nhiên đã ban tặng cho đất nước Việt Nam. "
            "Chúng ta cần chung tay bảo vệ môi trường, hạn chế rác thải nhựa để giữ gìn màu xanh tươi đẹp này. "
            "Mỗi hành động nhỏ hôm nay đều góp phần mang lại tương lai tươi sáng và bền vững cho thế hệ mai sau."
        ]
        return random.choice(fallback_paragraphs)

def decompose_word(word):
    """Decomposes a word into base letters, modifiers, and word tone."""
    base_chars = []
    modifiers = []
    word_tone = ''
    for char in word:
        if char in CHAR_MAP:
            base, mod, tone = CHAR_MAP[char]
            base_chars.append(base)
            modifiers.append(mod)
            if tone:
                word_tone = tone
        else:
            base_chars.append(char)
            modifiers.append('')
    return base_chars, modifiers, word_tone

def convert_word(word, method):
    """Converts a single word into the chosen layout's key sequences."""
    base_chars, modifiers, tone = decompose_word(word)
    result = []
    
    for i, (base, mod) in enumerate(zip(base_chars, modifiers)):
        orig_char = word[i]
        is_upper = orig_char.isupper()
        
        if method == 'Telex':
            if mod == 'hat':
                result.append(base + base.lower())
            elif mod in ('breve', 'horn'):
                result.append(base + ('W' if is_upper else 'w'))
            elif mod == 'đ':
                result.append(base + ('D' if is_upper else 'd'))
            else:
                result.append(base)
                
        elif method == 'VNI':
            if mod == 'hat':
                result.append(base + '6')
            elif mod == 'breve':
                result.append(base + '8')
            elif mod == 'horn':
                result.append(base + '7')
            elif mod == 'đ':
                result.append(base + '9')
            else:
                result.append(base)
                
        elif method == 'VIQR':
            if mod == 'hat':
                result.append(base + '^')
            elif mod == 'breve':
                result.append(base + '(')
            elif mod == 'horn':
                result.append(base + '+')
            elif mod == 'đ':
                result.append(base + ('D' if is_upper else 'd'))
            else:
                result.append(base)
                
        elif method == 'Microslop VI Layout':
            if mod == 'hat':
                if base.lower() == 'a': result.append('2')
                elif base.lower() == 'e': result.append('3')
                elif base.lower() == 'o': result.append('4')
                else: result.append(base)
            elif mod == 'breve':
                if base.lower() == 'a': result.append('1')
                else: result.append(base)
            elif mod == 'horn':
                if base.lower() == 'u': result.append('[')
                elif base.lower() == 'o': result.append(']')
                else: result.append(base)
            elif mod == 'đ':
                result.append('0')
            else:
                result.append(base)
                
        elif method == 'Simple Telex':
            if mod == 'hat':
                result.append(base + base.lower())
            elif mod in ('breve', 'horn'):
                result.append(base + ('W' if is_upper else 'w'))
            elif mod == 'đ':
                result.append(base + ('D' if is_upper else 'd'))
            else:
                result.append(base)
                
        elif method == 'Simple Telex 2':
            if mod == 'hat':
                result.append(base + base.lower())
            elif mod == 'breve':
                result.append(base + ('W' if is_upper else 'w'))
            elif mod == 'horn':
                if base.lower() == 'u':
                    if i == 0:
                        result.append(base + ('W' if is_upper else 'w'))
                    else:
                        result.append('W' if is_upper else 'w')
                else:
                    result.append(base + ('W' if is_upper else 'w'))
            elif mod == 'đ':
                result.append(base + ('D' if is_upper else 'd'))
            else:
                result.append(base)
                
        elif method == 'Telex + VNI':
            if mod == 'hat':
                result.append(base + base.lower())
            elif mod in ('breve', 'horn'):
                result.append(base + ('W' if is_upper else 'w'))
            elif mod == 'đ':
                result.append(base + ('D' if is_upper else 'd'))
            else:
                result.append(base)
                
    word_str = ''.join(result)
    if tone in TONE_MAP[method]:
        word_str += TONE_MAP[method][tone]
    return word_str

def convert_paragraph(paragraph, method):
    """Tokenizes word boundaries and processes conversion, keeping whitespace and punctuation intact."""
    vietnamese_letters = r"[a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ]"
    tokens = re.split(f"({vietnamese_letters}+)", paragraph)
    converted_tokens = []
    for token in tokens:
        if re.match(f"^{vietnamese_letters}+$", token):
            converted_tokens.append(convert_word(token, method))
        else:
            converted_tokens.append(token)
    return ''.join(converted_tokens)

def auto_type_layout(text, interval=0.05):
    """Performs the simulated automated keystroke injection with safety fail-safes."""
    if not PYAUTOGUI_AVAILABLE:
        print("\n[-] pyautogui is not installed. Run 'pip install pyautogui' to enable this feature.")
        return

    print("\n[!] WARNING: PyAutoGUI will simulate hardware keyboard inputs directly.")
    print("    Make sure your target text input is active and your IME is set to the correct mode.")
    print("    (Fail-safe: Move your mouse cursor to any of the 4 corners of the screen to abort anytime.)")
    print("    You have 5 seconds to switch focus to your text editor (e.g., Notepad, VS Code)...")
    
    for i in range(5, 0, -1):
        print(f"    Starting in {i}...", end="\r", flush=True)
        time.sleep(1)
        
    print("    TYPING NOW! Keep your hands off the keyboard and mouse.")
    
    # Active fail-safe triggerable by slamming mouse to screen corners
    pyautogui.FAILSAFE = True
    
    # Simulates sequence typing with short pauses between keys so the IME can process state correctly
    pyautogui.write(text, interval=interval)
    print("\n[+] Done typing.")

def main():
    print("=" * 60)
    print("      VIETNAMESE IME TEST CASE GENERATION UTILITY")
    print("=" * 60)
    
    if not PYAUTOGUI_AVAILABLE:
        print("[!] Note: 'pyautogui' is not installed. Automated typing feature is disabled.")
        print("    To enable, install via command line: pip install pyautogui")
    else:
        print("[+] 'pyautogui' module successfully detected. Keystroke testing is enabled.")
    
    current_paragraph = get_random_vietnamese_paragraph()
    methods = ['Telex', 'VNI', 'VIQR', 'Microslop VI Layout', 'Simple Telex', 'Simple Telex 2', 'Telex + VNI']
    
    while True:
        conversions = {m: convert_paragraph(current_paragraph, m) for m in methods}
        
        print("\n" + "=" * 80)
        print(f"ORIGINAL TEXT: {current_paragraph}")
        print("=" * 80)
        for idx, method in enumerate(methods, 1):
            print(f" [{idx}] {method:<22}: {conversions[method]}")
        print("-" * 80)
        
        print("\nOPTIONS:")
        print(" [R] Generate another random paragraph (API)")
        print(" [C] Input custom Vietnamese text")
        print(" [Y] Copy specific layout to clipboard")
        print(" [T] Auto-type a layout (using PyAutoGUI)")
        print(" [S] Save all outputs to a text file")
        print(" [Q] Exit")
        
        choice = input("\nSelect an option: ").strip().lower()
        
        if choice == 'r':
            current_paragraph = get_random_vietnamese_paragraph()
        elif choice == 'c':
            custom = input("Enter your custom Vietnamese text: ").strip()
            if custom:
                current_paragraph = custom
        elif choice == 's':
            filename = "ime_test_outputs.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"Original Text: {current_paragraph}\n\n")
                for method, result in conversions.items():
                    f.write(f"[{method}]\n{result}\n\n")
            print(f"\n[+] Saved successfully to: {filename}")
        elif choice == 'y':
            try:
                selected_idx = int(input(f"Enter layout index to copy (1-{len(methods)}): ")) - 1
                if 0 <= selected_idx < len(methods):
                    method_name = methods[selected_idx]
                    if copy_to_clipboard(conversions[method_name]):
                        print(f"\n[+] Copied '{method_name}' keystrokes to clipboard.")
                    else:
                        print("\n[-] Clipboard copy failed.")
                else:
                    print("[-] Invalid selection.")
            except ValueError:
                print("[-] Invalid input.")
        elif choice == 't':
            if not PYAUTOGUI_AVAILABLE:
                print("\n[-] Please install pyautogui to use this feature: pip install pyautogui")
                continue
            try:
                selected_idx = int(input(f"Enter layout index to auto-type (1-{len(methods)}): ")) - 1
                if 0 <= selected_idx < len(methods):
                    method_name = methods[selected_idx]
                    
                    # Ask the user for typing speed interval to accommodate IME buffers
                    interval_input = input("Enter typing delay per key in seconds (Default 0.05): ").strip()
                    interval = float(interval_input) if interval_input else 0.05
                    
                    auto_type_layout(conversions[method_name], interval=interval)
                else:
                    print("[-] Invalid selection.")
            except ValueError:
                print("[-] Invalid input.")
        elif choice == 'q':
            print("\nExiting utility.")
            break
        else:
            print("[-] Option unrecognized.")

if __name__ == "__main__":
    main()