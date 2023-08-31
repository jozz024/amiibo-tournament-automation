from tournament import Tournament
from joycontrol.protocol import controller_protocol_factory
from joycontrol.server import create_hid_server
from joycontrol.controller import Controller
import logging
from joycontrol.controller_state import ControllerState
from joycontrol.controller_state import button_push
from joycontrol.ScriptRunner import ScriptRunner
from joycontrol import logging_default as log, utils
import os
import webhook
import io
import json
import ftplib
import asyncio
from joycontrol.nfc_tag import NFCTag
import socket
import csv
import re
import unicodedata

if not os.path.exists("config.json"):
    config = {}
    config["ip"] = input("Input your switch's IP address.\n")
    config["webhook_url"] = input("Input the url of your webhook.\n")
    config["webhook_name"] = input("Input the preferred name of your webhook.\n")
    config["webhook_avatar_url"] = input("Input the link to the profile picture you would like the bot to use:\n")
    config["challonge_username"] = input("Please input your challonge username.\n")
    config["challonge_api_key"] = input("Please input your challonge api key.\n")
    config["save_after_match"] = False
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

async def restart_match(controller_state, fp1_tag, fp2_tag):
    global s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    await load_match(controller_state, True, fp1_tag, fp2_tag)

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

def get_player_info(player_str):
    player_info = player_str.split("-")
    return player_info[0].strip(), player_info[1].strip()

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


async def load_match(controller_state, game_start, fp1_tag, fp2_tag):
    if game_start == True:
        await execute(controller_state, "tournament-scripts/start_game")
        s.connect((ip, int(port)))
        await asyncio.sleep(18)
        await execute(controller_state, "tournament-scripts/smash_menu")
    else:
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


