import logging
import re
import socket
import subprocess
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, Poll, PollOption, KeyboardButton, KeyboardButtonPollType, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, Bot
import telegram
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, Application, PollAnswerHandler, PollHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode
import asyncio
from colorama import Fore
import argparse
import os
import pickle
import time

global chat_id

scale_method = None

with open('./data/TEST_BOT_CREDENTIALS.txt', 'r') as f:
    token = str(f.read())
chat_id = None

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_id
    chat_id = update.effective_chat.id
    with open('./data/chat_ID.txt', 'w') as f:
        f.write(str(chat_id))
    await context.bot.send_message(chat_id=chat_id, text="Hi! Im Pixy and i can upscale images or videos for you.")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, parse_mode = 'html', text="<b>start</b> - Set the chat_id so that the bot can send you messages\n<b>help</b> - Tells you the bot commands\n<b>scale</b> - Tells you info about scale methods")

async def scale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, parse_mode = 'html', text=f"- <b>Interpolation</b>: applies the Lanczos4 interpolation method which uses a cubic function to calculate the new pixel values from the existing ones. This method scales the image by a factor of x2. Available for image and video.\n- <b>AI</b>: It uses the ESRGAN model which makes use of a deep neural network to scale images. This method scales the image by a factor of x4. Available only for images.")

async def get_me():
    bot = telegram.Bot(token)
    async with bot:
        print(await bot.get_me())

