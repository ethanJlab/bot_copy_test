import os
import discord
import openai
import tiktoken
import time
import requests
import shutil
import random
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('gpt_bot_token')
# GUILD = os.getenv('DISCORD_GUILD')
openai.api_key = os.getenv("OPENAI_API_KEY")

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

CALL_RESPONSE_LIMIT = 4000
TOPIC = ""
MODEL = "gpt-3.5-turbo"
# this bot should keep this to False for now, should create a seperate bot for this
add_personality = False
main_prompt = "You’re a kind helpful assistant."
personality_prompt = ""
outputChannel = "chatgpt"

@client.event
async def on_ready():
    # announce that the bot is active
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
    global personality_prompt 
    global main_prompt

    #check if the message is from the bot
    if message.author == client.user:
        return
    
    if message.content.lower().startswith("!"):
        return
    
    #define all channels
    output = discord.utils.get(client.get_all_channels(), name=outputChannel)
    

    # use [] to set the personality prompt
    # this should only be used by admins/develoeprs
    if message.content.startswith("["):
        # parse the message to get the prompt
        personality_prompt = message.content.replace("[", "")
        personality_prompt = personality_prompt.replace("]", "")
        response = await message.channel.send("Personality prompt set to: " + personality_prompt)
        await message.delete()
        time.sleep(5)
        await response.delete()
        return
    
    # use () to set the main prompt
    # this should only be used by admins/develoeprs
    if message.content.startswith("("):
        # parse the message to get the prompt
        main_prompt = message.content.replace("(", "")
        main_prompt = main_prompt.replace(")", "")
        response = await message.channel.send("Main prompt set to: " + main_prompt)
        await message.delete()
        time.sleep(5)
        await response.delete()
        return
    
    if message.content.lower() == "?resetprompts":
        main_prompt = "You’re a kind helpful assistant."
        personality_prompt = ""
        response = await message.channel.send("Prompts reset")
        time.sleep(5)
        await response.delete()
        return
    
    if message.content.lower() == "?developerlog":
        developer_message = "Version 0.1: \n - Added ?help command\n - Fixed bug where images do not consistently show up \n Changed the gpt bot command prefix from ! to ? so that it wont interfere with other bots.\nKnown Bugs: \n - If image generation is being used by multiple users, sometimes the wrong image is returned \n - The bot may get unexpected results if messages are spammed in the chat channel"
        await message.channel.send(developer_message)
        await message.delete()
        return
    
    if message.content.lower() == "?togglepersonality":
        add_personality = not add_personality
        response = await message.channel.send("Personality prompt is now: " + str(add_personality))
        time.sleep(5)
        await response.delete()
        return        
    
    # define a help command, this will give the user a list of commands
    if message.content.lower() == "?help":
        help_msg = "Commands:\n?startChat - starts a chat thread with GPT\n?GenerateImage <Prompt> - generates an image based on the prompt\n?deleteThread - deletes the current thread\n?MainPrompt - gets the current main prompt\n?clearAll - clears all messages in the channel\n?help - displays this message\n?developerLog - displays the developer log\n"
        await message.channel.send(help_msg)
        return
    
    # define a command to get the current personality prompt
    if message.content.lower()  == "?personality":
        if personality_prompt == "":
            await message.channel.send("No personality prompt set")
            return
        await message.channel.send("Personality prompt is currently: " + personality_prompt)
        return
    
    # define a command to get the current main prompt
    if message.content.lower()  == "?mainprompt":
        await message.channel.send("Main prompt is currently: " + main_prompt)
        return

    # define command to start a thread
    if message.content.lower()  == "?startchat":

        thread_start = await output.send('Starting a thread for %s ' % message.author.mention)
        thread = await thread_start.create_thread(name = message.author.name)
        await thread.send("Type ?help to get started\n\nHello " + message.author.name + ", what would you like to talk about?")
        # delete the message that started the thread
        await message.delete()
        return
    
    # define a command to generate an image
    if message.content.lower().startswith("?generateimage"):
        thread = message.channel
        thinking_msg = await thread.send(getImageGenMsg())
        prompt = message.content.lower().replace("?GenerateImage".lower() , "")
        imageURL = imageGen(prompt)
        res = requests.get(imageURL, stream=True)
        image = ""
        with open('image.png', 'wb') as out_file:
            shutil.copyfileobj(res.raw, out_file)
        await thinking_msg.delete()
        await thread.send("Prompt: " + prompt + "\n")
        await message.delete()
        await thread.send(file = discord.File('image.png'))
        return         
    
    # define a command to delete a thread
    if message.content.lower() == "?deletethread":
        if message.channel.type == discord.ChannelType.public_thread or message.channel.type == discord.ChannelType.private_thread:
            await message.channel.delete()

        return

    # if the message was sent in a thread, get the history of the thread
    if message.channel.type == discord.ChannelType.public_thread or message.channel.type == discord.ChannelType.private_thread:
        thread = message.channel
        messages = [message async for message in message.channel.history(limit=None)]
        typing_msg = await thread.send(getThinkingMsg())
        messages.reverse()
        contentBlob = ""
        for message in messages:
            contentBlob += message.content + "\n"
        # conversation blob will be sent to gpt here
        if tokenCount(contentBlob) > CALL_RESPONSE_LIMIT:
            contentBlob = cutText(contentBlob)
        response = callGPT(contentBlob)
        #await to_gpt.purge(limit=None)
        #await to_gpt.send(contentBlob)

        # represents the response from gpt
        await typing_msg.delete()
        await thread.send(response)
        return
    
    if message.content.lower()  == "?clearall":
        def not_pinned(m):
            return not m.pinned
        await message.channel.purge(limit=None, check=not_pinned)
        return

