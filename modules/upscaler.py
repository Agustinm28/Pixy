from multiprocessing import Manager
import os
from queue import Queue
import subprocess
import cv2
from tqdm import tqdm
from PIL import Image
from moviepy.video.io.VideoFileClip import VideoFileClip
import moviepy.editor as mp
from ffprobe import FFProbe
from colorama import Fore
import ffmpeg
import io
import os
import PIL
import requests
import replicate
from modules.telegram_sender import send_message, send_file
from modules.compresser import compress_image, compress_video

with open('./data/REPLICATE_KEY.txt', 'r') as f:
    token = str(f.read())
os.environ["REPLICATE_API_TOKEN"] = token


def scale_image(filename, factor):

    image_path = f'./rec_files/{filename}'
    chat_id = int((filename.split("_"))[0])
    try:
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            raise IOError(f'[{Fore.RED}ERROR{Fore.RESET}] Could not read image {image_path}')
        # Read the input resolution of the image
        height, width = image.shape[:2]
        # Duplicate image resolution
        new_height = height * factor
        new_widht = width * factor

        # Scale the image with the cv2.INTER_LANCZOS method.
        print(f"[{Fore.GREEN}SCALING{Fore.RESET}] {filename} scaling with lanczos")
        
        # Start scaling message is sent and scaled.
        send_message(chat_id, "Scaling Image (Interpolation)...")
        imagen_escalada = cv2.resize(
            image, (new_widht, new_height), interpolation=cv2.INTER_LANCZOS4)
        print(f"[{Fore.GREEN}SCALING{Fore.RESET}] {filename} scaling finished")

        # Apply bilateral noise reduction filtering
        print(f"[{Fore.GREEN}DENOISING{Fore.RESET}] {filename} denoising image")
        imagen_escalada = cv2.bilateralFilter(imagen_escalada, 7, 50, 50)
        print(f"[{Fore.GREEN}DENOISING{Fore.RESET}] {filename} denoising finished")

        # Shaping of edges with unsharp mask filter
        print(f"[{Fore.GREEN}SHARPENING{Fore.RESET}] {filename} sharpening image")
        sigma = 1
        amount = 1.5
        threshold = 0
        blurred = cv2.GaussianBlur(imagen_escalada, (0, 0), sigma)
        imagen_escalada = cv2.addWeighted(imagen_escalada, 1 + amount, blurred, -amount, threshold)
        print(f"[{Fore.GREEN}SHARPENING{Fore.RESET}] {filename} sharpening finished")

        # Export the scaled image locally
        print(f"[{Fore.GREEN}SCALING{Fore.RESET}] {filename} exporting")
        os.makedirs('./upscaled_files/', exist_ok=True)
        export_path = f'./upscaled_files/upscaled_{filename}'
        cv2.imwrite(export_path, imagen_escalada)
        print(f"[{Fore.GREEN}SCALING{Fore.RESET}] {filename} exported succesfully")

        # Log information
        print(f'{Fore.YELLOW}Input resolution:{Fore.RESET} {height}x{width}')
        print(f'{Fore.YELLOW}Scale factor:{Fore.RESET} x{factor}')
        print(f'{Fore.YELLOW}Output resolution:{Fore.RESET} {new_height}x{new_widht}')
        send_message(chat_id, f"Scaling finished, output resolution: {new_widht}x{new_height}")

        # Compression algorithm to achieve a weight of less than 50 MB
        max_size = 50 * 1024 * 1024
        while os.path.getsize(export_path) > max_size:
            compress_image(export_path)
    
    except IOError as e:
        print(f'[{Fore.RED}ERROR{Fore.RESET}] {e}')
        send_message(chat_id, "An error occurred while reading or writing the image file.")
    except cv2.error as e:
        print(f'[{Fore.RED}ERROR{Fore.RESET}] {e}')
        send_message(chat_id, "An error occurred while processing the image.")
    except Exception as e:
        print(f'[{Fore.RED}ERROR{Fore.RESET}] {e}')
        send_message(chat_id, "An unexpected error occurred.")
    finally:
        cv2.waitKey(1000)
        cv2.destroyAllWindows()


def scale_image_ia(filename, factor, face):
    try:
        # Load input image
        image_path = f'./rec_files/{filename}'
        input_image = PIL.Image.open(image_path)
        chat_id = int((filename.split("_"))[0])

        input_file = io.BytesIO()
        input_image.save(input_file, format="JPEG")

        if face == 5:
            face_value = True
        else:
            face_value = False

        # Send the image to replicate through its API to be scaled
        print(f'[{Fore.GREEN}SCALING{Fore.RESET}] {filename} scaling with AI')
        send_message(chat_id, "Scaling Image (AI)...")
        output_image = replicate.run(
            "nightmareai/real-esrgan:42fed1c4974146d4d2414e2be2c5277c7fcf05fcc3a73abf41610695738c1d7b",
            input={"image": input_file, "face_enhance":face_value, "scale":factor}
        )
        print(f'[{Fore.GREEN}SCALING{Fore.RESET}] Scaling with AI finished')

        # Download the image from the URL
        print(f'[{Fore.GREEN}SCALING{Fore.RESET}] Saving image')
        response = requests.get(output_image)
        output_image = PIL.Image.open(io.BytesIO(response.content))
        width, height = output_image.size
        # Save the output image
        os.makedirs('./upscaled_files/', exist_ok=True)
        output_image.save(f"./upscaled_files/upscaled_{filename}")
        print(f'[{Fore.GREEN}SCALING{Fore.RESET}] Image saved correctly')
        send_message(chat_id, f"Scaling finished, output resolution: {width}x{height}")

    except replicate.exceptions.ModelError as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] {e}")
        send_message(chat_id, "An error occurred while scaling the image with AI. Send the image as a Photo, not File.")
    except Exception as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] {e}")

