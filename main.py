import requests as req  
from bs4 import BeautifulSoup as bs 
from config import *  # Importing configuration variables
import json  
import time  
from datetime import datetime 
import pytz  
from tqdm import tqdm  
from telegram.ext import CommandHandler
from telegram.ext.callbackcontext import CallbackContext
from telegram.update import Update
from telegram.ext import Updater

html_list = []  # Initializing an empty list to store HTML content
scrap_enabled = False  # Flag to control scraping process
sent_projects = set()  # Set to keep track of projects already sent to Telegram
limit_value = None  # Variable to store the limit for project bids count

def time_now():
    """
    Get the current hour for Tehran timezone.
    """
    return datetime.now(pytz.timezone('Asia/Tehran')).strftime('%H:%M:%S')

def capture():
    """
    Fetch HTML pages for each desired skill from Ponisha.
    """
    global html_list
    html_list.clear()  # Clearing the list before fetching new HTML
    
    # Iterating over desired skills and fetching HTML pages
    for skill in tqdm(desired_skill, desc="Fetching skills"):
        url = f'https://ponisha.ir/search/projects/skill-{skill}/status-open/page/1'
        url2 = f'https://ponisha.ir/search/projects/{skill}'
        
        try:
            response = req.get(url)
            if response.status_code == 200:
                html_list.append(response.text)
            else:
                response = req.get(url2)
                response.raise_for_status()  # Raise an exception for unsuccessful response
                html_list.append(response.text)
        except req.RequestException as e:
            print(f"Error fetching {url} or {url2}: {e}")

def finder():
    """
    Extract job offer details (title, description, link, price) from HTML pages.
    """
    global sent_projects
    global limit_value
    send = []  # List to store messages to be sent to Telegram
    
    # Iterating over HTML content to find job details
    for html in tqdm(html_list, desc="Processing HTML"):
        try:
            motor = bs(html, "html.parser")
            script_tag = motor.find("script", {"id": "__NEXT_DATA__", "type": "application/json"})
            
            if script_tag:
                json_data = json.loads(script_tag.string)
                
                if 'props' in json_data and 'pageProps' in json_data['props'] and 'dehydratedState' in json_data['props']['pageProps']:
                    queries = json_data['props']['pageProps']['dehydratedState']['queries']
                    
                    for query in queries:
                        if 'state' in query and 'data' in query['state'] and 'data' in query['state']['data']:
                            projects = query['state']['data']['data']
                            
                            for project in projects:
                                # Extracting project details
                                title = project['title']
                                slug = project['slug']
                                description = project['description']
                                project_bids_count = project['project_bids_count']
                                skills = [skill['title'] for skill in project['skills']]
                                amount_min = project['amount_min']
                                amount_max = project['amount_max']
                                project_id = project['id']
                                
                                # Generating URL for the project
                                url = f"https://ponisha.ir/project/{project_id}/{slug}"
                                
                                # Creating message for Telegram
                                message = (
                                    f"(<a href='{url}'> {title} </a>)\n\n"
                                    f"{description}\n\n"
                                    f"پیشنهاد های ارسال شده : {project_bids_count}\n"
                                    f"مهارت های مورد نیاز : {', '.join(skills)}\n"
                                    f"بازه قیمتی: {amount_min} - {amount_max}"
                                )
                                
                                # Checking if project has already been sent
                                if project_id not in sent_projects:
                                    # Adding project to sent projects
                                    sent_projects.add(project_id)
                                    
                                    # Checking if project bids count meets the limit
                                    if limit_value is None or project_bids_count <= limit_value:
                                        send.append(message)
        except (ValueError, KeyError, AttributeError) as e:
            print(f"Error processing HTML: {e}")

    return send  # Returning list of messages to be sent to Telegram

