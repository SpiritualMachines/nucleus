import os

SETTINGS_FILE = os.path.join("theme", "settings.txt")


class Settings:
    def __init__(self):
        self.APP_NAME = "Nucleus Daemon"
        self.APP_VERSION = "v0.0.0"
        self.HACKSPACE_NAME = "Hackspace"
        self.TAG_NAME = "Makerspace"
        self.ASCII_LOGO = ""
        self._load()

    def _load(self):
        if not os.path.exists(SETTINGS_FILE):
            return

        with open(SETTINGS_FILE, "r") as f:
            lines = f.readlines()

        reading_logo = False
        logo_lines = []

        for line in lines:
            line = line.rstrip()

            if line == "ASCII_LOGO_START":
                reading_logo = True
                continue
            if line == "ASCII_LOGO_END":
                reading_logo = False
                continue

            if reading_logo:
                logo_lines.append(line)
            else:
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key == "APP_NAME":
                        self.APP_NAME = value
                    elif key == "APP_VERSION":
                        self.APP_VERSION = value
                    elif key == "HACKSPACE_NAME":
                        self.HACKSPACE_NAME = value
                    elif key == "TAG_NAME":
                        self.TAG_NAME = value

        self.ASCII_LOGO = "\n".join(logo_lines)


# Singleton instance
settings = Settings()
