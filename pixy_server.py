import re
import socket
import socketserver
import argparse
from multiprocessing import Manager
import pickle
import os
import sys
from queue import Queue
from tqdm import tqdm
import multiprocessing
import mimetypes
from colorama import Fore
from modules.telegram_sender import send_file, send_message
from modules.upscaler import scale_image, scale_image_ia, scale_video

manager = Manager()  
queue = manager.Queue()


class ForkedTCPServer4(socketserver.ForkingMixIn, socketserver.TCPServer):
    address_family = socket.AF_INET
    pass

class ForkedTCPServer6(socketserver.ForkingMixIn, socketserver.TCPServer):
    address_family = socket.AF_INET6
    pass


class TCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        """
        Handles a client connection in a server.

        Returns:
        - None
        """
        BUFFER_SIZE = 1024 * 1024
        print(f'[{Fore.CYAN}NEW CONNECTION{Fore.RESET}]' +  ' {} connected.'.format(self.client_address))
        client = self.client_address
    
        try:
            # Read the complete serialized object
            print(Fore.GREEN + f'[{Fore.GREEN}READING{Fore.RESET}] Reading searialized object')
            file_pickle = b''
            while True:
                data = self.request.recv(BUFFER_SIZE)
                if not data:
                    break
                file_pickle += data
            print(f'[{Fore.GREEN}READING{Fore.RESET}] Serialized object readed')

            # Deserialize the object
            file_obj = pickle.loads(file_pickle)
            print(f'[{Fore.GREEN}READING{Fore.RESET}] Object deserialized')

            # Read the complete file
            file_data = b''
            print(f'[{Fore.GREEN}READING{Fore.RESET}] Reading file')
            while True:
                data = self.request.recv(BUFFER_SIZE)
                if not data:
                    break
                file_data += data

            # Write the file in the disk
            filename = file_obj['filename']
            file_data = file_obj['data']
            scale_method = file_obj['scale']
            print(f'[{Fore.GREEN}SAVING{Fore.RESET}] Saving file locally')
            os.makedirs('./rec_files/', exist_ok=True)
            with open('./rec_files/' + filename, 'wb') as f:
                f.write(file_data)
            print(f'[{Fore.GREEN}SAVED{Fore.RESET}] File saved as {filename}')
            self.request.close()

            print(f'[{Fore.GREEN}PROCESSING{Fore.RESET}] Sending to queue')
            queue.put_nowait((filename, scale_method))
        except (ConnectionResetError, ConnectionAbortedError) as e:
            print(f"[{Fore.RED}ERROR{Fore.RESET}] Error connecting to the client {client}: {e}")

        except Exception as e:
            print(f"[{Fore.RED}ERROR{Fore.RESET}] Error in the {client} client connection handle: {e}")


def process_queue():
    """
    Processes the queue of files for scaling and sends the processed files to the corresponding Telegram user.

    Returns:
    - None
    """
    try:
        while True:
            while not queue.empty():
                filename, scale_method = queue.get_nowait()
                mimetypes.add_type("image/webp", ".webp", strict=True)
                filetype, encoding = mimetypes.guess_type(filename)
                chat_id = int((filename.split("_"))[0])
                print(f'[{Fore.GREEN}PROCESSING{Fore.RESET}] Processing file {filename}...')
                try:
                    if filetype.startswith('video/'):
                        # A child process is spawned to process the video
                        p_image = multiprocessing.Process(
                            target=scale_video, args=(filename, 2))
                        print(f'[{Fore.BLUE}PROCESSING{Fore.RESET}] Generating son process for {filename}')
                        p_image.start()
                        p_image.join()
                    else:
                        # A child process is spawned to process the image
                        if scale_method == 0:
                            # Image Processing with Pixel Interpolation
                            p_image = multiprocessing.Process(
                                target=scale_image, args=(filename, 2))
                            print(f'[{Fore.BLUE}PROCESSING{Fore.RESET}] Generating son process for {filename}')
                            p_image.start()
                            p_image.join()
                        elif scale_method == 1:
                            # Image Processing with AI
                            p_image = multiprocessing.Process(
                                target=scale_image_ia, args=(filename,))
                            print(f'[{Fore.BLUE}PROCESSING{Fore.RESET}] Generating son process for {filename}')
                            p_image.start()
                            p_image.join()
                    print(f'[{Fore.GREEN}PROCESSING{Fore.RESET}] File {filename} processed')
                    file_path = f'./upscaled_files/upscaled_{filename}'
                    print(f'[{Fore.GREEN}SENDING{Fore.RESET}] Sending file {filename} to Telegram user')
                    os.remove(f'./rec_files/{filename}')
                    try:
                        send_file(file_path, filetype, chat_id)
                        os.remove(file_path)
                    except FileNotFoundError or UnboundLocalError:
                        print(f"[{Fore.RED}ERROR{Fore.RESET}] File not found")
                        send_message(chat_id, "There was an error processing the file.")
                except AttributeError:
                    print(f'[{Fore.RED}ERROR{Fore.RESET}] File type is incorrect')
                    send_message(chat_id, "File type is incorrect")
                
    except KeyboardInterrupt:
        print(f'[{Fore.BLUE}TERMINATED{Fore.RESET}] Queue process terminated')
    except BrokenPipeError as e:
        print(f'[{Fore.RED}ERROR{Fore.RESET}] {e}')
    except ConnectionResetError or BrokenPipeError as e:
        sys.exit(0)

def server(args):

    HOST, PORT = args.ip, args.port

    with open('./data/ipv4.txt', 'r') as f:
        ipv4 = str(f.read())
    with open('./data/ipv6.txt', 'r') as f:
        ipv6 = str(f.read())

    if re.search(ipv6, args.ip):
        try:
            with ForkedTCPServer6((HOST, PORT), TCPRequestHandler) as server:
                print(f'[{Fore.BLUE}WAITING{Fore.RESET}] Server is waiting for connections on {HOST}:{PORT}')
                server.serve_forever()
        except OSError as e:
            print(Fore.RED + f'[{Fore.RED}ERROR{Fore.RESET}] {e} for IP address')
            sys.exit(0)
    elif re.search(ipv4, args.ip):
        try:
            with ForkedTCPServer4((HOST, PORT), TCPRequestHandler) as server:
                print(f'[{Fore.BLUE}WAITING{Fore.RESET}] Server is waiting for connections on {HOST}:{PORT}')

                server.serve_forever()
        except OSError as e:
            print(f'[{Fore.RED}ERROR{Fore.RESET}] {e} for IP address') 
            sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-ip', type=str, default='127.0.0.1',
                        help='IP of the server process')
    parser.add_argument('-port', '-p', type=int, default=5556,
                        help='Port of the server process')
    args = parser.parse_args()

    # Procesa la cola en un proceso hijo

    try:
        queue_process = multiprocessing.Process(target=process_queue)
        queue_process.start()
        print(f'[{Fore.BLUE}PROCESSING{Fore.RESET}] Started queue process {queue_process.pid}...')

        # Inicia el servidor y se queda esperando conexiones en el proceso padre
        print(f'[{Fore.BLUE}PROCESSING{Fore.RESET}] Started server process')

        try:
            server(args)
        except UnboundLocalError as e:
            print(f'[{Fore.RED}ERROR{Fore.RESET}] {e}. Server shutting down')
            sys.exit(0)

        # Espera a que los procesos hijos terminen
        queue_process.join()
    except KeyboardInterrupt:
        print(f'[{Fore.BLUE}TERMINATED{Fore.RESET}] Server shutting down')

    print(f'[{Fore.BLUE}PROCESSING{Fore.RESET}] All processes finished.')