def sail():
    """
    Send job details to the Telegram bot.
    """
    global sent_projects
    send = finder()  # Calling finder function to get messages to send
    
    # Iterating over messages and sending them to Telegram
    for message in tqdm(send, desc="Sending messages"):
        try:
            url = f"https://api.telegram.org/bot{API_KEY}/sendMessage"
            params = {
                'chat_id': CHAT_ID,
                'parse_mode': 'HTML',
                'text': message
            }
            req.get(url, params=params)
        except req.RequestException as e:
            print(f"Error sending message: {e}")

    # Sending description to user about current status
    try:
        current_hour = time_now()
        description_for_user = f"ساعت {current_hour} \n پوزیشن های باز برای شما : {len(send)}"
        url = f"https://api.telegram.org/bot{API_KEY}/sendMessage"
        params = {
            'chat_id': CHAT_ID,
            'text': description_for_user
        }
        req.get(url, params=params)
    except req.RequestException as e:
        print(f"Error sending description: {e}")

def loading_indicator(sleep_time):
    """
    Show a loading indicator for the sleep period.
    """
    for _ in tqdm(range(sleep_time), desc="Sleeping", unit="s"):
        time.sleep(1)

def send_welcome(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Welcome to 🚀 Ponisha(Iranina Frelancer) Scraper Bot!\n\n'
        '💻 Author: `MasNiper`\n\n'
        '🤖 Global commands:\n'
        '🟣 `/startScrap` - Start scraping for job postings\n'
        '🟣 `/stopScrap` - Stop the scraping process\n'
        '🟣 `/restartBot` - Restart the bot and clear all data\n'
        '🟣 `/limitbids (number)` - Set a limit for maximum project bids count\n'
        '🟣 `/help` - Display help menu\n'
    )
def send_help(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        '🤖 Global commands:\n'
        '🟣 `/startScrap` - Start scraping for job postings\n'
        '🟣 `/stopScrap` - Stop the scraping process\n'
        '🟣 `/restartBot` - Restart the bot and clear all data\n'
        '🟣 `/limitbids (number)` - Set a limit for maximum project bids count\n'
    )
def start_scrap(update: Update, context: CallbackContext) -> None:
    """
    Start the scraping process,Please Waite....
    """
    global scrap_enabled, sent_projects
    scrap_enabled = True
    update.message.reply_text('Start the scraping process,Please Waite....')

def stop_scrap(update: Update, context: CallbackContext) -> None:
    """
    Stop the scraping process.
    """
    global scrap_enabled
    scrap_enabled = False
    update.message.reply_text('Scraping process stopped.')

def restart_bot(update: Update, context: CallbackContext) -> None:
    """
    Restart the bot.
    """
    update.message.reply_text('Bot is restarting...')
    global html_list, sent_projects, limit_value
    html_list.clear()  # Clearing HTML list
    sent_projects.clear()  # Clearing sent projects set
    limit_value = None  # Resetting limit value

def limit_bids(update: Update, context: CallbackContext) -> None:
    """
    Set a limit for project bids count.
    """
    try:
        global html_list, sent_projects, limit_value
        html_list.clear()  # Clearing HTML list
        sent_projects.clear()  # Clearing sent projects set
        limit_value = int(context.args[0])  # Setting limit value from command argument
        print(f"Limit value set to: {limit_value}")
        update.message.reply_text(f"Limit value set to: {limit_value}")

    except (IndexError, ValueError) as e:
        print(f"Error setting limit value: {e}")
        update.message.reply_text('Please provide a valid limit value.')

if __name__ == '__main__':
    updater = Updater(token=API_KEY, use_context=True)
    dispatcher = updater.dispatcher

    # Adding handlers for different commands
    dispatcher.add_handler(CommandHandler("start", send_welcome))
    dispatcher.add_handler(CommandHandler("startScrap", start_scrap))
    dispatcher.add_handler(CommandHandler("stopScrap", stop_scrap))
    dispatcher.add_handler(CommandHandler("restartBot", restart_bot))
    dispatcher.add_handler(CommandHandler("limitbids", limit_bids))
    dispatcher.add_handler(CommandHandler("help", send_help))

    updater.start_polling()  # Starting the bot

    while True:
        if scrap_enabled:
            capture()  # Fetching HTML pages
            sail()  # Sending job details to Telegram
            loading_indicator(3600)  # Showing loading indicator for an hour
updater.idle()  # Bot goes idle