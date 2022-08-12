import asyncio
import csv
import ftplib
import io
import json
import logging
import os
import socket
import threading
from queue import Queue

from flask import Flask, request

import webhook
from joycontrol import logging_default as log
from joycontrol import utils
from joycontrol.controller import Controller
from joycontrol.controller_state import ControllerState, button_push
from joycontrol.memory import FlashMemory
from joycontrol.nfc_tag import NFCTag
from joycontrol.protocol import controller_protocol_factory
from joycontrol.ScriptRunner import ScriptRunner
from joycontrol.server import create_hid_server
from tournament import Tournament

app = Flask(__name__)

mailbox = Queue()

if not os.path.exists("config.json"):
    config = {}
    config["ip"] = input("Input your switch's IP address.\n")
    config["webhook_url"] = input("Input the url of your webhook.\n")
    config["webhook_name"] = input("Input the preferred name of your webhook.\n")
    config["challonge_username"] = input("Please input your challonge username.\n")
    config["challonge_api_key"] = input("Please input your challonge api key.\n")
    with open("config.json", "w+") as cfg:
        json.dump(config, cfg, indent=4)

with open("config.json") as cfg:
    config: dict = json.load(cfg)
    if type(config["webhook_url"]) != list:
        config["webhook_url"] = [config["webhook_url"], ]
    with open("config.json", "w+") as cfg:
        json.dump(config, cfg, indent=4)

ip = config["ip"]
port = "6969"
bindict = {}
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socket_connected = False
webhook_list = []
match_num = 0
proceed = False

def joycontrol_main(mailbox, controller_state, loop: asyncio.AbstractEventLoop):
    loop.create_task(
        joycontrol(mailbox, controller_state)
    )
    loop.run_forever()

def real_main():
    global tour
    toururl = input("please input the url of the tournament:\n")
    tour = Tournament(toururl, config["challonge_username"], config["challonge_api_key"])

    log.configure(console_level=logging.ERROR)
    loop = asyncio.new_event_loop()
    loop.create_task(main(tour, loop))

    loop.run_forever()

async def joycontrol(mailbox, controller_state):
    script_runner = ScriptRunner(controller_state)

    # Waits for instructions from the Flask thread and executes them.
    while True:
        cmd, data = mailbox.get(block = True)

        if cmd == "nfc":
            controller_state.set_nfc(data)
        elif cmd == "script":
            await script_runner.execute_script_string(data)

def setup_thread(tour: Tournament):
    global webhook_list
    webhook_list = []
    for urls in config["webhook_url"]:
        webhook_list.append(webhook.MatchResultWebhoook(urls, config["webhook_name"]))

    try:
        with open("entries.tsv") as fp:
            # open the entry tsv submissionapp provides
            entry_tsv = csv.reader(fp, delimiter = "\t")
            next(entry_tsv)
            for entry in entry_tsv:
                amiibo_name = entry[0]
                character_name = entry[1]
                trainer_name = entry[2]

                name_for_bracket = f"{trainer_name} - {character_name}"
                print(name_for_bracket)
                full_name = f"{name_for_bracket} - {amiibo_name}"
                while name_for_bracket in bindict:
                    old_amiibo = bindict[name_for_bracket]["full_name"]
                    old_amiibo_file = bindict[name_for_bracket]["file_name"]

                    bindict.pop(name_for_bracket)
                    bindict[old_amiibo] = {"full_name": old_amiibo, "file_name": old_amiibo_file}

                bindict[name_for_bracket] = {"full_name": full_name, "file_name": validate_filename(f"{trainer_name.rstrip()}-{character_name}-{amiibo_name}")}

                try:
                    tour.add_participant(name_for_bracket)
                except:
                    pass
        try:
            tour.shuffle_participants()
            tour.start()
        except:
            return
    except:
        return


async def restart_match(controller_state, fp1_tag, fp2_tag):
    global s
    start_game(controller_state)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    await load_match(controller_state, fp1_tag, fp2_tag)

def replace_bad_character(letter):
    if letter in "%:/'\"\\[]<>*?":
        return "+"
    else:
        return letter

def validate_filename(value: str):
    real_value = ""
    for letter in value:
        real_value += (replace_bad_character(letter))
    return real_value

def get_latest_image():
    ftp = ftplib.FTP()
    ftp.connect(config["ip"], 5000)
    ftp.login()
    directory_to_grab = "/Nintendo/Album/"
    dirs = ftp.nlst(directory_to_grab)
    years = []
    for dir in dirs:
        number = dir.split("/")
        years.append(number[-1])
    years.sort()
    years.reverse()
    directory_to_grab += years[0] + "/"
    dirs = ftp.nlst(directory_to_grab)
    months = []
    for dir in dirs:
        number = dir.split("/")
        months.append(number[-1])
    months.sort()
    months.reverse()
    directory_to_grab += months[0] + "/"
    dirs = ftp.nlst(directory_to_grab)
    days = []
    for dir in dirs:
        number = dir.split("/")
        days.append(number[-1])
    days.sort()
    days.reverse()
    directory_to_grab += days[0] + "/"
    entries = list(ftp.mlsd(directory_to_grab))
    entries.sort(key = lambda entry: entry[1]['modify'], reverse = True)
    latest_name = entries[0][0]
    filename = directory_to_grab + latest_name
    image = io.BytesIO(b"")
    ftp.retrbinary("RETR " + filename, image.write)
    image.seek(0)
    return image

async def execute(controller_state, script_path):
    script_runner = ScriptRunner(controller_state)
    script_runner.is_looping = False
    script_file_name = os.path.expanduser(script_path)
    if os.path.exists(script_file_name):
        await script_runner.execute_script_file(script_file_name)
    else:
        print("not found")