async def get_updates():
    bot = telegram.Bot(token)
    async with bot:
        print((await bot.get_updates())[0])

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receives a video update and saves it locally. Verifies the size of the video, sends a message if it exceeds the maximum size, and returns early. Otherwise, it downloads the video file and saves it to a specified path. If an error occurs during the download process, an error message is sent. Then, it sends a message indicating that the video was uploaded correctly and proceeds to send the video file to a server for processing.

    Parameters:
        update (Update): The update object containing information about the received message.
        context (ContextTypes.DEFAULT_TYPE): The context object for handling the bot's functionality.
    Returns:
        None
    """

    chat_id = update.effective_chat.id
    video = update.message.video

    # Check the video size
    if video.file_size > 20 * 1024 * 1024:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="The maximum size for the video is 20MB")
        return

    await context.bot.send_message(chat_id=chat_id, text="The video upscaler is temporarily disabled due to hardware limitations.")
    # # Saves the video locally
    # await context.bot.send_message(chat_id=chat_id, text="Uploading video")
    # video_file = await context.bot.get_file(video.file_id)
    # os.makedirs("./videos", exist_ok=True)
    # video_path = "./videos/" + f"{chat_id}_{video.file_unique_id}.{video.mime_type.split('/')[1]}"
    # try:
    #     await video_file.download_to_drive(video_path)
    # except Exception as e:
    #     logging.error(e)
    #     await context.bot.send_message(chat_id=update.effective_chat.id, text="Error processing video")

    # # Send the video to the server to be processed
    # await context.bot.send_message(chat_id=update.effective_chat.id, text="Video uploaded correctly")
    # await send_file(file=video_path, scale_method=None)

async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receives an image update and saves it locally. Verifies the size of the image, sends a message if it exceeds the maximum size, and returns early. Otherwise, it downloads the image file and saves it to a specified path. If an error occurs during the download process, an error message is sent. Finally, it sends a message indicating that the image was uploaded correctly and provides an inline keyboard for selecting an upscale method.

    Parameters:

    - update (Update): The update object containing information about the received message.
    - context (ContextTypes.DEFAULT_TYPE): The context object for handling the bot's functionality.

    Returns:
    - None
    """
    chat_id = update.effective_chat.id
    image = update.message.photo[-1]

    # Check the image size
    if image.file_size > 20 * 1024 * 1024:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="The maximum size for the image is 20MB")
        return

    # Saves the video locally
    await context.bot.send_message(chat_id=chat_id, text="Uploading image")
    image_file = await context.bot.get_file(image.file_id)
    os.makedirs("./images", exist_ok=True)
    image_path = "./images/" + f"{chat_id}_{image.file_unique_id}.jpeg"
    try:
        await image_file.download_to_drive(image_path)
    except Exception as e:
        logging.error(e)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error processing image")

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Image uploaded correctly")

    # Keyboard inline to select scale method
    keyboard = [
            [InlineKeyboardButton("Interpolation", callback_data=f"0_{image_path}")],
            [InlineKeyboardButton("AI", callback_data=f"1_{image_path}")],
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select a upscale method:", reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the button callback from an inline keyboard. Extracts the scale method and file path from the callback data. Sends a response to the callback query, indicating the selected upscale method. Then, sends the file to a server for processing using the specified scale method.

    Parameters:

    - update (Update): The update object containing information about the callback query.
    - context (ContextTypes.DEFAULT_TYPE): The context object for handling the bot's functionality.

    Returns:
    - None
    """
    # Handler in charge of waiting for a response for Keyboard inline
    query = update.callback_query
    await query.answer()
    scale = query.data

    # Gets the file path and scaling method from callback_data
    scale_data = scale.split('_', 1)
    scale_method = int(scale_data[0])
    file_path = scale_data[1]
    if scale_method == 0:
        scale_type = "Interpolation"
    else:
        scale_type = "AI"
    await query.edit_message_text(text=f"Upscale method: {scale_type}")

    # Define another inline keyboard for asking another thing
    keyboard2 = [
        [InlineKeyboardButton("2x", callback_data=f"2x_{file_path}")],
        [InlineKeyboardButton("3x", callback_data=f"3x_{file_path}")],
        [InlineKeyboardButton("4x", callback_data=f"4x_{file_path}")],
    ]

    reply_markup2 = InlineKeyboardMarkup(keyboard2)
    # Check if the first keyboard has been answered
    if scale_method is not None:
        # Send the second keyboard and wait for a response
        await update.message.reply_text("Select a upscale factor:", reply_markup=reply_markup2)

        # Get the response from the second keyboard
        query2 = update.callback_query
        await query2.answer()
        factor = query2.data

        factor_data = factor.split('_', 1)
        factor_value = int(factor_data[0])

        await query2.edit_message_text(text=f"Upscale factor: {factor_value}")

        # Check if both keyboards have been answered
        if factor is not None:
            # Send the image to the server to be processed
            print(f'[{Fore.YELLOW}TEST{Fore.RESET}] Scale method: {scale_method}')
            print(f'[{Fore.YELLOW}TEST{Fore.RESET}] Scale factor: {factor_value}')
            await send_file(file=file_path, scale_method=scale_method)


async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):  
    """
    Receives a file update and saves it locally. Verifies the size of the file based on its MIME type (video or image). If the file size exceeds the maximum allowed, a message is sent and the function returns early. Otherwise, the file is downloaded and saved to the appropriate directory. If an error occurs during the download process, an error message is sent. For videos, the file is sent to a server for processing. For images, an inline keyboard is provided to select an upscale method. If the file type is not recognized, a corresponding message is sent.

    Parameters:

    - update (Update): The update object containing information about the received message.
    - context (ContextTypes.DEFAULT_TYPE): The context object for handling the bot's functionality.
    
    Returns:
    - None
    """
    chat_id = update.effective_chat.id
    file = update.message.document

    if file.mime_type.startswith('video/'):
        # Checks the file size
        if file.file_size > 20 * 1024 * 1024:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="The maximum size for the video is 20MB")
            return
        
        await context.bot.send_message(chat_id=chat_id, text="The video upscaler is temporarily disabled due to hardware limitations.")
        # # Saves the video locally
        # await context.bot.send_message(chat_id=chat_id, text="Uploading video")
        # document_file = await context.bot.get_file(file.file_id)
        # os.makedirs("./videos", exist_ok=True)
        # file_path = "./videos/" + f"{chat_id}_{file.file_unique_id}.{file.mime_type.split('/')[1]}"
        # try:
        #     await document_file.download_to_drive(file_path)
        # except Exception as e:
        #     logging.error(e)
        #     await context.bot.send_message(chat_id=update.effective_chat.id, text="Error processing video")

        # # Sends the video to the server to be processed
        # await context.bot.send_message(chat_id=update.effective_chat.id, text="Video uploaded correctly")
        # await send_file(file=file_path, scale_method=None)
    elif file.mime_type.startswith('image/'):
        
        if file.file_size > 20 * 1024 * 1024:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="The maximum size for the image is 20MB")
            return
        await context.bot.send_message(chat_id=chat_id, text="Uploading image")
        document_file = await context.bot.get_file(file.file_id)
        os.makedirs("./images", exist_ok=True)
        file_path = "./images/" + f"{chat_id}_{file.file_unique_id}.{file.mime_type.split('/')[1]}"
        try:
            await document_file.download_to_drive(file_path)
        except Exception as e:
            logging.error(e)
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Error processing image")

        await context.bot.send_message(chat_id=update.effective_chat.id, text="Image uploaded correctly")

        
        keyboard = [
                [InlineKeyboardButton("Interpolation", callback_data=f"0_{file_path}")],
                [InlineKeyboardButton("AI", callback_data=f"1_{file_path}")],
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Select a upscale method:", reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="File type not recognized")
        return

async def send_file(file, scale_method):
    """
    Sends a file to a server for processing.

    Parameters:

    - file (str): The path of the file to be sent.
    - scale_method (int): The method of scaling to be applied to the file.
    
    Returns:
    - None
    """
    HOST, PORT = args.ip, int(args.port)

    with open('./data/ipv4.txt', 'r') as f:
        ipv4 = str(f.read())
    with open('./data/ipv6.txt', 'r') as f:
        ipv6 = str(f.read())

    try:
        with open(file, "rb") as f:
            print(f"[{Fore.GREEN}SERIALIZING{Fore.RESET}] Loading object") 
            filename = os.path.basename(file)
            file_data = f.read()
            file_obj = {'filename':filename, 'data':file_data, 'scale':scale_method}
            file_pickle = pickle.dumps(file_obj) 
            print(f"[{Fore.GREEN}SERIALIZING{Fore.RESET}] Pickle object loaded")
            f.close()
    except IOError as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] Could not read file: {e}")
        return

    try:
        if re.search(ipv6, args.ip):
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
                sock.connect((HOST, PORT))
                print(f"[{Fore.GREEN}CONNECT{Fore.RESET}] Connection established with {HOST} on port {PORT}")
                print(f"[{Fore.GREEN}SENDING{Fore.RESET}] Sending file")        
                sock.sendall(file_pickle)
                sock.close()
                os.remove(file)
        elif re.search(ipv4, args.ip):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((HOST, PORT))
                print(f"[{Fore.GREEN}CONNECT{Fore.RESET}] Connection established with {HOST} on port {PORT}")
                print(f"[{Fore.GREEN}SENDING{Fore.RESET}] Sending file")        
                sock.sendall(file_pickle)
                sock.close()
                try:
                    os.remove(file)
                except Exception as e:
                    print(f"[{Fore.RED}ERROR{Fore.RESET}] Could not delete file: {e}")
    except ConnectionError as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] Could not connect to server: {e}")
    except Exception as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] Unknown error occurred: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Telegram Bot')
    parser.add_argument('-ip', type=str, default='127.0.0.1', help='IP of the process server')
    parser.add_argument('-port', '-p', type=int, default=5556, help='Port of the process server')
    args = parser.parse_args()

    application = ApplicationBuilder().token(token).build()
    
    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help)
    scale_handler = CommandHandler('scale', scale)
    button_handler = CallbackQueryHandler(button)

    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(button_handler)
    application.add_handler(scale_handler)
    application.add_handler(MessageHandler(filters.VIDEO, receive_video))
    application.add_handler(MessageHandler(filters.PHOTO, receive_image))
    application.add_handler(MessageHandler(filters.ATTACHMENT, receive_file))
    
    
    application.run_polling()