def scale_video(filename, scale):
    try:
        # Open the received video
        video_path = f'./rec_files/{filename}'
        cap = cv2.VideoCapture(video_path)

        # Get the width and height of the video
        widht = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Get the number of video frames
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        pbar = tqdm(total=frames, desc="Processing Video",
                    unit="frame", colour="green")

        # Define the new width and height
        new_widht = widht * scale
        new_height = height * scale

        # Get video framerate
        framerate = cap.get(cv2.CAP_PROP_FPS)

        # Define the codec and the name of the new video
        fourcc = cv2.VideoWriter_fourcc(*"hvc1")  # Codec H264 (avc1), H265 (hvc1)
        os.makedirs('./upscaled_files/', exist_ok=True)
        out = cv2.VideoWriter(f"./upscaled_files/upscaled_{filename}", fourcc, framerate, (new_widht, new_height))

        # Get user chat_id from filename
        chat_id = int((filename.split("_"))[0])
        send_message(chat_id, "Scaling Video...")

        # Get the output of ffprobe as a string
        output_audio = subprocess.run(["ffprobe", "-show_streams", video_path], capture_output=True, text=True).stdout

        # Using ffmpeg to extract the audio from the received video
        # Check if the output contains the word "audio"
        if "audio" in output_audio:
            # The video has audio, extract it
            subprocess.run(["ffmpeg", "-i", video_path, "-vn", "-acodec", "copy", "audio.aac"])
        else:
            # The video has no audio, do nothing
            print(f"[{Fore.YELLOW}INFO{Fore.RESET}] The video has no audio")

        # Reads every frame of the received video and scales them up
        while True:
            try:
                ret, frame = cap.read()
                if ret:
                    pbar.update(1)
                    # Frame scaling with loop interpolation
                    upscaled_frame = cv2.resize(frame, (new_widht, new_height), interpolation=cv2.INTER_LANCZOS4)
                    frame
                    # Apply bilateral noise reduction filtering
                    upscaled_frame = cv2.bilateralFilter(upscaled_frame, 7, 50, 50)
                    # Shaping of edges with unsharp mask filter
                    sigma = 1
                    amount = 1.5
                    threshold = 0
                    blurred = cv2.GaussianBlur(upscaled_frame, (0, 0), sigma)
                    upscaled_frame = cv2.addWeighted(upscaled_frame, 1 + amount, blurred, -amount, threshold)
                    # Write the scaled frame in the new video
                    out.write(upscaled_frame)
                else:
                    break
            except Exception as e:
                print(f"[{Fore.RED}ERROR{Fore.RESET}] Error reading or processing the frame: {e}")

        pbar.close()

        # Output log
        print(f'{Fore.YELLOW}Input resolution:{Fore.RESET} {widht}x{height}')
        print(f'{Fore.YELLOW}Scale factor:{Fore.RESET} x{scale}')
        print(f'{Fore.YELLOW}Output resolution:{Fore.RESET} {new_widht}x{new_height}')
        send_message(
            chat_id, f"Scaling finished, output resolution: {new_widht}x{new_height}")

        cap.release()
        out.release()

        export_path = f"./upscaled_files/upscaled_{filename}"
        output = f"./upscaled_files/a_upscaled_{filename}"
        # Use ffmpeg to apply the audio to the newly scaled video
        # Check if the audio file exists
        if os.path.exists("audio.aac"):
            # The audio file exists, apply it to the new video
            subprocess.run(["ffmpeg", "-v", "quiet", "-stats", "-i", export_path, "-i", "audio.aac", "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-y", output])
            os.remove(export_path)
            os.rename(output, export_path)
        else:
            # The audio file does not exist, do nothing or handle the case
            print(f"[{Fore.YELLOW}PROCESS{Fore.RESET}] The audio file does not exist")

        cv2.destroyAllWindows()

        try:
            os.remove("audio.aac")
        except OSError as e:
            print(f"[{Fore.RED}ERROR{Fore.RESET}] {e.filename} - {e.strerror}.")
        
        # Compress the video if it is more than 50MB in size.
        max_size = 50 * 1024 * 1024
        if os.path.getsize(export_path) > max_size:
            input_path = f"./upscaled_files/upscaled_{filename}"
            output_path = f"./upscaled_files/c_upscaled_{filename}"
            send_message(chat_id, "Compressing video, this may take a while...")
            compress_video(input_path, output_path, 50) 
    
    except FileNotFoundError as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] {e}")
    except NameError as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] {e}")
    except TypeError as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] {e}")