async def main(tour: Tournament, whole_thing: bool):
    global bindict
    webhook_list = []
    for urls in config["webhook_url"]:
        webhook_list.append(webhook.MatchResultWebhoook(urls, config["webhook_name"], config["webhook_avatar_url"]))

    # the type of controller to create
    controller = Controller.PRO_CONTROLLER # or JOYCON_L or JOYCON_R
    # a callback to create the corresponding protocol once a connection is established
    factory = controller_protocol_factory(controller)
    # start the emulated controller
    transport, protocol = await create_hid_server(factory, reconnect_bt_addr="auto")
    # get a reference to the state beeing emulated.
    controller_state: ControllerState = protocol.get_controller_state()
    # wait for input to be accepted
    await controller_state.connect()
    entries = []
    with open("entries.tsv") as fp:
        # open the entry tsv submissionapp provides
        entry_tsv = csv.reader(fp, delimiter = "\t")
        next(entry_tsv)
        for entry in entry_tsv:
            amiibo_name = entry[0]
            character_name = entry[1]
            trainer_name = entry[2]

            starting_num = 1

            name_for_bracket = f"{trainer_name} - {character_name}"
            while name_for_bracket in entries:
                starting_num += 1
                if str(starting_num - 1) == name_for_bracket[-1]:
                    name_for_bracket = name_for_bracket.replace(starting_num - 1, starting_num)
                else:
                    name_for_bracket = f"{name_for_bracket} - {starting_num}"

            entries.append(name_for_bracket)
            print(name_for_bracket)
            bindict[name_for_bracket] = validate_filename(f"{trainer_name.rstrip()}-{character_name}-{amiibo_name}")

    print("Finished parsing Submissionapp TSV")
    for entry in entries:
        try:
            tour.add_participant(name_for_bracket)
        except:
            break
    try:
        tour.shuffle_participants()
        tour.start()
    except:
        pass
    new_match = True
    game_start = True
    matches_to_do = []
    if whole_thing == False:
        while True:
            match_num = input("Please input a match number for the match you want to be done, and x to exit.\n")
            if match_num != "x":
                matches_to_do += [int(match_num)]
            else:
                break
    match_num = 0
    while new_match == True:
        tour.refresh_matches()
        try:
            if tour.matches[match_num]["state"] == "complete":
                match_num += 1
            elif tour.matches[match_num]["scores_csv"] != "":
                match_num += 1
            elif whole_thing == False and match_num not in matches_to_do:
                match_num += 1
            else:
                p1 = tour.get_user_from_id(tour.matches[match_num]["player1_id"])
                p2 = tour.get_user_from_id(tour.matches[match_num]["player2_id"])
                name_to_id = {
                    p1: tour.matches[match_num]["player1_id"],
                    p2: tour.matches[match_num]["player2_id"]
                }
                p1_filepath = bindict[p1]
                p2_filepath = bindict[p2]
                tour.mark_in_progress(tour.matches[match_num]["id"])
                with open(os.path.join("tourbins", p1_filepath + ".bin"), "rb") as fp1_file:
                    fp1_hex = fp1_file.read()

                with open(os.path.join("tourbins", p2_filepath + ".bin"), "rb") as fp2_file:
                    fp2_hex = fp2_file.read()
                fp1_tag = NFCTag(data=fp1_hex, source=p1_filepath, mutable=True)
                fp2_tag = NFCTag(data=fp2_hex, source=p2_filepath, mutable=True)
                await load_match(controller_state, game_start, fp1_tag, fp2_tag)
                game_start = False
                while True:
                    data = s.recv(1024)
                    # try:
                    print(data.decode())
                    if data.decode().startswith("[match_end] match_data_json: "):
                        print(data.decode().strip("[match_end] match_data_json: ").lstrip().strip('"'))
                        data_json = json.loads(data.decode().strip("[match_end] match_data_json: ").lstrip().strip('"').replace("\\", ""))
                        print(data_json)
                        break
                    if data.decode().startswith("[match_end] One of the fighters is not an amiibo, exiting."):
                        await restart_match(controller_state, fp1_tag, fp2_tag)
                        continue
                    # except:
                    #     await restart_match(controller_state, fp1_tag, fp2_tag)
                    #     continue

                score = data_json["fp1_info"]["score"] + "-" + data_json["fp2_info"]["score"]
                print(score)
                p1_score = int(data_json["fp1_info"]["score"])
                p2_score = int(data_json["fp2_info"]["score"])

                if p1_score > p2_score:
                    winner_str, loser_str = p1, p2
                    winner_score, loser_score = p1_score, p2_score
                else:
                    winner_str, loser_str = p2, p1
                    winner_score, loser_score = p2_score, p1_score
                winner_name, winner_character = get_player_info(winner_str)
                loser_name, loser_character = get_player_info(loser_str)

                tour.set_score(tour.matches[match_num]["id"], name_to_id[winner_str], score)
                await asyncio.sleep(5)
                await button_push(controller_state, "capture", sec=0.15)
                await execute(controller_state, "tournament-scripts/on_match_end")
                if config["save_after_match"] == True:
                    await execute(controller_state, "tournament-scripts/after_match_save")
                    controller_state.set_nfc(fp1_tag)
                    await asyncio.sleep(5)
                    fp1_tag.save()
                    controller_state.set_nfc(None)
                    await asyncio.sleep(2)
                    controller_state.set_nfc(fp2_tag)
                    await asyncio.sleep(5)
                    fp2_tag.save()
                    controller_state.set_nfc(None)
                else:
                    await execute(controller_state, "tournament-scripts/after_match")
                for webhooks in webhook_list:
                    try:
                        await webhooks.send_result(f"{winner_name}'s {winner_character} {winner_score}-{loser_score} {loser_name}'s {loser_character}", get_latest_image())
                    except ConnectionResetError:
                        await webhooks.send_result(f"{winner_name}'s {winner_character} {winner_score}-{loser_score} {loser_name}'s {loser_character}", get_latest_image())
                await asyncio.sleep(12)
                new_match = True
        except IndexError:
            tour.refresh_matches()
            tour.end()
            await execute(controller_state, "tournament-scripts/exit_to_home_and_close_game")
            new_match = False
    # wait for it to be sent at least once
    await controller_state.send()

if __name__ == "__main__":
    toururl = input("please input the url of the tournament:\n")
    tour = Tournament(toururl, config["challonge_username"], config["challonge_api_key"])
    run_or_matches = input("Run the entire tournament, or do specific matches?")
    if run_or_matches == "run":
        log.configure(console_level=logging.ERROR)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main(tour, True))
    else:
        log.configure(console_level=logging.ERROR)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main(tour, False))