async def start_game(controller_state):
    await controller_state.connect()
    await execute(controller_state, "tournament-scripts/start_game")
    s.connect((ip, int(port)))
    await asyncio.sleep(18)
    await execute(controller_state, "tournament-scripts/smash_menu")

async def load_match(controller_state, fp1_tag, fp2_tag):
    await execute(controller_state, "tournament-scripts/smash_menu_after_match")
    await execute(controller_state, "tournament-scripts/load_fp1")
    controller_state.set_nfc(fp1_tag)
    await asyncio.sleep(5)
    controller_state.set_nfc(None)
    await execute(controller_state, "tournament-scripts/load_fp2")
    controller_state.set_nfc(fp2_tag)
    await asyncio.sleep(5)
    controller_state.set_nfc(None)
    await execute(controller_state, "tournament-scripts/start_match")


async def main(tour: Tournament, loop):
    global bindict
    global match_num

    # the type of controller to create
    controller = Controller.PRO_CONTROLLER # or JOYCON_L or JOYCON_R
    # a callback to create the corresponding protocol once a connection is established
    factory = controller_protocol_factory(controller)
    # start the emulated controller
    transport, protocol = await create_hid_server(factory, reconnect_bt_addr="auto")
    # get a reference to the state beeing emulated.
    controller_state: ControllerState = protocol.get_controller_state()
    # wait for input to be accepted
    entry_thread = threading.Thread(target=setup_thread, daemon=True, args = [tour])
    entry_thread.start()

    t1 = threading.Thread(target = joycontrol_main, daemon=True, args = (mailbox, controller_state, loop))
    t1.start()

    await start_game(controller_state)
    new_match = True
    match_num = 0
    entry_thread.join()
    while new_match == True:
        tour.refresh_matches()
        try:
            if tour.matches[match_num]["state"] == "complete":
                match_num += 1
            elif tour.matches[match_num]["scores_csv"] != "":
                match_num += 1
            else:
                p1 = tour.get_user_from_id(tour.matches[match_num]["player1_id"])
                p2 = tour.get_user_from_id(tour.matches[match_num]["player2_id"])
                p1_filepath = bindict[p1]["file_name"]
                p2_filepath = bindict[p2]["file_name"]
                tour.mark_in_progress(tour.matches[match_num]["id"])
                with open(os.path.join("tourbins", p1_filepath + ".bin"), "rb") as fp1_file:
                    fp1_hex = fp1_file.read()

                with open(os.path.join("tourbins", p2_filepath + ".bin"), "rb") as fp2_file:
                    fp2_hex = fp2_file.read()
                fp1_tag = NFCTag(data=fp1_hex, source=p1_filepath, mutable=True)
                fp2_tag = NFCTag(data=fp2_hex, source=p2_filepath, mutable=True)
                await load_match(controller_state, fp1_tag, fp2_tag)
                proceed = False
                while proceed != True:
                    pass
                new_match = True
        except IndexError:
            tour.refresh_matches()
            tour.end()
            await execute(controller_state, "tournament-scripts/exit_to_home_and_close_game")
            new_match = False
    # wait for it to be sent at least once
    await controller_state.send()

@app.route("/match_end", methods=["POST"])
def match_end():
    global proceed
    data = request.json
    score = f"{data['fp1_info']['score']}-{data['fp1_info']['score']}"
    print(score)
    p1_score, p2_score = score.replace("\n", "").split("-")
    p1 = tour.get_user_from_id(tour.matches[match_num]["player1_id"])
    p2 = tour.get_user_from_id(tour.matches[match_num]["player2_id"])
    name_to_id = {
        p1: tour.matches[match_num]["player1_id"],
        p2: tour.matches[match_num]["player2_id"]
    }

    if int(p1_score) > int(p2_score):
        tour.set_score(tour.matches[match_num]["id"], name_to_id[p1], score)
        winner = p1.split("-")
        winner_name = winner[0].strip(" ")
        winner_character = winner[1].strip(" ")
        winner_score = p1_score.strip(" ")
        loser_score = p2_score.strip(" ")
        loser = p2.split("-")
        loser_name = loser[0].strip(" ")
        loser_character = loser[1].strip(" ")
    else:
        tour.set_score(tour.matches[match_num]["id"], name_to_id[p2], score)
        winner = p2.split("-")
        winner_name = winner[0].strip(" ")
        winner_character = winner[1].strip(" ")
        winner_score = p2_score.strip(" ")
        loser_score = p1_score.strip(" ")
        loser = p1.split("-")
        loser_name = loser[0].strip(" ")
        loser_character = loser[1].strip(" ")
    mailbox.put(("script", ": 5000\nCapture: 150"))
    with open("tournament-scripts/on_match_end") as script:
        mailbox.put(("script", script.read()))

    with open("tournament-scripts/after_match") as script:
        mailbox.put(("script", script.read()))
    mailbox.put(("script", ": 15000"))
    for webhooks in webhook_list:
        try:
            webhooks.send_result(f"{winner_name}'s {winner_character} {winner_score}-{loser_score} {loser_name}'s {loser_character}", get_latest_image())
        except ConnectionResetError:
            webhooks.send_result(f"{winner_name}'s {winner_character} {winner_score}-{loser_score} {loser_name}'s {loser_character}", get_latest_image())
    proceed = False


if __name__ == "__main__":
    main_thread = threading.Thread(target = real_main, daemon=True)

    main_thread.start()

    app.run("0.0.0.0")