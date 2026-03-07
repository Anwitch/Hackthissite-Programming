"""
HackThisSite Programming Level 8 Solver
IRC bot that connects to irc.hackthissite.org and completes the challenge.

Pipeline:
 1. Connect to IRC, identify with NickServ (registered nick with autoop on)
 2. NOTICE moo with !perm8
 3. moo NOTICEs back with !md5 <string> → reply with !perm8-result <md5hash>
 4. moo sends CTCP VERSION → reply with version string (NOT mIRC)
 5. moo NOTICEs with !perm8-attack → join #takeoverz and kick moo

Prerequisites:
 - Register your IRC nick on irc.hackthissite.org:
     /msg NickServ REGISTER <password> <email>
 - Enable autoop:
     /ns set autoop on
 - Link your IRC nick to your HTS account in #perm8:
     !link AndrieUntan
"""

import os
import socket
import ssl
import hashlib
import time
import re
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ─── Configuration ──────────────────────────────────────────────
IRC_SERVER = "irc.hackthissite.org"
IRC_PORT = 6697  # SSL port; use 6667 for non-SSL
USE_SSL = True

# Your registered IRC nickname and NickServ password
IRC_NICK = os.getenv("IRC_NICK", "AndrieUntan")
IRC_NICKSERV_PASS = os.getenv("IRC_NICKSERV_PASS", "")  # NickServ password (set in .env)

# Bot version reply (must NOT be mIRC)
BOT_VERSION = "HTS-Bot 1.0 (Python)"