# this function generates the response from gpt
def callGPT(input):
    tempPersonality = ""
    if add_personality:
        tempPersonality = personality_prompt

    messages = [
        {"role": "system", "content" : main_prompt + " " + tempPersonality}
    ]
    savedConversation = []
    userInput = input
    content = userInput
    messages.append({"role": "user", "content": content})

    completion = gpt_conversation(messages)
    chat_response = completion.choices[0].message.content

    if add_personality:
        chat_response = personalityGen(chat_response)
    
    messages.append({"role": "user", "content": chat_response})
    return chat_response
    

def gpt_conversation(conversation_log):
    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=conversation_log
    )
    return response

def tokenCount(text):
    encoding = tiktoken.encoding_for_model(MODEL)
    num_tokens = len(encoding.encode(text))
    return num_tokens

def cutText(text):
    encoding = tiktoken.encoding_for_model(MODEL)
    tokens = encoding.encode(text)
    tokens = tokens[:CALL_RESPONSE_LIMIT]
    text = encoding.decode(tokens)
    return text

def imageGen(input):
    response = openai.Image.create(
        prompt = input,
        n=1,
        size="1024x1024"
    )
    image_url = response['data'][0]['url']
    return image_url

def personalityGen(input):
    messages = [
        {"role": "system", "content" : personality_prompt}
    ]
    userInput = input
    content = userInput
    messages.append({"role": "user", "content": content})

    completion = gpt_conversation(messages)
    chat_response = completion.choices[0].message.content
    messages.append({"role": "user", "content": chat_response})
    return chat_response

def ImageRelationCheck(input):
    messages = [
        {"role": "system", "content" : "Only answer yes or no. Don't think just answer. Does the prompt relate to image generation?"}
    ]
    completion = gpt_conversation(messages)
    chat_response = completion.choices[0].message.content
    return boolChecker(chat_response)

def boolChecker(input):
    return input.contains("yes")

# these functions just add some variety to the bot's responses
def getThinkingMsg():
    thinking_msgs = [
        "Thinking...",
        "Generating a response...",
        "Processing your request...",
        "Let me check...",
        "Let me think for a moment...",
        "Searching for the answer..."
        "Just a moment...",
        "I'm working on it...",
        "I'm on it...",
    ]
    return random.choice(thinking_msgs)

def getImageGenMsg():
    thinking_msg = [
        "Generating Image...",
        "Generating a picture...",
        "Processing your request...",
        "Creating a masterpiece...",
        "Using wizardry to create a picture...",
        "Just a moment...",
        "Magic is happening...",
        "I'm working on it...",
        "I'm on it...",
        "I'm creating a masterpiece...",
        "Beep boop, creating a picture...",
        "Beep boop, processing your request...",
        "Beep boop, generating image...",
    ]
    return random.choice(thinking_msg)

        
    
client.run(TOKEN)