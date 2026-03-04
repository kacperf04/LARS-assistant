import logging
import os
import subprocess
import time

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class AndroidClient:
    """Context manager for handling ADB connections and commands."""
    def __init__(self):
        load_dotenv()
        self._ip = os.environ.get("PHONE_IP")
        self._debug_port = os.environ.get("PHONE_DEBUG_PORT")
        self._pin = os.environ.get("PHONE_PIN")
        if not all([self._ip, self._debug_port, self._pin]):
            raise ValueError("Missing required environment variables.")
        self._device_id = f"{self._ip}:{self._debug_port}"


    def __enter__(self):
        logger.info(f"Connecting to device {self._device_id}...")
        self._run_cmd(["adb", "connect", self._device_id], delay=1.0)
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info(f"Disconnecting from device {self._device_id}...")
        self._run_cmd(["adb", "disconnect", self._device_id])
        return False


    def _run_cmd(self, command: list[str], delay: float = 0.5) -> None:
        """Base execution method for subprocess."""
        try:
            subprocess.run(command, check=True)
            if delay > 0:
                time.sleep(delay)
        except subprocess.CalledProcessError as e:
            logger.error(f"ADB command failed: {e}")
            raise


    def shell(self, command: str, delay: float = 0.5) -> None:
        """Executes a shell command on the connected device."""
        cmd = ["adb", "-s", self._device_id, "shell"] + command.split()
        self._run_cmd(cmd, delay)


    def wake_and_unlock(self) -> None:
        """Sequence to wake the screen and input the PIN."""
        logger.info("Waking up phone...")
        self.shell("input keyevent 223", delay=1)
        self.shell("input keyevent 224", delay=0.5)
        self.shell("input swipe 500 2000 500 200 150", delay=0.5)
        self.shell(f"input text {self._pin}", delay=1)


    def launch_app(self, app_name: str) -> None:
        """Sequence to launch the Spotify app."""
        self.shell(f"monkey -p {app_name} -c android.intent.category.LAUNCHER 1", delay=2)
        self.shell("input keyevent 126", delay=3.0)