# ─── IRC helpers ────────────────────────────────────────────────
class IRCBot:
    def __init__(self):
        self.sock = None
        self.buffer = ""

    def connect(self):
        """Connect to the IRC server (with optional SSL)."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(300)

        if USE_SSL:
            ctx = ssl.create_default_context()
            # Some IRC servers have self-signed certs
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self.sock = ctx.wrap_socket(raw_sock, server_hostname=IRC_SERVER)
        else:
            self.sock = raw_sock

        print(f"[*] Connecting to {IRC_SERVER}:{IRC_PORT} (SSL={USE_SSL})...")
        self.sock.connect((IRC_SERVER, IRC_PORT))
        print("[*] Connected!")

    def send_raw(self, msg):
        """Send a raw IRC line."""
        line = msg + "\r\n"
        self.sock.sendall(line.encode("utf-8"))
        print(f">>> {msg}")

    def send_nick(self, nick):
        self.send_raw(f"NICK {nick}")

    def send_user(self, username, realname):
        self.send_raw(f"USER {username} 0 * :{realname}")

    def send_privmsg(self, target, message):
        self.send_raw(f"PRIVMSG {target} :{message}")

    def send_notice(self, target, message):
        self.send_raw(f"NOTICE {target} :{message}")

    def send_join(self, channel):
        self.send_raw(f"JOIN {channel}")

    def send_kick(self, channel, nick, reason="Bye!"):
        self.send_raw(f"KICK {channel} {nick} :{reason}")

    def send_pong(self, payload):
        self.send_raw(f"PONG :{payload}")

    def send_ctcp_reply(self, target, tag, value):
        """Send a CTCP reply via NOTICE."""
        self.send_notice(target, f"\x01{tag} {value}\x01")

    def identify(self, password):
        """Identify with NickServ."""
        self.send_privmsg("NickServ", f"IDENTIFY {password}")

    def recv_lines(self):
        """Receive data and yield complete IRC lines."""
        try:
            data = self.sock.recv(4096)
        except socket.timeout:
            return
        if not data:
            raise ConnectionError("Connection closed by server")

        self.buffer += data.decode("utf-8", errors="replace")
        while "\r\n" in self.buffer:
            line, self.buffer = self.buffer.split("\r\n", 1)
            yield line

    def run(self):
        """Main event loop."""
        self.connect()

        # Register with the server
        self.send_nick(IRC_NICK)
        self.send_user(IRC_NICK, "HTS Programming 8 Bot")

        identified = False
        perm8_sent = False
        challenge_done = False

        while True:
            for line in self.recv_lines():
                print(f"<<< {line}")
                self.handle_line(
                    line,
                    state={
                        "identified": identified,
                        "perm8_sent": perm8_sent,
                        "challenge_done": challenge_done,
                    },
                )

                # ── PING / PONG ──
                if line.startswith("PING"):
                    payload = line.split(":", 1)[1] if ":" in line else line.split(" ", 1)[1]
                    self.send_pong(payload)

                # ── After MOTD (end of welcome), identify and start challenge ──
                # RPL_ENDOFMOTD = 376, ERR_NOMOTD = 422
                if " 376 " in line or " 422 " in line:
                    if not identified:
                        print("[*] End of MOTD, identifying with NickServ...")
                        self.identify(IRC_NICKSERV_PASS)
                        identified = True
                        # Wait a moment for identification to process
                        time.sleep(3)
                        print("[*] Sending !perm8 to moo...")
                        self.send_notice("moo", "!perm8")
                        perm8_sent = True

    def handle_line(self, line, state):
        """Handle a single IRC line for challenge-specific logic."""
        # Parse the line: :source COMMAND params :trailing
        # ── Handle NOTICE from moo ──
        # Format: :moo!user@host NOTICE <yournick> :!md5 <string>
        #     or: :moo!user@host NOTICE <yournick> :!perm8-attack
        notice_match = re.match(
            r":(\S+?)!\S+\s+NOTICE\s+\S+\s+:(.*)", line, re.IGNORECASE
        )
        if notice_match:
            sender_nick = notice_match.group(1)
            message = notice_match.group(2).strip()

            if sender_nick.lower() == "moo":
                # ── !md5 challenge ──
                if message.startswith("!md5 "):
                    random_string = message[5:]
                    md5_hash = hashlib.md5(random_string.encode("utf-8")).hexdigest()
                    print(f"[*] MD5 challenge: '{random_string}' -> {md5_hash}")
                    self.send_notice("moo", f"!perm8-result {md5_hash}")

                # ── !perm8-attack ──
                elif message.strip() == "!perm8-attack":
                    print("[!] Attack command received! Joining #takeoverz...")
                    self.send_join("#takeoverz")
                    # Small delay to ensure we're in channel and have ops
                    time.sleep(0.5)
                    self.send_kick("#takeoverz", "moo", "!perm8")
                    print("[*] Kicked moo from #takeoverz!")

        # ── Handle CTCP VERSION request ──
        # Format: :source PRIVMSG <yournick> :\x01VERSION\x01
        ctcp_match = re.match(
            r":(\S+?)!\S+\s+PRIVMSG\s+\S+\s+:\x01VERSION\x01", line
        )
        if ctcp_match:
            sender_nick = ctcp_match.group(1)
            print(f"[*] CTCP VERSION request from {sender_nick}")
            self.send_ctcp_reply(sender_nick, "VERSION", BOT_VERSION)

        # ── Handle being kicked (rejoin) ──
        kick_match = re.match(
            r":\S+\s+KICK\s+(#\S+)\s+(\S+)", line
        )
        if kick_match:
            channel = kick_match.group(1)
            kicked_nick = kick_match.group(2)
            if kicked_nick.lower() == IRC_NICK.lower():
                print(f"[!] We were kicked from {channel}, rejoining...")
                time.sleep(0.5)
                self.send_join(channel)


# ─── Entry point ────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  HackThisSite Programming Level 8 - IRC Bot Solver")
    print("=" * 60)
    print()
    print("PREREQUISITES (do these manually first):")
    print("  1. Connect to irc.hackthissite.org with an IRC client")
    print("  2. Register your nick:")
    print("       /msg NickServ REGISTER <password> <email>")
    print("  3. Enable autoop:")
    print("       /ns set autoop on")
    print("  4. Go to #perm8 and link your HTS account:")
    print("       !link AndrieUntan")
    print("  5. Update IRC_NICKSERV_PASS in this script")
    print()

    if IRC_NICKSERV_PASS == "YOUR_NICKSERV_PASSWORD_HERE":
        print("[!] ERROR: You must set IRC_NICKSERV_PASS first!")
        print("    Edit this script and replace YOUR_NICKSERV_PASSWORD_HERE")
        print("    with your NickServ registration password.")
        return

    bot = IRCBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n[*] Bot stopped by user.")
    except Exception as e:
        print(f"\n[!] Error: {e}")
    finally:
        if bot.sock:
            try:
                bot.send_raw("QUIT :Bye!")
            except Exception:
                pass
            bot.sock.close()


if __name__ == "__main__":
    main()
