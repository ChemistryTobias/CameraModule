import socket
import threading
import json
# import struct
import time
# import cv2
import numpy as np
import logging
import io
import os


class CameraException(Exception):
    def __init__(self, message):
        super().__init__(message)
    
class CameraDriver():
    def __init__(self, IP, CMD_PORT=8000, DATA_PORT=8001, STREAM_PORT=8002):
         # Socket configuration
        self.IP = IP
        self.CMD_PORT  = CMD_PORT
        self.DATA_PORT = DATA_PORT
        self.STREAM_PORT  = STREAM_PORT
        
        # Configure logging
        camera_identifier = "Camera"
        verbose = True
        if verbose: logging.basicConfig(level=logging.DEBUG, format=f"[{camera_identifier}]    %(message)s")
        elif not verbose: logging.basicConfig(level=logging.INFO, format=f"[{camera_identifier}]   %(message)s")
        self.logger = logging.getLogger(f"{camera_identifier}")
        
        # Initialize TCP socket connection to command port
        self.logger.debug(f"Connecting to camera server command port '{self.IP}:{self.CMD_PORT}'")
        self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cmd_socket.connect((self.IP, self.CMD_PORT))
        self.logger.info("Connected")
        

    def send(self, cmd: dict) -> dict:
        """Send a JSON command over TCP, wait for reply, and return the JSON response."""
        try:
            self.cmd_socket.sendall(json.dumps(cmd).encode("utf-8"))
            # self.cmd_socket.settimeout(100.0)
            raw = self.cmd_socket.recv(2048)
            response = json.loads(raw.decode("utf-8"))
        except Exception as e:
            response = {"status": "error", 
                        "details": {"error during sending or recieving a message": str(e)}}
        return response


    def _video_receiver_thread(self, file_name, file_path):
        """Runs in a daemon thread. Connects to self.IP:self.DATA_PORT,
        reads raw H.264 packets from the server until the socket closes,
        and writes everything to file_path/file_name.h264.
        """
        data_socket = None
        try:
            self.logger.debug(f"Connecting to camera data socket '{self.IP}:{self.DATA_PORT}'.")
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_socket.connect((self.IP, self.DATA_PORT))
            self.logger.debug("Connection established with DATA_PORT. Starting real-time video data transfer…")
            
            full_dir = os.path.abspath(file_path)
            os.makedirs(full_dir, exist_ok=True)
            full_path = os.path.join(full_dir, f"{file_name}.h264")
            
            with open(full_path, "wb") as f:
                while True:
                    packet = data_socket.recv(4096)
                    if not packet:
                        break
                    f.write(packet)

            self.logger.debug(f"Video stream complete; saved to '{full_path}'")

        except Exception as e:
            raise CameraException(f"Video stream failed. DETAILS: {e}")

        finally:
            if data_socket:
                try:
                    data_socket.close()
                except:
                    pass


    def template_action(self, test_int=0):
        cmd = {"action": "template_action", 
               "args": {"test_int": test_int}}
        response = self.send(cmd)
        if response["status"] == "warning": 
            self.logger.warning(f"WARNING: {response['details']['warning_message']}")
            return response
        elif response["status"] == "error": raise CameraException(response["details"]["error_message"])
        
        self.logger.debug(response)
        return response

    # ======= CAMERA METHODS ======= #

    def capture(self, file_name=None, file_path=".", file_format="jpeg", resolution=(4608, 2592), autofocus=True, focus_length=0.0):
        """Captures image with external camera (server) of specified format, resolution, and focus settings. Receive the raw image data over the data socket and save it to disk at the given path.

        Args:
            file_name (str, [default:`picam_<timestamp>`]): File identifier under which it will be saved to disk.
            file_path (str [default:`.`]): Relative or absolute file path, where the file will be saved to. Default is the driver directory.
            file_format (str [default:`jpeg`]):  Supported are the following file formats: `jpeg`, `png`, `bmp`, and `gif`.
            resolution (str [default:`(4608, 2592)`]): Height and width of the RGB array.
            autofocus (bool [default:`True`]): Triggers standard autofocus cycle of [PiCamera2 library](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf).<br>`True` = 'autofocus on', `False` = 'autofocus off'
            focus_length (float [default:`0.0`]): Lens position must only set manually, if before `autofocus=False`.<br>The minimum value for the lens position is most commonly `0.0` (meaning infinity). For the maximum, a value of `10.0` would indicate that the closest focal distance is 1 / 10 metres, or 10cm. Default values might often be around `0.5` to `1.0`, implying a hyperfocal distance of approximately 1m to 2m.
        
        Returns:
            response_dictionary (dict): DETAILS: `file_name`, `file_name` 
        """
        self.logger.debug("Send 'capture' command to camera server and wait for response")
        cmd = {"action": "capture", 
               "args": {"file_format": file_format, 
                        "resolution": resolution, 
                        "autofocus": autofocus, 
                        "focus_length": focus_length}}
        response = self.send(cmd)
        if response["status"] == "warning": 
            self.logger.warning(f"WARNING: {response['details']['warning_message']}")
            return response
        elif response["status"] == "error": raise CameraException(response["details"]["error_message"])
        
        try: 
            picture_data = bytearray()
            if file_name != None: response["details"]["file_name"] = f"{file_name}.{file_format}"
            file_name = response["details"].get("file_name")
            file_size = response["details"].get("file_size")
            
            self.logger.debug(f"Connecting to camera data socket '{self.IP}:{self.CMD_PORT}'")
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_socket.connect((self.IP, self.DATA_PORT))
            
            self.logger.debug(f"Connection established with the DATA_PORT. Starting transfer...")
            while len(picture_data) < file_size:
                packet = data_socket.recv(4096)
                if packet is None: raise BrokenPipeError()
                picture_data.extend(packet)
            data_socket.close()
            self.logger.debug(f"Transfer successfull, data socket closed")
            
            with open(os.path.join(file_path, file_name), 'wb') as f:
                f.write(picture_data)
                
        except Exception as e:
            raise CameraException(e)
    
        response["status"] = "Picture captured and saved to disk"
        self.logger.info(response["status"])
        return response


    def start_video(self, file_name, file_path=".", resolution=(1280, 720), duration=5):
        """Starts streaming H.264‐encoded video from the external camera (server) and writes the raw `.h264` data to disk at the given path.

        Args:
            file_name (str): Base name for the output file ('.h264' extension will be appended).
            file_path (str [default:`.`]): Relative or absolute directory where the file will be saved. Default is the driver directory.
            resolution (tuple [default:`(1280, 720)`]): Width and height of the video stream.
            duration (int [default:`5`]): Duration in seconds to record. If `None` or `0`, streaming continues until `stop_video` is called.
        
        Returns:
            response_dictionary (dict): DETAILS: `file_name`, `duration` 
        """
        self.logger.debug("Send 'start_video' command to camera server and wait for response")
        cmd = {"action": "start_video", 
               "args": {"resolution": resolution}}
        response = self.send(cmd)
        if response["status"] == "warning": 
            self.logger.warning(f"WARNING: {response['details']['warning_message']}")
            return response
        elif response["status"] == "error": raise CameraException(response["details"]["error_message"])
        
        try:
            receiver_thread = threading.Thread(target=self._video_receiver_thread, args=(file_name, file_path), daemon=True)
            receiver_thread.start()
            self._video_thread = receiver_thread 
            
            if duration in (None, 0):
                response["details"]["file_name"] = f"{file_name}.h264" 
                response["details"]["duration"] = "N/A"
                return response
            elif isinstance(duration, int) and (duration > 0):
                time.sleep(duration)
                response = self.stop_video()
                response["details"]["file_name"] = f"{file_name}.h264" 
                response["details"]["duration"] = duration
                return response
            else:
                raise TypeError(f"Unsupported duration argument '{duration}'. Expected POSITIVE INTEGER or NONE.")
        
        except Exception as e:
                raise CameraException(e)


    def stop_video(self):
        """Sends a 'stop_video' command to the camera server to end the active video stream.
        
        Returns:
            response_dictionary (dict):
        """
        cmd = {"action": "stop_video", "args": {}}
        response = self.send(cmd)
        if response["status"] == "warning": 
            self.logger.warning(f"WARNING: {response['details']['warning_message']}")
            return response
        elif response["status"] == "error": raise CameraException(response["details"]["error_message"])
        
        self.logger.debug(response["status"])
        return response

    def read_qrcode(self):
        raise NotImplementedError("'read_qrcode' method not fully implemented")
        """_missing docstring_"""
        cmd = {"action": "read_qrcode", "args": {}}
        response = self.send(cmd)
        if response["status"] == "warning": 
            self.logger.warning(f"WARNING: {response['details']['warning_message']}")
            return response
        elif response["status"] == "error": raise CameraException(response["details"]["error_message"])
        
        self.logger.debug(f"{response["status"]}: {response["datails"]["qr_str_tuple"]}")
        return response


    def read_barcode(self):
        raise NotImplementedError("'read_barcode' method not implemented")


    def start_stream(self, resolution = (1280, 720), IP_out = None):
        """Starts streaming H.264‐encoded video from the external camera (server) to UDP socket.

        Args:
            resolution (tuple [default:`(1280, 720)`]): Width and height of the video stream.
            IP_out (str | None): IP adress the UDP stream is directed to. Defaults to client adress.
            
        Returns:
            response_dictionary (dict): DETAILS: `url` 
        """
        self.logger.debug("Send 'start_stream' command to camera server and wait for response")
        cmd = {"action": "start_stream", 
               "args": {"resolution": resolution,
                        "IP_out": IP_out}}
        response = self.send(cmd)
        if response["status"] == "warning": 
            self.logger.warning(f"WARNING: {response['details']['warning_message']}")
            return response
        elif response["status"] == "error": raise CameraException(response["details"]["error_message"])
        
        if IP_out != None: IP_out = self.IP
        response["details"]["url"] = f"udp://{IP_out}:{self.STREAM_PORT}"
        
        self.logger.info(f"UPD video stream started. See using: \n`ffplay -f mpegts -probesize 32 {response["details"]["url"]}`")
        return response

    def stop_stream(self):
        """Sends a 'stop_video' command to the camera server to end the active video stream.
        
        Returns:
            response_dictionary (dict):
        """
        cmd = {"action": "stop_stream", "args": {}}
        response = self.send(cmd)
        if response["status"] == "warning": 
            self.logger.warning(f"WARNING: {response['details']['warning_message']}")
            return response
        elif response["status"] == "error": raise CameraException(response["details"]["error_message"])
        
        self.logger.debug(response["status"])
        return response