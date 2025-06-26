#===============================================================================
# Server configuration
#===============================================================================
CMD_PORT    = 8000      # TCP port for control commands
DATA_PORT   = 8001      # TCP port for file transfers
STREAM_PORT = 8002      # (unused here, reserved for future streaming)
#===============================================================================

import socket
import threading
import json
import io
import picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput, PyavOutput
from libcamera import controls
# from qreader import QReader
import time

class CameraServer:
    def __init__(self, cmd_port: int, data_port: int, STREAM_PORT: int):
        # Socket configuration
        self.CMD_PORT  = cmd_port
        self.DATA_PORT = data_port
        self.STREAM_PORT  = STREAM_PORT
        # Listening server TCP socket for control messages 
        self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cmd_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.cmd_socket.bind(("", self.CMD_PORT))
        self.cmd_socket.listen(5)
        print(f"[Server] Command server listening on port {self.CMD_PORT}")
        # Listening server TCP socket for file transfer
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.data_socket.bind(("", self.DATA_PORT))
        self.data_socket.listen(5)

    def start(self):
        """Initialize Picamera and start accepting control‐connection requests."""
        self.camera = picamera2.Picamera2()
        try:
            while True:
                self.conn, self.addr = self.cmd_socket.accept()
                thread = threading.Thread(target=self.handle_client, daemon=True)
                thread.start()
        except KeyboardInterrupt:
            print("\n[Server] Shutting down...")
        finally:
            self.camera.close()
            self.cmd_socket.close()


    def handle_client(self):
        """Handles a JSON‐encoded command from the cmd_socket.
        1. Read a JSON command from the client.
        2. Dispatch to the appropriate action method.
        3. Send back a JSON‐encoded response.
        """
        client_ip, _ = self.addr
        print(f"[Server] Connected from {client_ip}")

        try:
            while True:
                raw = self.conn.recv(2048)
                if not raw:
                    # Client closed the connection
                    break

                try:
                    cmd_obj = json.loads(raw.decode("utf‐8"))
                except json.JSONDecodeError:
                    raise TypeError("Invalid JSON command.")

                action = cmd_obj.get("action")
                args   = cmd_obj.get("args")

                if action == "template_action":
                    self.template_action(**args)

                elif action == "capture":
                    self.capture(**args)
                    
                elif action == "start_video":
                    self.start_video(**args)
                    
                elif action == "stop_video":
                    warn_reply = {"status": "warning", "details": {"warning_message": "Command 'stop_video' can only be excecuted, if 'start_video' was called before."}}
                    self.conn.sendall(json.dumps(warn_reply).encode("utf‐8"))
                    
                elif action == "read_barcode":
                    self.read_barcode(**args)
                    
                elif action == "read_qrcode":
                    self.read_qrcode(**args)
                    
                elif action == "start_stream":
                    self.start_stream(**args)

                elif action == "stop_stream":
                    warn_reply = {"status": "warning", "details": {"warning_message": "Command 'stop_stream' can only be excecuted, if 'start_start' was called before."}}
                    self.conn.sendall(json.dumps(warn_reply).encode("utf‐8"))

                else:
                    raise ValueError(f"Unknown action '{action}'.")

        except Exception as e:
            err = {"status": "error",
                   "details": {"error_message": str(e)}}
            try:
                self.conn.sendall(json.dumps(err).encode("utf‐8"))
            except:
                pass

        finally:
            self.conn.close()
            print(f"[Server] Connection with {client_ip} closed.")

    # ======= CAMERA METHODS ======= #

    def template_action(self, test_int):
        cmd_reply = {"status": "template_action executed",
                 "details": {"test_int": test_int}}
        self.conn.sendall(json.dumps(cmd_reply).encode("utf‐8"))
        

    def capture(self, file_format, resolution, autofocus, focus_length):
        """Capture a single still image and transferrs the raw data to the client via data socket.
        
        Args:
            file_format (str): Supported are the following file formats: `jpeg`, `png`, `bmp`, and `gif`.
            resolution (tuple): Width and height integer duple. Example: `(1280, 720)`
            autofocus (bool): Triggers standard autofocus cycle of Picamera2. (`True`: 'autofocus on', `False`: 'autofocus off')
            focus_length (float): Lens position must only set manually, if before `autofocus=False`. Value range between `0.0`-`10.0`. See Picamera2 manual for more information.
            
        Returns:
            status_dictonary (dict): `details` key provides information regarding `file_name`, `file_size`
        """
        # configure camera resolution
        print("[Server] configure camera resolution")
        try:
            width, height = resolution
        except: 
            raise TypeError(f"Unsupported resolution argument '{resolution}'. Expected integer TUPLE of format (width, height).")
        if not isinstance(width, int) or not (0 <= width <= 4608): 
            raise ValueError(f"Invalid WIDTH resolution value '{width}'. Expected INTEGER: 0<=WIDTH<=4608.")
        if not isinstance(height, int) or not (0 <= height <= 2592): 
            raise ValueError(f"Invalid HEIGHT resolution value '{width}'. Expected INTEGER: 0<=HEIGHT<=2592.")
        
        self.camera.still_configuration.main.size = (width, height)
        self.camera.configure("still")
        
        # handle camera focus
        print("[Server] handle camera focus")
        self.camera.start()
        time.sleep(0.2)
        
        if autofocus == True:
            self.camera.set_controls({"AfMode": controls.AfModeEnum.Continuous})
            autofocus_success = self.camera.autofocus_cycle()
            if not autofocus_success:
                raise RuntimeError("Autofocus cycle failed.")

        elif autofocus == False:
            if not isinstance(focus_length, float) or not (0.0 <= focus_length <= 10.0): 
                raise ValueError(f"Invalid '{width}'. Expected .")
            self.camera.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": focus_length})
            
        else:
            raise ValueError(f"Invalid autofocus argument '{autofocus}'. Expected BOOLEAN.")
        
        # capture file
        print("[Server] capture file")
        fmt = file_format.lower()
        if fmt not in ("jpeg", "png", "bmp", "gif"): 
            raise TypeError(f"Unsupported file format '{file_format}'. Only 'jpeg', 'png', 'bmp', and 'gif' are available.")   
        file_name = time.strftime(f"picam_%Y%m%d_%H%M%S.{fmt}")
        picture_data = io.BytesIO()
        
        self.camera.capture_file(picture_data, format=fmt)
        file_size = len(picture_data.getvalue())

        # camera shut-down and return of success dictionary
        print("[Server] camera shut-down and return of success dictionary")
        self.camera.stop()
        cmd_reply = {"status": "picture captured, starting transfer...",
                     "details": {"file_name": file_name,
                                 "file_size": file_size}}
        self.conn.sendall(json.dumps(cmd_reply).encode("utf‐8"))
        
        # send file via data socket
        print(f"[Server] send file via data socket")
        data_connection, _ = self.data_socket.accept()
        print("[Server] data port connected")
        data_connection.sendall(picture_data.getvalue())
        print("[Server] file was sent")


    def start_video(self, resolution=(1280, 720)):
        """Start streaming H.264‐encoded video over the data socket. The stream continues until the server recives the `stop_video` command.

        Args:
            resolution (tuple): Width and height of the video recording. Example: `(1280, 720)`
        """
        print("[Server] configure camera resolution, format, and encoder")
        try:
            width, height = resolution
        except: 
            raise TypeError(f"Unsupported resolution argument '{resolution}'. Expected integer TUPLE of format (width, height).")
        if not isinstance(width, int) or not (0 <= width <= 1920): 
            raise ValueError(f"Invalid WIDTH resolution value '{width}'. Expected INTEGER: 0<=WIDTH<=1920.")
        if not isinstance(height, int) or not (0 <= height <= 1080): 
            raise ValueError(f"Invalid HEIGHT resolution value '{width}'. Expected INTEGER: 0<=HEIGHT<=1080.")

        self.camera.video_configuration.main.size = (width, height)
        encoder = H264Encoder()
        self.camera.configure("video")

        cmd_reply = {"status": "Video recording started...", "details": {}}
        self.conn.sendall(json.dumps(cmd_reply).encode("utf‐8"))
        
        # Send file via data socket in real time data stream
        print(f"[Server] connect to TCP data socket")
        data_connection, _ = self.data_socket.accept()
        print("[Server] stream the video output in real time to connected data socket")
        data_stream = data_connection.makefile("wb")
        print("[Server] start recording")
        self.camera.start_recording(encoder, FileOutput(data_stream))
        
        # Continue streaming until stop command is recieved
        while True:
            raw = self.conn.recv(2048)
            cmd_obj = json.loads(raw.decode("utf‐8"))
            if cmd_obj.get("action") != "stop_video": 
                warn_reply = {"status": "warning",
                              "details": {"warning_message": f"Command '{cmd_obj}' could not be excecuted, because of active action. Allowed action: 'stop_video'"}}
                self.conn.sendall(json.dumps(warn_reply).encode("utf‐8"))
                continue
            break
        
        self.camera.stop_recording()
        cmd_reply = {"status": "Video successfully recorded and data socket closed", "details": {}}
        self.conn.sendall(json.dumps(cmd_reply).encode("utf‐8"))
        print(f"[Server] {cmd_reply['status']}")   


    def read_barcode(self):
        raise NotImplementedError("'read_barcode' method not implemented")

                
    def read_qrcode(self):
        raise NotImplementedError("'read_qrcode' method not fully implemented")
        print("[Server] configure camera")
        read_config = self.camera.create_still_configuration()
        self.camera = self.camera.configure(read_config)
        self.camera.start()
        time.sleep(1)
        print("[Server] take picture")
        rgb_array = self.camera.capture_array()
        print("[Server] import qreader")
        qreader = QReader()
        print("[Server] analyze picture")
        qr_str_tuple = qreader.detect_and_decode(rgb_array)
        print("[Server] send back to client")
        if qr_str_tuple == ():
            cmd_reply = {"status": "warning", 
                         "details": {"warning_message": "No readable QR code detected."}}
        else:
            cmd_reply = {"status": "QR-code[s] successfully read.", 
                         "details": {"qr_str_tuple": qr_str_tuple}}
        self.conn.sendall(json.dumps(cmd_reply).encode("utf‐8"))

      
    def start_stream(self, resolution=(1280, 720), IP_out = None):
        """Start streaming H.264 over UDP to the client’s STREAM_PORT. Continues until a 'stop_stream' command arrives on the control socket.
        
        Args:
            resolution (tuple): Width and height of the video stream. Example: `(1280, 720)`
            IP_out (str | None): IP adress the UDP stream is directed to. Defaults to client adress.
        """
        print("[Server] configure camera for UDP stream")
        try:
            width, height = resolution
        except:
            raise TypeError(f"Unsupported resolution argument '{resolution}'. Expected integer TUPLE (width, height).")
        if not isinstance(width, int) or not (0 <= width <= 1920):
            raise ValueError(f"Invalid WIDTH '{width}'. Expected INTEGER 0<=WIDTH<=1920.")
        if not isinstance(height, int) or not (0 <= height <= 1080):
            raise ValueError(f"Invalid HEIGHT '{height}'. Expected INTEGER 0<=HEIGHT<=1080.")

        # Configure Picamera2 for video stream
        self.camera.video_configuration.main.size = (width, height)
        encoder = H264Encoder()
        self.camera.configure("video")

        # Create PyavOutput for sending MPEG-TS, build UDP URL and inform client that streaming started
        if IP_out == None: 
            udp_url = f"udp://{self.addr[0]}:{self.STREAM_PORT}"
            IP_out = self.addr[0]
        else:
            udp_url = f"udp://{IP_out}:{self.STREAM_PORT}"
            IP_out = "<server_ip>"
        print(f"[Server] streaming over UDP to {udp_url}")
        output = PyavOutput(udp_url, format="mpegts")
        self.camera.start_recording(encoder, output)
        cmd_reply = {"status": "Stream started over UDP stream socket.", 
                     "details": {"url": f"udp://{IP_out}:{self.STREAM_PORT}"}}
        self.conn.sendall(json.dumps(cmd_reply).encode("utf‐8"))

        # Continue streaming until stop command is recieved
        while True:
            raw = self.conn.recv(2048)
            cmd_obj = json.loads(raw.decode("utf‐8"))
            if cmd_obj.get("action") != "stop_stream":
                warn_reply = {"status": "warning",
                              "details": {"warning_message": (f"Command '{cmd_obj}' cannot be executed. Allowed action: 'stop_stream'.")}}
                self.conn.sendall(json.dumps(warn_reply).encode("utf‐8"))
                continue
            break

        self.camera.stop_recording()
        cmd_reply = {"status": "UDP stream stopped.", "details": {}}
        self.conn.sendall(json.dumps(cmd_reply).encode("utf‐8"))
        print(f"[Server] {cmd_reply['status']}")
    
if __name__ == "__main__":
    server = CameraServer(CMD_PORT, DATA_PORT, STREAM_PORT)
    server.start()