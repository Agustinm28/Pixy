import os
import ffmpeg
from PIL import Image
from colorama import Fore
from moviepy.video.io.VideoFileClip import VideoFileClip
import subprocess

def compress_video(input_path:str, export_path:str, max_size:int):
    print(f'[{Fore.YELLOW}COMPRESSION{Fore.RESET}] File is larger than {max_size}MB ({os.path.getsize(input_path) // (1024 * 1024)}MB), starting compression')

    # Initial compression with H265 codec
    print(f'[{Fore.YELLOW}COMPRESSION{Fore.RESET}] Writing with H265 codec, this may take a while...')

    try:
        # Create an FFmpeg object for the input file
        input_stream = ffmpeg.input(input_path)

        # Configure H.265 codec for the output file
        output = export_path
        output_stream = ffmpeg.output(input_stream, output, vcodec='libx265')

        # Add "-loglevel" argument to display as little information as possible
        output_stream = output_stream.global_args('-loglevel', 'quiet')
        output_stream = output_stream.global_args('-stats')

        # Execute the coding process
        ffmpeg.run(output_stream)

        # The original file is replaced by the compressed one
        os.remove(input_path)
        os.rename(export_path, input_path)
        print(f'[{Fore.GREEN}COMPRESSION{Fore.RESET}] Writing finalized: ({os.path.getsize(input_path) // (1024 * 1024)}MB)')
    except subprocess.CalledProcessError as e:
        print(f'[{Fore.RED}ERROR{Fore.RESET}] ffmepg process fail. {e}')
    except OSError as e:
        print(f'[{Fore.RED}ERROR{Fore.RESET}] File cannot be read or not exist. {e}')

    # More aggressive compression in case the file still exceeds the maximum MB file size
    if os.path.getsize(input_path) > max_size * 1024 * 1024:
        print(f'[{Fore.YELLOW}COMPRESSION{Fore.RESET}] File is still larger than {max_size}MB ({os.path.getsize(export_path) // (1024 * 1024)}MB), starting agresive compression')
        try:    
            
            clip = VideoFileClip(input_path)

            # Set the target bit rate
            new_bitrate = f"{int((max_size * 8 * 1000) / clip.duration)}k"

            # New bit rate compression
            print(f'[{Fore.YELLOW}COMPRESSION{Fore.RESET}] Compressing file')
            clip.write_videofile(input_path, bitrate=new_bitrate)
        except ValueError:
            print(f'[{Fore.RED}ERROR{Fore.RESET}] Clip object cannot be created or video writing failed')


def compress_image(export_path):
    print(f"[{Fore.YELLOW}COMPRESSION{Fore.RESET}] The file is too large {os.path.getsize(export_path)}")
    try:
        img = Image.open(export_path)
        img.save(export_path, "JPEG", quality=90, optimize=True)
    except OSError:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] File doesn't exist or cannot be read")
    except ValueError:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] Format or wuality value not valid")
    except IOError:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] File cannot be written")